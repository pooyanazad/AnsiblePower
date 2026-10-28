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
import fcntl
import stat
import tempfile
import inventory
from io import StringIO

# =============================================================================
# Directory / file constants
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "data/config.json")
DEFAULT_PLAYBOOKS_DIR = os.path.join(BASE_DIR, "playbooks")
HOSTS_FILE = os.path.join(inventory.INVENTORY_DIR, "hosts")
LEGACY_HOSTS_FILE = os.path.join(BASE_DIR, "data", "hosts")
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

def load_config():
    """Load and return the application configuration dictionary."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception as e:
                logger.error("Error loading config: %s", e)
                return {"playbooks_dir": DEFAULT_PLAYBOOKS_DIR}
    return {"playbooks_dir": DEFAULT_PLAYBOOKS_DIR}


def save_config(config):
    """Atomically persist configuration so failed migrations keep the old file."""
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".config-", dir=os.path.dirname(os.path.abspath(CONFIG_FILE)))
        with os.fdopen(fd, "w") as f:
            json.dump(config, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, CONFIG_FILE)
        return True
    except Exception as e:
        logger.error("Error saving config: %s", e)
        return False
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def get_playbooks_dir():
    """Return the configured playbooks directory path."""
    config = load_config()
    return config.get("playbooks_dir", DEFAULT_PLAYBOOKS_DIR)


def get_hosts_file():
    """Revalidate persisted inventory configuration on every use."""
    config = load_config()
    return inventory.validate_path(config.get("hosts_file", HOSTS_FILE), must_exist=False)


def init_inventory():
    """Copy the legacy default inventory without overwriting either copy.

    Keep data/hosts as a backup. Conflicts and unsafe configured paths require
    administrator repair rather than silently choosing a different inventory.
    """
    root = os.path.abspath(inventory.INVENTORY_DIR)
    with inventory.directory_fd(os.path.dirname(root)) as data_dir:
        # Serialize migration across Gunicorn workers without a public lock file.
        fcntl.flock(data_dir, fcntl.LOCK_EX)
        try:
            try:
                os.mkdir(os.path.basename(root), mode=0o700, dir_fd=data_dir)
            except FileExistsError:
                pass
            with inventory.directory_fd(root) as destination_dir:
                config = load_config()
                configured = config.get("hosts_file", LEGACY_HOSTS_FILE)
                if not isinstance(configured, str):
                    raise ValueError("Invalid configured inventory path")
                selected = os.path.abspath(os.path.join(BASE_DIR, configured))
                if selected != os.path.abspath(LEGACY_HOSTS_FILE):
                    # Existing explicit inventories must pass the current policy.
                    inventory.validate_path(configured)
                    return

                content = b"# Ansible hosts file\n[webservers]\n# web1.example.com\n\n[databases]\n"
                if os.path.lexists(LEGACY_HOSTS_FILE):
                    with inventory.directory_fd(os.path.dirname(LEGACY_HOSTS_FILE)) as legacy_dir:
                        fd = os.open(os.path.basename(LEGACY_HOSTS_FILE), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=legacy_dir)
                        try:
                            metadata = os.fstat(fd)
                            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                                raise ValueError("Legacy inventory must be a regular file without hard links")
                            source = os.fdopen(fd, "rb")
                        except BaseException:
                            os.close(fd)
                            raise
                        with source:
                            content = source.read()

                destination = inventory.validate_path(HOSTS_FILE, must_exist=False)
                if os.path.lexists(destination):
                    # Compare bytes without changing line endings or encoding.
                    with inventory.directory_fd(os.path.dirname(destination)) as parent:
                        fd = os.open(os.path.basename(destination), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                        try:
                            inventory.check_regular_file(os.fstat(fd))
                            existing = os.fdopen(fd, "rb")
                        except BaseException:
                            os.close(fd)
                            raise
                    with existing:
                        if existing.read() != content:
                            raise ValueError("Inventory migration conflict; both files were left untouched")
                else:
                    fd = os.open(os.path.basename(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=destination_dir)
                    with os.fdopen(fd, "wb") as target:
                        target.write(content)
                        target.flush()
                        os.fsync(target.fileno())
                config["hosts_file"] = destination
                if not save_config(config):
                    raise OSError("Could not persist migrated inventory configuration")
        finally:
            fcntl.flock(data_dir, fcntl.LOCK_UN)


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
                    with open(HISTORY_FILE, "r") as f:
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
    """Load playbook run history from SQLite as a list of dictionaries.

    Each record includes the ``id`` field so callers (e.g. the delete
    endpoint) can reference individual rows by their stable primary key.
    """
    try:
        init_history_db()

        with get_history_db_connection() as conn:
            rows = conn.execute("""
                SELECT id, action, playbook, output, time
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


def delete_history_record(record_id):
    """Delete a single history record by its primary-key *record_id*.

    Returns ``True`` if exactly one row was deleted, ``False`` otherwise.
    """
    try:
        init_history_db()
        with get_history_db_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM playbook_runs WHERE id = ?", (record_id,)
            )
            return cursor.rowcount == 1
    except Exception as e:
        logger.error("Error deleting history record %s from SQLite: %s", record_id, e)
        return False
