import requests
from bs4 import BeautifulSoup
import time

BASE_URL = "http://localhost:5000"

def test_homepage():
    print("Testing Homepage...")
    res = requests.get(BASE_URL)
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
    # 1. Show Playbook
    res = requests.post(f"{BASE_URL}/show_playbook", data={"playbook": "sample.yml"})
    assert res.status_code == 200
    assert "content" in res.json(), "No content in show_playbook response"
    assert "Sample playbook" in res.json()["content"]

    # 2. Run Playbook
    res = requests.post(f"{BASE_URL}/run_playbook", data={"playbook": "sample.yml"})
    assert res.status_code == 200
    assert "output" in res.json(), "No output in run_playbook response"
    
    # Wait for history to be written
    time.sleep(1)
    
    # 3. History Page
    res = requests.get(f"{BASE_URL}/history/")
    assert res.status_code == 200
    soup = BeautifulSoup(res.text, 'html.parser')
    table = soup.find('table')
    assert table, "History table not found"
    
    # 4. Export History
    res = requests.get(f"{BASE_URL}/history/export_history?format=json")
    assert res.status_code == 200
    history_data = res.json()
    assert isinstance(history_data, list), "Exported history is not a list"
    assert len(history_data) >= 1, "Exported history is empty"
    
    # 5. Settings Page and Dark Mode Toggle
    res = requests.get(f"{BASE_URL}/settings/")
    assert res.status_code == 200
    soup = BeautifulSoup(res.text, 'html.parser')
    assert soup.find('button', id='toggle-dark-mode'), "Dark Mode Toggle not found in settings"
    
    # 6. Settings System Status
    res = requests.get(f"{BASE_URL}/settings/system_status")
    assert res.status_code == 200
    data = res.json()
    assert "cpu" in data and "memory" in data, "System status missing cpu or memory"
    
    # 7. Settings Hosts File
    res = requests.get(f"{BASE_URL}/settings/get_hosts")
    assert res.status_code == 200
    data = res.json()
    assert "content" in data, "Hosts file missing content"
    
    print("All functional and GUI tests passed successfully!")

if __name__ == "__main__":
    test_homepage()
    test_endpoints()
