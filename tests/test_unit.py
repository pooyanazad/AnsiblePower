import unittest
import os
import json
import csv
import sys
from io import BytesIO, StringIO
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

        self.assertEqual(
            [{k: v for k, v in r.items() if k != 'id'} for r in load_history()],
            history_data,
        )

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
        self.assertEqual(
            [{k: v for k, v in r.items() if k != 'id'} for r in load_history()],
            history_data,
        )

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
        csp = response.headers.get("Content-Security-Policy", "")
        self.assertTrue(csp, "Content-Security-Policy header must be present")
        self.assertIn("'self'", csp)
        self.assertIn("stackpath.bootstrapcdn.com", csp)
        self.assertIn("cdnjs.cloudflare.com", csp)
        self.assertIn("cdn.jsdelivr.net", csp)

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

    def test_csp_whitelists_required_sources(self):
        """CSP header must whitelist 'self', stackpath, cdnjs, and jsdelivr (task 66)."""
        resp = self.client.get("/")
        csp = resp.headers.get("Content-Security-Policy")
        self.assertIsNotNone(csp)
        for expected in ("'self'", "stackpath.bootstrapcdn.com", "cdnjs.cloudflare.com", "cdn.jsdelivr.net"):
            self.assertIn(expected, csp, f"Expected {expected} in Content-Security-Policy header")


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

    def test_import_history_unsupported_file_types_all_return_400(self):
        """Various non-JSON/CSV extensions (.yaml, .xml, .py, .tar.gz) must all return 400."""
        for bad_filename in ["dump.yaml", "data.xml", "script.py", "backup.tar.gz"]:
            with self.subTest(filename=bad_filename):
                file_data = {"file": (BytesIO(b"data"), bad_filename)}
                resp = self.client.post(
                    "/history/import_history",
                    data=file_data,
                    content_type="multipart/form-data",
                )
                self.assertEqual(resp.status_code, 400)
                data = resp.get_json()
                self.assertIn("Unsupported file type", data.get("error", ""))

    def test_import_history_file_exceeds_max_content_length(self):
        """Uploading a file exceeding 5MB must return HTTP 413 with a JSON error (task 67)."""
        large_content = b"0" * (5 * 1024 * 1024 + 1024)
        file_data = {"file": (BytesIO(large_content), "large.json")}
        resp = self.client.post(
            "/history/import_history",
            data=file_data,
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 413)
        self.assertTrue(resp.is_json, "Response must be JSON")
        data = resp.get_json()
        self.assertIn("error", data)
        self.assertIn("5MB", data["error"])
        self.mock_save_history.assert_not_called()

    def test_max_content_length_config(self):
        """MAX_CONTENT_LENGTH must be configured to 5MB (task 67)."""
        self.assertEqual(self.app.config.get("MAX_CONTENT_LENGTH"), 5 * 1024 * 1024)


class TestHistoryExport(unittest.TestCase):
    """Task 62 — test GET /history/export_history in JSON and CSV formats."""

    def setUp(self):
        import ansiblePower
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        self.sample_records = [
            {
                "time": "2026-10-14 10:00:00",
                "playbook": "site.yml",
                "action": "run",
                "output": "ok: [web1]\nchanged: 0\nfailed: 0",
            },
            {
                "time": "2026-10-14 11:30:00",
                "playbook": "deploy.yml",
                "action": "run",
                "output": "fatal: [db1]: UNREACHABLE!",
            },
        ]

    def test_export_history_default_format_is_json(self):
        """Default export format (no query parameter) must be JSON."""
        with patch("ansiblePower.load_history", return_value=self.sample_records):
            resp = self.client.get("/history/export_history")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.content_type.startswith("application/json"))
            self.assertEqual(
                resp.headers.get("Content-Disposition"),
                "attachment;filename=history.json",
            )
            data = resp.get_json()
            self.assertEqual(data, self.sample_records)

    def test_export_history_json_explicit(self):
        """Export with format=json returns valid JSON with attachment header."""
        with patch("ansiblePower.load_history", return_value=self.sample_records):
            resp = self.client.get("/history/export_history?format=json")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.content_type.startswith("application/json"))
            self.assertEqual(
                resp.headers.get("Content-Disposition"),
                "attachment;filename=history.json",
            )
            data = resp.get_json()
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["playbook"], "site.yml")
            self.assertEqual(data[1]["playbook"], "deploy.yml")

    def test_export_history_json_empty(self):
        """Exporting an empty history as JSON returns empty JSON list []."""
        with patch("ansiblePower.load_history", return_value=[]):
            resp = self.client.get("/history/export_history?format=json")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json(), [])

    def test_export_history_csv_format(self):
        """Export with format=csv returns CSV file with header and record rows."""
        with patch("ansiblePower.load_history", return_value=self.sample_records):
            resp = self.client.get("/history/export_history?format=csv")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.content_type.startswith("text/csv"))
            self.assertEqual(
                resp.headers.get("Content-Disposition"),
                "attachment;filename=history.csv",
            )
            content = resp.data.decode("utf-8")
            reader = list(csv.reader(StringIO(content)))
            self.assertGreaterEqual(len(reader), 3)
            # Header check
            self.assertEqual(reader[0], ["time", "playbook", "action", "output"])
            # First record
            self.assertEqual(reader[1], [
                "2026-10-14 10:00:00",
                "site.yml",
                "run",
                "ok: [web1]\nchanged: 0\nfailed: 0",
            ])
            # Second record
            self.assertEqual(reader[2], [
                "2026-10-14 11:30:00",
                "deploy.yml",
                "run",
                "fatal: [db1]: UNREACHABLE!",
            ])

    def test_export_history_csv_empty(self):
        """Exporting an empty history as CSV returns only the header row."""
        with patch("ansiblePower.load_history", return_value=[]):
            resp = self.client.get("/history/export_history?format=csv")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.content_type.startswith("text/csv"))
            content = resp.data.decode("utf-8")
            reader = list(csv.reader(StringIO(content)))
            self.assertEqual(len(reader), 1)
            self.assertEqual(reader[0], ["time", "playbook", "action", "output"])




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


# =============================================================================
# Task 61 — Tests for settings endpoints
# =============================================================================

class TestSettingsUpdatePlaybooksDir(unittest.TestCase):
    """Task 61 — update_playbooks_dir valid / invalid path variants."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        import tempfile
        self._tmp = tempfile.mkdtemp(prefix="ap_t61_pbdir_")
        self._config_file = os.path.join(self._tmp, "config.json")
        self._history_file = os.path.join(self._tmp, "history.json")

        self._config_patcher = patch("utils.CONFIG_FILE", self._config_file)
        self._history_patcher = patch("utils.HISTORY_FILE", self._history_file)
        self._config_patcher.start()
        self._history_patcher.start()

    def tearDown(self):
        self._config_patcher.stop()
        self._history_patcher.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _post(self, path):
        return self.client.post(
            "/settings/update_playbooks_dir",
            data={"playbooks_dir": path},
        )

    def test_valid_existing_subdir_accepted(self):
        """A real subdirectory inside BASE_DIR is accepted."""
        safe_path = os.path.join(ansiblePower.BASE_DIR, "playbooks")
        resp = self._post(safe_path)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("message", data)

    def test_empty_path_rejected(self):
        """Empty path returns 400."""
        resp = self._post("")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_root_path_rejected(self):
        """'/' is outside BASE_DIR and must be rejected."""
        resp = self._post("/")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_etc_path_rejected(self):
        """/etc is a dangerous system directory and must be rejected."""
        resp = self._post("/etc")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_parent_traversal_rejected(self):
        """A path that escapes BASE_DIR via '..' must be rejected."""
        outside = os.path.dirname(ansiblePower.BASE_DIR)
        resp = self._post(outside)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_nonexistent_dir_rejected(self):
        """A path that doesn't exist on disk is rejected."""
        nonexistent = os.path.join(ansiblePower.BASE_DIR, "does_not_exist_xyz")
        resp = self._post(nonexistent)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())


class TestSettingsUpdateHostsFile(unittest.TestCase):
    """Task 61 — update_hosts_file valid / invalid path variants."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        import tempfile
        self._tmp = tempfile.mkdtemp(prefix="ap_t61_hosts_")
        self._config_file = os.path.join(self._tmp, "config.json")
        self._history_file = os.path.join(self._tmp, "history.json")

        self._config_patcher = patch("utils.CONFIG_FILE", self._config_file)
        self._history_patcher = patch("utils.HISTORY_FILE", self._history_file)
        self._config_patcher.start()
        self._history_patcher.start()

        # Create a real hosts file inside BASE_DIR/data so it passes all checks
        self._data_dir = os.path.join(ansiblePower.BASE_DIR, "data")
        os.makedirs(self._data_dir, exist_ok=True)
        self._valid_hosts = os.path.join(self._data_dir, "test_hosts_t61")
        with open(self._valid_hosts, "w") as fh:
            fh.write("[test]\nlocalhost\n")

    def tearDown(self):
        self._config_patcher.stop()
        self._history_patcher.stop()
        if os.path.exists(self._valid_hosts):
            os.remove(self._valid_hosts)
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _post(self, path):
        return self.client.post(
            "/settings/update_hosts_file",
            data={"hosts_file": path},
        )

    def test_valid_hosts_file_accepted(self):
        """An existing file inside BASE_DIR/data is accepted."""
        resp = self._post(self._valid_hosts)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")

    def test_empty_path_rejected(self):
        """Empty path returns 400."""
        resp = self._post("")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_path_traversal_rejected(self):
        """A path containing '..' must be rejected."""
        resp = self._post("../etc/passwd")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_nonexistent_file_rejected(self):
        """A path that doesn't point to an existing file is rejected."""
        resp = self._post(os.path.join(ansiblePower.BASE_DIR, "data", "no_such_file"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

    def test_path_outside_data_dir_rejected(self):
        """A file outside BASE_DIR/data must be rejected even if it exists."""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"hosts")
            outside_file = tf.name
        try:
            resp = self._post(outside_file)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("error", resp.get_json())
        finally:
            os.unlink(outside_file)


class TestSettingsSaveHosts(unittest.TestCase):
    """Task 61 — save_hosts endpoint: success, not-found, permission-denied."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        import tempfile
        self._tmp = tempfile.mkdtemp(prefix="ap_t61_save_")
        self._config_file = os.path.join(self._tmp, "config.json")
        self._history_file = os.path.join(self._tmp, "history.json")
        self._hosts_file = os.path.join(self._tmp, "hosts")
        with open(self._hosts_file, "w") as fh:
            fh.write("[all]\nlocalhost\n")
        with open(self._config_file, "w") as fh:
            json.dump({
                "playbooks_dir": os.path.join(self._tmp, "playbooks"),
                "hosts_file": self._hosts_file,
            }, fh)

        self._config_patcher = patch("utils.CONFIG_FILE", self._config_file)
        self._history_patcher = patch("utils.HISTORY_FILE", self._history_file)
        self._config_patcher.start()
        self._history_patcher.start()

    def tearDown(self):
        self._config_patcher.stop()
        self._history_patcher.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_save_hosts_success(self):
        """Posting valid content writes it to the hosts file."""
        resp = self.client.post(
            "/settings/save_hosts",
            data={"content": "[webservers]\nweb1.example.com\n"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")
        with open(self._hosts_file) as fh:
            self.assertIn("web1.example.com", fh.read())

    def test_save_hosts_file_not_found(self):
        """404 is returned when the configured hosts file doesn't exist."""
        os.remove(self._hosts_file)
        resp = self.client.post(
            "/settings/save_hosts",
            data={"content": "content"},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.get_json())

    def test_save_hosts_permission_denied(self):
        """403 is returned when the hosts file isn't writable."""
        os.chmod(self._hosts_file, 0o444)  # read-only
        try:
            resp = self.client.post(
                "/settings/save_hosts",
                data={"content": "content"},
            )
            self.assertEqual(resp.status_code, 403)
            self.assertIn("error", resp.get_json())
        finally:
            os.chmod(self._hosts_file, 0o644)  # restore


class TestSettingsSystemStatus(unittest.TestCase):
    """Task 61 — system_status endpoint returns CPU and memory percentages."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def test_system_status_returns_cpu_and_memory(self):
        """GET /settings/system_status must return cpu and memory keys."""
        resp = self.client.get("/settings/system_status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("cpu", data)
        self.assertIn("memory", data)
        self.assertIsInstance(data["cpu"], (int, float))
        self.assertIsInstance(data["memory"], (int, float))

    def test_system_status_values_in_valid_range(self):
        """CPU and memory percentages must be between 0 and 100."""
        resp = self.client.get("/settings/system_status")
        data = resp.get_json()
        self.assertGreaterEqual(data["cpu"], 0)
        self.assertLessEqual(data["cpu"], 100)
        self.assertGreaterEqual(data["memory"], 0)
        self.assertLessEqual(data["memory"], 100)

    def test_system_status_error_response(self):
        """If psutil raises an exception the endpoint returns 500 with error key."""
        import psutil
        with patch.object(psutil, "cpu_percent", side_effect=RuntimeError("no cpu")):
            resp = self.client.get("/settings/system_status")
        self.assertEqual(resp.status_code, 500)
        self.assertIn("error", resp.get_json())


class TestToggleDarkModeRemoved(unittest.TestCase):
    """Task 61 — toggle_dark_mode was removed (task 37); endpoint must return 404."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def test_toggle_dark_mode_endpoint_does_not_exist(self):
        """POST /settings/toggle_dark_mode must return 404 (endpoint removed in task 37)."""
        resp = self.client.post("/settings/toggle_dark_mode")
        self.assertEqual(resp.status_code, 404)


# =============================================================================
# Task 60 — Tests for DELETE single history entry endpoint
# =============================================================================

class TestDeleteHistory(unittest.TestCase):
    """Task 60 — POST /history/delete/<id> endpoint."""

    def setUp(self):
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        import tempfile
        self._tmp = tempfile.mkdtemp(prefix="ap_t60_del_")
        self._config_file = os.path.join(self._tmp, "config.json")
        self._history_file = os.path.join(self._tmp, "history.json")
        with open(self._config_file, "w") as fh:
            json.dump({
                "playbooks_dir": os.path.join(self._tmp, "playbooks"),
                "hosts_file": os.path.join(self._tmp, "hosts"),
            }, fh)

        self._config_patcher = patch("utils.CONFIG_FILE", self._config_file)
        self._history_patcher = patch("utils.HISTORY_FILE", self._history_file)
        self._config_patcher.start()
        self._history_patcher.start()

        # Seed one history record and capture its id
        from ansiblePower import add_history_record, load_history
        add_history_record({
            "action": "run",
            "playbook": "sample.yml",
            "output": "ok",
            "time": "2026-01-01 00:00:00",
        })
        records = load_history()
        self._record_id = records[0]["id"]

    def tearDown(self):
        self._config_patcher.stop()
        self._history_patcher.stop()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_delete_existing_record_returns_ok(self):
        """Deleting an existing record returns 200 with status=ok."""
        resp = self.client.post(f"/history/delete/{self._record_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")

    def test_delete_removes_record_from_history(self):
        """After deletion the record no longer appears in load_history."""
        self.client.post(f"/history/delete/{self._record_id}")
        from ansiblePower import load_history
        remaining = load_history()
        ids = [r["id"] for r in remaining]
        self.assertNotIn(self._record_id, ids)

    def test_delete_nonexistent_record_returns_404(self):
        """Deleting a non-existent id returns 404 with error key."""
        resp = self.client.post("/history/delete/999999")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("error", resp.get_json())

    def test_delete_requires_post_method(self):
        """GET on the delete endpoint must return 405 Method Not Allowed."""
        resp = self.client.get(f"/history/delete/{self._record_id}")
        self.assertEqual(resp.status_code, 405)


class TestAnsibleBinaryResolution(unittest.TestCase):
    """Task 63 — test ansible binary resolution logic in _find_ansible_playbook.

    Tests scenarios using mocks:
    1. Environment variable override (ANSIBLE_PLAYBOOK_BIN).
    2. Virtualenv path resolution (venv/bin/ansible-playbook).
    3. System PATH fallback (shutil.which).
    4. Ultimate default fallback string ("ansible-playbook").
    """

    def test_env_var_override(self):
        """When ANSIBLE_PLAYBOOK_BIN is set, it overrides any venv or system binary."""
        custom_bin = "/custom/opt/bin/ansible-playbook"
        with patch.dict(os.environ, {"ANSIBLE_PLAYBOOK_BIN": custom_bin}):
            with patch("ansiblePower.os.path.isfile", return_value=True):
                with patch("ansiblePower.shutil.which", return_value="/usr/bin/ansible-playbook"):
                    resolved = ansiblePower._find_ansible_playbook()
                    self.assertEqual(resolved, custom_bin)

    def test_venv_path_resolution(self):
        """When no env override is present, existing venv binary is preferred over system PATH."""
        expected_venv_bin = os.path.join(ansiblePower.BASE_DIR, "venv", "bin", "ansible-playbook")

        def fake_isfile(path):
            return path == expected_venv_bin

        env_clean = dict(os.environ)
        env_clean.pop("ANSIBLE_PLAYBOOK_BIN", None)

        with patch.dict(os.environ, env_clean, clear=True):
            with patch("ansiblePower.os.path.isfile", side_effect=fake_isfile):
                with patch("ansiblePower.shutil.which", return_value="/usr/bin/ansible-playbook"):
                    resolved = ansiblePower._find_ansible_playbook()
                    self.assertEqual(resolved, expected_venv_bin)

    def test_system_path_fallback(self):
        """When neither env override nor venv binary exists, fallback to PATH via shutil.which."""
        system_bin = "/usr/local/bin/ansible-playbook"
        env_clean = dict(os.environ)
        env_clean.pop("ANSIBLE_PLAYBOOK_BIN", None)

        with patch.dict(os.environ, env_clean, clear=True):
            with patch("ansiblePower.os.path.isfile", return_value=False):
                with patch("ansiblePower.shutil.which", return_value=system_bin) as mock_which:
                    resolved = ansiblePower._find_ansible_playbook()
                    self.assertEqual(resolved, system_bin)
                    mock_which.assert_called_once_with("ansible-playbook")

    def test_default_fallback_when_not_found(self):
        """When no env var, no venv binary, and not on PATH, return default 'ansible-playbook'."""
        env_clean = dict(os.environ)
        env_clean.pop("ANSIBLE_PLAYBOOK_BIN", None)

        with patch.dict(os.environ, env_clean, clear=True):
            with patch("ansiblePower.os.path.isfile", return_value=False):
                with patch("ansiblePower.shutil.which", return_value=None):
                    resolved = ansiblePower._find_ansible_playbook()
                    self.assertEqual(resolved, "ansible-playbook")


class TestSettingsTabs(unittest.TestCase):
    """Task 65 — test settings page renders Bootstrap tabs."""

    def setUp(self):
        import ansiblePower
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

    def test_settings_page_contains_four_tabs(self):
        """GET /settings/ must render Hosts, System, Paths, and Data Management tabs."""
        resp = self.client.get("/settings/")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Tab navigation links
        self.assertIn('id="hosts-tab"', html)
        self.assertIn('href="#tab-hosts"', html)
        self.assertIn("Hosts", html)

        self.assertIn('id="system-tab"', html)
        self.assertIn('href="#tab-system"', html)
        self.assertIn("System", html)

        self.assertIn('id="paths-tab"', html)
        self.assertIn('href="#tab-paths"', html)
        self.assertIn("Paths", html)

        self.assertIn('id="data-tab"', html)
        self.assertIn('href="#tab-data"', html)
        self.assertIn("Data Management", html)

        # Tab panes
        self.assertIn('id="tab-hosts"', html)
        self.assertIn('id="tab-system"', html)
        self.assertIn('id="tab-paths"', html)
        self.assertIn('id="tab-data"', html)

        # Essential functional controls are preserved
        self.assertIn('id="show-hosts-btn"', html)
        self.assertIn('id="edit-hosts-btn"', html)
        self.assertIn('id="save-hosts-btn"', html)
        self.assertIn('id="status-btn"', html)
        self.assertIn('id="playbooks-dir-form"', html)
        self.assertIn('id="hosts-file-form"', html)
        self.assertIn('id="clear-history-btn"', html)


class TestErrorHandlers(unittest.TestCase):
    """Test custom HTTP error handlers (task 67)."""

    def setUp(self):
        import ansiblePower
        self.app = ansiblePower.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_413_errorhandler_returns_json(self):
        """HTTP 413 errorhandler must return JSON format with an error description (task 67)."""
        from werkzeug.exceptions import RequestEntityTooLarge
        with self.app.test_request_context():
            raw_response = self.app.handle_user_exception(RequestEntityTooLarge())
            response = self.app.make_response(raw_response)
            self.assertEqual(response.status_code, 413)
            self.assertTrue(response.is_json)
            data = response.get_json()
            self.assertIn("error", data)
            self.assertIn("5MB", data["error"])



