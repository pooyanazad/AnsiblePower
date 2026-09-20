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
from contextlib import closing
from io import StringIO

from filelock import FileLock, Timeout


# =============================================================================
# Directory / file constants
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "data/config.json")
DEFAULT_PLAYBOOKS_DIR = os.path.join(BASE_DIR, "playbooks")
HOSTS_FILE = os.path.join(BASE_DIR, "data/hosts")
HISTORY_FILE = os.path.join(BASE_DIR, "data/history.json")


# =============================================================================
# Logger
# =============================================================================

logger = logging.getLogger("ansiblePower")
logger.setLevel(logging.INFO)

_log_file = os.path.join(BASE_DIR, "logs/app.log")
_log_dir = os.path.dirname(_log_file)

if not os.path.exists(_log_dir):
    os.makedirs(_log_dir)

_log_handler = logging.handlers.RotatingFileHandler(
    _log_file,
    maxBytes=1_048_576,
    backupCount=3,
)

_log_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
)

if not logger.handlers:
    logger.addHandler(_log_handler)


# =============================================================================
# Config helpers
# =============================================================================

def _config_lock():
    """Return a process-safe lock for the config file."""
    config_dir = os.path.dirname(CONFIG_FILE)

    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)

    return FileLock(f"{CONFIG_FILE}.lock", timeout=5)


def load_config():
    """Load and return the application configuration dictionary."""
    try:
        lock = _config_lock()

        with lock:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as file:
                    return json.load(file)

    except Timeout:
        logger.error("Timed out waiting for config lock")
    except Exception as error:
        logger.error("Error loading config: %s", error)

    return {
        "playbooks_dir": DEFAULT_PLAYBOOKS_DIR,
    }


def save_config(config):
    """Persist config to disk using a lock and atomic replacement."""
    temporary_path = f"{CONFIG_FILE}.tmp"

    try:
        lock = _config_lock()

        with lock:
            with open(temporary_path, "w", encoding="utf-8") as file:
                json.dump(config, file, indent=2)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, CONFIG_FILE)

    except Timeout:
        logger.error("Timed out waiting for config lock")
    except Exception as error:
        logger.error("Error saving config: %s", error)
    finally:
        if os.path.exists(temporary_path):
            try:
                os.unlink(temporary_path)
            except OSError as error:
                logger.error(
                    "Error removing temporary config file: %s",
                    error,
                )


def get_playbooks_dir():
    """Return the configured playbooks directory path."""
    config = load_config()
    return config.get("playbooks_dir", DEFAULT_PLAYBOOKS_DIR)


def get_hosts_file():
    """Return the configured hosts file path."""
    config = load_config()
    return config.get("hosts_file", HOSTS_FILE)


# =============================================================================
# History helpers
# =============================================================================

def get_history_db_file():
    """Return the SQLite database path for playbook history."""
    return os.path.splitext(HISTORY_FILE)[0] + ".db"


def get_history_db_connection():
    """Create and return a SQLite connection for history storage."""
    history_db_file = get_history_db_file()
    history_dir = os.path.dirname(history_db_file)

    if history_dir and not os.path.exists(history_dir):
        os.makedirs(history_dir, exist_ok=True)

    connection = sqlite3.connect(history_db_file)
    connection.row_factory = sqlite3.Row
    return connection


def _history_records_to_rows(history):
    """Convert history dictionaries to SQLite insert rows."""
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
        with closing(get_history_db_connection()) as connection:
            with connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS playbook_runs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT NOT NULL,
                        playbook TEXT NOT NULL,
                        output TEXT NOT NULL,
                        time TEXT NOT NULL
                    )
                """)

                row_count = connection.execute(
                    "SELECT COUNT(*) FROM playbook_runs"
                ).fetchone()[0]

                if row_count == 0 and os.path.exists(HISTORY_FILE):
                    try:
                        with open(
                            HISTORY_FILE,
                            "r",
                            encoding="utf-8",
                        ) as file:
                            history = json.load(file)

                        if isinstance(history, list):
                            connection.executemany("""
                                INSERT INTO playbook_runs
                                (action, playbook, output, time)
                                VALUES (?, ?, ?, ?)
                            """, _history_records_to_rows(history))

                            logger.info(
                                "Migrated existing history.json records "
                                "to SQLite"
                            )

                    except Exception as error:
                        logger.error(
                            "Error migrating history.json to SQLite: %s",
                            error,
                        )

    except Exception as error:
        logger.error(
            "Error initializing history database: %s",
            error,
        )


def load_history():
    """Load playbook run history from SQLite."""
    try:
        init_history_db()

        with closing(get_history_db_connection()) as connection:
            rows = connection.execute("""
                SELECT action, playbook, output, time
                FROM playbook_runs
                ORDER BY id ASC
            """).fetchall()

        return [dict(row) for row in rows]

    except Exception as error:
        logger.error(
            "Error loading history from SQLite: %s",
            error,
        )
        return []


def save_history(history):
    """Replace playbook run history in SQLite."""
    try:
        init_history_db()

        with closing(get_history_db_connection()) as connection:
            with connection:
                connection.execute("DELETE FROM playbook_runs")

                connection.executemany("""
                    INSERT INTO playbook_runs
                    (action, playbook, output, time)
                    VALUES (?, ?, ?, ?)
                """, _history_records_to_rows(history))

    except Exception as error:
        logger.error(
            "Error saving history to SQLite: %s",
            error,
        )


def add_history_record(record):
    """Insert a single playbook run history record into SQLite."""
    try:
        init_history_db()

        with closing(get_history_db_connection()) as connection:
            with connection:
                connection.execute("""
                    INSERT INTO playbook_runs
                    (action, playbook, output, time)
                    VALUES (?, ?, ?, ?)
                """, (
                    record.get("action", ""),
                    record.get("playbook", ""),
                    record.get("output", ""),
                    record.get("time", ""),
                ))

    except Exception as error:
        logger.error(
            "Error adding history record to SQLite: %s",
            error,
        )