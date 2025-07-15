import unittest
import os
import json
from unittest.mock import patch, mock_open

# Assuming ansiblePower.py is in the same directory
# If not, you might need to adjust the import path
from ansiblePower import load_config, save_config, load_history, save_history

class TestConfigAndHistory(unittest.TestCase):

    def setUp(self):
        # Set up temporary file paths for testing
        self.test_config_file = "test_config.json"
        self.test_history_file = "test_history.json"
        self.default_playbooks_dir = "/path/to/default/playbooks"
        # Patch the constants in the original module
        patcher_config = patch('ansiblePower.CONFIG_FILE', self.test_config_file)
        patcher_history = patch('ansiblePower.HISTORY_FILE', self.test_history_file)
        patcher_default_dir = patch('ansiblePower.DEFAULT_PLAYBOOKS_DIR', self.default_playbooks_dir)
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

    def tearDown(self):
        # Clean up test files after each test
        if os.path.exists(self.test_config_file):
            os.remove(self.test_config_file)
        if os.path.exists(self.test_history_file):
            os.remove(self.test_history_file)

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

    @patch('ansiblePower.open', new_callable=mock_open)
    def test_save_config_write_error(self, mock_file):
        mock_file.side_effect = IOError("Permission denied")
        config_data = {"playbooks_dir": "/new/path"}
        with self.assertLogs('ansiblePower', level='ERROR') as cm:
            save_config(config_data)
        self.assertIn("Error saving config:", cm.output[0])

    # Test load_history
    def test_load_history_existing_valid(self):
        history_data = [{"action": "run", "playbook": "test.yml", "time": "now", "output": "success"}]
        with open(self.test_history_file, "w") as f:
            json.dump(history_data, f)
        self.assertEqual(load_history(), history_data)

    def test_load_history_file_not_found(self):
        self.assertEqual(load_history(), [])

    def test_load_history_invalid_json(self):
        with open(self.test_history_file, "w") as f:
            f.write("invalid json history")
        self.assertEqual(load_history(), [])

    # Test save_history
    def test_save_history_success(self):
        history_data = [{"action": "show", "playbook": "other.yml", "time": "later", "output": "content"}]
        save_history(history_data)
        self.assertTrue(os.path.exists(self.test_history_file))
        with open(self.test_history_file, "r") as f:
            loaded_history = json.load(f)
        self.assertEqual(loaded_history, history_data)

    @patch('ansiblePower.open', new_callable=mock_open)
    def test_save_history_write_error(self, mock_file):
        mock_file.side_effect = IOError("Disk full")
        history_data = [{"action": "save", "playbook": "fail.yml"}]
        with self.assertLogs('ansiblePower', level='ERROR') as cm:
            save_history(history_data)
        self.assertIn("Error saving history:", cm.output[0])

if __name__ == '__main__':
    unittest.main()