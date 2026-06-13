# AnsiblePower — Improvement Plan

> Each item = one commit. Check off when done.
>
> 🔒 Security · 🧹 Code · 🎨 GUI · 🧪 Test · 🐳 DevOps · 📝 Docs · ✨ Feature · ⚡ Perf

## ✅ Done

- [x] Dynamic Flask secret key
- [x] Path traversal protection
- [x] CSRF on all POST endpoints
- [x] ansible-playbook binary resolution
- [x] Dark mode toggle in header
- [x] FontAwesome icons
- [x] Fix invisible text in dark mode
- [x] CI actions v4/v5
- [x] Dockerfile
- [x] .dockerignore
- [x] Fix bare relative paths for Docker

---

## 📋 Tasks

### Docker Setup (finish first)

- [ ] 1. 🐳 **Create `docker-compose.yml`** — mount volumes for `playbooks`, `data`, `logs`, and `~/.ssh` (read-only). Set `FLASK_SECRET_KEY` from env, `restart: unless-stopped`.
- [ ] 2. ✨ **Add `/health` endpoint** — simple `@main_bp.route("/health")` returning `jsonify({"status": "ok"})`. Used by Docker healthcheck and load balancers.
- [ ] 3. 🐳 **Update Dockerfile HEALTHCHECK** — change from `urllib` to `curl http://localhost:5000/health` using the new endpoint.
- [ ] 4. 🐳 **Create `.env.example`** — document `FLASK_SECRET_KEY`, `FLASK_DEBUG`, `ANSIBLE_PLAYBOOK_BIN` so users know what to configure.
- [ ] 5. 🐳 **Test Docker build + run locally** — verify app starts, pages load, playbooks dir works, data persists after restart.
- [ ] 6. 📝 **Update README with Docker section** — add quickstart: `docker compose up -d`, mention volume mounts and env vars. Remove outdated `pip install flask psutil` line and old screenshot reference.

### Improvements

- [ ] 7. 🎨 **Add SVG favicon** — inline `<svg>` lightning bolt in `base.html` `<head>`. No more generic browser tab icon.
- [ ] 8. 🎨 **Add per-page `<title>` tags** — `{% block title %}` in `base.html`, then "Playbooks — AnsiblePower", "History — AnsiblePower", "Settings — AnsiblePower" in child templates.
- [ ] 9. 🔒 **Add subprocess timeout** — `timeout=300` on `subprocess.check_output` in `run_playbook`. Prevents hung playbooks from blocking the server forever.
- [ ] 10. 🔒 **Handle timeout error** — catch `subprocess.TimeoutExpired`, return `"Playbook timed out after 5 minutes"`, save timeout to history.
- [ ] 11. 🧹 **Move misplaced imports to top** — `import shutil` from inside `_find_ansible_playbook()` and `from flask import Blueprint` from line 137 to the top-level import block.
- [ ] 12. 🧹 **Fix module docstring** — replace comment lines 2-3 with `"""AnsiblePower - Lightweight web interface for managing Ansible playbooks."""`
- [ ] 13. 🎨 **Add toast notification system** — create `showToast(message, type)` in `main.js`, add toast container to `base.html`, add CSS for success/error/info toasts with fade animation.
- [ ] 14. 🎨 **Replace all `alert()` with toasts** — `alert("Hosts saved.")`, `alert("History cleared.")`, and error alerts in `index.html` inline script.
- [ ] 15. 🎨 **Add loading spinner for playbook runs** — CSS spinner animation, show it instead of "Running, Please wait..." text, disable Run button during execution.
- [ ] 16. 🔒 **Add security headers** — `@app.after_request` setting `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.
- [ ] 17. 🎨 **Add confirm before running playbook** — `confirm("Run 'sample.yml'?")` before the fetch call. Prevents accidental execution.
- [ ] 18. 🧪 **Rename test files to pytest convention** — `ut_ansiblePower.py` → `test_unit.py`, `qt_ansiblePower.py` → `test_quality.py`, `smoke_test.py` → `test_smoke.py`. Update CI workflow.
- [ ] 19. 🧹 **Replace custom log handler with stdlib** — delete `CustomRotatingLogHandler`, use `logging.handlers.RotatingFileHandler(maxBytes=1MB, backupCount=5)`. Current handler rewrites entire file on every log message.
- [ ] 20. 🎨 **Add copy-to-clipboard button** — 📋 icon next to playbook output, uses `navigator.clipboard.writeText()`, shows "✓ Copied" for 2 seconds.
- [ ] 21. 🔒 **Validate playbooks directory path** — in `update_playbooks_dir`, check `os.path.isdir()` and reject paths like `/etc`, `/proc`, `/sys`.
- [ ] 22. 🔒 **Validate hosts file path** — in `update_hosts_file`, check `os.path.isfile()` and reject paths containing `..`.
- [ ] 23. 🎨 **Move dark mode to localStorage** — remove server round-trip, apply dark class immediately on page load, toggle icon with JS instead of Jinja, auto-detect OS preference.
- [ ] 24. 🎨 **Add dark mode transition** — `transition: background-color 0.3s ease` on body, sidebar, cards. Prevents jarring color flash on toggle.
- [ ] 25. 🧹 **Split requirements files** — `requirements.txt` (runtime only: Flask, psutil, gunicorn, Flask-WTF) and `requirements-dev.txt` (adds pytest, coverage, etc.). Update CI and Dockerfile.
- [ ] 26. 🎨 **Truncate history output** — max-height 80px with "Show more ▼" toggle. Long outputs currently break the table layout.
- [ ] 27. 🔒 **Add filename validation** — regex `^[a-zA-Z0-9_-]+\.(yml|yaml)$` in both `run_playbook` and `show_playbook`. Reject names with spaces or special characters.
- [ ] 28. 🧪 **Create shared test fixtures** — `tests/conftest.py` with Flask test client, temp directory, mock config/history. Simplify setup in all test files.
- [ ] 29. 🎨 **Visual system status gauges** — replace plain "CPU: 50% | Memory: 60%" text with colored progress bars (green < 60%, yellow < 80%, red > 80%).
- [ ] 30. 🧹 **Extract duplicate path validation** — `run_playbook` and `show_playbook` share 13 identical lines. Extract to `_validate_playbook_path()` helper.
- [ ] 31. 🎨 **Add confirm before clearing history** — `confirm("Delete all history? Cannot be undone.")`. Change button from `btn-warning` to `btn-danger`.
- [ ] 32. 🧪 **Add tests for `run_playbook`** — valid playbook (mock subprocess), subprocess failure, timeout, path traversal.
- [ ] 33. 🧪 **Add tests for `show_playbook`** — valid playbook, missing name, nonexistent file, directory-as-playbook.
- [ ] 34. 🧹 **Add custom error pages** — `templates/errors/404.html` and `500.html` extending `base.html`. Register `@app.errorhandler` handlers. No more ugly Flask defaults.
- [ ] 35. 📝 **Update README** — reflect new features: toast notifications, security headers, subprocess timeout, dark mode improvements, test conventions.

- [ ] 36. 🎨 **Add search box for playbooks** — text input above the list, JS filters `.list-group-item` by name as you type.
- [ ] 37. 🎨 **Add search box for history** — text input above the table, JS hides non-matching rows.
- [ ] 38. 🎨 **Add mobile navigation** — sidebar links in `#navbarNav` collapse so mobile users can access History/Settings via hamburger menu.
- [ ] 39. 🎨 **Add footer** — version number + GitHub link at bottom of every page, styled for dark mode.
- [ ] 40. 🎨 **Improve active sidebar link** — colored left border + background tint instead of just bold text. Styled for both light and dark mode.
- [ ] 41. 🎨 **Color-code history rows** — green tint for `failed=0`, red for failures, yellow for unreachable. Uses Jinja template logic, no backend change.
- [ ] 42. 🔒 **Add rate limiting** — `flask-limiter` with `5/minute` on `/run_playbook` and `60/minute` default. Prevents abuse of shell command execution.
- [ ] 43. 🧹 **Extract helpers to `utils.py`** — move `load_config`, `save_config`, `load_history`, `save_history`, `get_playbooks_dir`, `get_hosts_file`, and constants. Keeps `ansiblePower.py` focused on routes.
- [ ] 44. 🎨 **Empty states** — icon + helpful message when no playbooks exist or no history available. Link to Settings from empty playbooks page.
- [ ] 45. 🐳 **Add Makefile** — `make run`, `make test`, `make lint`, `make docker-build`, `make docker-up`, `make clean`.
- [ ] 46. 🔒 **Limit upload file size** — `MAX_CONTENT_LENGTH = 5MB` and `@app.errorhandler(413)` for history import.
- [ ] 47. 🔒 **Limit imported history count** — cap at 10,000 records in `import_history`.
- [ ] 48. 🎨 **Color-code playbook output** — green for `ok:`, yellow for `changed:`, red for `fatal:`/`failed:`, bold for `PLAY RECAP`.
- [ ] 49. 🧹 **Standardize error responses** — make all endpoints return `{"error": "message"}` consistently. Fix `update_playbooks_dir` and `update_hosts_file` which use different format.
- [ ] 50. 🧪 **Add tests for settings endpoints** — `update_playbooks_dir` (valid/invalid), `update_hosts_file`, `save_hosts`, `clear_history`, `system_status`, `toggle_dark_mode`.
- [ ] 51. 📝 **Expand CONTRIBUTING.md** — dev setup, how to run tests, code style, PR checklist.

- [ ] 52. 🎨 **Relative timestamps in history** — "5 minutes ago" with original as tooltip. Small JS `timeAgo()` function.
- [ ] 53. 🎨 **History pagination** — 20 rows per page, Previous/Next buttons, "Page X of Y". Client-side, no backend change.
- [ ] 54. 🎨 **History column sorting** — clickable headers, toggle asc/desc, arrow indicator.
- [ ] 55. 🎨 **Re-run + delete on history rows** — "▶ Re-run" calls `/run_playbook`, "🗑 Delete" removes single entry via new endpoint.
- [ ] 56. 🧹 **Add docstrings** — to all functions in `ansiblePower.py`. Parameters, return values, side effects.
- [ ] 57. 🧹 **Add ruff linter** — `ruff.toml` with `line-length=120`, add lint job to CI, fix all issues.
- [ ] 58. 🎨 **Settings page tabs** — reorganize into Bootstrap tabs: Hosts, System, Paths, Data. Currently one long scroll.
- [ ] 59. 🔒 **Add Content-Security-Policy** — whitelist own CSS/JS + Bootstrap/FontAwesome CDNs. Prevents XSS from unknown scripts.
- [ ] 60. 🎨 **Path validity indicator** — ✅/❌ icon next to playbooks dir input, checked via new `GET /settings/check_path` endpoint with 500ms debounce.
- [ ] 61. 🧹 **App factory pattern** — `create_app()` function for easier testing. Keep `app = create_app()` at module level for Gunicorn.
- [ ] 62. ✨ **Execution time tracking** — `time.time()` before/after subprocess, save `"duration"` to history, show "12.3s" or "2m 15s" in history table.
- [ ] 63. 🧹 **Env var overrides** — `ANSIBLEPOWER_PLAYBOOKS_DIR` and `ANSIBLEPOWER_HOSTS_FILE` override config. Docker-friendly.
- [ ] 64. ✨ **Disk usage + uptime** — add `psutil.disk_usage('/')` and `psutil.boot_time()` to system status. Format uptime as "2d 5h 30m".
- [ ] 65. 🎨 **System status auto-refresh** — toggle button to poll every 5 seconds instead of manual click.
- [ ] 66. 🧪 **Add tests for import/export** — JSON import, CSV import, unsupported type, JSON export, CSV export.
- [ ] 67. 🧪 **Add tests for `_find_ansible_playbook`** — env override, venv path, system PATH fallback.
- [ ] 68. 🧪 **Add test for `/health`** — returns 200 with `{"status": "ok"}`.
- [ ] 69. 🧪 **Add coverage to CI** — `pytest --cov --cov-fail-under=40`. Start low, increase as tests grow.
- [ ] 70. 📝 **Add badges to README** — CI status, license, Python version at the top.
- [ ] 71. 📝 **Create CHANGELOG.md** — v1.0.0 with all existing features. Track future changes here.
- [ ] 72. 📝 **Update README** — document search, history features, settings tabs, rate limiting, error pages.

- [ ] 73. 🧹 **Pre-commit hooks** — `.pre-commit-config.yaml` with black, ruff, trailing-whitespace. Run `black` on all files.
- [ ] 74. 🧹 **Cap history at 1,000 entries** — auto-trim oldest in `save_history()`. JSON gets slow with thousands.
- [ ] 75. 🎨 **Hosts editor improvements** — monospace font, dark background, line numbers, "Reset" button.
- [ ] 76. 🧹 **Type hints** — add to all functions in `utils.py` and route handlers. Return types, parameter types.
- [ ] 77. 🎨 **Breadcrumb navigation** — "Home > Settings" at top of each page.
- [ ] 78. 🎨 **Accessibility** — `aria-label` on icon-only buttons, `aria-live="polite"` on output elements, `:focus-visible` outlines.
- [ ] 79. 🎨 **Playbook metadata** — show file size (KB) and last modified date below each playbook name.
- [ ] 80. 🎨 **Playbook sorting** — dropdown: Name A-Z, Name Z-A, Recently Modified, Size.
- [ ] 81. 🎨 **Playbook "Last run" timestamp** — from history, shown next to each playbook.
- [ ] 82. 🐳 **CI improvements** — pip caching, Python version matrix (3.9-3.12), Docker build step.
- [ ] 83. 🐳 **GitHub templates** — `.github/dependabot.yml`, PR template, issue templates (bug report, feature request).
- [ ] 84. 🎨 **CSS custom properties** — define `--color-primary`, `--color-bg`, etc. at `:root`, override in `.dark`. Replace all hardcoded colors.
- [ ] 85. 🎨 **Keyboard shortcuts** — `/` to focus search, `Ctrl+D` for dark mode, `Escape` to close outputs. Show hints via `?` icon.
- [ ] 86. 🧹 **Split main.js** — into `playbook.js`, `settings.js`, `theme.js`, `utils.js`. Add `defer` to all script tags.
- [ ] 87. 🧹 **Blueprint file separation** — `routes/main.py`, `routes/history.py`, `routes/settings.py`. Import in main file. Verify tests pass.
- [ ] 88. 🧹 **Create `pyproject.toml`** — project metadata, black/ruff/isort config.
- [ ] 89. 📝 **Update README** — document new architecture, file structure, keyboard shortcuts, accessibility.

- [ ] 90. ⚡ **Gzip compression** — `Flask-Compress` for automatic response compression. ~70% smaller payloads.
- [ ] 91. ⚡ **Static file caching** — HTTP `Cache-Control` and `ETag` headers for CSS/JS.
- [ ] 92. ⚡ **Self-host CSS/JS** — download Bootstrap + FontAwesome to `static/vendor/`. Works offline.
- [ ] 93. ✨ **Dry-run mode** — "🔍 Dry Run" button passes `--check` to ansible. Shows "[DRY RUN]" badge, skips history.
- [ ] 94. ✨ **Verbose level selector** — dropdown for `-v`, `-vv`, `-vvv` per run.
- [ ] 95. ✨ **Extra-vars input** — text field for `--extra-vars` key=value pairs.
- [ ] 96. ✨ **Host limit input** — text field for `--limit` host pattern.
- [ ] 97. ✨ **Playbook upload** — file picker + `POST /upload_playbook` with extension/filename/size validation.
- [ ] 98. ✨ **Playbook delete** — 🗑 button + `POST /delete_playbook` with confirm dialog and path validation.
- [ ] 99. ✨ **In-browser playbook editor** — CodeMirror with YAML highlighting, `POST /save_playbook`, syntax validation.
- [ ] 100. ✨ **About page** — version, Python version, Ansible version, dependencies list. Link in sidebar.
- [ ] 101. ✨ **Dashboard page** — total playbooks, total runs, success rate, recent activity widgets. Link in sidebar.
- [ ] 102. 📝 **Create API docs** — `docs/API.md` documenting all endpoints with examples.
- [ ] 103. 🎨 **Print stylesheet** — `@media print` hiding sidebar, nav, buttons. Clean history table.
- [ ] 104. 🧹 **Add mypy to CI** — static type checking for Python code.
- [ ] 105. 📝 **Final README update** — screenshots, architecture diagram, full feature list, API reference link.

---

## 🔮 Future Plans

### Real-time & Async
- Stream playbook output live via `subprocess.Popen` + Server-Sent Events
- "Stop playbook" button sending SIGTERM to subprocess
- Concurrent playbook queue (threading or Celery)
- Scheduled playbook runs (APScheduler)

### Multi-host & Inventory
- Multiple inventory files — manage and switch
- Inventory selection per playbook run
- Host ping test (`ansible -m ping`)
- Visual inventory manager — form-based host/group editor

### Notifications
- Webhook on playbook finish (Slack, email, generic)
- Playbook favorites/bookmarks
- Playbook tags and categories

### Data & Storage
- Migrate history from JSON to SQLite
- File locking for concurrent writes
- Structured JSON logging
- Request ID in log messages

### Framework Upgrades
- Bootstrap 4 → 5
- FontAwesome 5 → 6
- Gunicorn config file

### Advanced Testing
- Playwright end-to-end browser tests
- JavaScript unit tests (Jest/Vitest)
- Coverage badge via Codecov

### Deployment
- GitHub release workflow
- Helm chart for Kubernetes
- ARM Docker image for Raspberry Pi
- Charts (Chart.js) for runs-per-day and success/failure trends

---

## 📊 Progress

**0 / 105 done**
