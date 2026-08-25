import unittest
import os
import json
import sys
from unittest.mock import patch, mock_open

# Add parent directory to path to import ansiblePower
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ansiblePower import (
    get_history_db_file,
    load_config,
    load_history,
    save_config,
    save_history,
)


class TestConfigAndHistory(unittest.TestCase):

    def setUp(self):
        # Set up temporary file paths for testing
        self.test_config_file = "test_config.json"
        self.test_history_file = "test_history.json"
        self.test_history_db_file = "test_history.db"
        self.default_playbooks_dir = "/path/to/default/playbooks"

        # Patch the constants in the original module
        patcher_config = patch("ansiblePower.CONFIG_FILE", self.test_config_file)
        patcher_history = patch("ansiblePower.HISTORY_FILE", self.test_history_file)
        patcher_default_dir = patch(
            "ansiblePower.DEFAULT_PLAYBOOKS_DIR",
            self.default_playbooks_dir,
        )

        self.mock_config = patcher_config.start()
        self.mock_history = patcher_history.start()
        self.mock_default_dir = patcher_default_dir.start()

        self.addCleanup(patcher_config.stop)
        self.addCleanup(patcher_history.stop)
        self.addCleanup(patcher_default_dir.stop)

        # Ensure test files do not exist before each test
        if os.path.exists(self.test_config_file):
            os.remove(self.test_config_file)
        if os.path.exists(self.test_history_file):
            os.remove(self.test_history_file)
        if os.path.exists(self.test_history_db_file):
            os.remove(self.test_history_db_file)

    def tearDown(self):
        # Clean up test files after each test
        if os.path.exists(self.test_config_file):
            os.remove(self.test_config_file)
        if os.path.exists(self.test_history_file):
            os.remove(self.test_history_file)
        if os.path.exists(self.test_history_db_file):
            os.remove(self.test_history_db_file)

    # Test load_config
    def test_load_config_existing_valid(self):
        config_data = {"playbooks_dir": "/path/to/playbooks"}
        with open(self.test_config_file, "w") as f:
            json.dump(config_data, f)

        self.assertEqual(load_config(), config_data)

    def test_load_config_file_not_found(self):
        self.assertEqual(load_config(), {"playbooks_dir": self.default_playbooks_dir})

    def test_load_config_invalid_json(self):
        with open(self.test_config_file, "w") as f:
            f.write("invalid json")

        self.assertEqual(load_config(), {"playbooks_dir": self.default_playbooks_dir})

    # Test save_config
    def test_save_config_success(self):
        config_data = {"playbooks_dir": "/new/path"}
        save_config(config_data)

        self.assertTrue(os.path.exists(self.test_config_file))

        with open(self.test_config_file, "r") as f:
            loaded_config = json.load(f)

        self.assertEqual(loaded_config, config_data)

    @patch("ansiblePower.open", new_callable=mock_open)
    def test_save_config_write_error(self, mock_file):
        mock_file.side_effect = IOError("Permission denied")
        config_data = {"playbooks_dir": "/new/path"}

        with self.assertLogs("ansiblePower", level="ERROR") as cm:
            save_config(config_data)

        self.assertIn("Error saving config:", cm.output[0])

    # Test SQLite history helpers
    def test_get_history_db_file_uses_history_file_path(self):
        self.assertEqual(get_history_db_file(), "test_history.db")

    def test_load_history_existing_valid(self):
        history_data = [
            {
                "action": "run",
                "playbook": "test.yml",
                "time": "now",
                "output": "success",
            }
        ]

        save_history(history_data)

        self.assertEqual(load_history(), history_data)

    def test_load_history_file_not_found(self):
        self.assertEqual(load_history(), [])

    def test_load_history_invalid_json(self):
        with open(self.test_history_file, "w") as f:
            f.write("invalid json history")

        self.assertEqual(load_history(), [])

    def test_save_history_success(self):
        history_data = [
            {
                "action": "show",
                "playbook": "other.yml",
                "time": "later",
                "output": "content",
            }
        ]

        save_history(history_data)

        self.assertTrue(os.path.exists(self.test_history_db_file))
        self.assertEqual(load_history(), history_data)

    @patch("ansiblePower.sqlite3.connect")
    def test_save_history_write_error(self, mock_connect):
        mock_connect.side_effect = OSError("Disk full")
        history_data = [{"action": "save", "playbook": "fail.yml"}]

        with self.assertLogs("ansiblePower", level="ERROR") as cm:
            save_history(history_data)

        self.assertTrue(
            any("Error saving history to SQLite:" in message for message in cm.output)
        )


class TestUpdatePlaybooksDirSecurity(unittest.TestCase):
    """Tests for the path traversal fix in update_playbooks_dir (issue 15.1)."""

    def setUp(self):
        import ansiblePower
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _post(self, path):
        return self.client.post(
            "/settings/update_playbooks_dir",
            data={"playbooks_dir": path},
        )

    def test_root_path_rejected(self):
        """Setting playbooks_dir to '/' must be rejected (would bypass commonpath guard)."""
        resp = self._post("/")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)

    def test_etc_path_rejected(self):
        """/etc is outside BASE_DIR and must be rejected."""
        resp = self._post("/etc")
        self.assertEqual(resp.status_code, 400)

    def test_parent_traversal_rejected(self):
        """A path that escapes BASE_DIR via '..' must be rejected."""
        import ansiblePower
        outside = os.path.dirname(ansiblePower.BASE_DIR)
        resp = self._post(outside)
        self.assertEqual(resp.status_code, 400)

    def test_valid_subdir_accepted(self):
        """A path strictly inside BASE_DIR must be accepted."""
        import ansiblePower
        safe_path = os.path.join(ansiblePower.BASE_DIR, "playbooks")
        resp = self._post(safe_path)
        # 200 with status ok
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")

    def test_empty_path_rejected(self):
        """An empty path must be rejected."""
        resp = self._post("")
        self.assertEqual(resp.status_code, 400)


class TestSecurityHeaders(unittest.TestCase):
    """Task 21 — verify security headers are present on every response."""

    def setUp(self):
        import ansiblePower
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _assert_security_headers(self, response):
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(
            response.headers.get("Referrer-Policy"),
            "strict-origin-when-cross-origin",
        )

    def test_security_headers_on_homepage(self):
        """Security headers must be set on GET /."""
        resp = self.client.get("/")
        self._assert_security_headers(resp)

    def test_security_headers_on_health(self):
        """Security headers must be set on GET /health."""
        resp = self.client.get("/health")
        self._assert_security_headers(resp)

    def test_security_headers_on_history(self):
        """Security headers must be set on GET /history/."""
        resp = self.client.get("/history/")
        self._assert_security_headers(resp)

    def test_security_headers_on_settings(self):
        """Security headers must be set on GET /settings/."""
        resp = self.client.get("/settings/")
        self._assert_security_headers(resp)

    def test_security_headers_on_404(self):
        """Security headers must also be present on 404 error responses."""
        resp = self.client.get("/nonexistent-route-xyz")
        self._assert_security_headers(resp)


class TestRunPlaybookValid(unittest.TestCase):
    """Test 27 — run_playbook success: mock subprocess, verify output + history saved."""

    def setUp(self):
        import ansiblePower
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.ansiblePower = ansiblePower

        import tempfile
        self._tmp = tempfile.mkdtemp(prefix="ap_test27_")
        self._playbooks_dir = os.path.join(self._tmp, "playbooks")
        os.makedirs(self._playbooks_dir)

        self._playbook_name = "hello.yml"
        with open(os.path.join(self._playbooks_dir, self._playbook_name), "w") as fh:
            fh.write("---\n- hosts: all\n  tasks: []\n")

        self._config_file  = os.path.join(self._tmp, "config.json")
        self._history_file = os.path.join(self._tmp, "history.json")

        import json as _json
        with open(self._config_file, "w") as fh:
            _json.dump({
                "playbooks_dir": self._playbooks_dir,
                "hosts_file": os.path.join(self._tmp, "hosts"),
            }, fh)

        self._config_patcher  = patch("ansiblePower.CONFIG_FILE",  self._config_file)
        self._history_patcher = patch("ansiblePower.HISTORY_FILE", self._history_file)
        self._config_patcher.start()
        self._history_patcher.start()

    def tearDown(self):
        self._config_patcher.stop()
        self._history_patcher.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_run_playbook_valid(self):
        """Mocking subprocess.check_output: output is returned and saved in history."""
        fake_output = b"PLAY RECAP *** ok=1 changed=0 unreachable=0 failed=0"

        with patch("ansiblePower.subprocess.check_output", return_value=fake_output) as mock_sub:
            resp = self.client.post(
                "/run_playbook",
                data={"playbook": self._playbook_name},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("output", data)
        self.assertIn("PLAY RECAP", data["output"])

        # Verify the record was persisted in history
        history = self.ansiblePower.load_history()
        self.assertTrue(len(history) >= 1, "Expected at least one history record")
        last = history[-1]
        self.assertEqual(last["action"], "run")
        self.assertEqual(last["playbook"], self._playbook_name)
        self.assertIn("PLAY RECAP", last["output"])

        mock_sub.assert_called_once()


if __name__ == "__main__":
    unittest.main()

