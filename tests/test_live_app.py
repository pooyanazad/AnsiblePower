import requests
from bs4 import BeautifulSoup
import time
import threading
import sys
import pytest
from werkzeug.serving import make_server

import ansiblePower
import auth

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
        with open(config, "w") as stream:
            json.dump({"playbooks_dir": ansiblePower.DEFAULT_PLAYBOOKS_DIR, "hosts_file": hosts}, stream)
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
                         "import pathlib, sys\n"
                         "assert 'localhost' in pathlib.Path(sys.argv[sys.argv.index('-i') + 1]).read_text()\n"
                         "print('PLAY RECAP: localhost : ok=1 changed=0 unreachable=0 failed=0')\n")
        os.chmod(runner, 0o700)
        monkeypatch.setattr(ansiblePower, "ANSIBLE_PLAYBOOK", runner)
        auth.create_admin(ansiblePower.app.config["AUTH_DATABASE"], "admin", "live test password")
        server = make_server("127.0.0.1", 0, ansiblePower.app)
        BASE_URL = f"http://127.0.0.1:{server.server_port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
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
    assert res.status_code == 200, f"run_playbook returned {res.status_code}"
    assert "output" in res.json(), "No output in run_playbook response"
    assert "ok=1" in res.json()["output"]
    
    # Wait for history to be written
    time.sleep(1)
    
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

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
