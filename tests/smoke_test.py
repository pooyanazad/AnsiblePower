#!/usr/bin/env python3
"""
Smoke Tests for AnsiblePower Application

These tests verify basic functionality and ensure the application
can start and respond to basic requests without errors.
"""

import unittest
import sys
import os
import tempfile
import json
from unittest.mock import patch, MagicMock

# Add the parent directory to the path to import ansiblePower
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import ansiblePower
except ImportError as e:
    print(f"Error importing ansiblePower: {e}")
    sys.exit(1)


class SmokeTestAnsiblePower(unittest.TestCase):
    """Smoke tests for AnsiblePower application"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary directory for test data
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, 'config.json')
        self.hosts_file = os.path.join(self.test_dir, 'hosts')
        self.history_file = os.path.join(self.test_dir, 'history.json')
        
        # Create test config
        test_config = {
            "playbooks_dir": self.test_dir,
            "hosts_file": self.hosts_file
        }
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        # Create test hosts file
        with open(self.hosts_file, 'w') as f:
            f.write("[test]\nlocalhost ansible_connection=local\n")
        
        # Create empty history file
        with open(self.history_file, 'w') as f:
            json.dump([], f)
        
        # Mock the file paths in ansiblePower
        self.original_config_file = getattr(ansiblePower, 'CONFIG_FILE', None)
        self.original_history_file = getattr(ansiblePower, 'HISTORY_FILE', None)
        
        ansiblePower.CONFIG_FILE = self.config_file
        ansiblePower.HISTORY_FILE = self.history_file
        
        # Create Flask test client
        ansiblePower.app.config['TESTING'] = True
        self.client = ansiblePower.app.test_client()

    def tearDown(self):
        """Clean up after each test method."""
        # Restore original file paths
        if self.original_config_file:
            ansiblePower.CONFIG_FILE = self.original_config_file
        if self.original_history_file:
            ansiblePower.HISTORY_FILE = self.original_history_file
        
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_app_starts_successfully(self):
        """Test that the Flask application starts without errors"""
        self.assertIsNotNone(ansiblePower.app)
        self.assertTrue(ansiblePower.app.config['TESTING'])

    def test_homepage_loads(self):
        """Test that the homepage loads successfully"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AnsiblePower', response.data)

    def test_history_page_loads(self):
        """Test that the history page loads successfully"""
        response = self.client.get('/history/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_settings_page_loads(self):
        """Test that the settings page loads successfully"""
        response = self.client.get('/settings/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Settings', response.data)

    def test_api_endpoints_respond(self):
        """Test that API endpoints respond without server errors"""
        # Test settings API endpoints
        api_endpoints = [
            '/settings/get_hosts',
            '/settings/system_status'
        ]
        
        for endpoint in api_endpoints:
            response = self.client.get(endpoint, follow_redirects=True)
            # Should respond without server errors (not 500)
            self.assertNotEqual(response.status_code, 500)

    @patch('ansiblePower.psutil')
    def test_system_status_endpoint(self, mock_psutil):
        """Test that system status endpoint works"""
        # Mock psutil functions
        mock_psutil.cpu_percent.return_value = 50.0
        mock_psutil.virtual_memory.return_value = MagicMock(percent=60.0)
        
        response = self.client.get('/settings/system_status')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('cpu', data)
        self.assertIn('memory', data)

    def test_config_loading(self):
        """Test that configuration loads correctly"""
        # Test load_config function if it exists
        if hasattr(ansiblePower, 'load_config'):
            config = ansiblePower.load_config()
            self.assertIsInstance(config, dict)
            self.assertIn('playbooks_dir', config)

    def test_static_files_accessible(self):
        """Test that static files are accessible"""
        # Test CSS file
        response = self.client.get('/static/css/styles.css')
        self.assertEqual(response.status_code, 200)
        
        # Test JS file
        response = self.client.get('/static/js/main.js')
        self.assertEqual(response.status_code, 200)

    def test_error_handling(self):
        """Test that the application handles errors gracefully"""
        # Test non-existent route
        response = self.client.get('/nonexistent')
        self.assertEqual(response.status_code, 404)

    def test_post_endpoints_security(self):
        """Test that POST endpoints handle empty data gracefully"""
        # Test run_playbook with empty data - should return 400
        response = self.client.post('/run_playbook', data={}, follow_redirects=True)
        self.assertEqual(response.status_code, 400)
        
        # Test show_playbook with empty data - should return 400
        response = self.client.post('/show_playbook', data={}, follow_redirects=True)
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    # Run smoke tests
    unittest.main(verbosity=2)