"""Queue races, durable results, input repair, and runner failure behavior."""
import sys
import time
import fcntl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

import jobs
import utils
import worker


@pytest.fixture()
def spec(patched_paths):
    return {"playbook": "sample.yml", "playbook_path": str(Path(patched_paths["playbooks_dir"]) / "sample.yml"),
            "playbook_digest": jobs.digest((Path(patched_paths["playbooks_dir"]) / "sample.yml").read_bytes()),
            "execution_mode": "local"}


def test_launch_is_persisted_and_does_not_execute_in_http(flask_client):
    with patch("worker.run_command") as execute:
        response = flask_client.post("/run_playbook", data={"playbook": "sample.yml"})
    assert response.status_code == 202
    execute.assert_not_called()
    assert response.headers["Location"] == response.json["url"]
    assert jobs.get(response.json["job_id"])["state"] == "queued"
    assert flask_client.get(response.json["url"]).status_code == 200
    assert flask_client.get(response.json["status_url"]).json["state"] == "queued"
    assert response.json["url"].encode() in flask_client.get("/").data


def test_same_key_returns_completed_job_and_rejects_different_inputs(flask_client):
    headers = {"Idempotency-Key": "retry-this-request"}
    first = flask_client.post("/run_playbook", data={"playbook": "sample.yml"}, headers=headers)
    with patch("worker.run_command", return_value=("succeeded", "PLAY RECAP", 0)):
        assert worker.run_one(utils.get_history_db_file(), "ansible-playbook")
    again = flask_client.post("/run_playbook", data={"playbook": "sample.yml"}, headers=headers)
    assert again.json["job_id"] == first.json["job_id"]
    assert again.json["duplicate"] and again.json["state"] == "succeeded"
    conflict = flask_client.post("/run_playbook", data={"playbook": "sample.yml", "execution_mode": "local"}, headers=headers)
    assert conflict.status_code == 409
    assert len(utils.load_history()) == 1


def test_simultaneous_submissions_create_one_job(spec):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: jobs.enqueue(spec, f"submission-{i}"), range(16)))
    assert len({job["id"] for job, _ in results}) == 1
    assert sum(created for _, created in results) == 1
    job_id = results[0][0]["id"]
    with patch("worker.run_command", return_value=("succeeded", "done", 0)):
        worker.run_one(utils.get_history_db_file(), "ansible-playbook")
    # Every duplicate key remains attached to the same run after completion.
    for i in range(16):
        assert jobs.enqueue(spec, f"submission-{i}")[0]["id"] == job_id


def test_queue_capacity_and_atomic_claims(spec):
    jobs.enqueue(spec, "one", capacity=1)
    other = dict(spec, playbook_path=spec["playbook_path"] + ".other")
    with pytest.raises(jobs.QueueFull):
        jobs.enqueue(other, "two", capacity=1)
    assert not jobs.enqueue(spec, "duplicate", capacity=1)[1]
    database = utils.get_history_db_file()
    with ThreadPoolExecutor(max_workers=8) as pool:
        claimed = list(pool.map(lambda _: jobs.claim(database), range(8)))
    assert sum(job is not None for job in claimed) == 1


@pytest.mark.parametrize("change", ["missing", "empty", "invalid", "unreadable", "changed"])
def test_inventory_is_checked_again_before_starting(flask_client, change):
    response = flask_client.post("/run_playbook", data={"playbook": "sample.yml"})
    hosts = Path(utils.get_hosts_file())
    if change == "missing":
        hosts.unlink()
    elif change == "unreadable":
        hosts.chmod(0)
    else:
        hosts.write_text({"empty": "", "invalid": "[broken", "changed": "[prod]\nnew.example.test\n"}[change])
    try:
        with patch("worker.run_command") as execute:
            worker.run_one(utils.get_history_db_file(), "ansible-playbook")
        execute.assert_not_called()
        result = flask_client.get(response.json["status_url"]).json
        assert result["state"] == "blocked"
        assert result["repair"]["url"] == "/settings/"
    finally:
        if hosts.exists():
            hosts.chmod(0o600)


def test_changed_playbook_is_blocked(spec):
    job, _ = jobs.enqueue(spec, "one")
    Path(spec["playbook_path"]).write_text("- hosts: different\n")
    with patch("worker.run_command") as execute:
        worker.run_one(utils.get_history_db_file(), "ansible-playbook")
    execute.assert_not_called()
    assert jobs.get(job["id"])["state"] == "blocked"


def test_crash_recovery_never_replays_and_requires_review(flask_client, spec):
    job, _ = jobs.enqueue(spec, "one")
    database = utils.get_history_db_file()
    assert jobs.claim(database)["id"] == job["id"]
    jobs.recover(database)
    assert jobs.get(job["id"])["state"] == "interrupted"
    with patch("worker.run_command") as execute:
        assert not worker.run_one(database, "ansible-playbook")
    execute.assert_not_called()
    assert jobs.enqueue(spec, "retry")[0]["id"] == job["id"]
    url = f"/jobs/{job['id']}/acknowledge"
    assert flask_client.post(url).status_code == 400
    assert flask_client.post(url, data={"hosts_checked": "yes"}).status_code == 302
    assert jobs.get(job["id"])["state"] == "interrupted"
    assert jobs.enqueue(spec, "new-run")[0]["id"] != job["id"]


def test_unexpected_failure_is_uncertain(spec):
    job, _ = jobs.enqueue(spec, "one")
    with patch("worker.run_command", side_effect=RuntimeError("lost result")):
        worker.run_one(utils.get_history_db_file(), "ansible-playbook")
    assert jobs.get(job["id"])["state"] == "uncertain"


@pytest.mark.parametrize("exit_code,expected", [(0, "succeeded"), (2, "failed")])
def test_real_process_result_and_history(spec, exit_code, expected):
    job, _ = jobs.enqueue(spec, "one")
    with patch("worker.execute", side_effect=lambda *_: worker.run_command(
            [sys.executable, "-c", f"print('PLAY RECAP'); raise SystemExit({exit_code})"], (), 5)):
        worker.run_one(utils.get_history_db_file(), "unused")
    result = jobs.get(job["id"])
    assert result["state"] == expected
    assert result["exit_code"] == exit_code
    assert result["started_at"] and result["finished_at"]
    assert result["duration"] >= 0
    history = utils.load_history()[0]
    for field in ("state", "exit_code", "started_at", "finished_at", "duration"):
        assert history[field] == result[field]
    assert "PLAY RECAP" in result["output"]
    assert utils.load_history()[0]["output"] == result["output"]
    jobs.finish(utils.get_history_db_file(), job["id"], expected, "duplicate callback")
    assert len(utils.load_history()) == 1


def test_timeout_kills_descendants(tmp_path):
    marker = tmp_path / "child-survived"
    child = f"import time,pathlib; time.sleep(0.7); pathlib.Path({str(marker)!r}).touch()"
    script = f"import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', {child!r}]); print('started', flush=True); time.sleep(10)"
    state, output, exit_code = worker.run_command([sys.executable, "-c", script], (), 0.2)
    assert state == "timed_out"
    assert "started" in output and "timed out" in output
    time.sleep(0.8)
    assert not marker.exists()


def test_missing_job(flask_client):
    assert flask_client.get("/jobs/missing").status_code == 404
    assert flask_client.get("/jobs/missing/status").status_code == 404


def test_real_ansible_cannot_use_implicit_localhost(flask_client, patched_paths):
    marker = Path(patched_paths["base"]) / "local-task-ran"
    playbook = Path(patched_paths["playbooks_dir"]) / "sample.yml"
    playbook.write_text(f"""- hosts: localhost
  gather_facts: false
  tasks:
    - ansible.builtin.raw: touch {marker}
""")
    Path(patched_paths["hosts_file"]).write_text("[production]\nremote.example.test\n")
    response = flask_client.post("/run_playbook", data={"playbook": "sample.yml"})
    assert response.status_code == 202
    worker.run_one(utils.get_history_db_file(), utils.find_ansible_playbook())
    result = jobs.get(response.json["job_id"])
    assert result["state"] == "succeeded", result["output"]
    assert not marker.exists()  # Ansible's implicit localhost must not match.
    response = flask_client.post("/run_playbook", data={"playbook": "sample.yml", "execution_mode": "local"})
    worker.run_one(utils.get_history_db_file(), utils.find_ansible_playbook())
    result = jobs.get(response.json["job_id"])
    assert result["state"] == "succeeded", result["output"]
    assert marker.exists()


def test_second_worker_cannot_recover_or_consume_an_active_queue(spec):
    job, _ = jobs.enqueue(spec, "one")
    database = utils.get_history_db_file()
    jobs.claim(database)
    with open(database + ".worker.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="Another worker"):
            worker.serve(database, "ansible-playbook")
    assert jobs.get(job["id"])["state"] == "running"


def test_missing_binary_is_launch_error(spec):
    job, _ = jobs.enqueue(spec, "missing-binary")
    worker.run_one(utils.get_history_db_file(), "/missing/ansible-playbook")
    result = jobs.get(job["id"])
    assert result["state"] == "launch_error"
    assert result["exit_code"] is None
    assert utils.load_history()[0]["state"] == "launch_error"


def test_legacy_history_has_no_inferred_outcome(patched_paths):
    utils.add_history_record({"action": "run", "playbook": "old.yml", "time": "old", "output": "ok=2 failed=0"})
    result = utils.load_history()[0]
    assert result["state"] is None and result["exit_code"] is None


def test_cancel_queued_job_is_atomic_and_never_launches(flask_client, spec):
    job, _ = jobs.enqueue(spec, "cancel-queued")
    response = flask_client.post(f"/jobs/{job['id']}/cancel")
    assert response.status_code == 200
    result = response.json
    assert result["state"] == "canceled" and result["cancel_requested"]
    assert result["started_at"] is None and result["exit_code"] is None
    assert result["finished_at"] and result["duration"] is None
    assert not worker.run_one(utils.get_history_db_file(), "/missing/binary")
    assert flask_client.post(f"/jobs/{job['id']}/cancel").status_code == 200
    assert len(utils.load_history()) == 1


def test_cancel_committed_before_completion_wins(flask_client, spec):
    job, _ = jobs.enqueue(spec, "cancel-race")
    database = utils.get_history_db_file()
    jobs.claim(database)
    response = flask_client.post(f"/jobs/{job['id']}/cancel")
    assert response.status_code == 202
    assert response.json["state"] == "running" and response.json["cancel_requested"]
    jobs.finish(database, job["id"], "succeeded", "ok=1 failed=0", 0)
    result = jobs.get(job["id"])
    assert result["state"] == "canceled" and result["exit_code"] == 0
    assert utils.load_history()[0]["state"] == "canceled"


def test_cancel_does_not_relabel_completed_failure(flask_client, spec):
    job, _ = jobs.enqueue(spec, "already-failed")
    database = utils.get_history_db_file()
    jobs.claim(database)
    jobs.finish(database, job["id"], "failed", "syntax error", 4)
    assert flask_client.post(f"/jobs/{job['id']}/cancel").status_code == 409
    assert flask_client.post("/jobs/missing/cancel").status_code == 404
    assert jobs.get(job["id"])["state"] == "failed"
