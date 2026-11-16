import requests
from bs4 import BeautifulSoup
import time
import threading
import sys
import pytest
from werkzeug.serving import make_server

import ansiblePower
import auth
import worker
import utils

BASE_URL = "http://localhost:5000"

# Use a session so cookies (session cookie) persist between requests
session = requests.Session()


@pytest.fixture(autouse=True)
def live_server(isolated_auth):
    """Serve an isolated copy over real HTTP, including the login flow."""
    import tempfile
    import json
    import os
    import utils

    global BASE_URL, session
    with tempfile.TemporaryDirectory() as base, pytest.MonkeyPatch.context() as monkeypatch:
        config = os.path.join(base, "config.json")
        hosts = utils.HOSTS_FILE
        with open(hosts, "w") as stream:
            stream.write("[local]\nlocalhost ansible_connection=local\n")
        playbooks = os.path.join(base, "playbooks")
        os.mkdir(playbooks)
        with open(os.path.join(playbooks, "sample.yml"), "w") as stream:
            stream.write("- name: Sample playbook\n  hosts: all\n  gather_facts: false\n  tasks: []\n")
        with open(config, "w") as stream:
            json.dump({"playbooks_dir": playbooks, "hosts_file": hosts}, stream)
        monkeypatch.setattr(utils, "CONFIG_FILE", config)
        monkeypatch.setattr(utils, "HISTORY_FILE", os.path.join(base, "history.json"))
        monkeypatch.setitem(ansiblePower.app.config, "AUTH_DATABASE", os.path.join(base, "auth.db"))
        monkeypatch.setitem(ansiblePower.app.config, "WTF_CSRF_ENABLED", True)
        monkeypatch.setitem(ansiblePower.app.config, "SESSION_COOKIE_SECURE", False)
        # Exercise a real subprocess without connecting to infrastructure or
        # depending on Ansible being installed in the HTTP test environment.
        runner = os.path.join(base, "ansible-playbook-test")
        with open(runner, "w") as stream:
            stream.write(f"#!{sys.executable}\n"
                         "import pathlib, sys, time\n"
                         "target = sys.argv[sys.argv.index('-i') + 1]\n"
                         "if target == 'localhost,':\n"
                         "    assert '--connection=local' in sys.argv and '--limit' in sys.argv\n"
                         "else:\n"
                         "    assert 'localhost' in pathlib.Path(target).read_text()\n"
                         "content = pathlib.Path(sys.argv[1]).read_text()\n"
                         "print('started safely', flush=True)\n"
                         "if '# slow' in content: time.sleep(30)\n"
                         "if '# failed' in content:\n"
                         "    print('good : ok=1 failed=0 unreachable=0')\n"
                         "    print('bad : ok=1 failed=1 unreachable=0')\n"
                         "    sys.exit(2)\n"
                         "print('PLAY RECAP: localhost : ok=1 changed=0 unreachable=0 failed=0')\n")
        os.chmod(runner, 0o700)
        auth.create_admin(ansiblePower.app.config["AUTH_DATABASE"], "admin", "live test password")
        server = make_server("127.0.0.1", 0, ansiblePower.app)
        BASE_URL = f"http://127.0.0.1:{server.server_port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        stop_worker = threading.Event()

        def consume():
            while not stop_worker.is_set():
                if not worker.run_one(utils.get_history_db_file(), runner, stopping=stop_worker):
                    stop_worker.wait(0.05)

        worker_thread = threading.Thread(target=consume, daemon=True)
        worker_thread.start()
        session = requests.Session()
        try:
            assert session.get(f"{BASE_URL}/history/export_history").status_code == 401
            token = get_csrf_token()
            response = session.post(f"{BASE_URL}/login", data={
                "username": "admin", "password": "live test password", "csrf_token": token})
            assert response.status_code == 200
            yield
        finally:
            session.close()
            stop_worker.set()
            worker_thread.join(timeout=5)
            server.shutdown()
            thread.join(timeout=5)

def get_csrf_token():
    """Fetch the CSRF token from the homepage meta tag."""
    res = session.get(BASE_URL)
    soup = BeautifulSoup(res.text, 'html.parser')
    meta = soup.find('meta', attrs={'name': 'csrf-token'})
    assert meta, "CSRF meta tag not found in page"
    return meta['content']

def test_homepage():
    print("Testing Homepage...")
    res = session.get(BASE_URL)
    assert res.status_code == 200, f"Homepage returned {res.status_code}"
    
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # Check for visual/GUI elements in base layout
    assert soup.find('nav', class_='sidebar'), "Sidebar not found"
    assert soup.find('main', role='main'), "Main content not found"
    
    # Check for playbooks
    playbook_list = soup.find('div', class_='list-group')
    assert playbook_list, "Playbook list-group not found"
    
    options = [btn.get('data-playbook') for btn in playbook_list.find_all('button', class_='run-btn')]
    print(f"Found playbooks: {options}")
    assert "sample.yml" in options, "sample.yml not found in playbook list"

def test_endpoints():
    print("Testing Endpoints...")
    csrf_token = get_csrf_token()
    headers = {'X-CSRFToken': csrf_token}

    # 1. Show Playbook
    res = session.post(f"{BASE_URL}/show_playbook", data={"playbook": "sample.yml"}, headers=headers)
    assert res.status_code == 200, f"show_playbook returned {res.status_code}"
    assert "content" in res.json(), "No content in show_playbook response"
    assert "Sample playbook" in res.json()["content"]

    # 2. Run Playbook
    res = session.post(f"{BASE_URL}/run_playbook", data={"playbook": "sample.yml"}, headers=headers)
    assert res.status_code == 202, f"run_playbook returned {res.status_code}"
    status_url = res.json()["status_url"]
    for _ in range(100):
        result = session.get(f"{BASE_URL}{status_url}").json()
        if result["state"] not in {"queued", "running"}:
            break
        time.sleep(0.05)
    assert result["state"] == "succeeded", result
    assert "ok=1" in result["output"]
    
    # 3. History Page
    res = session.get(f"{BASE_URL}/history/")
    assert res.status_code == 200
    soup = BeautifulSoup(res.text, 'html.parser')
    table = soup.find('table')
    assert table, "History table not found"
    
    # 4. Export History
    res = session.get(f"{BASE_URL}/history/export_history?format=json")
    assert res.status_code == 200
    history_data = res.json()
    assert isinstance(history_data, list), "Exported history is not a list"
    assert len(history_data) >= 1, "Exported history is empty"
    
    # 5. Settings Page and Dark Mode Toggle (toggle is in the header, present on all pages)
    res = session.get(f"{BASE_URL}/settings/")
    assert res.status_code == 200
    soup = BeautifulSoup(res.text, 'html.parser')
    assert soup.find('button', id='toggle-dark-mode'), "Dark Mode Toggle not found in header"
    
    # 6. Settings System Status
    res = session.get(f"{BASE_URL}/settings/system_status")
    assert res.status_code == 200
    data = res.json()
    assert "cpu" in data and "memory" in data, "System status missing cpu or memory"
    
    # 7. Settings Hosts File
    res = session.get(f"{BASE_URL}/settings/get_hosts")
    assert res.status_code == 200
    data = res.json()
    assert "content" in data, "Hosts file missing content"
    
    print("All functional and GUI tests passed successfully!")


def wait_for_job(job, expected, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = session.get(BASE_URL + job["status_url"], timeout=2).json()
        if result["state"] in expected:
            return result
        time.sleep(0.05)
    pytest.fail(f"Run never reached {expected}: {result}")


def test_authenticated_workflow_reports_failure_cancels_and_repairs_inventory():
    """Real HTTP, real CSRF, and a harmless worker process exercise the UI APIs."""
    from pathlib import Path

    token = get_csrf_token()
    headers = {'X-CSRFToken': token}
    playbooks = Path(utils.get_playbooks_dir())
    for name, comment in (("failed.yml", "# failed"), ("slow.yml", "# slow")):
        (playbooks / name).write_text(comment + "\n- hosts: all\n  tasks: []\n")

    assert session.get(BASE_URL + '/static/js/main.js', timeout=2).status_code == 200
    assert session.get(BASE_URL + '/static/css/styles.css', timeout=2).status_code == 200
    original_config = Path(utils.CONFIG_FILE).read_bytes()
    rejected = session.post(BASE_URL + '/settings/update_hosts_file',
                            data={'hosts_file': utils.CONFIG_FILE}, headers=headers, timeout=2)
    assert rejected.status_code == 400 and Path(utils.CONFIG_FILE).read_bytes() == original_config
    inventory_text = '[local]\nlocalhost ansible_connection=local\n'
    assert session.post(BASE_URL + '/settings/save_hosts', data={'content': inventory_text},
                        headers=headers, timeout=2).status_code == 200
    assert session.get(BASE_URL + '/settings/get_hosts', timeout=2).json()['content'] == inventory_text

    launched = session.post(BASE_URL + '/run_playbook', data={'playbook': 'failed.yml'}, headers=headers, timeout=2)
    assert launched.status_code == 202
    failed = wait_for_job(launched.json(), {'failed'})
    assert failed['exit_code'] == 2 and failed['duration'] >= 0
    assert failed['started_at'] and failed['finished_at']
    assert 'good : ok=1 failed=0' in failed['output'] and 'bad : ok=1 failed=1' in failed['output']
    detail = session.get(BASE_URL + launched.json()['url'], timeout=2)
    soup = BeautifulSoup(detail.text, 'html.parser')
    assert soup.find(id='job-state').text == 'Failed'
    assert 'badge-danger' in soup.find(id='job-state')['class']
    history = session.get(BASE_URL + '/history/', timeout=2).text
    assert 'history-row--failed' in history and 'history-row--success' not in history

    launched = session.post(BASE_URL + '/run_playbook', data={'playbook': 'slow.yml'}, headers=headers, timeout=2)
    assert launched.status_code == 202
    live = wait_for_job(launched.json(), {'running'})
    deadline = time.monotonic() + 10
    while 'started safely' not in live['output']:
        assert time.monotonic() < deadline
        time.sleep(0.05)
        live = session.get(BASE_URL + launched.json()['status_url'], timeout=2).json()
    assert session.post(BASE_URL + f"/jobs/{live['id']}/cancel", timeout=2).status_code == 400
    canceled = session.post(BASE_URL + f"/jobs/{live['id']}/cancel", headers=headers, timeout=2)
    assert canceled.status_code == 202 and canceled.json()['cancel_requested']
    result = wait_for_job(launched.json(), {'canceled'})
    assert result['exit_code'] < 0 and 'started safely' in result['output']

    hosts = Path(utils.get_hosts_file())
    hosts.unlink()
    rejected = session.post(BASE_URL + '/run_playbook', data={'playbook': 'sample.yml'}, headers=headers, timeout=2)
    assert rejected.status_code == 404 and rejected.json()['repair']['url'] == '/settings/'
    # Only explicit Local mode can run while inventory is missing.
    local = session.post(BASE_URL + '/run_playbook', data={'playbook': 'sample.yml', 'execution_mode': 'local'},
                         headers=headers, timeout=2)
    assert local.status_code == 202
    assert wait_for_job(local.json(), {'succeeded'})['exit_code'] == 0
    hosts.write_text(inventory_text)
    exported = session.get(BASE_URL + '/history/export_history', timeout=2).json()
    assert {record['state'] for record in exported} == {'failed', 'canceled', 'succeeded'}
    assert all(record['started_at'] and record['finished_at'] and record['duration'] >= 0 for record in exported)

    assert session.post(BASE_URL + '/logout', headers=headers, timeout=2).status_code == 200
    assert session.get(BASE_URL + '/history/export_history', timeout=2).status_code == 401
    assert session.get(BASE_URL + launched.json()['status_url'], timeout=2).status_code == 401
    assert session.get(BASE_URL + '/health', timeout=2).json() == {'status': 'ok'}

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
