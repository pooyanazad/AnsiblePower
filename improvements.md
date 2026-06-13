# AnsiblePower — Daily Improvement Plan

> **How to use:** Pick one task each day, check it off, commit, push. Each day is a different type of work so progress feels fresh. Days are numbered but you can skip or reorder if something is blocked.
>
> **Time:** `[XS]` under 15 min · `[S]` 15–30 min · `[M]` 30–60 min · `[L]` 1–2 hours · `[XL]` 2–4 hours
>
> **Labels:** 🔒 Security · 🧹 Code · 🎨 GUI · 🧪 Test · 🐳 DevOps · 📝 Docs · ✨ Feature · ⚡ Performance

---

## ✅ Already Done

- Hardcoded Flask secret key → dynamic generation
- Path traversal protection in `run_playbook`/`show_playbook`
- CSRF protection on all POST endpoints
- `ansible-playbook` binary resolution for venv/system
- Dark mode toggle moved to header navbar
- FontAwesome icons in sidebar and playbook buttons
- Fixed invisible text in dark mode
- CI actions updated to v4/v5
- README section numbering fixed

---

## 📅 Daily Tasks

### Day 1 — 🐳 Dockerize the app (Part 1: Dockerfile)

**Why first:** Docker is the fastest way to get new users. Right now someone has to install Python, pip, Ansible, and configure everything manually. With Docker they just run `docker compose up` and it works.

**The app is ready for Docker** — gunicorn is in `requirements.txt`, secret key already reads from env var, debug mode already uses `FLASK_DEBUG` env var. Nothing blocks this.

- [x] `[M]` Create `Dockerfile` in project root:

```dockerfile
FROM python:3.12-slim

# Install Ansible and SSH client (needed to run playbooks against remote hosts)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ansible openssh-client sshpass \
    && rm -rf /var/lib/apt/lists/*

# Run as non-root for security
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

# Install Python dependencies (separate layer for Docker cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories and set ownership
RUN mkdir -p data logs playbooks && chown -R appuser:appuser /app

USER appuser
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Use Gunicorn instead of Flask dev server (2 workers, 120s timeout for long playbook runs)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "ansiblePower:app"]
```

- [x] `[S]` Also fix line 446 in [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py#L446) — it uses bare `"data"` instead of `os.path.join(BASE_DIR, "data")`, which breaks when Docker or Gunicorn starts from a different working directory.

---

### Day 2 — 🐳 Dockerize the app (Part 2: Compose + Health endpoint)

- [ ] `[M]` Create `docker-compose.yml`:

```yaml
services:
  ansiblepower:
    build: .
    container_name: ansiblepower
    ports:
      - "5000:5000"
    volumes:
      - ./playbooks:/app/playbooks       # Your playbooks stay on the host
      - ./data:/app/data                 # Config + history persist across restarts
      - ./logs:/app/logs                 # Log files persist
      - ~/.ssh:/home/appuser/.ssh:ro     # SSH keys for Ansible (read-only)
    environment:
      - FLASK_SECRET_KEY=${FLASK_SECRET_KEY:-change-me-in-production}
      - FLASK_DEBUG=false
    restart: unless-stopped
```

- [ ] `[S]` Add `/health` endpoint to `ansiblePower.py` — a simple `@main_bp.route("/health")` returning `jsonify({"status": "ok"})`. Docker healthcheck and load balancers use this.

- [x] `[XS]` Create `.dockerignore` — exclude `venv/`, `__pycache__/`, `.git/`, `.github/`, `tests/`, `*.log`, `.pytest_cache/`, `improvements.md`.

---

### Day 3 — 🐳 Dockerize the app (Part 3: Test it + Docs)

- [ ] `[M]` Build and test the Docker image locally:
  ```bash
  docker compose build
  docker compose up -d
  curl http://localhost:5000/health
  docker compose logs
  docker compose down
  ```
  Fix any issues that come up. Verify playbooks dir works, data persists after restart.

- [ ] `[S]` Add a "Docker" section to [README.md](file:///home/pooyan/project/AnsiblePower/README.md) with 3-line quickstart:
  ```
  git clone ... && cd AnsiblePower
  docker compose up -d
  open http://localhost:5000
  ```

---

### Day 4 — 🎨 Favicon + page titles

Two quick visual wins that make the app feel more professional in browser tabs.

- [ ] `[S]` **Add a favicon** — Create a simple SVG favicon (a lightning bolt ⚡ in an `<svg>` tag inline in `<head>`) and add `<link rel="icon" type="image/svg+xml" href="...">` to [base.html:7](file:///home/pooyan/project/AnsiblePower/templates/base.html#L7). No image file needed — inline SVG works in all modern browsers.

- [ ] `[S]` **Add page-specific `<title>` tags** — In [base.html](file:///home/pooyan/project/AnsiblePower/templates/base.html), change `<title>AnsiblePower</title>` to `<title>{% block title %}AnsiblePower{% endblock %}</title>`. Then in each child template add `{% block title %}Playbooks — AnsiblePower{% endblock %}`, `{% block title %}History — AnsiblePower{% endblock %}`, etc. Users with many tabs can find the right one.

---

### Day 5 — 🔒 Subprocess timeout

**Problem:** If a playbook hangs (unreachable host, infinite loop), the Flask worker thread is blocked forever. With only 2 Gunicorn workers, 2 hung playbooks = entire app frozen.

- [ ] `[M]` In [ansiblePower.py:205](file:///home/pooyan/project/AnsiblePower/ansiblePower.py#L205), add `timeout=300` (5 minutes) to `subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=300)`. Catch `subprocess.TimeoutExpired` and return a clear error message: `"Playbook timed out after 5 minutes"`. Save the timeout to history too so users can see what happened.

---

### Day 6 — 🎨 Replace `alert()` with toast notifications

**Problem:** The app uses ugly browser `alert()` popups for "Hosts saved", "History cleared", errors. This feels like a 2005 web app.

- [ ] `[M]` Create a reusable toast system in [main.js](file:///home/pooyan/project/AnsiblePower/static/js/main.js): Add a `showToast(message, type)` function that creates a small notification in the top-right corner. `type` can be `"success"` (green), `"error"` (red), or `"info"` (blue). Toast should auto-dismiss after 3 seconds with a fade-out animation. Add a fixed-position toast container `<div>` in [base.html](file:///home/pooyan/project/AnsiblePower/templates/base.html). Then replace all 4 `alert()` calls in `main.js` (lines 124, 126, 157, and any in settings.html inline scripts) with `showToast()`.

---

### Day 7 — 🧹 Move misplaced imports + fix module docstring

Two small code cleanup items that make the codebase look more professional.

- [ ] `[S]` In [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py): Move `import shutil` from inside `_find_ansible_playbook()` (line 72) to the top-level import block (after line 8). Move `from flask import Blueprint` from line 134 to the existing Flask import on line 12 (merge it: `from flask import Flask, render_template, ..., Blueprint`). Also replace the misleading comment on lines 2-3 ("Blueprint for the Flask application") with a proper docstring: `"""AnsiblePower - Lightweight web interface for managing Ansible playbooks."""`

---

### Day 8 — 🎨 Loading spinner for playbook execution

**Problem:** When you click "Run", the output area just shows "Running, Please wait..." as plain text. Users don't know if anything is happening.

- [ ] `[M]` In [main.js:19-20](file:///home/pooyan/project/AnsiblePower/static/js/main.js#L19-L20): Replace the plain text with an animated spinner. Use a CSS spinner (keyframe rotation on a border element) inside the output `<pre>` tag. Also disable the "Run" button (`btn.disabled = true`, change text to "Running...") to prevent double-clicks. Re-enable the button when the response arrives. Add the spinner CSS to [styles.css](file:///home/pooyan/project/AnsiblePower/static/css/styles.css).

---

### Day 9 — 🔒 Security response headers

**Problem:** The app sends no security headers. Any page can be embedded in an iframe (clickjacking), and browsers may guess content types wrong (MIME sniffing).

- [ ] `[S]` Add an `@app.after_request` handler in [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py) (before blueprint registration, around line 436) that sets these headers on every response:
  ```python
  @app.after_request
  def set_security_headers(response):
      response.headers['X-Frame-Options'] = 'DENY'
      response.headers['X-Content-Type-Options'] = 'nosniff'
      response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
      return response
  ```
  This is a 5-line change that blocks three attack vectors.

---

### Day 10 — 🧪 Rename test files to pytest conventions

**Problem:** pytest auto-discovers files named `test_*.py`. The current names (`ut_ansiblePower.py`, `qt_ansiblePower.py`, `smoke_test.py`) don't follow this, so you have to specify each file manually.

- [ ] `[S]` Rename: `ut_ansiblePower.py` → `test_unit.py`, `qt_ansiblePower.py` → `test_quality.py`, `smoke_test.py` → `test_smoke.py`. Update the 3 `run` steps in [test.yml](file:///home/pooyan/project/AnsiblePower/.github/workflows/test.yml) to use the new names. Now `pytest tests/` discovers everything automatically.

---

### Day 11 — 🎨 Confirmation before running playbooks

**Problem:** Clicking "Run" immediately executes a playbook. One accidental click can change production servers. Users expect a confirmation step.

- [ ] `[S]` In [main.js:15](file:///home/pooyan/project/AnsiblePower/static/js/main.js#L15), before the `fetch("/run_playbook")` call, add a `confirm("Run '" + playbook + "'? This will execute the playbook against your inventory.")` check. If the user cancels, `return` early. This is a 3-line addition. Later (Day 77) you can upgrade this to a styled modal.

---

### Day 12 — 📝 Fix README

**Problem:** README says `pip install flask psutil` which is outdated, and it references a screenshot of hardcoded variables that no longer exist.

- [ ] `[S]` In [README.md](file:///home/pooyan/project/AnsiblePower/README.md): Remove the `pip install flask psutil` line (line 43-44). The Installation section already has `pip install -r requirements.txt` — that's all you need. Remove or update the screenshot reference on line 48 since those variables are now configurable via the Settings page. Add a "Docker" option to the Quick Start pointing to `docker compose up -d`.

---

### Day 13 — 🧹 Replace custom log handler with stdlib

**Problem:** `CustomRotatingLogHandler` reads the **entire log file**, prepends one line, and rewrites the whole file on every single log message. With 200 lines of log, that's 200 file reads + writes per request. It also has a race condition — two concurrent requests can corrupt the file.

- [ ] `[L]` In [ansiblePower.py:18-50](file:///home/pooyan/project/AnsiblePower/ansiblePower.py#L18-L50): Delete the `CustomRotatingLogHandler` class entirely. Replace with:
  ```python
  from logging.handlers import RotatingFileHandler
  
  logger = logging.getLogger("ansiblePower")
  logger.setLevel(logging.INFO)
  os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
  log_handler = RotatingFileHandler(
      os.path.join(BASE_DIR, "logs/app.log"),
      maxBytes=1_048_576,   # 1 MB per file
      backupCount=5          # Keep 5 rotated files
  )
  log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
  logger.addHandler(log_handler)
  ```
  Note: `BASE_DIR` is defined on line 55 — you'll need to move the logger setup after it, or define `BASE_DIR` earlier.

---

### Day 14 — 🎨 Copy output to clipboard

**Problem:** Users often need to share playbook output with teammates. Currently they have to manually select all text in the `<pre>` block.

- [ ] `[S]` Add a "📋 Copy" button next to each playbook output in [index.html:63](file:///home/pooyan/project/AnsiblePower/templates/index.html#L63). In [main.js](file:///home/pooyan/project/AnsiblePower/static/js/main.js), when clicked, use `navigator.clipboard.writeText(outputEl.textContent)` and show a toast "Copied to clipboard". Change the button text to "✓ Copied" for 2 seconds, then revert.

---

### Day 15 — 🔒 Validate playbooks directory path

**Problem:** The Settings page lets you set the playbooks directory to literally any path — `/etc/passwd`, `/root`, anything. An attacker (or accidental typo) could point it at sensitive system directories.

- [ ] `[S]` In [ansiblePower.py:280-289](file:///home/pooyan/project/AnsiblePower/ansiblePower.py#L280-L289) (`update_playbooks_dir`): Before saving, check that `os.path.isdir(new_dir)` returns `True`. If not, return `{"error": "Directory does not exist"}` with status 400. Also reject paths that start with `/etc`, `/proc`, `/sys`, `/dev`. Log the rejected attempt.

---

### Day 16 — 🎨 Dark mode → localStorage

**Problem:** Dark mode is stored in Flask's server-side session. This means: (1) toggling dark mode requires a full page reload, (2) the state is lost when the server restarts, (3) different browsers on the same machine don't share the setting.

- [ ] `[M]` In [main.js:164-177](file:///home/pooyan/project/AnsiblePower/static/js/main.js#L164-L177): Remove the `fetch("/settings/toggle_dark_mode")` call. Instead use `localStorage.setItem("darkMode", "true"/"false")`. On page load (top of DOMContentLoaded), read `localStorage.getItem("darkMode")` and add/remove the `dark` class on `<html>`. Toggle the sun/moon icon with JavaScript instead of reloading. Also check `window.matchMedia('(prefers-color-scheme: dark)')` as the default when no localStorage value exists. The `/settings/toggle_dark_mode` endpoint in Python can stay for backward compatibility but won't be called anymore.

---

### Day 17 — 🧹 Split requirements files

**Problem:** `requirements.txt` mixes runtime packages (Flask, psutil) with test-only packages (pytest, beautifulsoup4). Anyone deploying the app installs test tools they don't need, and the Docker image is bigger than necessary.

- [ ] `[M]` Create two files:
  - `requirements.txt` — runtime only: `Flask==2.3.3`, `psutil==5.9.6`, `gunicorn==21.2.0`, `Flask-WTF==1.2.2`
  - `requirements-dev.txt` — starts with `-r requirements.txt` (includes runtime), then adds: `pytest==7.4.3`, `pytest-cov==4.1.0`, `unittest-xml-reporting==3.2.0`, `requests==2.31.0`, `beautifulsoup4==4.12.2`
  
  Update CI workflow to `pip install -r requirements-dev.txt`. Update Dockerfile to use `requirements.txt` only.

---

### Day 18 — 🎨 Truncate long output in history

**Problem:** The history table shows the full playbook output (can be 100+ lines) in every row. This makes the table unusable — you have to scroll forever.

- [ ] `[S]` In [history.html:24](file:///home/pooyan/project/AnsiblePower/templates/history.html#L24): Wrap the `<pre>` in a `<div>` with `max-height: 80px; overflow: hidden` and a "Show more ▼" button below it. When clicked, remove the `max-height` and change the button to "Show less ▲". Pure CSS + 5 lines of JavaScript. Add the styles to [styles.css](file:///home/pooyan/project/AnsiblePower/static/css/styles.css).

---

### Day 19 — 🔒 Sanitize playbook filenames

**Problem:** The `run_playbook` endpoint accepts any filename via POST form data. Although path traversal is blocked, names like `my file (2).yml` or `$(rm -rf).yml` could cause issues in shell commands or confuse `subprocess`.

- [ ] `[S]` In [ansiblePower.py:168](file:///home/pooyan/project/AnsiblePower/ansiblePower.py#L168), right after getting `playbook_name`, add a regex check: `if not re.match(r'^[a-zA-Z0-9_\-]+\.(yml|yaml)$', playbook_name)`. If it doesn't match, return `{"error": "Invalid playbook name. Use only letters, numbers, dashes, and underscores."}` with 400. Add `import re` to the top of the file.

---

### Day 20 — 🧪 Add shared test fixtures

**Problem:** All 3 test files (`ut_ansiblePower.py`, `qt_ansiblePower.py`, `smoke_test.py`) have nearly identical `setUp()` methods — creating temp dirs, mock config, mock history, patching module constants. This is 30 lines of copy-pasted code.

- [ ] `[M]` Create [tests/conftest.py](file:///home/pooyan/project/AnsiblePower/tests/conftest.py) with a `@pytest.fixture` that creates a temp directory, writes test config/history/hosts files, patches `ansiblePower.CONFIG_FILE` and `ansiblePower.HISTORY_FILE`, creates a Flask test client with CSRF disabled, and cleans up on teardown. Then simplify all 3 test files to use this fixture. Each test file should shrink by ~20 lines.

---

### Day 21 — 🎨 Visual CPU/Memory gauges

**Problem:** System status shows `CPU: 50% | Memory: 60%` as plain text. This looks like a debug log, not a dashboard.

- [ ] `[L]` In [main.js:136-143](file:///home/pooyan/project/AnsiblePower/static/js/main.js#L136-L143): Replace the `textContent` assignment with HTML that creates Bootstrap-style progress bars. Build two `<div class="progress">` elements with `<div class="progress-bar">` inside, setting `width` to the percentage value. Set the bar color based on thresholds: `bg-success` if < 60%, `bg-warning` if 60-80%, `bg-danger` if > 80%. Show the percentage as text inside the bar. Add labels "CPU" and "Memory" above each bar. Styles go in [styles.css](file:///home/pooyan/project/AnsiblePower/static/css/styles.css).

---

### Day 22 — 🧹 Extract duplicate path validation

**Problem:** `run_playbook` (lines 176-189) and `show_playbook` (lines 237-250) have identical 13-line path validation blocks — both do `os.path.realpath`, `os.path.commonpath`, and `os.path.isdir` checks. Fixing a bug means editing two places.

- [ ] `[S]` Create a `_validate_playbook_path(playbook_name, playbooks_dir)` function that returns `(playbook_path, error_response)`. If validation fails, it returns `(None, jsonify({"error": "..."}), status_code)`. Both `run_playbook` and `show_playbook` call it and return early if error. Net result: ~26 lines replaced by ~15 lines + one shared function.

---

### Day 23 — 🎨 Confirm before clearing history

**Problem:** The "Clear History" button immediately deletes all history with no undo. One misclick = all execution records gone.

- [ ] `[S]` In [main.js:149](file:///home/pooyan/project/AnsiblePower/static/js/main.js#L149): Add `if (!confirm("Delete all execution history? This cannot be undone.")) return;` before the fetch call. This is 1 line of code. Also change the button color from `btn-warning` to `btn-danger` in [settings.html:25](file:///home/pooyan/project/AnsiblePower/templates/settings.html#L25) to signal it's a destructive action.

---

### Day 24 — 🎨 Dark mode smooth transition + fix icon toggle

**Problem:** Toggling dark mode causes a jarring instant color change. Also the sun/moon icon requires a page reload to update (it's rendered server-side by Jinja2).

- [ ] `[S]` In [styles.css](file:///home/pooyan/project/AnsiblePower/static/css/styles.css), add to `body`: `transition: background-color 0.3s ease, color 0.3s ease;`. Also add the same transition to `.sidebar`, `.card`, `.list-group-item`, `.form-control`. In [main.js](file:///home/pooyan/project/AnsiblePower/static/js/main.js) dark mode toggle handler: after adding/removing the `dark` class, also swap the button icon (`fa-moon` ↔ `fa-sun`) and text (`Dark Mode` ↔ `Light Mode`) with JavaScript — don't rely on the Jinja template.

---

### Day 25 — 🧪 Add unit tests for `run_playbook`

- [ ] `[M]` In [tests/](file:///home/pooyan/project/AnsiblePower/tests), add tests for the `run_playbook` endpoint:
  1. **Missing playbook name** → expects 400 with `{"error": "No playbook specified"}`
  2. **Nonexistent playbook file** → expects 404 with `{"error": "Playbook does not exist"}`
  3. **Path traversal attempt** (`../../etc/passwd`) → expects 400 with `{"error": "Invalid playbook path"}`
  4. **Valid playbook** (mock `subprocess.check_output` to return fake output) → expects 200, output in response, history entry created
  5. **Subprocess failure** (mock `CalledProcessError`) → expects 200 with error output saved

---

### Day 26 — 🎨 Mobile navigation

**Problem:** On screens smaller than 768px, the sidebar has `d-none d-md-block` which completely hides it. Mobile users cannot navigate to History or Settings at all — there's no hamburger menu.

- [ ] `[M]` In [base.html:17](file:///home/pooyan/project/AnsiblePower/templates/base.html#L17): The navbar toggler button (lines 3-6 in [_header.html](file:///home/pooyan/project/AnsiblePower/templates/partials/_header.html)) already exists but only toggles `#navbarNav` (the dark mode button). Add the sidebar links (Homepage, History, Settings) to the navbar collapse `#navbarNav` section so they appear in the mobile dropdown. Keep the sidebar for desktop. This way mobile users get navigation through the hamburger menu.

---

### Day 27 — 🧹 Custom 404 and 500 error pages

**Problem:** Hitting a wrong URL (like `/settigns/`) shows Flask's ugly default "Not Found" page with a plain white background. It looks broken and doesn't match the app's design.

- [ ] `[M]` Create two new templates: `templates/errors/404.html` and `templates/errors/500.html`, both extending `base.html`. The 404 page should show "Page not found" with a link back to the homepage. The 500 page should show "Something went wrong" with a suggestion to check logs. In [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py), add:
  ```python
  @app.errorhandler(404)
  def not_found(e):
      return render_template("errors/404.html", dark_mode=session.get("dark_mode", False)), 404
  
  @app.errorhandler(500)
  def server_error(e):
      return render_template("errors/500.html", dark_mode=session.get("dark_mode", False)), 500
  ```

---

### Day 28 — 🎨 Search/filter on history page

**Problem:** With 50+ history entries, finding a specific playbook run requires scrolling through the entire table. No way to filter or search.

- [ ] `[M]` In [history.html](file:///home/pooyan/project/AnsiblePower/templates/history.html): Add a `<input type="text" id="history-search" placeholder="Filter by playbook name or date...">` above the table. In JavaScript, on `input` event, loop through all `<tr>` rows in `<tbody>` and hide any row where the `textContent` doesn't include the search term (case-insensitive). This is ~10 lines of JS with no backend changes.

---

### Day 29 — 🔒 Validate hosts file path

**Problem:** Same as Day 15 but for the hosts file setting. The `update_hosts_file` endpoint accepts any path without checking if it exists or is a regular file.

- [ ] `[S]` In [ansiblePower.py:291-301](file:///home/pooyan/project/AnsiblePower/ansiblePower.py#L291-L301): Add `os.path.isfile(new_hosts_file)` check. If it doesn't exist, return `{"error": "File does not exist at this path"}` with 400. Also reject paths containing `..` to prevent traversal. This mirrors what you did on Day 15 for the playbooks directory.

---

### Day 30 — 🎨 Improve sidebar active link

**Problem:** The active sidebar link only gets `font-weight-bold`. It's hard to see which page you're on, especially in dark mode.

- [ ] `[S]` In [styles.css](file:///home/pooyan/project/AnsiblePower/static/css/styles.css): Add styles for `.sidebar a.active`: colored left border (`border-left: 3px solid #007bff`), light blue background tint (`background-color: rgba(0, 123, 255, 0.1)`), and the text color to match (`color: #007bff`). In dark mode: use `#63b3ed` for the border and color, `rgba(99, 179, 237, 0.1)` for the background. The active class is already being set by Jinja in [_sidebar.html](file:///home/pooyan/project/AnsiblePower/templates/partials/_sidebar.html).

---

### Day 31 — 🧪 Add unit tests for `show_playbook`

- [ ] `[M]` In [tests/](file:///home/pooyan/project/AnsiblePower/tests), add tests:
  1. **Valid playbook** → 200, response contains `{"content": "---\n..."}` 
  2. **Missing name** (empty POST body) → 400
  3. **Nonexistent file** → 404
  4. **Path traversal** (`../../etc/passwd`) → 400 with "Invalid playbook path"
  5. **Directory passed as playbook name** → 400

---

### Day 32 — 📝 Expand CONTRIBUTING.md

**Problem:** Current CONTRIBUTING.md is only 5 lines — just a link to GitHub Issues. New contributors have no idea how to set up the dev environment, run tests, or submit PRs.

- [ ] `[M]` Rewrite [CONTRIBUTING.md](file:///home/pooyan/project/AnsiblePower/CONTRIBUTING.md) to include: (1) Development setup (clone, venv, install deps), (2) How to run the app locally, (3) How to run tests (`pytest tests/`), (4) Code style (will add linter later — for now just mention PEP 8), (5) PR checklist (tests pass, no new warnings), (6) Where to find issues to work on.

---

### Day 33 — 🎨 Color-code history rows

**Problem:** All history rows look identical — you can't tell at a glance which runs succeeded and which failed.

- [ ] `[S]` In [history.html](file:///home/pooyan/project/AnsiblePower/templates/history.html): Use Jinja to check if `"failed=0"` appears in `record.output`. If yes, add `class="table-success"` to the `<tr>`. If `"failed="` appears with a non-zero number, add `class="table-danger"`. If the output contains `"unreachable="` with non-zero, add `class="table-warning"`. Default rows (no Ansible recap line) stay uncolored. This uses only template logic — no backend change.

---

### Day 34 — 🔒 Rate-limit the run endpoint

**Problem:** `/run_playbook` triggers `subprocess` shell commands. Without rate limiting, a script or attacker could fire hundreds of playbook runs per second and overwhelm the server or cause damage to managed hosts.

- [ ] `[M]` Install `flask-limiter` (add to `requirements.txt`). In [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py), add:
  ```python
  from flask_limiter import Limiter
  from flask_limiter.util import get_remote_address
  limiter = Limiter(get_remote_address, app=app, default_limits=["60/minute"])
  ```
  Then on the `run_playbook` route, add `@limiter.limit("5/minute")`. This limits playbook runs to 5 per minute per IP while allowing normal page browsing at 60/min.

---

### Day 35 — 🎨 Show playbook metadata

**Problem:** The playbook list only shows filenames. You can't tell when a playbook was last modified or how big it is without opening a terminal.

- [ ] `[S]` In [ansiblePower.py:155-157](file:///home/pooyan/project/AnsiblePower/ansiblePower.py#L155-L157): Instead of just returning filenames, return a list of dicts: `{"name": f, "size": os.path.getsize(path), "modified": os.path.getmtime(path)}`. In [index.html](file:///home/pooyan/project/AnsiblePower/templates/index.html), show the file size (formatted as KB) and last modified date (formatted with Jinja's `datetimeformat` filter or a Python helper) in small gray text below each playbook name.

---

### Day 36 — 🧹 Extract helpers to `utils.py`

**Problem:** `ansiblePower.py` is 474 lines long and mixing route handlers with file I/O helpers. As you add features, this single file will become harder to navigate.

- [ ] `[M]` Create [utils.py](file:///home/pooyan/project/AnsiblePower/utils.py) and move these 6 functions into it: `load_config`, `save_config`, `get_playbooks_dir`, `get_hosts_file`, `load_history`, `save_history`. Also move the constants `BASE_DIR`, `CONFIG_FILE`, `DEFAULT_PLAYBOOKS_DIR`, `HOSTS_FILE`, `HISTORY_FILE`. In `ansiblePower.py`, add `from utils import ...` for everything you moved. Run existing tests to make sure nothing breaks.

---

### Day 37 — 🎨 Empty states for playbooks + history

**Problem:** When there are no playbooks, the page shows nothing. When there's no history, it shows "No history available." in plain text. Both feel broken rather than intentional.

- [ ] `[S]` In [index.html](file:///home/pooyan/project/AnsiblePower/templates/index.html): When `playbooks` is empty (and no error/prompt), show a centered message with a folder icon (`<i class="fas fa-folder-open fa-3x">`) + "No playbooks found" + a link "Configure playbooks directory in Settings →". In [history.html:7](file:///home/pooyan/project/AnsiblePower/templates/history.html#L7): Replace the plain `<p>` with a centered icon (`<i class="fas fa-history fa-3x">`) + "No runs yet" + "Run a playbook from the homepage to see results here."

---

### Day 38 — 🐳 Add Makefile

**Problem:** Developers have to remember exact commands: `python ansiblePower.py`, `pytest tests/`, `docker compose build`, etc. A Makefile gives everyone a consistent interface.

- [ ] `[S]` Create a [Makefile](file:///home/pooyan/project/AnsiblePower/Makefile) with these targets:
  ```makefile
  .PHONY: run test lint docker-build docker-up docker-down clean
  
  run:
  	python ansiblePower.py
  
  test:
  	pytest tests/ -v
  
  lint:
  	ruff check ansiblePower.py
  
  docker-build:
  	docker compose build
  
  docker-up:
  	docker compose up -d
  
  docker-down:
  	docker compose down
  
  clean:
  	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
  	find . -type f -name '*.pyc' -delete 2>/dev/null; true
  ```

---

### Day 39 — 🔒 Limit uploaded file size

**Problem:** The history import endpoint (`/history/import_history`) accepts file uploads with no size limit. An attacker could upload a multi-gigabyte file and crash the server.

- [ ] `[S]` In [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py), right after `app = Flask(__name__)`, add: `app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024` (5 MB limit). Flask will automatically return a 413 "Request Entity Too Large" error for larger uploads. Also add `@app.errorhandler(413)` to return a friendly JSON error: `{"error": "File too large. Maximum size is 5 MB."}`.

---

### Day 40 — 🎨 Color-code playbook run output

**Problem:** Playbook output is plain white/black text. You have to read through walls of text to find what changed, what failed, and what succeeded.

- [ ] `[M]` In [main.js:31-34](file:///home/pooyan/project/AnsiblePower/static/js/main.js#L31-L34): Instead of setting `outputEl.textContent`, parse the output line by line. Wrap each line in a `<span>` with a CSS class based on content:
  - Lines containing `ok:` → class `ansible-ok` (green text)
  - Lines containing `changed:` → class `ansible-changed` (amber/yellow text)
  - Lines containing `fatal:` or `failed:` → class `ansible-failed` (red text)
  - Lines containing `PLAY RECAP` → class `ansible-recap` (bold)
  - Other lines → default color
  
  Use `innerHTML` (the output comes from your own server, not user input, so XSS risk is minimal here — Ansible output doesn't contain HTML). Add the CSS classes to [styles.css](file:///home/pooyan/project/AnsiblePower/static/css/styles.css) with both light and dark mode variants.

---

### Day 41 — 🧪 Add unit tests for settings endpoints

- [ ] `[M]` Add tests for: `update_playbooks_dir` (valid dir, empty input, nonexistent path), `update_hosts_file` (valid file, empty input), `get_hosts` (file exists, file missing), `save_hosts` (valid content, missing file), `clear_history` (verify history becomes empty), `system_status` (mock psutil, check response shape).

---

### Day 42 — 🎨 Standardize error responses + add footer

- [ ] `[S]` Review all `jsonify({"error": ...})` calls in [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py). Make sure every error response follows the same shape: `{"error": "Human-readable message"}`. Some endpoints return `{"error": "..."}` and some return `{"status": "error", "message": "..."}` — pick one format and make it consistent.

- [ ] `[S]` Add a small footer to [base.html](file:///home/pooyan/project/AnsiblePower/templates/base.html): After the `</main>` tag, add `<footer class="text-center text-muted py-3 mt-4"><small>AnsiblePower v1.0 · <a href="https://github.com/pooyanazad/AnsiblePower">GitHub</a></small></footer>`. Add dark mode styles for the footer.

---

### Day 43 — 🎨 History pagination

**Problem:** With hundreds of history entries, the page loads slowly and scrolling is painful.

- [ ] `[M]` In [history.html](file:///home/pooyan/project/AnsiblePower/templates/history.html): Implement client-side pagination. Show 20 rows per page. Add Previous/Next buttons below the table. In JavaScript: hide all `<tr>` elements except rows `(page * 20)` through `((page + 1) * 20 - 1)`. Show "Page 1 of N" and disable Previous on page 1, Next on last page. No backend changes needed — the data is already loaded.

---

### Day 44 — 🧹 Add ruff linter to CI

**Problem:** No automated code quality checks. Bad formatting, unused imports, or style issues only get caught in code review (if at all).

- [ ] `[S]` In [test.yml](file:///home/pooyan/project/AnsiblePower/.github/workflows/test.yml), add a new job `lint` that runs before `unit-tests`:
  ```yaml
  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.12" }
    - run: pip install ruff
    - run: ruff check ansiblePower.py tests/
  ```
  Create a minimal `ruff.toml` in the project root with `line-length = 120` and any rules you want to ignore. Fix all issues found.

---

### Day 45 — 🎨 Path validity indicator in Settings

**Problem:** After typing a playbooks directory path, you have to save and go to the homepage to find out if the path is valid. No immediate feedback.

- [ ] `[S]` In [settings.html:36](file:///home/pooyan/project/AnsiblePower/templates/settings.html#L36): Add an `input` event listener on the playbooks dir text field. On each keystroke (debounced by 500ms), send a GET request to a new endpoint `/settings/check_path?path=...` that returns `{"exists": true/false, "readable": true/false}`. Show a green ✅ or red ❌ icon next to the input based on the response. Also add this new endpoint in [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py): `@settings_bp.route("/check_path")` that checks `os.path.isdir()` and `os.access()`.

---

### Day 46 — 📝 Add docstrings to all functions

- [ ] `[M]` Add one-liner or multi-line docstrings to every function in [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py) (there are ~20 functions). Focus on: what the function does, what it returns, and any side effects. Example:
  ```python
  def load_config() -> dict:
      """Load app configuration from the JSON config file.
      
      Returns the default config if the file is missing or corrupted.
      """
  ```
  This makes the code self-documenting and helps IDE tooltips.

---

### Day 47 — 🔒 Content Security Policy

**Problem:** Without a CSP header, if the Bootstrap or FontAwesome CDN is compromised, malicious scripts could run on your page.

- [ ] `[S]` Extend the `@app.after_request` handler from Day 9. Add a CSP header that explicitly lists allowed sources:
  ```python
  response.headers['Content-Security-Policy'] = (
      "default-src 'self'; "
      "style-src 'self' 'unsafe-inline' https://stackpath.bootstrapcdn.com https://cdnjs.cloudflare.com; "
      "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
      "font-src 'self' https://cdnjs.cloudflare.com; "
      "img-src 'self' data:;"
  )
  ```
  Note: `'unsafe-inline'` is needed because you have inline `<script>` blocks in templates. Later when you move all JS to external files, you can remove it.

---

### Day 48 — 🎨 Re-run from history + delete single entry

Two small features that make the history page actually useful:

- [ ] `[S]` **Re-run button:** Add a "▶ Re-run" button on each history row. When clicked, call `/run_playbook` with the playbook name from that row. Show the output in a new expandable section on the history page.

- [ ] `[S]` **Delete button:** Add a new endpoint `@history_bp.route("/delete_entry/<int:index>", methods=["POST"])` that removes a specific entry from history by index. Add a small "🗑" button on each row that calls this endpoint, then removes the row from the DOM. Add a confirmation `confirm()` before deleting.

---

### Day 49 — 🎨 Show relative timestamps

**Problem:** History shows raw timestamps like "2025-06-13 14:30:00". Users have to do mental math to figure out "was this recent?"

- [ ] `[S]` Add a small JavaScript function `timeAgo(dateString)` in [main.js](file:///home/pooyan/project/AnsiblePower/static/js/main.js) that converts timestamps to "2 minutes ago", "3 hours ago", "yesterday", etc. In [history.html:21](file:///home/pooyan/project/AnsiblePower/templates/history.html#L21), add `class="time-ago"` and `data-time="{{ record.time }}"` to each time `<td>`. On page load, find all `.time-ago` elements and replace their text with the relative time. Keep the original timestamp as a `title` attribute (tooltip on hover) so users can still see the exact time.

---

### Day 50 — 🧹 App factory pattern

**Problem:** The app is created at module level (`app = Flask(__name__)`), which means importing `ansiblePower` creates the app immediately. This makes testing hard — you can't create different app instances with different configs.

- [ ] `[M]` Create a `create_app(config=None)` function that:
  1. Creates `Flask(__name__)`
  2. Sets `secret_key` from env or config
  3. Initializes `CSRFProtect`
  4. Registers all blueprints
  5. Returns the app

  Keep a module-level `app = create_app()` for backward compatibility (Gunicorn needs `ansiblePower:app`). Update tests to call `create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})` instead of patching module globals.

---

### Day 51 — 🎨 Settings page tabs

**Problem:** The settings page is a single long scroll with unrelated sections mixed together (Hosts editor, system status, history management, directory config). It's hard to find what you're looking for.

- [ ] `[M]` Reorganize [settings.html](file:///home/pooyan/project/AnsiblePower/templates/settings.html) into Bootstrap tabs (or a simple accordion). Four sections: "Hosts" (show/edit hosts), "System" (CPU/memory status), "Paths" (playbooks dir, hosts file path), "Data" (clear history). Use Bootstrap's nav-tabs component. Each tab content is wrapped in a `<div class="tab-pane">`. Default to the "Hosts" tab.

---

### Day 52 — ✨ Execution time tracking

**Problem:** History shows what was run and when, but not how long it took. Users can't tell if a playbook is getting slower over time or which playbooks take the longest.

- [ ] `[M]` In [ansiblePower.py:204-224](file:///home/pooyan/project/AnsiblePower/ansiblePower.py#L204-L224): Record `start_time = time.time()` before `subprocess.check_output()` and `duration = round(time.time() - start_time, 1)` after. Add `"duration": duration` to the history entry dict. In history.html, show a new "Duration" column displaying "12.3s" or "2m 15s" for longer runs. Add `import time` if not already imported.

---

### Day 53 — 📝 CI badges + CHANGELOG

- [ ] `[S]` Add CI status, license, and Python version badges to the top of [README.md](file:///home/pooyan/project/AnsiblePower/README.md):
  ```markdown
  ![Tests](https://github.com/pooyanazad/AnsiblePower/actions/workflows/test.yml/badge.svg)
  ![License](https://img.shields.io/github/license/pooyanazad/AnsiblePower)
  ![Python](https://img.shields.io/badge/python-3.9+-blue)
  ```

- [ ] `[S]` Create [CHANGELOG.md](file:///home/pooyan/project/AnsiblePower/CHANGELOG.md) listing everything from "Already Done" as v1.0.0, then track future changes here. Use [Keep a Changelog](https://keepachangelog.com) format.

---

### Day 54 — 🎨 History column sorting

- [ ] `[M]` In [history.html](file:///home/pooyan/project/AnsiblePower/templates/history.html): Make table headers clickable. Add `<th class="sortable" data-column="0">Time ⇅</th>` etc. In JavaScript, on header click, sort all `<tbody>` rows by that column's text content. Toggle between ascending/descending on repeated clicks. Show an arrow (▲/▼) indicating current sort direction.

---

### Day 55 — 🐳 .env.example + env var overrides

- [ ] `[S]` Create `.env.example` documenting all environment variables:
  ```env
  FLASK_SECRET_KEY=change-me-to-a-random-string
  FLASK_DEBUG=false
  ANSIBLE_PLAYBOOK_BIN=
  # ANSIBLEPOWER_PLAYBOOKS_DIR=/path/to/playbooks
  # ANSIBLEPOWER_HOSTS_FILE=/path/to/hosts
  ```

- [ ] `[S]` In [ansiblePower.py](file:///home/pooyan/project/AnsiblePower/ansiblePower.py) `load_config()`: Check env vars first — `os.environ.get("ANSIBLEPOWER_PLAYBOOKS_DIR")` overrides the JSON config value if set. Same for hosts file. This makes Docker and CI configuration much easier since you can configure everything via environment variables without touching config files.

---

### Day 56 — 🧪 Add test coverage reporting

- [ ] `[M]` In [test.yml](file:///home/pooyan/project/AnsiblePower/.github/workflows/test.yml): Change the test commands from `python tests/test_unit.py` to `pytest tests/ --cov=ansiblePower --cov-report=term-missing --cov-fail-under=40`. This runs all tests with coverage tracking and fails CI if coverage drops below 40% (start low, increase as you add tests). The `term-missing` flag shows exactly which lines are uncovered.

---

### Day 57 — ✨ Add disk usage to system status

- [ ] `[M]` In [ansiblePower.py:340-350](file:///home/pooyan/project/AnsiblePower/ansiblePower.py#L340-L350) (`system_status` endpoint): Add `disk = psutil.disk_usage('/')` and return `{"cpu": ..., "memory": ..., "disk_total_gb": round(disk.total / (1024**3), 1), "disk_used_percent": disk.percent}`. In the frontend, show a third progress bar for disk usage next to CPU and memory.

---

### Day 58 — 🧹 Add `pre-commit` hooks + black formatter

- [ ] `[S]` Create `pyproject.toml` with:
  ```toml
  [tool.black]
  line-length = 120
  
  [tool.ruff]
  line-length = 120
  
  [tool.isort]
  profile = "black"
  line_length = 120
  ```

- [ ] `[S]` Create `.pre-commit-config.yaml`:
  ```yaml
  repos:
    - repo: https://github.com/psf/black
      rev: 24.4.2
      hooks: [{id: black}]
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.4.4
      hooks: [{id: ruff, args: [--fix]}]
    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v4.6.0
      hooks: [{id: trailing-whitespace}, {id: end-of-file-fixer}]
  ```
  Run `black ansiblePower.py tests/` to format everything. Commit the result.

---

### Day 59 — 🎨 Accessibility: ARIA + focus styles

- [ ] `[S]` In all templates: Add `aria-label` to icon-only buttons — `<button aria-label="Run playbook {{ playbook }}">`, `<button aria-label="Toggle dark mode">`, etc. Add `role="status"` and `aria-live="polite"` to the playbook output `<pre>` elements and the status box so screen readers announce updates.

- [ ] `[S]` In [styles.css](file:///home/pooyan/project/AnsiblePower/static/css/styles.css): Add `:focus-visible` styles for all interactive elements — `outline: 2px solid #007bff; outline-offset: 2px;`. Don't use `outline: none` — that breaks keyboard navigation.

---

### Day 60 — 🎨 Breadcrumbs + playbook search

- [ ] `[S]` Add breadcrumb navigation in [base.html](file:///home/pooyan/project/AnsiblePower/templates/base.html) inside `<main>`, before `{% block content %}`: `<nav aria-label="breadcrumb"><ol class="breadcrumb"><li>Home</li><li>{% block breadcrumb %}{% endblock %}</li></ol></nav>`. Each child template sets its breadcrumb. Helps users orient themselves.

- [ ] `[M]` Add a search box to the playbook page. In [index.html](file:///home/pooyan/project/AnsiblePower/templates/index.html): Add `<input type="text" id="playbook-search" placeholder="Search playbooks...">` above the list. JavaScript `input` listener filters `.list-group-item` elements by matching the search text against the playbook name. ~8 lines of JS.

---

### Day 61 — 🧹 Blueprint file separation

**Problem:** `ansiblePower.py` handles everything — main routes, history routes, settings routes, config loading, history management. As features grow, this file becomes unmanageable.

- [ ] `[L]` Create a `routes/` directory with:
  - `routes/__init__.py` — empty
  - `routes/main.py` — `main_bp` with `homepage`, `run_playbook`, `show_playbook`
  - `routes/history.py` — `history_bp` with `history`, `export_history`, `import_history`
  - `routes/settings.py` — `settings_bp` with all settings endpoints
  
  In `ansiblePower.py`, import blueprints from the route files: `from routes.main import main_bp` etc. Move the route decorators and their functions, but keep `create_app()` and blueprint registration in the main file. Run tests to verify nothing breaks.

---

### Day 62 — ✨ Dry-run mode for playbooks

**Problem:** Users have no way to preview what a playbook will do before actually running it. In production environments, this is risky.

- [ ] `[M]` Add a "🔍 Dry Run" button next to the "▶ Run" button in [index.html](file:///home/pooyan/project/AnsiblePower/templates/index.html). When clicked, call a new endpoint `/run_playbook` with an extra parameter `check=true`. In the backend, when `request.form.get("check")` is truthy, add `--check` to the ansible-playbook command. The output shows what *would* change without actually changing anything. Show the output with a "[DRY RUN]" badge so users know it's not a real execution. Don't save dry runs to history.

---

### Day 63 — 🐳 CI: Docker build + pip cache + Python matrix

- [ ] `[S]` Add pip caching to all CI jobs using `actions/cache`:
  ```yaml
  - uses: actions/cache@v4
    with:
      path: ~/.cache/pip
      key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}
  ```

- [ ] `[S]` Add a `docker-build` job to [test.yml](file:///home/pooyan/project/AnsiblePower/.github/workflows/test.yml) that runs `docker compose build` to catch Dockerfile errors on every PR.

- [ ] `[S]` Add `strategy: matrix: python-version: ["3.9", "3.10", "3.11", "3.12"]` to the unit-tests job to test across Python versions.

---

### Day 64 — 🎨 Keyboard shortcuts

- [ ] `[M]` In [main.js](file:///home/pooyan/project/AnsiblePower/static/js/main.js), add a `keydown` listener:
  - `/` → focus the playbook search box (if on homepage) — prevent default so `/` doesn't type in the box
  - `Ctrl+D` or `Cmd+D` → toggle dark mode
  - `Escape` → close any open modals or collapse expanded outputs
  
  Show a small "?" icon in the footer or header that opens a tooltip listing available shortcuts.

---

### Day 65 — ✨ Playbook upload

- [ ] `[M]` Add a "⬆ Upload Playbook" button on the homepage. When clicked, show a file input accepting `.yml`/`.yaml` files. Add a new endpoint `@main_bp.route("/upload_playbook", methods=["POST"])` that saves the uploaded file to the playbooks directory. Validate: file extension must be `.yml`/`.yaml`, filename must match the safe regex from Day 19, file size under 1 MB. After upload, redirect to homepage where the new playbook appears in the list.

---

### Day 66 — 🧹 Type hints for all functions

- [ ] `[L]` Add type annotations to every function in `ansiblePower.py` (and `utils.py` if you did Day 36). Focus on:
  - Return types: `-> dict`, `-> list`, `-> Response`, `-> tuple[Response, int]`
  - Parameter types: `config: dict`, `history: list[dict]`
  - Use `from flask.wrappers import Response` for Flask response types
  
  Don't worry about being perfect — the goal is basic annotations that help IDEs and catch obvious bugs. You can add `mypy` to CI later.

---

### Day 67 — ✨ Playbook delete with confirmation

- [ ] `[M]` Add a "🗑 Delete" button next to each playbook in [index.html](file:///home/pooyan/project/AnsiblePower/templates/index.html). Clicking it shows a confirmation dialog ("Permanently delete sample.yml?"). Add a new endpoint `@main_bp.route("/delete_playbook", methods=["POST"])` that deletes the file from the playbooks directory. Apply the same path validation and filename sanitization from Days 19 and 22. Log the deletion. Return success and remove the playbook card from the DOM.

---

### Day 68 — ⚡ Performance: gzip + async scripts

- [ ] `[S]` Install `Flask-Compress` (add to requirements.txt). In the app, add `from flask_compress import Compress; Compress(app)`. This automatically gzip-compresses all responses, reducing payload size by ~70% for HTML/CSS/JS.

- [ ] `[S]` In [base.html:26-27](file:///home/pooyan/project/AnsiblePower/templates/base.html#L26-L27): Add `defer` attribute to the Bootstrap and main.js `<script>` tags. This lets the browser parse HTML first and run JS after, improving perceived load time.

---

### Day 69 — 🎨 System status auto-refresh + uptime

- [ ] `[M]` In [main.js:136-143](file:///home/pooyan/project/AnsiblePower/static/js/main.js#L136-L143): After clicking "Get Status", start a `setInterval(fetchStatus, 5000)` that auto-refreshes CPU/memory every 5 seconds. Add a "⏸ Pause" toggle button to stop polling. Show an "Auto-refreshing every 5s" indicator.

- [ ] `[S]` In the `system_status` endpoint: Add `uptime = round(time.time() - psutil.boot_time())` and return it as seconds. Format it in JavaScript as "2d 5h 30m".

---

### Day 70 — 🧹 History size cap

**Problem:** History is stored in a JSON file that grows forever. With thousands of entries, loading/saving gets slow and the file can get corrupted by concurrent writes.

- [ ] `[S]` In `save_history()` (or wherever history is appended in `run_playbook`): After appending, check `if len(history) > 1000:` and trim to the latest 1000 entries with `history = history[-1000:]`. Log a warning when trimming happens. This keeps history manageable without losing recent data.

---

### Day 71 — 🎨 Hosts file editor improvements

- [ ] `[M]` In [settings.html:11](file:///home/pooyan/project/AnsiblePower/templates/settings.html#L11): Give the textarea a `monospace` font-family and a dark background (`#1e1e1e` with light text) to feel like a code editor. Add line numbers by placing a `<div>` to the left of the textarea that counts `\n` characters and shows line numbers. Update line numbers on every `input` event. Add a "Reset" button that reloads the original content (re-fetches from server) in case the user wants to undo their changes.

---

### Day 72 — 🐳 Dependabot + GitHub templates

- [ ] `[S]` Create `.github/dependabot.yml`:
  ```yaml
  version: 2
  updates:
    - package-ecosystem: "pip"
      directory: "/"
      schedule: { interval: "weekly" }
    - package-ecosystem: "github-actions"
      directory: "/"
      schedule: { interval: "weekly" }
  ```

- [ ] `[S]` Create `.github/pull_request_template.md` with a checklist: "[ ] Tests pass", "[ ] No new warnings", "[ ] Updated CHANGELOG.md".

- [ ] `[S]` Create `.github/ISSUE_TEMPLATE/bug_report.md` and `feature_request.md` with appropriate fields.

---

### Day 73 — 🎨 Playbook sorting

- [ ] `[M]` Add a dropdown above the playbook list: "Sort by: Name (A-Z) | Name (Z-A) | Recently modified | File size". In JavaScript, on dropdown change, sort the `.list-group-item` elements in the DOM. For "recently modified" and "file size", you'll need the metadata from Day 35 stored in `data-*` attributes on each list item.

---

### Day 74 — 🧹 CSS custom properties

- [ ] `[S]` In [styles.css](file:///home/pooyan/project/AnsiblePower/static/css/styles.css): Define all colors as CSS variables at `:root`:
  ```css
  :root {
    --color-primary: #007bff;
    --color-success: #28a745;
    --color-danger: #dc3545;
    --color-bg: #f8f9fa;
    --color-text: #2c3e50;
    --color-sidebar-bg: #ffffff;
  }
  .dark {
    --color-primary: #63b3ed;
    --color-bg: #2c3e50;
    --color-text: #ecf0f1;
    --color-sidebar-bg: #34495e;
  }
  ```
  Then replace all hardcoded color values with `var(--color-xxx)`. This makes future theming changes a one-place edit.

---

### Day 75 — 🧪 Test coverage badge + JS modularization

- [ ] `[S]` Set up Codecov or add a coverage badge to README using the CI output from Day 56.

- [ ] `[M]` Split [main.js](file:///home/pooyan/project/AnsiblePower/static/js/main.js) (178 lines) into 4 smaller files: `static/js/playbook.js` (run/show handlers), `static/js/settings.js` (hosts, status, paths), `static/js/theme.js` (dark mode), `static/js/utils.js` (CSRF token, toast function). Add all 4 `<script>` tags to [base.html](file:///home/pooyan/project/AnsiblePower/templates/base.html). Each file is focused and easier to test/debug independently.

---

## 🚀 Beyond Day 75 — Pick based on what users ask for

These are bigger features you can tackle in any order:

| Task | Size | What it does |
|------|------|-------------|
| ✨ Bootstrap 4 → 5 upgrade | `[XL]` | Drop jQuery, native dark mode utils, modern grid. Change `ml-`→`ms-`, `mr-`→`me-`, `data-toggle`→`data-bs-toggle` everywhere. |
| ✨ Real-time streaming output | `[XL]` | Replace `subprocess.check_output` with `Popen` + SSE. Show output line-by-line as playbook runs. |
| ✨ Browser-based playbook editor | `[L]` | Edit YAML files in CodeMirror/Monaco with syntax highlighting and save back. |
| ✨ Dashboard page | `[L]` | Summary widgets: total playbooks, runs today, success rate, system health, recent activity. |
| ✨ History charts | `[L]` | Chart.js: runs per day, success/failure pie chart, execution time trends. |
| ✨ Extra vars input | `[M]` | Pass `--extra-vars` key=value pairs or JSON when running a playbook. |
| ✨ Host `--limit` pattern | `[M]` | Target specific hosts per run. |
| ✨ Verbose level selector | `[S]` | Choose `-v`, `-vv`, `-vvv` per run. |
| ✨ Playbook subdirectories | `[M]` | Organize in subfolders, show as tree view. |
| ✨ Inventory selection per run | `[M]` | Pick which hosts file to use for each execution. |
| ✨ YAML validation pre-run | `[L]` | `yaml.safe_load()` or `ansible-lint` before running. Show syntax errors. |
| ✨ Stop running playbook | `[M]` | Cancel button sends SIGTERM to subprocess. |
| ✨ Concurrent playbook queue | `[L]` | Threading or Celery for parallel playbook execution. |
| ✨ Visual inventory manager | `[L]` | Form-based host/group editor instead of textarea. |
| ✨ Multiple inventory files | `[M]` | Manage and switch between inventories. |
| ✨ Host ping test | `[M]` | Button to `ansible -m ping` all hosts. |
| ✨ Scheduled runs | `[L]` | APScheduler to run playbooks on a cron schedule. |
| ✨ Webhook notifications | `[M]` | Slack/email/webhook when playbook finishes. |
| ✨ Playbook favorites | `[M]` | Star frequently-used playbooks for quick access. |
| ✨ SQLite for history | `[M]` | Replace JSON with a proper database. |
| ✨ Self-host CSS/JS | `[M]` | Download Bootstrap + FA to `static/vendor/`. Offline-capable. |
| ✨ FontAwesome 5 → 6 | `[S]` | More icons, better SVG rendering. |
| ✨ Gunicorn config file | `[M]` | `gunicorn.conf.py` with workers, timeout, access log. |
| ✨ API documentation | `[M]` | Swagger/OpenAPI at `/api/docs` or `docs/API.md`. |
| ✨ GitHub release workflow | `[M]` | Auto-create releases on version tags. |

---

## 📊 Progress Tracker

| Phase | Days | Focus | Status |
|-------|------|-------|--------|
| Docker & Deploy | 1–3 | Dockerfile, compose, test, README | 🔄 |
| Quick Wins | 4–12 | Favicon, toasts, spinner, security, tests | ⬜ |
| Core Quality | 13–22 | Logging, clipboard, dark mode, pagination | ⬜ |
| UX Polish | 23–32 | Transitions, mobile, error pages, search | ⬜ |
| Testing & Safety | 33–42 | Route tests, rate limiting, color coding | ⬜ |
| Maturity | 43–52 | Linting, pagination, CSP, timestamps | ⬜ |
| Features | 53–62 | Duration tracking, dry run, upload, badges | ⬜ |
| Architecture | 63–75 | CI matrix, shortcuts, sorting, CSS vars | ⬜ |
| Beyond 75 | 75+ | Big features based on user demand | ⬜ |
