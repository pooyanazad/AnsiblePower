#!/usr/bin/env python3
# Blueprint for the Flask application
# This file contains the Flask application blueprint.
import os
import json
import subprocess
import psutil
import csv
import logging
from io import StringIO
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response

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

logger = logging.getLogger("ansiblePower")
logger.setLevel(logging.INFO)
log_handler = CustomRotatingLogHandler("logs/app.log", max_lines=200)
formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)

# =============================================================================
# Configuration Variables and Helper Functions
# =============================================================================
CONFIG_FILE = "data/config.json"
DEFAULT_PLAYBOOKS_DIR = "/home/pooyan/ansible/playbooks"  # Default path
HOSTS_FILE = "/etc/ansible/hosts"                  # Adjust as needed.
HISTORY_FILE = "data/history.json"
app = Flask(__name__)
app.secret_key = "some_random_secret_key"  # Replace with your secret key

# Configuration variables
CONFIG_FILE = "data/config.json"
DEFAULT_PLAYBOOKS_DIR = "/home/pooyan/ansible/playbooks"  # Default path
HOSTS_FILE = "/etc/ansible/hosts"                  # Adjust as needed.
HISTORY_FILE = "data/history.json"

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

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception as e:
                logger.error("Error loading history: %s", e)
                return []
    return []

def save_history(history):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error("Error saving history: %s", e)

# =============================================================================
# Flask App Setup
# =============================================================================


# =============================================================================
# Blueprints
# =============================================================================
from flask import Blueprint

main_bp = Blueprint('main', __name__)
history_bp = Blueprint('history', __name__, url_prefix='/history')
settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

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
    if not os.path.exists(playbook_path):
        logger.error("Playbook does not exist: %s", playbook_path)
        return jsonify({"error": "Playbook does not exist"}), 404

    cmd = ["ansible-playbook", playbook_path]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        output = output.decode("utf-8")
    except subprocess.CalledProcessError as e:
        # Even if the play fails (e.g. unreachable host), record the output.
        output = e.output.decode("utf-8")
    except Exception as e:
        logger.exception("Unexpected error running playbook %s", playbook_name)
        output = "Unexpected error occurred: " + str(e)
    if not output.strip():
        output = "No output produced."
    timestamp = subprocess.check_output(["date"]).decode("utf-8").strip()
    history = load_history()
    history.append({
        "action": "run",
        "playbook": playbook_name,
        "output": output,
        "time": timestamp
    })
    save_history(history)
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
    
@app.route("/settings")
def settings():
    dark_mode = session.get("dark_mode", False)
    config = load_config()
    playbooks_dir = config.get("playbooks_dir", DEFAULT_PLAYBOOKS_DIR)
    return render_template("settings.html", dark_mode=dark_mode, playbooks_dir=playbooks_dir)

@settings_bp.route("/update_playbooks_dir", methods=["POST"])
def update_playbooks_dir():
    new_dir = request.form.get("playbooks_dir", "").strip()
    if not new_dir:
        return jsonify({"error": "Directory path cannot be empty"}), 400
    
    config = load_config()
    config["playbooks_dir"] = new_dir
    save_config(config)
    logger.info("Updated playbooks directory to: %s", new_dir)
    return jsonify({"status": "ok", "message": "Playbooks directory updated successfully"})

@settings_bp.route("/get_hosts", methods=["GET"])
def get_hosts():
    try:
        if not os.access(HOSTS_FILE, os.R_OK):
            logger.error("Read permission denied for hosts file: %s", HOSTS_FILE)
            return jsonify({"error": "Add read permission to user to file"}), 403
        if os.path.exists(HOSTS_FILE):
            with open(HOSTS_FILE, "r") as f:
                content = f.read()
            logger.info("Hosts file read successfully")
            return jsonify({"content": content})
        else:
            logger.error("Hosts file not found: %s", HOSTS_FILE)
            return jsonify({"error": "Hosts file not found"}), 404
    except Exception as e:
        logger.exception("Error getting hosts file")
        return jsonify({"error": "Unexpected error occurred"}), 500

@settings_bp.route("/save_hosts", methods=["POST"])
def save_hosts():
    new_content = request.form.get("content", "")
    try:
        if not os.access(HOSTS_FILE, os.W_OK):
            logger.error("Write permission denied for hosts file: %s", HOSTS_FILE)
            return jsonify({"error": "Please add write permission to host file"}), 403
        with open(HOSTS_FILE, "w") as f:
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
        save_history(data)
        logger.info("History imported from %s", file.filename)
        return jsonify({"status": "ok", "message": "History imported successfully."})
    except Exception as e:
        logger.exception("Error importing history")
        return jsonify({"error": "Error processing file: " + str(e)}), 500

# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    try:
        if not os.path.exists("data"):
            os.makedirs("data")
        if not os.path.exists(HISTORY_FILE):
            save_history([])
        if not os.path.exists(CONFIG_FILE):
            save_config({"playbooks_dir": DEFAULT_PLAYBOOKS_DIR})
        app.run(host="0.0.0.0", port=5000)
 app.register_blueprint(main_bp)
 app.register_blueprint(history_bp)
 # Register blueprints
 app.register_blueprint(main_bp)
 app.register_blueprint(history_bp)
 app.register_blueprint(settings_bp)
    except Exception as e:
        logger.exception("Error starting application")
        raise
