# Operating ansible-power

Set up the web server and runner using the [quick start](../README.md#quick-start).
Both processes need access to the same checkout and the same data directory.

## Docker deployments

Compose starts Gunicorn and the queue consumer under Supervisor. It uses these
bind mounts for persistent data and Ansible access.

| Host path | Container path | Purpose |
| --- | --- | --- |
| `./playbooks/` | `/app/playbooks` | Playbooks available in the web UI |
| `./data/` | `/app/data` | Inventories, settings, credentials, history, and run logs |
| `./logs/` | `/app/logs` | Application logs |
| `~/.ssh/` | `/home/appuser/.ssh` | Read-only SSH files for remote hosts |

For an existing deployment from before the repository rename, run
`docker compose down` with the previous Compose file and project name before
starting the new `ansible-power` service. Reuse the existing bind-mounted
`data/`, `playbooks/`, and `logs/`, and carry over your `.env` settings. Then run
`docker compose up -d --build`. The existing administrator can sign in.

## Configuration

In Docker, set Compose variables in `.env`. On bare metal, export the variables
for both processes as applicable. Use **Settings** to change playbook and
inventory paths, which must be visible from the runner and the web server.

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `FLASK_SECRET_KEY` | Random key stored in `data/auth.db` | Cookie signing key shared by all web workers |
| `SESSION_COOKIE_SECURE` | `false` | Set to `true` when serving over HTTPS |
| `FLASK_DEBUG` | `false` | Flask debug mode for development |
| `ANSIBLE_PLAYBOOK_BIN` | `ansible-playbook` on `PATH` or an auto-detected path | Ansible executable used by the runner |
| `ANSIBLEPOWER_RUN_CONCURRENCY` | `1` | Maximum simultaneous runs, from 1 to 8 |
| `ANSIBLEPOWER_RUN_TIMEOUT` | `300` | Maximum duration per run in seconds |
| `ANSIBLEPOWER_AUTH_DATABASE` | `data/auth.db` | Credentials and session database path for bare-metal web workers and the admin CLI |

Create the administrator locally with `flask --app ansiblePower create-admin`.
The command refuses to replace an existing administrator. The app stores
password and session-token hashes in `data/auth.db`. Sessions expire after 30
minutes, and signing out revokes the server-side session. Writes require CSRF
tokens. `/health` exposes liveness without authentication. Serve deployments over
HTTPS and enable secure cookies.

The app applies a default limit of 60 requests per minute and caps
`POST /run_playbook` at 5 requests per minute. Requests over the limit receive
HTTP `429`.

## Inventories and execution targets

Keep static INI and YAML inventories under `data/inventories/`. The default is
`data/inventories/hosts`. Settings and the runner validate paths on each access.
Symbolic links, hard links, hidden paths, and internal application files are
rejected. The runner creates a private snapshot of the selected inventory for
each run and uses the adjacent `group_vars/` and `host_vars/` directories.

**Configured inventory** requires a readable, valid inventory with at least one
host declared. Select **Local — this control node** to intentionally run on the
control node. History re-runs require choosing a target and confirming it again.

When upgrading from the legacy `data/hosts` location, the app copies it to
`data/inventories/hosts` and preserves the original. If the destination already
has different contents, resolve the conflict and restart. Copy custom inventory
files from outside `data/inventories/` into that directory and select them in
Settings.

## Queue and run status

The web server persists requests to `POST /run_playbook` and returns HTTP `202`
with `job_id`, `url`, and `status_url`. Follow the returned `url` in the browser
or poll `status_url` for the recorded outcome. Open **Recent runs** to return to
a run after navigating away. An exclusive lock allows one queue consumer per
database. The queue holds up to 100 pending or running jobs and returns HTTP
`503` when it reaches capacity.

Send an `Idempotency-Key` header when retrying a launch. Reusing a key with the
same inputs returns the original job, even after completion. Reusing it with
changed inputs returns HTTP `409`. Different keys still share an active job for
the same playbook and execution target. The browser retains pending keys after a
lost response or uncertain server error. The runner rechecks inputs at launch
and blocks jobs when the files have changed or gone missing.

The run page, status API, Recent runs, History, and exports use persisted outcomes.

| Outcome | Meaning |
| --- | --- |
| `succeeded` | Ansible exited with code 0 |
| `failed` | Ansible exited with a nonzero code |
| `launch_error` | The executable could not start |
| `blocked` | The job failed a preflight check |
| `timed_out` | The run exceeded its configured timeout |
| `canceled` | An administrator canceled the run |
| `interrupted` | The runner stopped or crashed while the job was active |
| `uncertain` | Job cleanup or the final outcome could not be verified |
| Unknown | Legacy history lacks a structured outcome |

The status API and history include `exit_code`, `started_at`, `finished_at`,
and `duration` in seconds. Unavailable values are `null`. A queued job canceled
before launch has no start time or duration. An HTTP `200` from the status
endpoint confirms the read succeeded. Use the recorded outcome to determine
whether the playbook succeeded.

## Cancellation and recovery

Click **Cancel run** or send an authenticated `POST /jobs/<job_id>/cancel` with a
CSRF token. Queued jobs are canceled immediately. The runner records cancellation
for active jobs and sends `SIGTERM` to their local process group, followed by
`SIGKILL` after a two-second grace period. A cancellation accepted before a job
completes determines its final outcome. Repeating an accepted cancellation is
safe.

On bare metal, supervise `worker.py` separately from the web server. Give the
runner time to clean up after `SIGTERM` or `SIGINT`. The included Supervisor
configuration allows 310 seconds. Restarting a web worker has no effect on
active playbooks. On runner restart, recorded Linux process identities let the
runner stop surviving local groups and preserve partial output. Older in-flight
jobs without a recorded process identity report that cleanup could not be
verified.

Interrupted jobs and uncertain results require an administrator to check the
affected hosts and acknowledge the result before running the same target again.
Acknowledgment preserves the original outcome, and previously queued jobs remain
available after restart. A forced runner kill postpones local cleanup until
restart.

**Check the affected hosts after a timeout, cancellation, or interruption.**
Remote SSH commands, asynchronous tasks, and processes that leave the local
process group can continue independently.

## Backups and history

Keep `data/` private and on a local filesystem. Back up the application data as a
set, including `auth.db`, `history.db`, `history.db.logs/`, configuration, and
inventories. Save `playbooks/` and your deployment settings separately.

The runner writes private stdout and stderr files in `data/history.db.logs/`.
The run page shows partial output during a run. These files survive restarts and
remain on disk when you delete a history row. Use JSON exports for history that
you want to import back into the app. CSV exports are available for analysis.
