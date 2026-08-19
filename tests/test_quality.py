import unittest
import os
import json
import sys
import tempfile
import shutil

# Add parent directory to path to import ansiblePower
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ansiblePower


class TestFlaskRoutes(unittest.TestCase):
    """Quality tests for Flask route responses and API endpoints."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.playbooks_dir = os.path.join(self.test_dir, "playbooks")
        os.makedirs(self.playbooks_dir)
        self.config_file = os.path.join(self.test_dir, "config.json")
        self.hosts_file = os.path.join(self.test_dir, "hosts")
        self.history_file = os.path.join(self.test_dir, "history.json")

        # Create test config
        with open(self.config_file, "w") as f:
            json.dump({"playbooks_dir": self.playbooks_dir, "hosts_file": self.hosts_file}, f)

        # Create test hosts file
        with open(self.hosts_file, "w") as f:
            f.write("[test]\nlocalhost ansible_connection=local\n")

        # Create empty history
        with open(self.history_file, "w") as f:
            json.dump([], f)

        # Create a sample playbook
        with open(os.path.join(self.playbooks_dir, "test.yml"), "w") as f:
            f.write("---\n- name: Test\n  hosts: all\n  tasks:\n    - debug: msg='hello'\n")

        # Patch module-level constants
        self.original_config = ansiblePower.CONFIG_FILE
        self.original_history = ansiblePower.HISTORY_FILE
        ansiblePower.CONFIG_FILE = self.config_file
        ansiblePower.HISTORY_FILE = self.history_file

        ansiblePower.app.config["TESTING"] = True
        ansiblePower.app.config["WTF_CSRF_ENABLED"] = False
        self.client = ansiblePower.app.test_client()

    def tearDown(self):
        ansiblePower.CONFIG_FILE = self.original_config
        ansiblePower.HISTORY_FILE = self.original_history
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_homepage_returns_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_homepage_lists_playbooks(self):
        response = self.client.get("/")
        self.assertIn(b"test.yml", response.data)

    def test_history_page_returns_200(self):
        response = self.client.get("/history/")
        self.assertEqual(response.status_code, 200)

    def test_settings_page_returns_200(self):
        response = self.client.get("/settings/")
        self.assertEqual(response.status_code, 200)

    def test_show_playbook_returns_content(self):
        response = self.client.post("/show_playbook", data={"playbook": "test.yml"})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("content", data)
        self.assertIn("Test", data["content"])

    def test_show_playbook_missing_name_returns_400(self):
        response = self.client.post("/show_playbook", data={})
        self.assertEqual(response.status_code, 400)

    def test_show_playbook_nonexistent_returns_404(self):
        response = self.client.post("/show_playbook", data={"playbook": "nonexistent.yml"})
        self.assertEqual(response.status_code, 404)

    def test_show_playbook_path_traversal_blocked(self):
        response = self.client.post("/show_playbook", data={"playbook": "../../etc/passwd"})
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("Invalid playbook path", data["error"])

    def test_run_playbook_missing_name_returns_400(self):
        response = self.client.post("/run_playbook", data={})
        self.assertEqual(response.status_code, 400)

    def test_run_playbook_path_traversal_blocked(self):
        response = self.client.post("/run_playbook", data={"playbook": "../../../etc/shadow"})
        self.assertEqual(response.status_code, 400)

    def test_get_hosts_returns_content(self):
        response = self.client.get("/settings/get_hosts")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("content", data)

    def test_clear_history(self):
        # Add a dummy history entry first
        with open(self.history_file, "w") as f:
            json.dump([{"action": "run", "playbook": "test.yml", "time": "now", "output": "ok"}], f)
        response = self.client.post("/settings/clear_history")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "ok")

    def test_export_history_json(self):
        response = self.client.get("/history/export_history?format=json")
        self.assertEqual(response.status_code, 200)

    def test_export_history_csv(self):
        response = self.client.get("/history/export_history?format=csv")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()