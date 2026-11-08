"""Real Supervisor/Gunicorn lifecycle test, including a run over 120 seconds."""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import requests

import auth


def eventually(check, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for the supervised service")


def test_long_runs_survive_web_recycling_and_crashes_are_not_replayed(tmp_path):
    source = Path(__file__).resolve().parents[1]
    for name in ("ansiblePower.py", "auth.py", "utils.py", "inventory.py", "jobs.py", "worker.py"):
        shutil.copy(source / name, tmp_path / name)
    for name in ("templates", "static"):
        shutil.copytree(source / name, tmp_path / name)
    data = tmp_path / "data"
    hosts = data / "inventories" / "hosts"
    hosts.parent.mkdir(parents=True)
    hosts.write_text("[production]\nnode.example.test\n")
    playbooks = tmp_path / "playbooks"
    playbooks.mkdir()
    for name, delay in (("first", 125), ("second", 125), ("third", 0), ("crash", 5)):
        (playbooks / f"{name}.yml").write_text(f"# delay: {delay}\n- hosts: all\n  tasks: []\n")
    (data / "config.json").write_text(json.dumps({"playbooks_dir": str(playbooks), "hosts_file": str(hosts)}))
    (tmp_path / "logs").mkdir()
    auth_database = str(data / "auth.db")
    auth.create_admin(auth_database, "admin", "lifecycle test password")
    fake_runner = tmp_path / "fake-ansible"
    fake_runner.write_text(
        f"#!{sys.executable}\n"
        "import pathlib,sys,time\n"
        "playbook = pathlib.Path(sys.argv[1])\n"
        "with open('starts.log', 'a') as stream: stream.write(playbook.name + '\\n')\n"
        "delay = int(playbook.read_text().splitlines()[0].split(':')[1])\n"
        "time.sleep(delay)\n"
        "print('PLAY RECAP: node.example.test : ok=1 changed=0 unreachable=0 failed=0')\n")
    fake_runner.chmod(0o700)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    supervisor_config = tmp_path / "supervisord.conf"
    supervisor_config.write_text(f"""
[supervisord]
nodaemon=true
logfile={tmp_path}/supervisor.log
pidfile={tmp_path}/supervisor.pid
[program:web]
command={sys.executable} -m gunicorn --bind 127.0.0.1:{port} --workers 2 --timeout 120 --pid {tmp_path}/web.pid ansiblePower:app
directory={tmp_path}
autorestart=true
stopasgroup=true
killasgroup=true
stdout_logfile={tmp_path}/web.log
stderr_logfile={tmp_path}/web-errors.log
[program:runner]
command={sys.executable} worker.py --concurrency 2 --timeout 160
directory={tmp_path}
autorestart=true
stopasgroup=true
killasgroup=true
stopwaitsecs=170
stdout_logfile={tmp_path}/runner.log
stderr_logfile={tmp_path}/runner-errors.log
""")
    environment = dict(os.environ, ANSIBLEPOWER_AUTH_DATABASE=auth_database,
                       ANSIBLE_PLAYBOOK_BIN=str(fake_runner), SESSION_COOKIE_SECURE="false",
                       FLASK_SECRET_KEY="lifecycle-test-key")
    with open(tmp_path / "service.log", "w") as service_log:
        supervisor = subprocess.Popen([sys.executable, "-m", "supervisor.supervisord", "-c", str(supervisor_config)],
                                      stdout=service_log, stderr=subprocess.STDOUT, env=environment)
        client = requests.Session()
        descendants = []
        try:
            def ready():
                try:
                    return client.get(base + "/health", timeout=1).status_code == 200
                except requests.RequestException:
                    return False

            eventually(ready)
            login = client.get(base + "/login", timeout=2)
            token = re.search(r'name="csrf-token" content="([^"]+)"', login.text)[1]
            assert client.post(base + "/login", data={"username": "admin", "password": "lifecycle test password",
                                                      "csrf_token": token}, timeout=3).status_code == 200
            home = client.get(base, timeout=2)
            token = re.search(r'name="csrf-token" content="([^"]+)"', home.text)[1]

            def launch(name, key):
                started = time.monotonic()
                response = client.post(base + "/run_playbook", data={"playbook": name + ".yml"},
                                       headers={"X-CSRFToken": token, "Idempotency-Key": key}, timeout=3)
                assert response.status_code == 202, response.text
                assert time.monotonic() - started < 3
                return response.json()

            def status(job):
                return client.get(base + job["status_url"], timeout=2).json()

            first = launch("first", "first")
            second = launch("second", "second")
            third = launch("third", "third")
            duplicate = launch("first", "double-click")
            assert duplicate["job_id"] == first["job_id"]
            starts = tmp_path / "starts.log"
            eventually(lambda: starts.exists() and len(starts.read_text().splitlines()) == 2)
            states = {job["job_id"]: status(job) for job in (first, second, third)}
            assert states[first["job_id"]]["state"] == "running", states
            assert states[second["job_id"]]["state"] == "running", states
            assert states[third["job_id"]]["state"] == "queued", states
            assert client.get(base + first["url"], timeout=2).status_code == 200
            assert first["url"] in client.get(base, timeout=2).text

            # Recycle both HTTP workers while the separate runner keeps working.
            master = psutil.Process(int((tmp_path / "web.pid").read_text()))
            original_workers = {process.pid for process in master.children()}
            assert len(original_workers) == 2
            for process in master.children():
                process.kill()
            eventually(lambda: len(master.children()) == 2 and not original_workers.intersection(
                process.pid for process in master.children()))
            eventually(ready)
            assert status(first)["state"] == "running"

            deadline = time.monotonic() + 140
            while status(first)["state"] in {"queued", "running"}:
                assert time.monotonic() < deadline
                request_started = time.monotonic()
                assert client.get(base + "/health", timeout=2).status_code == 200
                assert time.monotonic() - request_started < 2
                time.sleep(1)
            eventually(lambda: all(status(job)["state"] == "succeeded" for job in (first, second, third)))
            result = status(first)
            from datetime import datetime
            assert (datetime.fromisoformat(result["finished_at"]) - datetime.fromisoformat(result["started_at"])).total_seconds() > 120
            assert "PLAY RECAP" in result["output"]
            assert starts.read_text().splitlines().count("first.yml") == 1

            # A killed queue consumer is restarted, but its in-flight run is held.
            crashing = launch("crash", "crash")
            eventually(lambda: starts.read_text().splitlines().count("crash.yml") == 1)
            processes = psutil.Process(supervisor.pid).children()
            runner = next(process for process in processes if "worker.py" in process.cmdline())
            descendants = runner.children(recursive=True)
            runner.kill()
            eventually(lambda: status(crashing)["state"] == "uncertain")
            time.sleep(1)
            assert starts.read_text().splitlines().count("crash.yml") == 1
            assert status(crashing)["state"] == "uncertain"
            assert client.get(base + "/health", timeout=2).status_code == 200
        finally:
            client.close()
            for process in descendants:
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
            supervisor.terminate()
            try:
                supervisor.wait(timeout=10)
            except subprocess.TimeoutExpired:
                for process in psutil.Process(supervisor.pid).children(recursive=True):
                    try:
                        process.kill()
                    except psutil.NoSuchProcess:
                        pass
                supervisor.kill()
                supervisor.wait(timeout=5)
