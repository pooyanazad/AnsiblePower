import os
import jsonhttps://github.com/pooyanazad/AnsiblePower/blob/main/ansiblePower.py
import subprocess
import psutil
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = "some_random_secret_key" #Replace with your Secret key

PLAYBOOKS_DIR = "/home" #Replace with your playbook directory 
HOSTS_FILE = "/etc/ansible/hosts" #Replace with your inventory location
HISTORY_FILE = "data/history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

@app.route("/")
def homepage():
    dark_mode = session.get("dark_mode", False)
    playbooks = [f for f in os.listdir(PLAYBOOKS_DIR) if f.endswith('.yml') or f.endswith('.yaml')]
    return render_template("index.html", playbooks=playbooks, dark_mode=dark_mode)

@app.route("/run_playbook", methods=["POST"])
def run_playbook():
    playbook_name = request.form.get("playbook")
    if not playbook_name:
        return jsonify({"error": "No playbook specified"}), 400

    playbook_path = os.path.join(PLAYBOOKS_DIR, playbook_name)
    if not os.path.exists(playbook_path):
        return jsonify({"error": "Playbook does not exist"}), 404

    # Run ansible-playbook command
    cmd = ["ansible-playbook", playbook_path]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        output = output.decode('utf-8')
        
        # Save to history
        history = load_history()
        history.append({
            "action": "run",
            "playbook": playbook_name,
            "output": output,
            "time": subprocess.check_output(["date"]).decode('utf-8').strip()
        })
        save_history(history)
        
        return jsonify({"output": output})
    except subprocess.CalledProcessError as e:
        return jsonify({"error": e.output.decode('utf-8')}), 500

@app.route("/show_playbook", methods=["POST"])
def show_playbook():
    playbook_name = request.form.get("playbook")
    if not playbook_name:
        return jsonify({"error": "No playbook specified"}), 400

    playbook_path = os.path.join(PLAYBOOKS_DIR, playbook_name)
    if not os.path.exists(playbook_path):
        return jsonify({"error": "Playbook does not exist"}), 404

    with open(playbook_path, 'r') as f:
        content = f.read()
    return jsonify({"content": content})

@app.route("/history")
def history():
    dark_mode = session.get("dark_mode", False)
    history = load_history()
    return render_template("history.html", history=history, dark_mode=dark_mode)

@app.route("/settings")
def settings():
    dark_mode = session.get("dark_mode", False)
    return render_template("settings.html", dark_mode=dark_mode)

@app.route("/get_hosts", methods=["GET"])
def get_hosts():
    # Check read permission
    if not os.access(HOSTS_FILE, os.R_OK):
        return jsonify({"error": "Add read permission to user to file"}), 403

    if os.path.exists(HOSTS_FILE):
        with open(HOSTS_FILE, 'r') as f:
            content = f.read()
        return jsonify({"content": content})
    return jsonify({"error": "Hosts file not found"}), 404

@app.route("/save_hosts", methods=["POST"])
def save_hosts():
    new_content = request.form.get("content", "")
    # Check write permission
    if not os.access(HOSTS_FILE, os.W_OK):
        return jsonify({"error": "Please add write permission to host file"}), 403

    with open(HOSTS_FILE, 'w') as f:
        f.write(new_content)
    return jsonify({"status": "ok"})

@app.route("/system_status", methods=["GET"])
def system_status():
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    memory_percent = mem.percent
    return jsonify({"cpu": cpu_percent, "memory": memory_percent})

@app.route("/clear_history", methods=["POST"])
def clear_history():
    save_history([])
    return jsonify({"status": "ok"})

@app.route("/toggle_dark_mode", methods=["POST"])
def toggle_dark_mode():
    current = session.get("dark_mode", False)
    session["dark_mode"] = not current
    return jsonify({"dark_mode": session["dark_mode"]})

if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(HISTORY_FILE):
        save_history([])
    app.run(debug=True, host='0.0.0.0', port=5000)
