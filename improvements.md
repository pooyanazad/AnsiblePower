# AnsiblePower — Improvement Plan

> Each item = one commit. Check off when done. Mix of categories keeps work interesting.

## ✅ Done

- [x] Dynamic Flask secret key generation
- [x] Path traversal protection in run/show playbook
- [x] CSRF protection on all POST endpoints
- [x] ansible-playbook binary resolution (venv/system/env)
- [x] Dark mode toggle in header navbar
- [x] FontAwesome icons in sidebar and buttons
- [x] Fix invisible text in dark mode
- [x] CI actions updated to v4/v5
- [x] README section numbering fix
- [x] Create Dockerfile
- [x] Create .dockerignore
- [x] Fix bare relative paths in ansiblePower.py for Docker/Gunicorn compatibility

---

## 📋 Tasks

### Docker & Deploy

- [ ] 1. Create `docker-compose.yml` with volume mounts for playbooks, data, logs, SSH keys
- [ ] 2. Add `/health` endpoint returning `{"status": "ok"}` for Docker healthcheck
- [ ] 3. Update Dockerfile HEALTHCHECK to use `/health` endpoint
- [ ] 4. Add Docker quickstart section to README.md
- [ ] 5. Create `.env.example` with all supported env vars documented

### Security

- [ ] 6. Add `timeout=300` to `subprocess.check_output` in `run_playbook`
- [ ] 7. Catch `subprocess.TimeoutExpired` and return friendly timeout error
- [ ] 8. Add `X-Frame-Options: DENY` header via `@app.after_request`
- [ ] 9. Add `X-Content-Type-Options: nosniff` header
- [ ] 10. Add `Referrer-Policy: strict-origin-when-cross-origin` header
- [ ] 11. Add `Content-Security-Policy` header allowing only known CDN sources
- [ ] 12. Validate `update_playbooks_dir` — reject if `os.path.isdir()` is False
- [ ] 13. Validate `update_playbooks_dir` — reject paths starting with `/etc`, `/proc`, `/sys`
- [ ] 14. Validate `update_hosts_file` — reject if `os.path.isfile()` is False
- [ ] 15. Validate `update_hosts_file` — reject paths containing `..`
- [ ] 16. Add regex filename validation in `run_playbook` — allow only `[a-zA-Z0-9_-]+\.(yml|yaml)`
- [ ] 17. Add same filename regex to `show_playbook`
- [ ] 18. Add `app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024` for file upload limit
- [ ] 19. Add `@app.errorhandler(413)` returning JSON error for oversized uploads
- [ ] 20. Limit imported history to max 10,000 records in `import_history`
- [ ] 21. Add `flask-limiter` to requirements.txt
- [ ] 22. Add rate limit `5/minute` on `/run_playbook` endpoint
- [ ] 23. Add rate limit `60/minute` as default for all endpoints

### Code Quality

- [ ] 24. Move `import shutil` from inside `_find_ansible_playbook()` to top of file
- [ ] 25. Move `from flask import Blueprint` from line 137 to the top-level Flask import (line 12)
- [ ] 26. Replace module comment lines 2-3 with proper docstring
- [ ] 27. Remove duplicate `_BASE` variable — use `BASE_DIR` for log handler path too
- [ ] 28. Replace `CustomRotatingLogHandler` with stdlib `RotatingFileHandler`
- [ ] 29. Delete the now-unused `CustomRotatingLogHandler` class
- [ ] 30. Extract duplicate path-traversal logic from `run_playbook` into `_validate_playbook_path()`
- [ ] 31. Reuse `_validate_playbook_path()` in `show_playbook`
- [ ] 32. Extract `load_config`, `save_config` into `utils.py`
- [ ] 33. Extract `load_history`, `save_history` into `utils.py`
- [ ] 34. Extract `get_playbooks_dir`, `get_hosts_file` into `utils.py`
- [ ] 35. Move constants `BASE_DIR`, `CONFIG_FILE`, etc. into `utils.py`
- [ ] 36. Standardize all error responses to `{"error": "message"}` format
- [ ] 37. Change `update_playbooks_dir` success response from `{"status": "ok", "message": ...}` to match standard
- [ ] 38. Change `update_hosts_file` success response to match standard
- [ ] 39. Add `import re` to top of file (needed for filename validation)
- [ ] 40. Add docstring to `load_config()`
- [ ] 41. Add docstring to `save_config()`
- [ ] 42. Add docstring to `load_history()`
- [ ] 43. Add docstring to `save_history()`
- [ ] 44. Add docstring to `get_playbooks_dir()`
- [ ] 45. Add docstring to `get_hosts_file()`
- [ ] 46. Add docstring to `_find_ansible_playbook()`
- [ ] 47. Add docstring to `run_playbook()`
- [ ] 48. Add docstring to `show_playbook()`
- [ ] 49. Add docstring to `homepage()`
- [ ] 50. Add docstring to `system_status()`
- [ ] 51. Add docstring to `export_history()`
- [ ] 52. Add docstring to `import_history()`
- [ ] 53. Add type hints to all functions in `utils.py`
- [ ] 54. Add type hints to all route functions in `ansiblePower.py`
- [ ] 55. Cap history at 1,000 entries — auto-trim oldest in `save_history()`
- [ ] 56. Create `create_app()` factory function
- [ ] 57. Move blueprint registration inside `create_app()`
- [ ] 58. Keep module-level `app = create_app()` for Gunicorn backward compat
- [ ] 59. Add env var override for playbooks dir: `ANSIBLEPOWER_PLAYBOOKS_DIR`
- [ ] 60. Add env var override for hosts file: `ANSIBLEPOWER_HOSTS_FILE`

### GUI — Quick Wins

- [ ] 61. Add inline SVG favicon to `base.html`
- [ ] 62. Add `{% block title %}` to `base.html` `<title>` tag
- [ ] 63. Set title to "Playbooks — AnsiblePower" in `index.html`
- [ ] 64. Set title to "History — AnsiblePower" in `history.html`
- [ ] 65. Set title to "Settings — AnsiblePower" in `settings.html`
- [ ] 66. Add footer with version number and GitHub link to `base.html`
- [ ] 67. Style footer for dark mode

### GUI — Toast Notifications

- [ ] 68. Add toast container `<div>` to `base.html`
- [ ] 69. Add `showToast(message, type)` function to `main.js`
- [ ] 70. Add toast CSS styles (success green, error red, info blue, fade animation)
- [ ] 71. Replace `alert("Hosts saved.")` with `showToast()` in `main.js:124`
- [ ] 72. Replace `alert(data.error)` with `showToast()` in `main.js:126`
- [ ] 73. Replace `alert("History cleared.")` with `showToast()` in `main.js:157`
- [ ] 74. Replace `alert()` calls in `index.html` inline script (lines 43, 48) with `showToast()`

### GUI — Playbook Execution UX

- [ ] 75. Add CSS spinner animation to `styles.css`
- [ ] 76. Show spinner instead of "Running, Please wait..." text in `main.js`
- [ ] 77. Disable Run button while playbook is running
- [ ] 78. Re-enable Run button when response arrives
- [ ] 79. Change Run button text to "Running..." while executing
- [ ] 80. Add `confirm()` dialog before executing a playbook
- [ ] 81. Add `confirm()` dialog before clearing history
- [ ] 82. Change Clear History button from `btn-warning` to `btn-danger`
- [ ] 83. Add "Copy output to clipboard" button next to playbook output
- [ ] 84. Show "✓ Copied" feedback for 2 seconds after copy

### GUI — Dark Mode

- [ ] 85. Move dark mode state from Flask session to `localStorage`
- [ ] 86. Read `localStorage` on page load and apply dark class immediately
- [ ] 87. Toggle sun/moon icon with JavaScript instead of Jinja template
- [ ] 88. Remove the `fetch("/settings/toggle_dark_mode")` server call from toggle
- [ ] 89. Auto-detect OS dark mode with `matchMedia('prefers-color-scheme: dark')`
- [ ] 90. Add `transition: background-color 0.3s ease` to `body` in CSS
- [ ] 91. Add same transition to `.sidebar`, `.card`, `.list-group-item`

### GUI — History Page

- [ ] 92. Replace "No history available." text with icon + helpful message
- [ ] 93. Truncate long output in history — max-height 80px with "Show more" toggle
- [ ] 94. Add CSS for history output truncation and expand/collapse
- [ ] 95. Color-code history rows: green for `failed=0`, red for failed > 0
- [ ] 96. Add search/filter input above history table
- [ ] 97. Add JS to filter history rows by search text
- [ ] 98. Add relative timestamps ("5 minutes ago") with JS `timeAgo()` function
- [ ] 99. Keep original timestamp as tooltip on hover
- [ ] 100. Add client-side pagination — 20 rows per page
- [ ] 101. Add Previous/Next buttons for pagination
- [ ] 102. Add "Page X of Y" indicator
- [ ] 103. Make table headers clickable for column sorting
- [ ] 104. Toggle ascending/descending on repeated header click
- [ ] 105. Show sort direction arrow (▲/▼) on active column
- [ ] 106. Add "Re-run" button on each history row
- [ ] 107. Add "Delete single entry" endpoint `DELETE /history/<index>`
- [ ] 108. Add delete button (🗑) on each history row with confirm

### GUI — Playbook List

- [ ] 109. Add empty state with icon when no playbooks exist
- [ ] 110. Add "configure directory in Settings →" link in empty state
- [ ] 111. Add search/filter input above playbook list
- [ ] 112. Add JS to filter playbooks by name as you type
- [ ] 113. Return file size and mtime from `homepage()` route alongside filenames
- [ ] 114. Show file size (KB) and last modified date below each playbook name
- [ ] 115. Add sort dropdown: Name A-Z, Name Z-A, Recently Modified, Size
- [ ] 116. Add JS sorting logic using `data-*` attributes
- [ ] 117. Add "Last run" timestamp from history next to each playbook
- [ ] 118. Add "Collapse all / Expand all" toggle for playbook outputs

### GUI — Settings Page

- [ ] 119. Reorganize settings into Bootstrap tabs: Hosts, System, Paths, Data
- [ ] 120. Add tab content wrappers for each section
- [ ] 121. Replace plain "CPU: X% | Memory: Y%" text with progress bars
- [ ] 122. Color progress bars: green < 60%, yellow 60-80%, red > 80%
- [ ] 123. Add auto-refresh toggle for system status (poll every 5 seconds)
- [ ] 124. Add disk usage to system status using `psutil.disk_usage('/')`
- [ ] 125. Add system uptime to status using `psutil.boot_time()`
- [ ] 126. Format uptime as "2d 5h 30m" in JavaScript
- [ ] 127. Add path validity indicator (✅/❌) next to playbooks dir input
- [ ] 128. Add endpoint `GET /settings/check_path?path=...` returning `{"exists": bool}`
- [ ] 129. Debounce path check to 500ms on keystroke
- [ ] 130. Add monospace font to hosts textarea
- [ ] 131. Add dark background to hosts textarea to feel like a code editor
- [ ] 132. Add line numbers next to hosts textarea
- [ ] 133. Add "Reset" button to reload original hosts content from server

### GUI — Navigation & Layout

- [ ] 134. Add mobile hamburger menu — add sidebar links to `#navbarNav` collapse
- [ ] 135. Add breadcrumb nav to `base.html` before `{% block content %}`
- [ ] 136. Set breadcrumb in each child template (Playbooks, History, Settings)
- [ ] 137. Improve active sidebar link: add colored left border + background tint
- [ ] 138. Style active sidebar link for dark mode

### GUI — Accessibility

- [ ] 139. Add `aria-label="Run playbook"` to run buttons
- [ ] 140. Add `aria-label="Show playbook"` to show buttons
- [ ] 141. Add `aria-label="Toggle dark mode"` to dark mode button
- [ ] 142. Add `aria-label` to all other icon-only buttons
- [ ] 143. Add `role="status"` and `aria-live="polite"` to playbook output `<pre>`
- [ ] 144. Add `:focus-visible` outline styles for all interactive elements
- [ ] 145. Never use `outline: none` on buttons/links

### GUI — CSS & Theming

- [ ] 146. Define CSS custom properties at `:root` (--color-primary, --color-bg, etc.)
- [ ] 147. Override custom properties in `.dark` selector
- [ ] 148. Replace all hardcoded color values with `var(--color-xxx)`
- [ ] 149. Add `@media print` stylesheet — hide sidebar, nav, buttons

### GUI — Keyboard & Advanced

- [ ] 150. Add keyboard shortcut `/` to focus playbook search
- [ ] 151. Add `Ctrl+D` to toggle dark mode
- [ ] 152. Add `Escape` to close expanded outputs
- [ ] 153. Add shortcut hint tooltip accessible via `?` icon

### Testing

- [ ] 154. Rename `ut_ansiblePower.py` → `test_unit.py`
- [ ] 155. Rename `qt_ansiblePower.py` → `test_quality.py`
- [ ] 156. Rename `smoke_test.py` → `test_smoke.py`
- [ ] 157. Update CI workflow to use new test file names
- [ ] 158. Create `tests/conftest.py` with shared Flask test client fixture
- [ ] 159. Add temp directory fixture for test isolation
- [ ] 160. Add mock config/history fixtures
- [ ] 161. Simplify test setup in `test_unit.py` using conftest fixtures
- [ ] 162. Simplify test setup in `test_quality.py` using conftest fixtures
- [ ] 163. Simplify test setup in `test_smoke.py` using conftest fixtures
- [ ] 164. Add test: `run_playbook` with valid playbook (mock subprocess)
- [ ] 165. Add test: `run_playbook` subprocess failure returns error output
- [ ] 166. Add test: `run_playbook` timeout returns friendly error
- [ ] 167. Add test: `show_playbook` with valid playbook returns content
- [ ] 168. Add test: `show_playbook` directory-as-playbook returns 400
- [ ] 169. Add test: `update_playbooks_dir` with valid directory
- [ ] 170. Add test: `update_playbooks_dir` with nonexistent path returns 400
- [ ] 171. Add test: `update_hosts_file` with valid file
- [ ] 172. Add test: `update_hosts_file` with nonexistent path returns 400
- [ ] 173. Add test: `save_hosts` writes content correctly
- [ ] 174. Add test: `clear_history` empties history
- [ ] 175. Add test: `system_status` returns cpu and memory keys
- [ ] 176. Add test: `toggle_dark_mode` flips session value
- [ ] 177. Add test: `import_history` with valid JSON
- [ ] 178. Add test: `import_history` with valid CSV
- [ ] 179. Add test: `import_history` with unsupported file type returns 400
- [ ] 180. Add test: `import_history` with oversized file returns 413
- [ ] 181. Add test: `export_history` JSON format
- [ ] 182. Add test: `export_history` CSV format
- [ ] 183. Add test: `_find_ansible_playbook` with env override
- [ ] 184. Add test: `_find_ansible_playbook` with venv path
- [ ] 185. Add test: `_find_ansible_playbook` fallback to system PATH
- [ ] 186. Add test: `/health` endpoint returns 200
- [ ] 187. Add `pytest --cov` to CI workflow
- [ ] 188. Set `--cov-fail-under=40` threshold

### CI/CD & DevOps

- [ ] 189. Add pip caching with `actions/cache` to all CI jobs
- [ ] 190. Add `ruff` linter to requirements-dev.txt
- [ ] 191. Add lint job to CI that runs `ruff check ansiblePower.py`
- [ ] 192. Create `ruff.toml` with `line-length = 120`
- [ ] 193. Fix all ruff lint issues
- [ ] 194. Add Python version matrix (3.9, 3.10, 3.11, 3.12) to unit-tests job
- [ ] 195. Add Docker build step to CI to catch Dockerfile errors
- [ ] 196. Create `.github/dependabot.yml` for pip and GitHub Actions
- [ ] 197. Create `.github/pull_request_template.md`
- [ ] 198. Create `.github/ISSUE_TEMPLATE/bug_report.md`
- [ ] 199. Create `.github/ISSUE_TEMPLATE/feature_request.md`
- [ ] 200. Add `Makefile` with `run`, `test`, `lint`, `docker-build`, `docker-up`, `docker-down`, `clean`

### Dependencies & Config

- [ ] 201. Split requirements.txt into runtime-only packages
- [ ] 202. Create `requirements-dev.txt` that includes runtime + test packages
- [ ] 203. Update CI to `pip install -r requirements-dev.txt`
- [ ] 204. Update Dockerfile to use runtime-only `requirements.txt`
- [ ] 205. Create `pyproject.toml` with `[project]` metadata
- [ ] 206. Add black config to `pyproject.toml`
- [ ] 207. Add ruff config to `pyproject.toml` (can replace `ruff.toml`)
- [ ] 208. Create `.pre-commit-config.yaml` with black, ruff, trailing-whitespace
- [ ] 209. Run `black` on all Python files and commit formatted code
- [ ] 210. Add `mypy` to CI

### Docs

- [ ] 211. Update LICENSE copyright year to 2024-2026
- [ ] 212. Remove `pip install flask psutil` from README — `requirements.txt` covers it
- [ ] 213. Remove/update outdated screenshot reference in README (line 48)
- [ ] 214. Add Docker section to README with `docker compose up -d` quickstart
- [ ] 215. Add CI status badge to top of README
- [ ] 216. Add license badge to README
- [ ] 217. Add Python version badge to README
- [ ] 218. Create `CHANGELOG.md` listing v1.0.0 with all existing features
- [ ] 219. Rewrite CONTRIBUTING.md with dev setup, test instructions, PR checklist
- [ ] 220. Create `docs/API.md` documenting all endpoints

### Architecture — Blueprint Separation

- [ ] 221. Create `routes/` directory with `__init__.py`
- [ ] 222. Move `main_bp` routes to `routes/main.py`
- [ ] 223. Move `history_bp` routes to `routes/history.py`
- [ ] 224. Move `settings_bp` routes to `routes/settings.py`
- [ ] 225. Import blueprints in `ansiblePower.py` from route modules
- [ ] 226. Verify all tests still pass after blueprint separation

### JavaScript

- [ ] 227. Split `main.js` into `playbook.js` (run/show handlers)
- [ ] 228. Split `main.js` into `settings.js` (hosts, status, paths)
- [ ] 229. Split `main.js` into `theme.js` (dark mode logic)
- [ ] 230. Split `main.js` into `utils.js` (CSRF token, toast, shared helpers)
- [ ] 231. Add all 4 script tags to `base.html`
- [ ] 232. Add `defer` attribute to all `<script>` tags in `base.html`

### Performance

- [ ] 233. Add `Flask-Compress` to requirements for gzip compression
- [ ] 234. Initialize `Compress(app)` in app setup
- [ ] 235. Add HTTP caching headers for static CSS/JS files
- [ ] 236. Self-host Bootstrap CSS in `static/vendor/` for offline use
- [ ] 237. Self-host FontAwesome in `static/vendor/` for offline use
- [ ] 238. Self-host Bootstrap JS in `static/vendor/` for offline use

### Features — Playbook Execution

- [ ] 239. Add execution time tracking — `time.time()` before/after subprocess
- [ ] 240. Save `"duration"` field to history entries
- [ ] 241. Show duration column in history table ("12.3s" or "2m 15s")
- [ ] 242. Add `--check` dry-run mode — new "Dry Run" button
- [ ] 243. Pass `--check` flag to subprocess when dry-run requested
- [ ] 244. Show "[DRY RUN]" badge on dry-run output
- [ ] 245. Don't save dry-run results to history
- [ ] 246. Add verbose level selector dropdown (`-v`, `-vv`, `-vvv`)
- [ ] 247. Pass verbose flag to subprocess based on selection
- [ ] 248. Add `--extra-vars` input field for playbook runs
- [ ] 249. Pass extra-vars to subprocess command
- [ ] 250. Add `--limit` host pattern input
- [ ] 251. Pass limit flag to subprocess

### Features — Playbook Management

- [ ] 252. Add playbook upload button to homepage
- [ ] 253. Add `POST /upload_playbook` endpoint with file validation
- [ ] 254. Validate upload: extension must be `.yml`/`.yaml`
- [ ] 255. Validate upload: filename matches safe regex
- [ ] 256. Validate upload: size under 1 MB
- [ ] 257. Add playbook delete button with confirm dialog
- [ ] 258. Add `POST /delete_playbook` endpoint
- [ ] 259. Apply path validation to delete endpoint
- [ ] 260. Add in-browser playbook editor (CodeMirror)
- [ ] 261. Add `POST /save_playbook` endpoint
- [ ] 262. Add YAML syntax validation before save

### Features — Error Pages

- [ ] 263. Create `templates/errors/404.html` extending `base.html`
- [ ] 264. Create `templates/errors/500.html` extending `base.html`
- [ ] 265. Register `@app.errorhandler(404)` handler
- [ ] 266. Register `@app.errorhandler(500)` handler

### Features — New Pages

- [ ] 267. Add "About" page showing version, Python version, Ansible version, dependencies
- [ ] 268. Add "About" link to sidebar
- [ ] 269. Add dashboard page with summary widgets (total playbooks, total runs, success rate)
- [ ] 270. Add dashboard link to sidebar
- [ ] 271. Add Chart.js for runs-per-day bar chart on dashboard
- [ ] 272. Add success/failure pie chart on dashboard

---

## 🔮 Future Plans

These are bigger directions to explore after the core improvements are done:

### Real-time & Async
- Stream playbook output in real-time using `subprocess.Popen` + Server-Sent Events
- Add "Stop running playbook" button sending SIGTERM to subprocess
- Concurrent playbook execution queue using threading or Celery
- Scheduled playbook runs using APScheduler

### Multi-host / Multi-inventory
- Support multiple inventory files — manage and switch between them
- Inventory selection per playbook run
- Host ping/connectivity test (`ansible -m ping`)
- Visual inventory manager — form-based host/group editor

### Notifications & Integration
- Webhook notifications when playbook finishes (Slack, email, generic webhook)
- Playbook favorites/bookmarks for quick access
- Playbook tags and categories

### Data & Storage
- Migrate history from JSON to SQLite
- Add file locking (`filelock`) for concurrent JSON writes
- Structured JSON logging for log aggregators (ELK, Loki)
- Request ID in log messages for traceability

### Framework Upgrades
- Bootstrap 4 → Bootstrap 5 (drops jQuery, modern grid, native dark mode utils)
- FontAwesome 5 → 6 (better SVG, more icons)
- Gunicorn config file (`gunicorn.conf.py`) with worker tuning

### End-to-end & Advanced Testing
- Playwright browser tests for full user flow
- JavaScript unit tests with Jest/Vitest
- Coverage badge on README via Codecov

### Deployment
- GitHub release workflow — auto-create releases on version tags
- Helm chart for Kubernetes deployment
- ARM Docker image for Raspberry Pi

---

## 📊 Progress

| Category | Count | Done |
|----------|-------|------|
| Docker & Deploy | 5 | 0 |
| Security | 18 | 0 |
| Code Quality | 37 | 0 |
| GUI | 89 | 0 |
| Testing | 35 | 0 |
| CI/CD & DevOps | 12 | 0 |
| Dependencies | 10 | 0 |
| Docs | 10 | 0 |
| Architecture | 6 | 0 |
| JavaScript | 6 | 0 |
| Performance | 6 | 0 |
| Features | 34 | 0 |
| **Total** | **268** | **0** |
