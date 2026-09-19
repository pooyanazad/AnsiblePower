#!/usr/bin/env python3
"""AnsiblePower utility helpers — shared constants and I/O functions.

Extracted from ``ansiblePower.py`` to keep the main module focused on
Flask routes and application wiring.
"""
import csv
import json
import logging
import logging.handlers
import os
import shutil
import sqlite3
from io import StringIO

from filelock import FileLock

# =============================================================================
# Directory / file constants
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "data/config.json")
DEFAULT_PLAYBOOKS_DIR = os.path.join(BASE_DIR, "playbooks")
HOSTS_FILE = os.path.join(BASE_DIR, "data/hosts")
HISTORY_FILE = os.path.join(BASE_DIR, "data/history.json")
MAX_IMPORT_HISTORY_RECORDS = 10_000

# =============================================================================
# Logger (shared across the package)
# =============================================================================
logger = logging.getLogger("ansiblePower")
logger.setLevel(logging.INFO)

_log_file = os.path.join(BASE_DIR, "logs/app.log")
_log_dir = os.path.dirname(_log_file)
if not os.path.exists(_log_dir):
    os.makedirs(_log_dir)

_log_handler = logging.handlers.RotatingFileHandler(
    _log_file, maxBytes=1_048_576, backupCount=3
)
_log_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
)
logger.addHandler(_log_handler)


# =============================================================================
# Config helpers
# =============================================================================

def _config_lock():
    """Return a process-safe lock for the config file."""
    config_dir = os.path.dirname(CONFIG_FILE)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    return FileLock(f"{CONFIG_FILE}.lock")


def load_config():
    """Load and return the application configuration dictionary."""
    lock = _config_lock()
    with lock:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Error loading config: %s", e)
                return {"playbooks_dir": DEFAULT_PLAYBOOKS_DIR}
        return {"playbooks_dir": DEFAULT_PLAYBOOKS_DIR}


def save_config(config):
    """Persist *config* dictionary to disk using a lock and atomic replace."""
    lock = _config_lock()
    with lock:
        config_dir = os.path.dirname(CONFIG_FILE)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        tmp_path = f"{CONFIG_FILE}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, CONFIG_FILE)
        except Exception as e:
            logger.error("Error saving config: %s", e)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


def get_playbooks_dir():
    """Return the configured playbooks directory path."""
    config = load_config()
    return config.get("playbooks_dir", DEFAULT_PLAYBOOKS_DIR)


def get_hosts_file():
    """Return the configured hosts file path."""
    config = load_config()
    return config.get("hosts_file", HOSTS_FILE)


# =============================================================================
# History helpers (SQLite-backed)
# =============================================================================

def get_history_db_file():
    """Return the SQLite database path for playbook history."""
    return os.path.splitext(HISTORY_FILE)[0] + ".db"


def get_history_db_connection():
    """Create and return a SQLite connection for history storage."""
    history_db_file = get_history_db_file()
    history_dir = os.path.dirname(history_db_file)

    if history_dir and not os.path.exists(history_dir):
        os.makedirs(history_dir)

    conn = sqlite3.connect(history_db_file)
    conn.row_factory = sqlite3.Row
    return conn


def _history_records_to_rows(history):
    """Convert history dicts to SQLite insert rows (4-tuples)."""
    return [
        (
            record.get("action", ""),
            record.get("playbook", ""),
            record.get("output", ""),
            record.get("time", ""),
        )
        for record in history
        if isinstance(record, dict)
    ]


def init_history_db():
    """Initialize SQLite history storage and migrate existing JSON history."""
    try:
        with get_history_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS playbook_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    playbook TEXT NOT NULL,
                    output TEXT NOT NULL,
                    time TEXT NOT NULL
                )
            """)
            row_count = conn.execute(
                "SELECT COUNT(*) FROM playbook_runs"
            ).fetchone()[0]

            if row_count == 0 and os.path.exists(HISTORY_FILE):
                try:
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        history = json.load(f)

                    if isinstance(history, list):
                        conn.executemany("""
                            INSERT INTO playbook_runs
                            (action, playbook, output, time)
                            VALUES (?, ?, ?, ?)
                        """, _history_records_to_rows(history))
                        logger.info("Migrated existing history.json records to SQLite")
                except Exception as e:
                    logger.error("Error migrating history.json to SQLite: %s", e)
    except Exception as e:
        logger.error("Error initializing history database: %s", e)


def load_history():
    """Load playbook run history from SQLite as a list of dictionaries."""
    try:
        init_history_db()

        with get_history_db_connection() as conn:
            rows = conn.execute("""
                SELECT action, playbook, output, time
                FROM playbook_runs
                ORDER BY id ASC
            """).fetchall()

        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("Error loading history from SQLite: %s", e)
        return []


def save_history(history):
    """Replace playbook run history in SQLite with the provided records."""
    try:
        init_history_db()

        with get_history_db_connection() as conn:
            conn.execute("DELETE FROM playbook_runs")
            conn.executemany("""
                INSERT INTO playbook_runs (action, playbook, output, time)
                VALUES (?, ?, ?, ?)
            """, _history_records_to_rows(history))
    except Exception as e:
        logger.error("Error saving history to SQLite: %s", e)


def add_history_record(record):
    """Insert a single playbook run history record into SQLite."""
    try:
        init_history_db()

        with get_history_db_connection() as conn:
            conn.execute("""
                INSERT INTO playbook_runs (action, playbook, output, time)
                VALUES (?, ?, ?, ?)
            """, (
                record.get("action", ""),
                record.get("playbook", ""),
                record.get("output", ""),
                record.get("time", ""),
            ))
    except Exception as e:
        logger.error("Error adding history record to SQLite: %s", e)