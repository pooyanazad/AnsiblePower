#!/usr/bin/env python3
"""AnsiblePower — Lightweight web interface for managing Ansible playbooks."""
import os
import json
import sqlite3
import shutil
import subprocess
import psutil
import csv
import logging
from datetime import datetime
from io import StringIO
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response, Blueprint
from flask_wtf.csrf import CSRFProtect

# =============================================================================
# Custom Logging Handler: Keeps a maximum of 200 lines with newest messages at the top.
# =============================================================================
class CustomRotatingLogHandler(logging.Handler):
    def __init__(self, filename, max_lines=200):
        super().__init__()
        self.filename = filename
        self.max_lines = max_lines
        log_dir = os.path.dirname(filename)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                f.write("")

    def emit(self, record):
        try:
            msg = self.format(record)
            if os.path.exists(self.filename):
                with open(self.filename, "r") as f:
                    lines = f.readlines()
            else:
                lines = []
            new_lines = [msg + "\n"] + lines
            new_lines = new_lines[:self.max_lines]
            with open(self.filename, "w") as f:
                f.writelines(new_lines)
        except Exception:
            self.handleError(record)

# =============================================================================
# Configuration Variables
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger("ansiblePower")
logger.setLevel(logging.INFO)
log_handler = CustomRotatingLogHandler(os.path.join(BASE_DIR, "logs/app.log"), max_lines=200)
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
CONFIG_FILE = os.path.join(BASE_DIR, "data/config.json")
DEFAULT_PLAYBOOKS_DIR = os.path.join(BASE_DIR, "playbooks")
HOSTS_FILE = os.path.join(BASE_DIR, "data/hosts")
HISTORY_FILE = os.path.join(BASE_DIR, "data/history.json")

# Resolve ansible-playbook: prefer the venv binary, then system PATH, then env override
def _find_ansible_playbook():
    # 1. Respect explicit environment override
    env_override = os.environ.get("ANSIBLE_PLAYBOOK_BIN")
    if env_override:
        return env_override
    # 2. Check venv next to this file (most common dev setup)
    venv_bin = os.path.join(BASE_DIR, "venv", "bin", "ansible-playbook")
    if os.path.isfile(venv_bin):
        return venv_bin
    # 3. Fall back to whatever is on PATH
    system_bin = shutil.which("ansible-playbook")
    if system_bin:
        return system_bin
    return "ansible-playbook"  # will raise a clear error at runtime

ANSIBLE_PLAYBOOK = _find_ansible_playbook()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

csrf = CSRFProtect(app)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception as e:
                logger.error("Error loading config: %s", e)
                return {"playbooks_dir": DEFAULT_PLAYBOOKS_DIR}
    return {"playbooks_dir": DEFAULT_PLAYBOOKS_DIR}

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error("Error saving config: %s", e)

def get_playbooks_dir():
    config = load_config()
    return config.get("playbooks_dir", DEFAULT_PLAYBOOKS_DIR)

def get_hosts_file():
    config = load_config()
    return config.get("hosts_file", HOSTS_FILE)

def get_history_db_file():
    """Return the SQLite database path for playbook history."""
    return os.path.splitext(HISTORY_FILE)[0] + ".db"


def get_history_db_connection():
    """Create a SQLite connection for history storage."""
    history_db_file = get_history_db_file()
    history_dir = os.path.dirname(history_db_file)

    if history_dir and not os.path.exists(history_dir):
        os.makedirs(history_dir)

    conn = sqlite3.connect(history_db_file)
    conn.row_factory = sqlite3.Row
    return conn


def _history_records_to_rows(history):
    """Convert history dictionaries to SQLite insert rows."""
    return [
        (
            record.get("action", ""),
            record.get("playbook", ""),
            record.get("output", ""),
            record.get("time", "")
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
                record.get("time", "")
            ))
    except Exception as e:
        logger.error("Error adding history record to SQLite: %s", e)

# =============================================================================
# Flask App Setup
# =============================================================================


# =============================================================================
# Blueprints
# =============================================================================

main_bp = Blueprint('main', __name__)
history_bp = Blueprint('history', __name__, url_prefix='/history')
settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@main_bp.route("/health")
def health():
    return jsonify({"status": "ok"})

@main_bp.route("/")
def homepage():
    dark_mode = session.get("dark_mode", False)
    playbooks_dir = get_playbooks_dir()
    error = None
    prompt_for_dir = False

    if not os.path.exists(playbooks_dir):
        prompt_for_dir = True
        playbooks = []
    elif not (os.access(playbooks_dir, os.R_OK) and os.access(playbooks_dir, os.W_OK)):
        error = (f"Insufficient permissions for the playbooks directory '{playbooks_dir}'. "
                 "Ensure the directory is readable and writable by the current user.")
        playbooks = []
    else:
        try:
            playbooks = [f for f in os.listdir(playbooks_dir)
                         if f.endswith('.yml') or f.endswith('.yaml')]
        except Exception as e:
            logger.exception("Error listing playbooks: %s", e)
            playbooks = []
            error = "An error occurred while accessing the playbooks directory."
    
    return render_template("index.html", playbooks=playbooks, dark_mode=dark_mode, 
                          error=error, prompt_for_dir=prompt_for_dir, playbooks_dir=playbooks_dir)

@main_bp.route("/run_playbook", methods=["POST"])
def run_playbook():
    playbook_name = request.form.get("playbook")
    if not playbook_name:
        logger.error("No playbook specified in run_playbook")
        return jsonify({"error": "No playbook specified"}), 400

    playbooks_dir = get_playbooks_dir()
    playbook_path = os.path.join(playbooks_dir, playbook_name)

    # Path traversal protection: ensure resolved path is inside playbooks_dir
    real_playbook = os.path.realpath(playbook_path)
    real_dir = os.path.realpath(playbooks_dir)
    try:
        if os.path.commonpath([real_playbook, real_dir]) != real_dir:
            raise ValueError("outside")
    except ValueError:
        logger.error("Path traversal attempt blocked: %s", playbook_name)
        return jsonify({"error": "Invalid playbook path"}), 400

    # Prevent directories from being passed as playbook names
    if os.path.isdir(real_playbook):
        logger.error("Directory passed as playbook name: %s", playbook_name)
        return jsonify({"error": "Invalid playbook path"}), 400

    if not os.path.exists(playbook_path):
        logger.error("Playbook does not exist: %s", playbook_path)
        return jsonify({"error": "Playbook does not exist"}), 404

    cmd = [ANSIBLE_PLAYBOOK, playbook_path]

    # Pass the inventory/hosts file if configured
    hosts_file = get_hosts_file()
    if os.path.exists(hosts_file):
        cmd += ["-i", hosts_file]
    else:
        # No hosts file — fall back to localhost for convenience
        cmd += ["-i", "localhost,", "--connection=local"]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=300)
        output = output.decode("utf-8")
    except subprocess.CalledProcessError as e:
        # Even if the play fails (e.g. unreachable host), record the output.
        output = e.output.decode("utf-8")
    except subprocess.TimeoutExpired:
        logger.warning("Playbook %s timed out after 300 seconds", playbook_name)
        output = "⏱ Playbook timed out after 5 minutes (300 s). The process was killed.\nCheck your inventory and connection settings, or increase the timeout."
    except Exception as e:
        logger.exception("Unexpected error running playbook %s", playbook_name)
        output = "Unexpected error occurred: " + str(e)
    if not output.strip():
        output = "No output produced."
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_history_record({
        "action": "run",
        "playbook": playbook_name,
        "output": output,
        "time": timestamp
    })
    logger.info("Recorded playbook run: %s", playbook_name)
    return jsonify({"output": output})

@main_bp.route("/show_playbook", methods=["POST"])
def show_playbook():
    playbook_name = request.form.get("playbook")
    if not playbook_name:
        logger.error("No playbook specified in show_playbook")
        return jsonify({"error": "No playbook specified"}), 400

    playbooks_dir = get_playbooks_dir()
    playbook_path = os.path.join(playbooks_dir, playbook_name)

    # Path traversal protection: ensure resolved path is inside playbooks_dir
    real_playbook = os.path.realpath(playbook_path)
    real_dir = os.path.realpath(playbooks_dir)
    try:
        if os.path.commonpath([real_playbook, real_dir]) != real_dir:
            raise ValueError("outside")
    except ValueError:
        logger.error("Path traversal attempt blocked: %s", playbook_name)
        return jsonify({"error": "Invalid playbook path"}), 400

    # Prevent directories from being passed as playbook names
    if os.path.isdir(real_playbook):
        logger.error("Directory passed as playbook name: %s", playbook_name)
        return jsonify({"error": "Invalid playbook path"}), 400

    if not os.path.exists(playbook_path):
        logger.error("Playbook does not exist: %s", playbook_path)
        return jsonify({"error": "Playbook does not exist"}), 404

    try:
        with open(playbook_path, "r") as f:
            content = f.read()
        logger.info("Displayed playbook: %s", playbook_name)
        return jsonify({"content": content})
    except Exception as e:
        logger.exception("Error reading playbook %s", playbook_name)
        return jsonify({"error": "Error reading playbook"}), 500

@history_bp.route("/")
def history():
    dark_mode = session.get("dark_mode", False)
    history_data = load_history()
    return render_template("history.html", history=history_data, dark_mode=dark_mode)
    
@settings_bp.route("/")
def settings():
    dark_mode = session.get("dark_mode", False)
    config = load_config()
    playbooks_dir = config.get("playbooks_dir", DEFAULT_PLAYBOOKS_DIR)
    hosts_file = config.get("hosts_file", HOSTS_FILE)
    return render_template("settings.html", dark_mode=dark_mode, playbooks_dir=playbooks_dir, hosts_file=hosts_file)

@settings_bp.route("/update_playbooks_dir", methods=["POST"])
def update_playbooks_dir():
    new_dir = request.form.get("playbooks_dir", "").strip()
    if not new_dir:
        return jsonify({"error": "Directory path cannot be empty"}), 400

    # Security: restrict playbooks directory to paths inside BASE_DIR only.
    # Allowing arbitrary paths (e.g. "/") would bypass the commonpath check in
    # show_playbook and run_playbook, enabling arbitrary file read/execution.
    real_new_dir = os.path.realpath(new_dir)
    real_base = os.path.realpath(BASE_DIR)
    try:
        if os.path.commonpath([real_new_dir, real_base]) != real_base:
            raise ValueError("outside BASE_DIR")
    except ValueError:
        logger.warning("Rejected unsafe playbooks_dir path: %s", new_dir)
        return jsonify({"error": "Playbooks directory must be inside the application directory"}), 400

    config = load_config()
    config["playbooks_dir"] = new_dir
    save_config(config)
    logger.info("Updated playbooks directory to: %s", new_dir)
    return jsonify({"status": "ok", "message": "Playbooks directory updated successfully"})

@settings_bp.route("/update_hosts_file", methods=["POST"])
def update_hosts_file():
    new_hosts_file = request.form.get("hosts_file", "").strip()
    if not new_hosts_file:
        return jsonify({"error": "Hosts file path cannot be empty"}), 400

    # Security: restrict hosts file to paths inside BASE_DIR/data only.
    # Allowing arbitrary absolute paths enables arbitrary file read/write (e.g. ~/.ssh/id_rsa)
    real_new_hosts = os.path.realpath(new_hosts_file)
    safe_data_dir = os.path.realpath(os.path.join(BASE_DIR, "data"))
    try:
        if os.path.commonpath([real_new_hosts, safe_data_dir]) != safe_data_dir:
            raise ValueError("outside safe dir")
    except ValueError:
        logger.warning("Rejected unsafe hosts_file path: %s", new_hosts_file)
        return jsonify({"error": "Hosts file must be inside the application data directory"}), 400
    
    config = load_config()
    config["hosts_file"] = new_hosts_file
    save_config(config)
    logger.info("Updated hosts file path to: %s", new_hosts_file)
    return jsonify({"status": "ok", "message": "Hosts file path updated successfully"})

@settings_bp.route("/get_hosts", methods=["GET"])
def get_hosts():
    try:
        hosts_file = get_hosts_file()
        if not os.path.exists(hosts_file):
            logger.error("Hosts file not found: %s", hosts_file)
            return jsonify({"error": "Hosts file not found"}), 404
        if not os.access(hosts_file, os.R_OK):
            logger.error("Read permission denied for hosts file: %s", hosts_file)
            return jsonify({"error": "Add read permission to user to file"}), 403
        with open(hosts_file, "r") as f:
            content = f.read()
        logger.info("Hosts file read successfully")
        return jsonify({"content": content})
    except Exception as e:
        logger.exception("Error getting hosts file")
        return jsonify({"error": "Unexpected error occurred"}), 500

@settings_bp.route("/save_hosts", methods=["POST"])
def save_hosts():
    new_content = request.form.get("content", "")
    try:
        hosts_file = get_hosts_file()
        if not os.path.exists(hosts_file):
            logger.error("Hosts file not found: %s", hosts_file)
            return jsonify({"error": "Hosts file not found. Please check the path in settings."}), 404
        if not os.access(hosts_file, os.W_OK):
            logger.error("Write permission denied for hosts file: %s", hosts_file)
            return jsonify({"error": "Please add write permission to host file"}), 403
        with open(hosts_file, "w") as f:
            f.write(new_content)
        logger.info("Hosts file saved successfully")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.exception("Error saving hosts file")
        return jsonify({"error": "Error saving hosts file"}), 500

@settings_bp.route("/system_status", methods=["GET"])
def system_status():
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        memory_percent = mem.percent
        logger.info("System status: CPU %s%%, Memory %s%%", cpu_percent, memory_percent)
        return jsonify({"cpu": cpu_percent, "memory": memory_percent})
    except Exception as e:
        logger.exception("Error fetching system status")
        return jsonify({"error": "Error fetching system status"}), 500

@settings_bp.route("/clear_history", methods=["POST"])
def clear_history():
    try:
        save_history([])
        logger.info("History cleared")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.exception("Error clearing history")
        return jsonify({"error": "Error clearing history"}), 500

@settings_bp.route("/toggle_dark_mode", methods=["POST"])
def toggle_dark_mode():
    try:
        current = session.get("dark_mode", False)
        session["dark_mode"] = not current
        logger.info("Dark mode toggled to %s", session["dark_mode"])
        return jsonify({"dark_mode": session["dark_mode"]})
    except Exception as e:
        logger.exception("Error toggling dark mode")
        return jsonify({"error": "Error toggling dark mode"}), 500

# ---------------------------------------------------------------------------
# History Export and Import Endpoints (accessed from the History page)
# ---------------------------------------------------------------------------
@history_bp.route("/export_history")
def export_history():
    export_format = request.args.get("format", "json")
    history_data = load_history()
    if export_format == "csv":
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(["time", "playbook", "action", "output"])
        for record in history_data:
            cw.writerow([
                record.get("time", ""),
                record.get("playbook", ""),
                record.get("action", ""),
                record.get("output", "")
            ])
        output = si.getvalue()
        return Response(output, mimetype="text/csv",
                        headers={"Content-Disposition": "attachment;filename=history.csv"})
    else:
        return Response(json.dumps(history_data, indent=2), mimetype="application/json",
                        headers={"Content-Disposition": "attachment;filename=history.json"})

@history_bp.route("/import_history", methods=["POST"])
def import_history():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty file name"}), 400
    try:
        if file.filename.endswith(".json"):
            data = json.load(file)
        elif file.filename.endswith(".csv"):
            data = []
            stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            for row in csv_input:
                data.append(row)
        else:
            return jsonify({"error": "Unsupported file type. Only .json and .csv allowed."}), 400

        # Validate imported data structure
        if not isinstance(data, list):
            return jsonify({"error": "Invalid data format: expected a list of records."}), 400
        valid_keys = {"action", "playbook", "output", "time"}
        for record in data:
            if not isinstance(record, dict):
                return jsonify({"error": "Invalid record format: each entry must be a dictionary."}), 400
            # Sanitize: only keep known keys
            for key in list(record.keys()):
                if key not in valid_keys:
                    del record[key]

        save_history(data)
        logger.info("History imported from %s", file.filename)
        return jsonify({"status": "ok", "message": "History imported successfully."})
    except Exception as e:
        logger.exception("Error importing history")
        return jsonify({"error": "Error processing file: " + str(e)}), 500

# Register blueprints (moved outside of main block for testing)
app.register_blueprint(main_bp)
app.register_blueprint(history_bp)
app.register_blueprint(settings_bp)

@app.errorhandler(404)
def not_found_error(error):
    """Render a user-friendly 404 error page."""
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    """Render a user-friendly 500 error page."""
    logger.exception("Unhandled server error: %s", error)
    return render_template("errors/500.html"), 500

# =============================================================================
# Ensure required directories and default files exist.
# Called at module level so it runs under both `python ansiblePower.py` and
# Gunicorn/Docker (which imports the module but never enters __main__).
# =============================================================================
def _ensure_dirs():
    data_dir = os.path.join(BASE_DIR, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    if not os.path.exists(DEFAULT_PLAYBOOKS_DIR):
        os.makedirs(DEFAULT_PLAYBOOKS_DIR)
        sample_playbook = os.path.join(DEFAULT_PLAYBOOKS_DIR, "sample.yml")
        with open(sample_playbook, "w") as f:
            f.write("---\n# Sample Ansible Playbook\n- name: Sample playbook\n  hosts: all\n  tasks:\n    - name: Print hello message\n      debug:\n        msg: \"Hello from AnsiblePower!\"\n")
    init_history_db()
    if not os.path.exists(CONFIG_FILE):
        save_config({"playbooks_dir": DEFAULT_PLAYBOOKS_DIR, "hosts_file": HOSTS_FILE})
    hosts_file_path = get_hosts_file()
    if not os.path.exists(hosts_file_path):
        hosts_dir = os.path.dirname(hosts_file_path)
        if hosts_dir and not os.path.exists(hosts_dir):
            os.makedirs(hosts_dir)
        with open(hosts_file_path, "w") as f:
            f.write("# Ansible hosts file\n# Add your hosts here\n[webservers]\n# web1.example.com\n# web2.example.com\n\n[databases]\n# db1.example.com\n")

_ensure_dirs()

# =============================================================================
# Main — only used for local development (Gunicorn/Docker use the module import)
# =============================================================================
if __name__ == "__main__":
    try:
        debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
        app.run(host="0.0.0.0", port=5000, debug=debug_mode)
    except Exception as e:
        logger.exception("Error starting application")
        raise

