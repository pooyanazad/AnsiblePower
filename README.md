<p align="center">
  <img src="https://github.com/user-attachments/assets/fc6861f4-d1f5-4efb-8827-00e6b91f0c3a" alt="AnsiblePower" width="900">
</p>

<h1 align="center">⚡ AnsiblePower</h1>

<p align="center">
  <strong>A lightweight, self-hosted web UI for running Ansible playbooks.</strong><br>
  No database. No complex setup. Just clone, run, and manage your infrastructure.
</p>

<p align="center">
  <a href="https://github.com/pooyanazad/AnsiblePower/actions"><img src="https://github.com/pooyanazad/AnsiblePower/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/pooyanazad/AnsiblePower/blob/main/LICENSE"><img src="https://img.shields.io/github/license/pooyanazad/AnsiblePower" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/flask-2.3-lightgrey" alt="Flask">
</p>

---

## Why AnsiblePower?

| | AnsiblePower | AWX / Tower | Semaphore |
|---|---|---|---|
| **Setup** | 1 minute | 30+ minutes | 10 minutes |
| **Database** | None (JSON files) | PostgreSQL | MySQL / BoltDB |
| **Dependencies** | Python + Flask | Docker + PostgreSQL + Redis | Go + DB |
| **Footprint** | ~20 MB | ~2 GB | ~100 MB |
| **Cost** | Free & open source | Free / Paid | Free |

If you need a simple, fast way to run playbooks from a browser — without setting up a full platform — AnsiblePower is for you.

---

## Features

- **📋 Playbook Management** — List, view, and execute `.yml`/`.yaml` playbooks from a configurable directory
- **▶️ One-Click Execution** — Run playbooks with a single click and see output instantly
- **📊 Execution History** — Full log of every run with timestamps, export to JSON/CSV, import from backup
- **🖥️ System Monitoring** — CPU and memory usage of your Ansible control node
- **📁 Hosts Editor** — View and edit your Ansible inventory file directly from the browser
- **🌙 Dark Mode** — Toggle between light and dark themes
- **🔒 Security** — CSRF protection, path traversal prevention, input validation
- **⚙️ Configurable** — Set playbooks directory and hosts file path from the UI or environment variables

---

## Quick Start

```bash
# Clone
git clone https://github.com/pooyanazad/AnsiblePower.git
cd AnsiblePower

# Install
pip install -r requirements.txt

# Run
python ansiblePower.py
```

Open [http://localhost:5000](http://localhost:5000) and you're ready to go.

> **Requirements:** Python 3.9+, Ansible installed and accessible via `ansible-playbook`

---

## Screenshots

| Light Mode | Dark Mode |
|---|---|
|<img width="628" height="410" alt="image" src="https://github.com/user-attachments/assets/c4a10c44-0902-4ebf-b94b-d99dc873f1f8" />| <img width="621" height="403" alt="image" src="https://github.com/user-attachments/assets/87743392-00e3-418e-ba07-45e3f642952c" />|

---

## Project Structure

```
AnsiblePower/
├── ansiblePower.py        # Main Flask application
├── templates/             # Jinja2 HTML templates
│   ├── base.html          # Layout with sidebar and navbar
│   ├── index.html         # Playbook listing and execution
│   ├── history.html       # Execution history table
│   ├── settings.html      # Hosts editor, system status, config
│   └── partials/          # Header and sidebar components
├── static/
│   ├── css/styles.css     # Custom styling with dark mode support
│   └── js/main.js         # Frontend logic (run, show, hosts, dark mode)
├── data/                  # Runtime data (config, history, hosts)
├── playbooks/             # Your Ansible playbooks go here
├── logs/                  # Application logs
└── tests/                 # Unit, quality, smoke, and live tests
```

---

## Configuration

AnsiblePower works out of the box. You can customize it through the Settings page or environment variables:

| Environment Variable | Default | Description |
|---|---|---|
| `FLASK_SECRET_KEY` | Auto-generated | Session encryption key |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode |
| `ANSIBLE_PLAYBOOK_BIN` | Auto-detected | Path to `ansible-playbook` binary |

Playbooks directory and hosts file path can be changed from **Settings** in the web UI.

---

## Running Tests

```bash
# All tests
pytest tests/

# Unit tests only
pytest tests/ut_ansiblePower.py -v

# Quality tests (route responses)
pytest tests/qt_ansiblePower.py -v

# Smoke tests
pytest tests/smoke_test.py -v
```

---

## Contributing

Contributions are welcome! Check out [CONTRIBUTING.md](CONTRIBUTING.md) and the [open issues](https://github.com/pooyanazad/AnsiblePower/issues).

---

## License

[MIT](LICENSE) © 2024 Pooyan Azad
