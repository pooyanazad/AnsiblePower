"""Harmless local children exercise real signals and restart reconciliation."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

import jobs
import process_control
import utils
import worker


def eventually(check, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.05)
    pytest.fail("Child process did not reach the expected state")


@pytest.mark.parametrize("parent_exits", [False, True])
def test_escalates_for_stubborn_descendant(tmp_path, parent_exits):
    # The parent waits for the child to install its TERM handler before exiting.
    # A generous command deadline separates normal parent exit from timeout;
    # CPU scheduling and coverage instrumentation must not decide the outcome.
    child = ("import os,signal,sys,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
             "print('child ready', flush=True); os.write(int(sys.argv[1]), b'1'); "
             "os.close(int(sys.argv[1])); time.sleep(60)")
    script = ("import os,subprocess,sys,time; read_fd,write_fd=os.pipe(); "
              f"subprocess.Popen([sys.executable, '-c', {child!r}, str(write_fd)], pass_fds=(write_fd,)); "
              "os.close(write_fd); assert os.read(read_fd, 1) == b'1'; os.close(read_fd); "
              + ("sys.exit(0)" if parent_exits else "time.sleep(60)"))
    owners = []
    state, output, code = worker.run_command([sys.executable, "-c", script], (),
                                           10 if parent_exits else 5, grace=0.2, on_start=owners.append)
    assert state == ("succeeded" if parent_exits else "timed_out")
    assert code == (0 if parent_exits else -signal.SIGTERM)
    assert "child ready" in output
    assert not process_control.group_alive(owners[0])


def test_restart_keeps_partial_logs_and_stops_orphan_group(patched_paths):
    spec = {"playbook": "sample.yml", "playbook_path": "unused", "execution_mode": "local"}
    job, _ = jobs.enqueue(spec, "orphan")
    database = utils.get_history_db_file()
    jobs.claim(database)
    logfile = jobs.log_path(database, job["id"])
    with open(logfile, "wb") as output:
        process = subprocess.Popen([sys.executable, "-c", "import time; print('partial log', flush=True); time.sleep(30)"],
                                   stdout=output, start_new_session=True)
    try:
        owner = process_control.identity(process.pid)
        jobs.register_process(database, job["id"], owner)
        eventually(lambda: "partial log" in jobs.get(job["id"])["output"])
        jobs.recover(database)
        result = jobs.get(job["id"])
        assert result["state"] == "interrupted" and result["needs_review"]
        assert "partial log" in result["output"]
        assert not process_control.group_alive(owner)
        assert utils.load_history()[0]["state"] == "interrupted"
        jobs.recover(database)
        assert len(utils.load_history()) == 1
    finally:
        process_control.terminate(owner, grace=0.1)
        process.wait(timeout=3)


def test_stale_identity_never_signals_an_unrelated_process():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    try:
        owner = process_control.identity(process.pid)
        process_control.terminate(dict(owner, start=owner["start"] - 1), grace=0.01)
        process_control.terminate(dict(owner, boot="previous boot"), grace=0.01)
        assert process.poll() is None
    finally:
        process.terminate()
        process.wait(timeout=3)


def test_worker_crash_before_registration_never_releases_command(tmp_path):
    marker = tmp_path / "started"
    command = [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"]
    script = ("import os,signal,worker; "
              f"worker.run_command({command!r}, (), 5, on_start=lambda owner: os.kill(os.getpid(), signal.SIGKILL))")
    process = subprocess.Popen([sys.executable, "-c", script])
    assert process.wait(timeout=5) == -signal.SIGKILL
    time.sleep(0.3)
    assert not marker.exists()


@pytest.mark.parametrize("reason", ["canceled", "interrupted"])
def test_live_run_stops_children_and_records_distinct_outcome(patched_paths, reason):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    directory = Path(patched_paths["base"])
    marker = directory / "child-survived"
    child = f"import time,pathlib; print('child ready', flush=True); time.sleep(1.5); pathlib.Path({str(marker)!r}).touch()"
    fake = directory / "fake-ansible"
    fake.write_text(f"#!{sys.executable}\nimport subprocess,sys,time\nsubprocess.Popen([sys.executable, '-c', {child!r}])\ntime.sleep(30)\n")
    fake.chmod(0o700)
    path = Path(patched_paths["playbooks_dir"]) / "sample.yml"
    spec = {"playbook": path.name, "playbook_path": str(path), "playbook_digest": jobs.digest(path.read_bytes()),
            "execution_mode": "local"}
    job, _ = jobs.enqueue(spec, reason)
    stopping = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker.run_one, utils.get_history_db_file(), str(fake), 20, stopping)
        eventually(lambda: "child ready" in jobs.get(job["id"])["output"])
        if reason == "canceled":
            jobs.cancel(job["id"])
        else:
            stopping.set()
        assert future.result(timeout=5)
    result = jobs.get(job["id"])
    assert result["state"] == reason
    assert "child ready" in result["output"]
    assert result["exit_code"] < 0 and result["duration"] >= 0
    assert utils.load_history()[0]["state"] == reason
    time.sleep(1.6)
    assert not marker.exists()


def test_real_worker_signal_interrupts_live_group(tmp_path):
    """The service's actual signal handler drives cleanup, without a queue retry."""
    import json
    import sqlite3

    database = str(tmp_path / "worker.db")
    playbook = tmp_path / "playbook.yml"
    playbook.write_text("- hosts: all\n  tasks: []\n")
    # Enqueue into this test database without changing the service's CLI config.
    from unittest.mock import patch
    with patch("utils.get_history_db_file", return_value=database):
        job, _ = jobs.enqueue({"playbook": playbook.name, "playbook_path": str(playbook),
                               "playbook_digest": jobs.digest(playbook.read_bytes()), "execution_mode": "local"}, "signal")
    binary = tmp_path / "fake-ansible"
    binary.write_text(f"#!{sys.executable}\nimport time\nprint('running before signal', flush=True)\ntime.sleep(30)\n")
    binary.chmod(0o700)
    process = subprocess.Popen([sys.executable, "worker.py", "--database", database],
                               env=dict(os.environ, ANSIBLE_PLAYBOOK_BIN=str(binary)))
    try:
        eventually(lambda: "running before signal" in jobs.read_log(database, job["id"]))
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=8) == 0
        with sqlite3.connect(database) as conn:
            state, output, identity = conn.execute("SELECT state, output, process_identity FROM jobs").fetchone()
            assert state == "interrupted" and "running before signal" in output
            assert not process_control.group_alive(json.loads(identity))
            assert conn.execute("SELECT state FROM playbook_runs").fetchone()[0] == "interrupted"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        jobs.recover(database)


def test_cleanup_failure_cannot_be_reported_as_success(patched_paths, monkeypatch):
    """If the kernel never confirms group exit, hold the result for review."""
    path = Path(patched_paths["playbooks_dir"]) / "sample.yml"
    job, _ = jobs.enqueue({"playbook": path.name, "playbook_path": str(path),
                           "playbook_digest": jobs.digest(path.read_bytes()), "execution_mode": "local"}, "cleanup-failure")
    binary = Path(patched_paths["base"]) / "fake-ansible"
    binary.write_text(f"#!{sys.executable}\nprint('ok=1 failed=0', flush=True)\n")
    binary.chmod(0o700)
    def failed_cleanup(owner, grace):
        raise RuntimeError("Could not confirm group exit")
    monkeypatch.setattr(process_control, "terminate", failed_cleanup)
    worker.run_one(utils.get_history_db_file(), str(binary))
    result = jobs.get(job["id"])
    assert result["state"] == "uncertain" and result["needs_review"]
    assert "ok=1 failed=0" in result["output"]
    assert utils.load_history()[0]["state"] == "uncertain"


@pytest.mark.parametrize("timeout", ["nan", "inf", "0", "-1"])
def test_worker_rejects_invalid_timeout(timeout):
    result = subprocess.run([sys.executable, "worker.py", "--timeout", timeout],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 2
    assert "positive and finite" in result.stderr
