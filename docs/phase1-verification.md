# Tasks 01–06 verification

Reviewed on 2026-11-16 against the implementations through `c7ca63f` and the
follow-up fixes in this change. Tests use isolated credentials, configuration,
inventories, databases, and harmless local processes.

| Task | Implementation and regression evidence |
| --- | --- |
| 01 — Authentication | Local administrator setup hashes passwords and refuses replacement. Revocable sessions expire without sliding refresh. Every operational route, including static assets, job status and cancellation, requires an identity. Login, logout and writes enforce CSRF. Only login and minimal liveness are public. See `tests/test_auth.py` and the authenticated HTTP workflow in `tests/test_live_app.py`. |
| 02 — Inventory confinement | Configuration values and reads, writes and launches validate canonical paths inside the dedicated directory. Descriptor-based I/O rejects file/parent symlinks and hard links. Migration preserves the legacy source, handles conflicts and leaves configuration untouched on failure. Internal-file and race regressions are in `tests/test_inventory_security.py`; the snapshot-swap test now asserts a completed successful execution as well as unchanged private data. |
| 03 — Explicit local execution | Missing, empty, malformed and unreadable inventories block launches with a Settings repair action. Neither submission nor worker preflight falls back to localhost. Local mode requires selection, including history re-runs. Real Ansible tests verify that a production inventory cannot implicitly run a localhost task. See `tests/test_inventory_security.py`, `tests/test_jobs.py` and `tests/test_live_app.py`. |
| 04 — Durable worker | HTTP submissions return a persisted job ID and URL with 202. Atomic claims, queue capacity, concurrency limits, target deduplication and idempotency keys are tested. Both browser launch paths retain their keys across lost responses and server errors. A Supervisor/Gunicorn test runs two jobs for more than 120 seconds while recycling HTTP workers and checking responsive health/status. Crash recovery never replays in-flight jobs. See `tests/test_jobs.py`, `tests/test_worker_lifecycle.py` and `tests/test_ui_outcomes.js`. |
| 05 — Process lifecycle | A launch gate persists Linux process identity before execution. Private on-disk logs survive runner failure. Timeout, cancellation and interruption stop the local group with TERM/KILL escalation and remain distinct. Tests cover stubborn descendants, an exited leader, cancellation races, real SIGTERM, stale identities and restart reconciliation. Unconfirmed cleanup cannot produce success. See `tests/test_process_control.py` and `tests/test_jobs.py`. |
| 06 — Real outcomes | Jobs and history persist lifecycle state, exit code, start/end times and duration. APIs, badges, toasts, re-runs and JSON/CSV history use these fields. Real syntax errors, missing executables, mixed host recaps and timeouts cannot appear successful. Legacy history remains Unknown. Failure highlighting precedes successful counters. See `tests/test_jobs.py`, `tests/test_ui_outcomes.py`, `tests/test_ui_outcomes.js` and `tests/test_live_app.py`. |

## Failed CI run

[Run 43895087032](https://github.com/pooyanazad/ansible-power/actions/runs/43895087032)
failed only `test_escalates_for_stubborn_descendant[True]`: a 0.4-second deadline
included startup, coverage instrumentation and a 0.3-second sleep. The process
was still alive at the deadline, so the runner correctly reported `timed_out`.
The aggregate result correctly propagated that failure. Quality, smoke and live
application jobs passed.

The regression now synchronizes parent/child readiness with a pipe, uses a
separate generous deadline for normal parent exit, and directly verifies that
the entire group has stopped. The test still checks timeout and SIGKILL
escalation. Production timeout behavior is unchanged.

## Validation

The full pytest suite passed **267 tests**, including real HTTP and
Supervisor/Gunicorn checks. The coverage gate passed. Local verification used
Python 3.10 and Ansible Core 2.17; the workflow also tests Python 3.12 with the
Ansible version resolved by the supported requirements range. Production browser JavaScript runs in Node regression tests for highlighting,
outcome toasts/badges, re-run targets and retry identities. The formerly failing
case is also repeated ten times with coverage instrumentation.

Stopping a local runner cannot guarantee cancellation of commands or asynchronous
work already started remotely. Check affected hosts after timeout, cancellation,
or interruption. Legacy in-flight jobs without recorded process identity report
that local cleanup could not be verified. These limits also appear in the README
and run page.
