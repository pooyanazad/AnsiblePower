"""
Shared pytest fixtures for AnsiblePower test suite.

Provides reusable fixtures for the Flask test client, temporary directories,
and pre-populated mock config / history so individual test modules don't
need to repeat setUp / tearDown boilerplate.
"""

import json
import os
import shutil
import sys
import tempfile

import pytest

# Make the project root importable from any test directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ansiblePower  # noqa: E402  (must come after sys.path manipulation)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_data_dir():
    """
    Yield a temporary directory that is automatically removed after the test.

    The directory contains the standard sub-structure expected by AnsiblePower:
    - ``playbooks/``       – directory for Ansible playbook files
    - ``config.json``      – minimal configuration (playbooks_dir, hosts_file)
    - ``hosts``            – minimal Ansible inventory file
    - ``history.json``     – empty history list
    """
    base = tempfile.mkdtemp(prefix="ansiblepower_test_")

    playbooks_dir = os.path.join(base, "playbooks")
    os.makedirs(playbooks_dir)

    hosts_file = os.path.join(base, "hosts")
    config_file = os.path.join(base, "config.json")
    history_file = os.path.join(base, "history.json")

    with open(config_file, "w") as fh:
        json.dump({"playbooks_dir": playbooks_dir, "hosts_file": hosts_file}, fh)

    with open(hosts_file, "w") as fh:
        fh.write("[test]\nlocalhost ansible_connection=local\n")

    with open(history_file, "w") as fh:
        json.dump([], fh)

    # Add a sample playbook so route tests that list playbooks get real content.
    with open(os.path.join(playbooks_dir, "sample.yml"), "w") as fh:
        fh.write("---\n- name: Sample\n  hosts: all\n  tasks:\n    - debug: msg='hello'\n")

    yield {
        "base": base,
        "playbooks_dir": playbooks_dir,
        "config_file": config_file,
        "hosts_file": hosts_file,
        "history_file": history_file,
    }

    shutil.rmtree(base, ignore_errors=True)


# ---------------------------------------------------------------------------
# Module-level constant patching
# ---------------------------------------------------------------------------

@pytest.fixture()
def patched_paths(tmp_data_dir, monkeypatch):
    """
    Patch ``ansiblePower.CONFIG_FILE`` and ``ansiblePower.HISTORY_FILE`` to
    point at the temp directory created by ``tmp_data_dir``.

    Restores original values automatically via monkeypatch when the test ends.
    """
    monkeypatch.setattr(ansiblePower, "CONFIG_FILE", tmp_data_dir["config_file"])
    monkeypatch.setattr(ansiblePower, "HISTORY_FILE", tmp_data_dir["history_file"])
    return tmp_data_dir


# ---------------------------------------------------------------------------
# Flask test client
# ---------------------------------------------------------------------------

@pytest.fixture()
def flask_client(patched_paths):
    """
    Return a Flask test client with CSRF disabled and TESTING mode on.

    Depends on ``patched_paths`` so the app automatically reads config /
    history from the isolated temp directory rather than the real data files.
    """
    ansiblePower.app.config["TESTING"] = True
    ansiblePower.app.config["WTF_CSRF_ENABLED"] = False

    with ansiblePower.app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# Convenience fixtures built on top of the above
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_history(patched_paths):
    """
    Pre-populate the history file with one sample entry and return its path.

    Useful for tests that need at least one history record to exist before
    exercising a route (e.g. clear-history, export-history).
    """
    entry = {
        "action": "run",
        "playbook": "sample.yml",
        "time": "2026-01-01T00:00:00",
        "output": "ok: [localhost]",
    }
    history_file = patched_paths["history_file"]
    with open(history_file, "w") as fh:
        json.dump([entry], fh)
    return history_file


@pytest.fixture()
def mock_config(patched_paths):
    """
    Return the path to the temp config file (already written by tmp_data_dir).

    Tests can read / overwrite this file to simulate different configurations
    without touching the real ``data/config.json``.
    """
    return patched_paths["config_file"]
