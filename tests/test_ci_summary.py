"""Ensure failed, cancelled and missing test runs cannot produce a green summary."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/summarize_tests.py"
spec = importlib.util.spec_from_file_location("summarize_tests", SCRIPT)
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


@pytest.fixture()
def reports(tmp_path):
    directory = tmp_path / "reports"
    directory.mkdir()
    for key, _, _ in summary.SUITES:
        (directory / f"{key}-results.xml").write_text(
            '<testsuites><testsuite tests="2" failures="0" errors="0" skipped="0" time="0.1"/></testsuites>')
    return directory


def outcomes():
    return {job: {"result": "success"} for _, _, job in summary.SUITES}


def test_complete_passing_run_is_green(reports):
    text, passed = summary.summarize(reports, outcomes())
    assert passed and "✅ All passed" in text
    assert "**8**" in text


@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped", "missing"])
def test_job_result_is_required_even_when_xml_passes(reports, result):
    jobs = outcomes()
    jobs["unit-tests"] = {"result": result}
    text, passed = summary.summarize(reports, jobs)
    assert not passed and "✅ All passed" not in text
    assert result in text


@pytest.mark.parametrize("xml", [None, "not XML", "<testsuites/>",
                                 '<testsuite tests="2" failures="1"/>',
                                 '<testsuite tests="2" errors="1"/>',
                                 '<testsuite tests="0"/>',
                                 '<testsuite tests="2" skipped="2"/>'])
def test_missing_invalid_or_unsuccessful_report_is_red(reports, xml):
    report = reports / "unit-results.xml"
    if xml is None:
        report.unlink()
    else:
        report.write_text(xml)
    text, passed = summary.summarize(reports, outcomes())
    assert not passed and "✅ All passed" not in text


def test_missing_all_reports_matches_setup_failure(tmp_path):
    text, passed = summary.summarize(tmp_path, {})
    assert not passed and text.count("missing report") == 4


def test_failure_in_later_xml_suite_is_not_ignored(reports):
    (reports / "unit-results.xml").write_text(
        '<testsuites><testsuite tests="2" failures="0"/>'
        '<testsuite tests="1" failures="1"/></testsuites>')
    assert not summary.summarize(reports, outcomes())[1]


def test_duplicate_reports_cannot_hide_failures(reports):
    nested = reports / "extra-artifact"
    nested.mkdir()
    (nested / "unit-results.xml").write_text('<testsuite tests="1" failures="1"/>')
    text, passed = summary.summarize(reports, outcomes())
    assert not passed and "duplicate reports" in text


def test_cli_fails_and_writes_summary_for_setup_failure(tmp_path, monkeypatch):
    output = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(output))
    monkeypatch.setenv("TEST_JOB_RESULTS", json.dumps({job: {"result": "failure"} for job in outcomes()}))
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    assert "missing report" in output.read_text()
