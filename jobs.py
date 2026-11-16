"""Durable playbook queue shared by the web app and the runner."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import utils


class SubmissionConflict(ValueError):
    pass


class QueueFull(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def digest(content):
    return hashlib.sha256(content).hexdigest()


@contextmanager
def connect(database=None):
    database = database or utils.get_history_db_file()
    conn = sqlite3.connect(database, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                target_key TEXT NOT NULL,
                spec TEXT NOT NULL,
                playbook TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'queued',
                output TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS job_submissions (
                submission_key TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                job_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS playbook_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                playbook TEXT NOT NULL,
                output TEXT NOT NULL,
                time TEXT NOT NULL
            );
        """)
        conn.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        for name, kind in (("exit_code", "INTEGER"), ("duration", "REAL"),
                           ("cancel_requested", "INTEGER NOT NULL DEFAULT 0"),
                           ("process_identity", "TEXT"), ("acknowledged_at", "TEXT")):
            if name not in columns:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {kind}")
        conn.execute("DROP INDEX IF EXISTS jobs_active_target")
        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS jobs_unreviewed_target ON jobs(target_key)
            WHERE state IN ('queued', 'running') OR
            (state IN ('uncertain', 'interrupted') AND acknowledged_at IS NULL)""")
        conn.commit()
        utils.ensure_history_schema(conn)
        yield conn
    finally:
        conn.close()


def enqueue(spec, submission_key, capacity=100):
    encoded = json.dumps(spec, sort_keys=True)
    fingerprint = digest(encoded.encode())
    target_key = digest(json.dumps([spec["playbook_path"], spec["execution_mode"],
                                    spec.get("inventory_path")]).encode())
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute("""SELECT jobs.*, job_submissions.fingerprint AS request_fingerprint
            FROM job_submissions JOIN jobs ON jobs.id = job_submissions.job_id
            WHERE submission_key = ?""", (submission_key,)).fetchone()
        if previous:
            if previous["request_fingerprint"] != fingerprint:
                raise SubmissionConflict("This submission key belongs to a different run. Submit again with a new key.")
            return public(previous), False
        active = conn.execute("""SELECT * FROM jobs WHERE target_key = ? AND (state IN ('queued', 'running')
            OR (state IN ('uncertain', 'interrupted') AND acknowledged_at IS NULL))""",
                              (target_key,)).fetchone()
        if active:
            conn.execute("INSERT INTO job_submissions VALUES (?, ?, ?)", (submission_key, fingerprint, active["id"]))
            conn.commit()
            return public(active), False
        count = conn.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued', 'running')").fetchone()[0]
        if count >= capacity:
            raise QueueFull("The run queue is full. Wait for a run to finish before submitting again.")
        job_id = uuid.uuid4().hex
        conn.execute("""INSERT INTO jobs
            (id, fingerprint, target_key, spec, playbook, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
                     (job_id, fingerprint, target_key, encoded, spec["playbook"], now()))
        conn.execute("INSERT INTO job_submissions VALUES (?, ?, ?)", (submission_key, fingerprint, job_id))
        conn.commit()
        return public(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()), True


def public(row, database=None):
    result = {key: row[key] for key in ("id", "playbook", "state", "output", "created_at", "started_at",
                                        "finished_at", "exit_code", "duration", "cancel_requested")}
    if row["state"] == "running":
        result["output"] = read_log(database, row["id"], result["output"])
    result["needs_review"] = row["state"] in {"uncertain", "interrupted"} and row["acknowledged_at"] is None
    return result


def get(job_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return public(row) if row else None


def recent():
    with connect() as conn:
        return [public(row) for row in conn.execute("SELECT * FROM jobs ORDER BY created_at DESC, rowid DESC LIMIT 20")]


def claim(database):
    """Commit running *before* starting a process. Never reclaim running jobs."""
    with connect(database) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM jobs WHERE state = 'queued' ORDER BY rowid LIMIT 1").fetchone()
        if not row:
            return None
        conn.execute("UPDATE jobs SET state = 'running', started_at = ? WHERE id = ?", (now(), row["id"]))
        conn.commit()
        return {"id": row["id"], "spec": json.loads(row["spec"])}


def record_result(conn, row, state, output, exit_code=None):
    """Update one job and its history in the caller's transaction."""
    ended = now()
    duration = ((datetime.fromisoformat(ended) - datetime.fromisoformat(row["started_at"])).total_seconds()
                if row["started_at"] else None)
    conn.execute("""UPDATE jobs SET state = ?, output = ?, exit_code = ?, finished_at = ?, duration = ?
        WHERE id = ?""", (state, output, exit_code, ended, duration, row["id"]))
    conn.execute("""INSERT INTO playbook_runs
        (action, playbook, output, time, state, exit_code, started_at, finished_at, duration, job_id)
        VALUES ('run', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                 (row["playbook"], output, ended, state, exit_code, row["started_at"], ended, duration, row["id"]))


def finish(database, job_id, state, output, exit_code=None):
    """Persist the result and history together, once."""
    with connect(database) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM jobs WHERE id = ? AND state = 'running'", (job_id,)).fetchone()
        if row:
            # A cancellation committed before completion wins this race.
            if row["cancel_requested"] and state in {"succeeded", "failed"}:
                state = "canceled"
                output += "\nCancellation requested before completion. Remote work may still be running."
            record_result(conn, row, state, output, exit_code)
        conn.commit()


def log_path(database, job_id):
    directory = os.path.abspath(database or utils.get_history_db_file()) + ".logs"
    os.makedirs(directory, mode=0o700, exist_ok=True)
    return os.path.join(directory, job_id + ".log")


def read_log(database, job_id, fallback=""):
    try:
        return Path(log_path(database, job_id)).read_bytes().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return fallback


def register_process(database, job_id, owner):
    with connect(database) as conn:
        conn.execute("UPDATE jobs SET process_identity = ? WHERE id = ? AND state = 'running'",
                     (json.dumps(owner), job_id))
        conn.commit()


def recover(database):
    """Reconcile orphan groups under the exclusive runner lock; never replay."""
    import process_control

    with connect(database) as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE state = 'running'").fetchall()
    for row in rows:
        if row["process_identity"]:
            process_control.terminate(json.loads(row["process_identity"]))
        output = read_log(database, row["id"], row["output"])
        cleanup = ("Local process group stopped." if row["process_identity"] else
                   "No process identity was recorded; local cleanup could not be verified.")
        message = f"Run interrupted before its result was recorded. {cleanup} Remote work may still be running. Check the affected hosts before acknowledging this run. It will not be replayed."
        finish(database, row["id"], "interrupted", output + "\n" + message)


def acknowledge(job_id):
    with connect() as conn:
        result = conn.execute("""UPDATE jobs SET acknowledged_at = ? WHERE id = ?
            AND state IN ('uncertain', 'interrupted') AND acknowledged_at IS NULL""", (now(), job_id))
        conn.commit()
        return result.rowcount == 1


def cancel(job_id):
    """Cancel queued jobs atomically or ask the group owner to stop a live run."""
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        if row["state"] not in {"queued", "running", "canceled"}:
            return False
        conn.execute("UPDATE jobs SET cancel_requested = 1 WHERE id = ?", (job_id,))
        if row["state"] == "queued":
            record_result(conn, row, "canceled", "Canceled before a local process was started.")
        conn.commit()
        return public(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def cancellation_requested(database, job_id):
    # The claim has already initialized the schema; polling needs no DDL locks.
    conn = sqlite3.connect(database, timeout=5)
    try:
        return bool(conn.execute("SELECT cancel_requested FROM jobs WHERE id = ?", (job_id,)).fetchone()[0])
    finally:
        conn.close()
