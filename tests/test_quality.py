import unittest
import os
import json
import sys
import tempfile
import shutil

# Add parent directory to path to import ansiblePower
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ansiblePower
import utils


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

        # Patch module-level constants (now live in utils — task 50)
        self.original_config = utils.CONFIG_FILE
        self.original_history = utils.HISTORY_FILE
        utils.CONFIG_FILE = self.config_file
        utils.HISTORY_FILE = self.history_file

        ansiblePower.app.config["TESTING"] = True
        ansiblePower.app.config["WTF_CSRF_ENABLED"] = False
        self.client = ansiblePower.app.test_client()

    def tearDown(self):
        utils.CONFIG_FILE = self.original_config
        utils.HISTORY_FILE = self.original_history
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
        # The filename regex (issue #29) fires before the path-traversal check for
        # inputs like ../../etc/passwd; accept any error key — the 400 is the invariant.
        self.assertIn("error", data)

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


class TestStandardizedApiResponses(unittest.TestCase):
    """Issue 51 — all mutating endpoints must return {"status":"ok","message":"..."} on success
    and {"error":"..."} with a non-200 status on failure.
    """

    def setUp(self):
        import ansiblePower
        import utils as _utils

        self.test_dir = tempfile.mkdtemp()
        self.playbooks_dir = os.path.join(self.test_dir, "playbooks")
        os.makedirs(self.playbooks_dir)
        self.config_file = os.path.join(self.test_dir, "config.json")
        self.hosts_file = os.path.join(self.test_dir, "hosts")
        self.history_file = os.path.join(self.test_dir, "history.json")

        with open(self.config_file, "w") as f:
            json.dump({"playbooks_dir": self.playbooks_dir, "hosts_file": self.hosts_file}, f)
        with open(self.hosts_file, "w") as f:
            f.write("[test]\nlocalhost ansible_connection=local\n")
        with open(self.history_file, "w") as f:
            json.dump([], f)

        self._orig_config  = _utils.CONFIG_FILE
        self._orig_history = _utils.HISTORY_FILE
        _utils.CONFIG_FILE  = self.config_file
        _utils.HISTORY_FILE = self.history_file
        self._utils = _utils

        ansiblePower.app.config["TESTING"] = True
        ansiblePower.app.config["WTF_CSRF_ENABLED"] = False
        self.client = ansiblePower.app.test_client()

    def tearDown(self):
        self._utils.CONFIG_FILE  = self._orig_config
        self._utils.HISTORY_FILE = self._orig_history
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _assert_success(self, response, expected_status=200):
        """Assert status code, 'status':'ok', and a non-empty 'message' field."""
        self.assertEqual(response.status_code, expected_status)
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "ok", msg=f"Expected status=ok, got: {data}")
        self.assertIn("message", data, msg=f"Missing 'message' key in: {data}")
        self.assertTrue(data["message"], msg="'message' must not be empty")

    def _assert_error(self, response, expected_status):
        """Assert non-2xx status code and an 'error' key in the body."""
        self.assertEqual(response.status_code, expected_status)
        data = json.loads(response.data)
        self.assertIn("error", data, msg=f"Missing 'error' key in: {data}")
        self.assertTrue(data["error"], msg="'error' must not be empty")

    # --- update_playbooks_dir ---

    def test_update_playbooks_dir_success_schema(self):
        """Path must be inside BASE_DIR — use the real app playbooks dir."""
        import ansiblePower
        safe_path = ansiblePower.DEFAULT_PLAYBOOKS_DIR
        resp = self.client.post(
            "/settings/update_playbooks_dir",
            data={"playbooks_dir": safe_path},
        )
        self._assert_success(resp)

    def test_update_playbooks_dir_empty_returns_error(self):
        resp = self.client.post("/settings/update_playbooks_dir", data={"playbooks_dir": ""})
        self._assert_error(resp, 400)

    # --- update_hosts_file ---

    def test_update_hosts_file_success_schema(self):
        """Hosts file must be inside BASE_DIR/data — use the real app hosts file."""
        import ansiblePower
        safe_hosts = ansiblePower.HOSTS_FILE
        resp = self.client.post(
            "/settings/update_hosts_file",
            data={"hosts_file": safe_hosts},
        )
        self._assert_success(resp)

    def test_update_hosts_file_empty_returns_error(self):
        resp = self.client.post("/settings/update_hosts_file", data={"hosts_file": ""})
        self._assert_error(resp, 400)

    # --- save_hosts ---

    def test_save_hosts_success_schema(self):
        resp = self.client.post(
            "/settings/save_hosts",
            data={"content": "# test hosts\n"},
        )
        self._assert_success(resp)

    def test_save_hosts_missing_file_returns_error(self):
        """If hosts file is deleted, save_hosts must return {"error": ...} with 404."""
        os.remove(self.hosts_file)
        resp = self.client.post("/settings/save_hosts", data={"content": "x"})
        self._assert_error(resp, 404)

    # --- clear_history ---

    def test_clear_history_success_schema(self):
        resp = self.client.post("/settings/clear_history")
        self._assert_success(resp)

    # --- error shape: non-2xx responses must carry "error" key, never "status":"ok" ---

    def test_error_responses_never_contain_status_ok(self):
        """A sampling of error paths must not accidentally return status=ok."""
        error_cases = [
            ("/settings/update_playbooks_dir", {"playbooks_dir": ""}, 400),
            ("/settings/update_hosts_file",    {"hosts_file": ""},    400),
            ("/run_playbook",                  {"playbook": ""},      400),
            ("/show_playbook",                 {"playbook": ""},      400),
        ]
        for url, data, expected_status in error_cases:
            resp = self.client.post(url, data=data)
            self.assertEqual(resp.status_code, expected_status, msg=f"URL: {url}")
            body = json.loads(resp.data)
            self.assertNotEqual(
                body.get("status"), "ok",
                msg=f"Error response for {url} must not have status=ok: {body}",
            )
            self.assertIn("error", body, msg=f"Error response for {url} must have 'error' key: {body}")


if __name__ == "__main__":
    unittest.main()