"""Local administrator credentials and revocable, expiring sessions."""
import hashlib
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager

from werkzeug.security import check_password_hash, generate_password_hash


@contextmanager
def database(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # Credentials and the signing key must never be created world-readable.
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            conn.execute("CREATE TABLE IF NOT EXISTS administrator "
                         "(id INTEGER PRIMARY KEY CHECK (id = 1), "
                         "username TEXT NOT NULL, password_hash TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS sessions "
                         "(token_hash TEXT PRIMARY KEY, expires REAL NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS secrets "
                         "(name TEXT PRIMARY KEY, value TEXT NOT NULL)")
            yield conn
    finally:
        conn.close()


def signing_key(path):
    """Share one random signing key across restarts and Gunicorn workers."""
    with database(path) as conn:
        conn.execute("INSERT OR IGNORE INTO secrets VALUES ('session', ?)",
                     (secrets.token_hex(32),))
        return conn.execute("SELECT value FROM secrets WHERE name = 'session'").fetchone()[0]


def create_admin(path, username, password):
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", username):
        raise ValueError("Use 1–64 letters, numbers, dots, underscores or hyphens for the username.")
    if not 12 <= len(password) <= 1024:
        raise ValueError("Use a password between 12 and 1024 characters.")
    password_hash = generate_password_hash(password, method="pbkdf2:sha256:1000000")
    with database(path) as conn:
        try:
            conn.execute("INSERT INTO administrator VALUES (1, ?, ?)", (username, password_hash))
        except sqlite3.IntegrityError:
            raise ValueError("An administrator already exists; setup cannot replace it.") from None


# Keep failed logins comparable in cost, including before administrator setup.
_DUMMY_HASH = generate_password_hash(secrets.token_hex(32), method="pbkdf2:sha256:1000000")


def authenticate(path, username, password):
    with database(path) as conn:
        admin = conn.execute("SELECT username, password_hash FROM administrator WHERE id = 1").fetchone()
    valid_password = check_password_hash(admin["password_hash"] if admin else _DUMMY_HASH, password)
    return bool(admin and secrets.compare_digest(admin["username"].encode(), username.encode())
                and valid_password)


def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(path, lifetime):
    token = secrets.token_urlsafe(32)
    with database(path) as conn:
        conn.execute("DELETE FROM sessions WHERE expires <= ?", (time.time(),))
        conn.execute("INSERT INTO sessions VALUES (?, ?)", (_digest(token), time.time() + lifetime))
    return token


def valid_session(path, token):
    if not isinstance(token, str) or not token:
        return False
    with database(path) as conn:
        row = conn.execute("SELECT expires FROM sessions WHERE token_hash = ?", (_digest(token),)).fetchone()
        return bool(row and row["expires"] > time.time())


def end_session(path, token):
    if isinstance(token, str) and token:
        with database(path) as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_digest(token),))
