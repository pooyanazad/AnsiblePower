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
    marker = tmp_path / "survived"
    child = ("import signal,time,pathlib; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
             f"print('child ready', flush=True); time.sleep(1.5); pathlib.Path({str(marker)!r}).touch()")
    script = (f"import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', {child!r}]); "
              + ("time.sleep(0.3)" if parent_exits else "time.sleep(20)"))
    started = time.monotonic()
    state, output, code = worker.run_command([sys.executable, "-c", script], (), 0.4, grace=0.2)
    assert time.monotonic() - started < 3
    assert state == ("succeeded" if parent_exits else "timed_out")
    assert "child ready" in output
    time.sleep(1.6)
    assert not marker.exists()


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
