<p align="center">
  <img src="https://github.com/user-attachments/assets/fc6861f4-d1f5-4efb-8827-00e6b91f0c3a" alt="AnsiblePower" width="900">
</p>

<h1 align="center">⚡ AnsiblePower</h1>

<p align="center">
  <strong>A lightweight, self-hosted web UI for running Ansible playbooks.</strong><br>
  No complex setup. Just clone, run, and manage your infrastructure.
</p>

<p align="center">
  <a href="https://github.com/pooyanazad/AnsiblePower/actions"><img src="https://github.com/pooyanazad/AnsiblePower/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/pooyanazad/AnsiblePower/blob/main/LICENSE"><img src="https://img.shields.io/github/license/pooyanazad/AnsiblePower" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/flask-2.3-lightgrey" alt="Flask">
  <img src="https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white" alt="Docker">
</p>

---

## Why AnsiblePower?

| | AnsiblePower | AWX / Tower | Semaphore |
|---|---|---|---|
| **Setup** | 1 minute | 30+ minutes | 10 minutes |
| **Database** | SQLite (auto) | PostgreSQL | MySQL / BoltDB |
| **Dependencies** | Python + Flask | Docker + PostgreSQL + Redis | Go + DB |
| **Footprint** | ~20 MB | ~2 GB | ~100 MB |
| **Cost** | Free & open source | Free / Paid | Free |

If you need a simple, fast way to run playbooks from a browser — without setting up a full platform — AnsiblePower is for you.

---

## Features

- **📋 Playbook Management** — List, view, and execute `.yml`/`.yaml` playbooks from a configurable directory
- **▶️ One-Click Execution** — Run playbooks with a single click; a confirm dialog prevents accidental runs
- **🎨 Color-coded Output** — `ok:` lines are green, `changed:` amber, `fatal:`/`failed:` red, `PLAY RECAP` bold — output is scannable at a glance
- **📊 Color-coded History** — Green rows for successful runs, red for failures, yellow for unreachable hosts
- **🔍 Search & Filter** — Live search on the History page filters by playbook name or output text
- **📊 Execution History** — Full log of every run with timestamps; export to JSON/CSV, import from backup
- **🖥️ System Monitoring** — CPU and memory usage with colored progress bars
- **📁 Hosts Editor** — View and edit your Ansible inventory file directly from the browser
- **🌙 Dark Mode** — Toggle between light and dark themes (stored in `localStorage`, no server round-trip)
- **🔒 Security** — CSRF protection, path traversal prevention, input validation, and hardened HTTP headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`)
- **🚦 Rate Limiting** — 60 req/min default; `/run_playbook` capped at 5 req/min to prevent abuse
- **⚙️ Configurable** — Set playbooks directory and hosts file path from the UI or environment variables
- **⏱️ Timeout protection** — Playbooks that hang are killed after 5 minutes with a friendly message
- **🔔 Toast notifications** — Non-blocking success/error toasts replace browser `alert()` calls
- **⏳ Loading spinner** — Visual feedback while a playbook runs; button disabled to prevent double-clicks
- **🛡️ Confirm dialogs** — Destructive actions (run playbook, clear history) ask for confirmation first
- **📱 Mobile navigation** — Responsive sidebar collapses on small screens
- **🧩 Utils module** — Shared helpers (`utils.py`) keep route logic clean and testable

---

## Quick Start

### 🐳 Docker (recommended)

```bash
git clone https://github.com/pooyanazad/AnsiblePower.git
cd AnsiblePower
cp .env.example .env        # edit .env to set your FLASK_SECRET_KEY
docker compose up -d
```

Open [http://localhost:5000](http://localhost:5000) — done.

<details>
<summary><strong>Volume mounts</strong></summary>

| Host path | Container path | Purpose |
|---|---|---|
| `./playbooks/` | `/app/playbooks` | Your Ansible playbooks |
| `./data/` | `/app/data` | Config, history (SQLite), hosts file |
| `./logs/` | `/app/logs` | Application logs |
| `~/.ssh/` | `/home/appuser/.ssh` (read-only) | SSH keys for remote hosts |

Data persists across `docker compose down && up`.

</details>

### 🐍 Bare metal

```bash
git clone https://github.com/pooyanazad/AnsiblePower.git
cd AnsiblePower
pip install -r requirements.txt
python ansiblePower.py
```

Open [http://localhost:5000](http://localhost:5000) and you're ready to go.

> **Requirements:** Python 3.9+, Ansible installed and accessible via `ansible-playbook`

---

## One-Command Dev Experience (Makefile)

```bash
make run           # Start the Flask dev server (auto-reload)
make test          # Run the full pytest test suite
make lint          # Run flake8 on application source
make docker-build  # Build the Docker image
make docker-up     # Build + start via docker compose (detached)
make docker-down   # Stop and remove containers
make clean         # Remove __pycache__, .pyc, .coverage artefacts
```

Run `make` (no target) for a full help summary.

---

## Screenshots

| Light Mode | Dark Mode |
|---|---|
|<img width="628" height="410" alt="image" src="https://github.com/user-attachments/assets/c4a10c44-0902-4ebf-b94b-d99dc873f1f8" />| <img width="621" height="403" alt="image" src="https://github.com/user-attachments/assets/87743392-00e3-418e-ba07-45e3f642952c" />|

---

## Project Structure

```
AnsiblePower/
├── ansiblePower.py        # Main Flask application (routes, blueprints)
├── utils.py               # Shared helpers: config, history, logging
├── Makefile               # Developer convenience targets
├── Dockerfile             # Multi-stage Docker build
├── docker-compose.yml     # One-command deployment
├── .env.example           # Environment variable template
├── requirements.txt       # Python runtime dependencies
├── requirements-dev.txt   # Dev/test extras (pytest, flake8, …)
├── templates/             # Jinja2 HTML templates
│   ├── base.html          # Layout with sidebar, navbar, dark-mode toggle
│   ├── index.html         # Playbook listing and execution
│   ├── history.html       # Color-coded execution history table + search
│   ├── settings.html      # Hosts editor, system status, config
│   ├── errors/            # Custom 400 / 404 / 500 error pages
│   └── partials/          # Header and sidebar components
├── static/
│   ├── css/styles.css     # Custom styling + dark mode + output colors
│   └── js/main.js         # Frontend logic (run, colorize, search, dark mode)
├── data/                  # Runtime data (config.json, history.db, hosts)
├── playbooks/             # Your Ansible playbooks go here
├── logs/                  # Application logs (rotating, 1 MB × 3)
└── tests/                 # Unit and integration tests
```

---

## Color-coded Output

Playbook output is automatically highlighted after each run:

| Pattern | Color | Meaning |
|---|---|---|
| `ok:` / `ok=N` | 🟢 Green | Task succeeded, no change |
| `changed:` / `changed=N` | 🟡 Amber | Task ran and changed state |
| `fatal:` / `failed:` / `failed=N>0` | 🔴 Red | Task failed |
| `PLAY RECAP` | **Bold** | Summary section |
| `PLAY [name]` | **Bold** | Play header |
| `TASK [name]` | *Italic* | Task header |

History table rows are also color-coded:
- 🟢 **Green tint** — all tasks succeeded (`ok=N`, no failures)
- 🔴 **Red tint** — one or more tasks failed
- 🟡 **Yellow tint** — hosts were unreachable

---

## Rate Limiting

To prevent abuse and accidental DoS on the control node:

| Endpoint | Limit |
|---|---|
| All routes (default) | 60 requests / minute |
| `POST /run_playbook` | 5 requests / minute |

When a limit is exceeded the server responds with HTTP `429` and a JSON error: `{"error": "Too many requests. Please try again later."}`.

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
pytest tests/ -v

# With coverage report
pytest tests/ --cov=ansiblePower --cov=utils --cov-report=term-missing

# Or via make
make test
```

---

## Contributing

Contributions are welcome! Check out [CONTRIBUTING.md](CONTRIBUTING.md) and the [open issues](https://github.com/pooyanazad/AnsiblePower/issues).

---

## License

[MIT](LICENSE) © 2024 Pooyan Azad
