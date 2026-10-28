#!/usr/bin/env python3
"""Write the CI test summary and fail when a suite did not pass."""
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


SUITES = (
    ("unit", "Unit Tests", "unit-tests"),
    ("quality", "Quality Tests", "quality-tests"),
    ("smoke", "Smoke Tests", "smoke-tests"),
    ("live", "Live App Tests", "live-tests"),
)


def summarize(reports, job_results):
    rows = []
    totals = dict(tests=0, passed=0, failures=0, errors=0, time=0.0)
    all_passed = True
    for key, label, job in SUITES:
        result = job_results.get(job, {}).get("result", "missing")
        files = list(Path(reports).rglob(f"{key}-results.xml"))
        try:
            if len(files) != 1:
                raise ValueError("missing report" if not files else "duplicate reports")
            root = ET.parse(files[0]).getroot()
            suites = list(root.iter("testsuite"))
            if not suites:
                raise ValueError("empty report")
            counts = {name: sum(int(suite.get(name, 0)) for suite in suites)
                      for name in ("tests", "failures", "errors", "skipped")}
            elapsed = sum(float(suite.get("time", 0)) for suite in suites)
            passed = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
            ok = result == "success" and passed > 0 and counts["failures"] + counts["errors"] == 0
            status = "✅" if ok else f"❌ ({result})" if result != "success" else "❌"
            rows.append(f"| {label} | {status} | {counts['tests']} | {passed} | "
                        f"{counts['failures']} | {counts['errors']} | {elapsed:.1f}s |")
            for name in ("tests", "failures", "errors"):
                totals[name] += counts[name]
            totals["passed"] += passed
            totals["time"] += elapsed
            all_passed = all_passed and ok
        except (OSError, ET.ParseError, ValueError) as error:
            rows.append(f"| {label} | ❌ {error} ({result}) | — | — | — | — | — |")
            all_passed = False

    badge = "✅ All passed" if all_passed else "❌ Some suites failed or did not run"
    lines = [f"# Test Results — {badge}", "",
             "| Suite | Result | Total | Passed | Failed | Errors | Time |",
             "|---|:---:|---:|---:|---:|---:|---:|", *rows,
             f"| **Total** | {'✅' if all_passed else '❌'} | **{totals['tests']}** | "
             f"**{totals['passed']}** | **{totals['failures']}** | **{totals['errors']}** | "
             f"**{totals['time']:.1f}s** |", ""]
    return "\n".join(lines), all_passed


def main():
    summary, passed = summarize("reports", json.loads(os.environ["TEST_JOB_RESULTS"]))
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
        output.write(summary)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
