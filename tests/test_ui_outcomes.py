"""Outcome presentation must use stored state, including legacy and mixed recaps."""
import shutil
import subprocess
from pathlib import Path

import pytest

import utils


@pytest.mark.parametrize("state,exit_code", [
    ("failed", 2), ("timed_out", -9), ("launch_error", None),
    ("canceled", -15), ("interrupted", None), ("uncertain", None)
])
def test_history_never_colors_failed_or_stopped_job_as_success(flask_client, state, exit_code):
    output = "PLAY RECAP\nfirst : ok=1 failed=0 unreachable=0\nsecond : ok=1 failed=1 unreachable=0"
    utils.add_history_record({"action": "run", "playbook": "sample.yml", "output": output,
                              "time": "now", "state": state, "exit_code": exit_code})
    html = flask_client.get("/history/").text
    assert f'history-row--{state}' in html
    assert 'history-row--success' not in html
    assert 'badge-success' not in html


def test_legacy_success_looking_history_stays_unknown(flask_client):
    utils.add_history_record({"action": "run", "playbook": "sample.yml", "time": "old",
                              "output": "PLAY RECAP\nnode : ok=8 failed=0 unreachable=0"})
    html = flask_client.get("/history/").text
    assert 'history-row--unknown' in html and 'Unknown' in html
    assert 'badge-success' not in html


def test_browser_outcome_highlighting_and_rerun_behavior():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed to execute browser regression tests")
    subprocess.run([node, str(Path(__file__).with_suffix('.js'))], check=True, timeout=15)
