import unittest
import os
import json
import sys
from io import BytesIO
from unittest.mock import patch, mock_open

# Add parent directory to path to import ansiblePower
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils
import ansiblePower
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

        # Patch the constants in utils (task 50 moved them there)
        patcher_config = patch("utils.CONFIG_FILE", self.test_config_file)
        patcher_history = patch("utils.HISTORY_FILE", self.test_history_file)
        patcher_default_dir = patch(
            "utils.DEFAULT_PLAYBOOKS_DIR",
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

    @patch("utils.open", new_callable=mock_open)
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

    @patch("utils.sqlite3.connect")
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
        outside = os.path.dirname(ansiblePower.BASE_DIR)
        resp = self._post(outside)
        self.assertEqual(resp.status_code, 400)

    def test_valid_subdir_accepted(self):
        """A path strictly inside BASE_DIR must be accepted."""
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

        self._config_patcher  = patch("utils.CONFIG_FILE",  self._config_file)
        self._history_patcher = patch("utils.HISTORY_FILE", self._history_file)
        # Also disable rate limiter so test requests are not throttled (task 49)
        self._limiter_patcher = patch("ansiblePower.limiter.enabled", False)
        self._config_patcher.start()
        self._history_patcher.start()
        self._limiter_patcher.start()

    def tearDown(self):
        self._config_patcher.stop()
        self._history_patcher.stop()
        self._limiter_patcher.stop()
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


class TestRunPlaybookFailure(unittest.TestCase):
    """Test 28 — run_playbook CalledProcessError: error output is returned."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.ansiblePower = ansiblePower

        import tempfile
        self._tmp = tempfile.mkdtemp(prefix="ap_test28_")
        self._playbooks_dir = os.path.join(self._tmp, "playbooks")
        os.makedirs(self._playbooks_dir)

        self._playbook_name = "failing.yml"
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

        self._config_patcher  = patch("utils.CONFIG_FILE",  self._config_file)
        self._history_patcher = patch("utils.HISTORY_FILE", self._history_file)
        self._limiter_patcher = patch("ansiblePower.limiter.enabled", False)
        self._config_patcher.start()
        self._history_patcher.start()
        self._limiter_patcher.start()

    def tearDown(self):
        self._config_patcher.stop()
        self._history_patcher.stop()
        self._limiter_patcher.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_run_playbook_called_process_error(self):
        """CalledProcessError: the error output from the exception is returned."""
        import subprocess
        error_output = b"fatal: [localhost]: UNREACHABLE!"
        exc = subprocess.CalledProcessError(returncode=2, cmd=["ansible-playbook"], output=error_output)

        with patch("ansiblePower.subprocess.check_output", side_effect=exc):
            resp = self.client.post(
                "/run_playbook",
                data={"playbook": self._playbook_name},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("output", data)
        self.assertIn("UNREACHABLE", data["output"])

        # History still records the failure output
        history = self.ansiblePower.load_history()
        self.assertTrue(len(history) >= 1)
        self.assertIn("UNREACHABLE", history[-1]["output"])


class TestRunPlaybookTimeout(unittest.TestCase):
    """Test 29 — run_playbook TimeoutExpired: friendly error message returned."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        import tempfile
        self._tmp = tempfile.mkdtemp(prefix="ap_test29_")
        self._playbooks_dir = os.path.join(self._tmp, "playbooks")
        os.makedirs(self._playbooks_dir)

        self._playbook_name = "slow.yml"
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

        self._config_patcher  = patch("utils.CONFIG_FILE",  self._config_file)
        self._history_patcher = patch("utils.HISTORY_FILE", self._history_file)
        self._limiter_patcher = patch("ansiblePower.limiter.enabled", False)
        self._config_patcher.start()
        self._history_patcher.start()
        self._limiter_patcher.start()

    def tearDown(self):
        self._config_patcher.stop()
        self._history_patcher.stop()
        self._limiter_patcher.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_run_playbook_timeout(self):
        """TimeoutExpired: response must include a friendly timeout message."""
        import subprocess
        exc = subprocess.TimeoutExpired(cmd=["ansible-playbook"], timeout=300)

        with patch("ansiblePower.subprocess.check_output", side_effect=exc):
            resp = self.client.post(
                "/run_playbook",
                data={"playbook": self._playbook_name},
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("output", data)
        # The message must mention timeout (case-insensitive)
        self.assertIn("timed out", data["output"].lower())



class TestHealthEndpoint(unittest.TestCase):
    """Test 30 — GET /health returns HTTP 200 with {"status": "ok"}."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def test_health_returns_200(self):
        """GET /health must respond 200 OK."""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)

    def test_health_returns_status_ok(self):
        """GET /health body must be {"status": "ok"}."""
        resp = self.client.get("/health")
        data = resp.get_json()
        self.assertIsNotNone(data, "Response body must be valid JSON")
        self.assertEqual(data.get("status"), "ok")

    def test_health_content_type_is_json(self):
        """GET /health must return application/json content-type."""
        resp = self.client.get("/health")
        self.assertIn("application/json", resp.content_type)

class TestStandardizedErrorResponses(unittest.TestCase):
    """Issue #37 — all error responses must return {"error": "message"} JSON."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _json_headers(self):
        return {"Accept": "application/json"}

    def test_404_returns_json_error(self):
        resp = self.client.get("/nonexistent", headers=self._json_headers())
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertIn("error", data)

    def test_404_returns_html_for_browser(self):
        resp = self.client.get("/nonexistent", headers={"Accept": "text/html"})
        self.assertEqual(resp.status_code, 404)
        self.assertIn(b"404", resp.data)
        self.assertIn(b"Page not found", resp.data)

    def test_429_returns_json_error(self):
        """Rate-limited endpoint must return {"error": "..."}."""
        # Temporarily enable rate limiter with a very low limit
        original_enabled = ansiblePower.limiter.enabled
        ansiblePower.limiter.enabled = True
        try:
            # Exhaust the 5/min limit on run_playbook
            for _ in range(6):
                resp = self.client.post(
                    "/run_playbook",
                    data={"playbook": "x.yml"},
                    headers=self._json_headers(),
                )
            self.assertEqual(resp.status_code, 429)
            data = resp.get_json()
            self.assertIn("error", data)
        finally:
            ansiblePower.limiter.enabled = original_enabled
            ansiblePower.limiter.reset()

    def test_update_playbooks_dir_empty_returns_error_key(self):
        resp = self.client.post(
            "/settings/update_playbooks_dir",
            data={"playbooks_dir": ""},
            headers=self._json_headers(),
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)

    def test_update_hosts_file_empty_returns_error_key(self):
        resp = self.client.post(
            "/settings/update_hosts_file",
            data={"hosts_file": ""},
            headers=self._json_headers(),
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("error", data)


class TestImportHistory(unittest.TestCase):
    """Test POST /history/import_history validation and record limit (closes #23)."""

    def setUp(self):
        import ansiblePower
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        # Isolate save_history so tests don't modify or wipe persistent test data
        self.patcher_save = patch("ansiblePower.save_history")
        self.mock_save_history = self.patcher_save.start()
        self.addCleanup(self.patcher_save.stop)

    def test_import_history_missing_file(self):
        """Missing file field in multipart form data must return 400."""
        resp = self.client.post("/history/import_history")
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("error"), "No file provided")
        self.mock_save_history.assert_not_called()

    def test_import_history_empty_filename(self):
        """Empty filename must return 400."""
        file_data = {"file": (BytesIO(b""), "")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("error"), "Empty file name")
        self.mock_save_history.assert_not_called()

    def test_import_history_unsupported_file_type(self):
        """Non-JSON, non-CSV file must return 400."""
        file_data = {"file": (BytesIO(b"content"), "history.txt")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("Unsupported file type", data.get("error", ""))
        self.mock_save_history.assert_not_called()

    def test_import_history_invalid_json_format(self):
        """JSON payload that is not a list must return 400."""
        file_data = {"file": (BytesIO(b'{"key": "value"}'), "history.json")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("Invalid data format", data.get("error", ""))
        self.mock_save_history.assert_not_called()

    def test_import_history_malformed_json_syntax(self):
        """Malformed JSON syntax must return 400 with a descriptive error."""
        file_data = {"file": (BytesIO(b'{"broken": [}'), "broken.json")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("Invalid JSON format", data.get("error", ""))
        self.mock_save_history.assert_not_called()

    def test_import_history_non_utf8_csv(self):
        """Non-UTF-8 CSV content must return 400 with an encoding error."""
        file_data = {"file": (BytesIO(b"\xff\xfe\x00\x00"), "invalid.csv")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("File encoding error", data.get("error", ""))
        self.mock_save_history.assert_not_called()

    def test_import_history_invalid_record_entry(self):
        """JSON list containing non-dict items must return 400."""
        file_data = {"file": (BytesIO(b'["string-not-dict"]'), "history.json")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("Invalid record format", data.get("error", ""))
        self.mock_save_history.assert_not_called()

    def test_import_history_json_exceeds_max_limit(self):
        """JSON with > 10,000 records must return 400 to prevent DoS."""
        records = [{"action": "run", "playbook": "test.yml"}] * 10001
        file_data = {"file": (BytesIO(json.dumps(records).encode("utf-8")), "large.json")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("exceeds maximum limit", data.get("error", ""))
        self.mock_save_history.assert_not_called()

    def test_import_history_csv_exceeds_max_limit(self):
        """CSV with > 10,000 records must return 400 to prevent DoS."""
        csv_content = "action,playbook,output,time\n" + ("run,test.yml,ok,2026-09-17\n" * 10001)
        file_data = {"file": (BytesIO(csv_content.encode("utf-8")), "large.csv")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertIn("exceeds maximum limit", data.get("error", ""))
        self.mock_save_history.assert_not_called()

    def test_import_history_exact_max_boundary(self):
        """Exact boundary of 10,000 records must succeed."""
        records = [{"action": "run", "playbook": "test.yml", "output": "ok", "time": "2026-09-17"}] * 10000
        file_data = {"file": (BytesIO(json.dumps(records).encode("utf-8")), "boundary.json")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")
        self.mock_save_history.assert_called_once()
        saved_records = self.mock_save_history.call_args[0][0]
        self.assertEqual(len(saved_records), 10000)

    def test_import_history_json_within_limit(self):
        """Valid JSON within record limit must succeed and sanitize fields."""
        records = [{
            "action": "run",
            "playbook": "test.yml",
            "output": "ok",
            "time": "2026-09-17",
            "extra_dangerous_key": "should_be_stripped"
        }]
        file_data = {"file": (BytesIO(json.dumps(records).encode("utf-8")), "valid.json")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")
        self.mock_save_history.assert_called_once_with([{
            "action": "run",
            "playbook": "test.yml",
            "output": "ok",
            "time": "2026-09-17"
        }])

    def test_import_history_csv_within_limit(self):
        """Valid CSV within record limit must succeed."""
        csv_content = "action,playbook,output,time\nrun,test.yml,ok,2026-09-17\n"
        file_data = {"file": (BytesIO(csv_content.encode("utf-8")), "valid.csv")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")
        self.mock_save_history.assert_called_once_with([{
            "action": "run",
            "playbook": "test.yml",
            "output": "ok",
            "time": "2026-09-17"
        }])

    def test_import_history_case_insensitive_extension(self):
        """Uppercase .JSON and .CSV extensions must be accepted."""
        records = [{"action": "run", "playbook": "test.yml", "output": "ok", "time": "2026-09-17"}]
        file_data = {"file": (BytesIO(json.dumps(records).encode("utf-8")), "CAPS.JSON")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        self.mock_save_history.assert_called_once()



class TestHistoryRowColorCoding(unittest.TestCase):
    """Task 52 — history rows must carry the correct CSS modifier class."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def _get_history_html(self, output_text):
        """Patch load_history to return a single record, then GET /history/."""
        record = {"action": "run", "playbook": "test.yml",
                  "time": "2026-09-24 12:00:00", "output": output_text}
        with patch("ansiblePower.load_history", return_value=[record]):
            resp = self.client.get("/history/")
        self.assertEqual(resp.status_code, 200)
        return resp.data.decode("utf-8")

    def test_success_row_class(self):
        """Rows with 'ok=' and no failures get the --success class."""
        html = self._get_history_html(
            "PLAY RECAP\nlocalhost : ok=3 changed=0 unreachable=0 failed=0"
        )
        self.assertIn("history-row--success", html)

    def test_failed_row_class(self):
        """Rows with failed>0 get the --failed class."""
        html = self._get_history_html(
            "PLAY RECAP\nlocalhost : ok=1 changed=0 unreachable=0 failed=1"
        )
        self.assertIn("history-row--failed", html)

    def test_fatal_row_class(self):
        """Rows with 'fatal:' get the --failed class."""
        html = self._get_history_html("fatal: [localhost]: UNREACHABLE!")
        # 'unreachable' is in the text but the primary marker is fatal:
        # Jinja checks 'fatal:' under the failed branch
        self.assertIn("history-row--failed", html)

    def test_unreachable_row_class(self):
        """Rows with unreachable>0 get the --unreachable class."""
        html = self._get_history_html(
            "PLAY RECAP\nlocalhost : ok=0 changed=0 unreachable=1 failed=0"
        )
        self.assertIn("history-row--unreachable", html)

    def test_unknown_row_class(self):
        """Rows with no Ansible keywords get the --unknown class."""
        html = self._get_history_html("No output produced.")
        self.assertIn("history-row--unknown", html)


class TestColorCodedOutputEndpoint(unittest.TestCase):
    """Task 53 — /run_playbook JSON output must be suitable for colorization."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        import tempfile
        self._tmp = tempfile.mkdtemp(prefix="ap_test53_")
        self._playbooks_dir = os.path.join(self._tmp, "playbooks")
        os.makedirs(self._playbooks_dir)
        self._playbook_name = "color.yml"
        with open(os.path.join(self._playbooks_dir, self._playbook_name), "w") as fh:
            fh.write("---\n- hosts: all\n  tasks: []\n")

        self._config_file = os.path.join(self._tmp, "config.json")
        self._history_file = os.path.join(self._tmp, "history.json")
        import json as _json
        with open(self._config_file, "w") as fh:
            _json.dump({
                "playbooks_dir": self._playbooks_dir,
                "hosts_file": os.path.join(self._tmp, "hosts"),
            }, fh)

        self._config_patcher = patch("utils.CONFIG_FILE", self._config_file)
        self._history_patcher = patch("utils.HISTORY_FILE", self._history_file)
        self._limiter_patcher = patch("ansiblePower.limiter.enabled", False)
        self._config_patcher.start()
        self._history_patcher.start()
        self._limiter_patcher.start()

    def tearDown(self):
        self._config_patcher.stop()
        self._history_patcher.stop()
        self._limiter_patcher.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_output_contains_play_recap(self):
        """run_playbook response output must include PLAY RECAP when present."""
        fake_output = (
            b"PLAY [localhost] **\n"
            b"TASK [debug] **\n"
            b"ok: [localhost]\n"
            b"PLAY RECAP **\n"
            b"localhost : ok=1 changed=0 unreachable=0 failed=0\n"
        )
        with patch("ansiblePower.subprocess.check_output", return_value=fake_output):
            resp = self.client.post(
                "/run_playbook",
                data={"playbook": self._playbook_name},
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("PLAY RECAP", data["output"])
        self.assertIn("ok:", data["output"])


if __name__ == "__main__":
    unittest.main()

