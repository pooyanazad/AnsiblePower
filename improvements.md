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

- [ ] 1. 🐳 Create `docker-compose.yml` with volume mounts for playbooks, data, logs, SSH keys
- [ ] 2. ✨ Add `/health` endpoint returning `{"status": "ok"}`
- [ ] 3. 🐳 Update Dockerfile HEALTHCHECK to use `/health`
- [ ] 4. 🎨 Add inline SVG favicon to `base.html`
- [ ] 5. 🔒 Add `timeout=300` to `subprocess.check_output` in `run_playbook`
- [ ] 6. 🎨 Add `{% block title %}` to `base.html` and set per-page titles
- [ ] 7. 🧹 Move `import shutil` from inside `_find_ansible_playbook()` to top of file
- [ ] 8. 🎨 Add toast container `<div>` to `base.html`
- [ ] 9. 🎨 Add `showToast(message, type)` function to `main.js`
- [ ] 10. 🎨 Add toast CSS (success, error, info, fade animation)
- [ ] 11. 🔒 Catch `subprocess.TimeoutExpired` and return friendly error message
- [ ] 12. 🎨 Replace `alert("Hosts saved.")` with `showToast()` in `main.js`
- [ ] 13. 🎨 Replace `alert("History cleared.")` with `showToast()` in `main.js`
- [ ] 14. 🎨 Replace `alert()` calls in `index.html` inline script with `showToast()`
- [ ] 15. 🧹 Move `from flask import Blueprint` to top-level imports
- [ ] 16. 🎨 Add CSS spinner animation to `styles.css`
- [ ] 17. 🎨 Show spinner instead of "Running, Please wait..." in `main.js`
- [ ] 18. 🔒 Add `X-Frame-Options: DENY` header via `@app.after_request`
- [ ] 19. 🎨 Disable Run button while playbook is executing
- [ ] 20. 🎨 Re-enable Run button and restore text when response arrives
- [ ] 21. 🧪 Rename `ut_ansiblePower.py` → `test_unit.py`
- [ ] 22. 🧪 Rename `qt_ansiblePower.py` → `test_quality.py`
- [ ] 23. 🧪 Rename `smoke_test.py` → `test_smoke.py`
- [ ] 24. 🧪 Update CI workflow to use new test filenames
- [ ] 25. 🎨 Add `confirm()` dialog before executing a playbook
- [ ] 26. 📝 Remove `pip install flask psutil` from README — requirements.txt covers it
- [ ] 27. 📝 Remove/update outdated screenshot reference in README
- [ ] 28. 📝 Add Docker quickstart section to README
- [ ] 29. 🧹 Replace module comment lines 2-3 with proper docstring
- [ ] 30. 🧹 Replace `CustomRotatingLogHandler` with stdlib `RotatingFileHandler`
- [ ] 31. 🧹 Delete unused `CustomRotatingLogHandler` class
- [ ] 32. 🎨 Add "Copy output to clipboard" button next to playbook output
- [ ] 33. 🎨 Show "✓ Copied" feedback for 2 seconds after copy
- [ ] 34. 🔒 Validate `update_playbooks_dir` — reject if `os.path.isdir()` is False
- [ ] 35. 🔒 Validate `update_playbooks_dir` — reject paths like `/etc`, `/proc`, `/sys`
- [ ] 36. 🎨 Move dark mode from Flask session to `localStorage`
- [ ] 37. 🎨 Read `localStorage` on page load and apply dark class immediately
- [ ] 38. 🎨 Toggle sun/moon icon with JS instead of Jinja
- [ ] 39. 🎨 Remove `fetch("/settings/toggle_dark_mode")` from toggle handler
- [ ] 40. 🧹 Split `requirements.txt` into runtime-only packages
- [ ] 41. 🧹 Create `requirements-dev.txt` with `-r requirements.txt` + test deps
- [ ] 42. 🧹 Update CI to `pip install -r requirements-dev.txt`
- [ ] 43. 🧹 Update Dockerfile to use runtime-only `requirements.txt`
- [ ] 44. 🎨 Truncate long output in history table — max-height 80px + "Show more"
- [ ] 45. 🎨 Add CSS for truncation expand/collapse
- [ ] 46. 🔒 Add regex filename validation in `run_playbook`
- [ ] 47. 🔒 Add same regex validation in `show_playbook`
- [ ] 48. 🧪 Create `tests/conftest.py` with shared Flask test client fixture
- [ ] 49. 🧪 Add temp directory and mock config fixtures
- [ ] 50. 🧪 Simplify test setup in existing test files using conftest
- [ ] 51. 🎨 Replace system status plain text with progress bars
- [ ] 52. 🎨 Color progress bars: green < 60%, yellow 60-80%, red > 80%
- [ ] 53. 🧹 Extract duplicate path-traversal logic into `_validate_playbook_path()`
- [ ] 54. 🧹 Reuse `_validate_playbook_path()` in `show_playbook`
- [ ] 55. 🎨 Add `confirm()` dialog before clearing history
- [ ] 56. 🎨 Change Clear History button from `btn-warning` to `btn-danger`
- [ ] 57. 🐳 Create `.env.example` with all supported env vars documented
- [ ] 58. 🎨 Add `transition: background-color 0.3s ease` to body and components
- [ ] 59. 🧪 Add test: `run_playbook` with valid playbook (mock subprocess)
- [ ] 60. 🧪 Add test: `run_playbook` subprocess failure returns error output
- [ ] 61. 🎨 Auto-detect OS dark mode with `matchMedia('prefers-color-scheme: dark')`
- [ ] 62. 🎨 Add search/filter input above playbook list
- [ ] 63. 🎨 Add JS to filter playbooks by name as you type
- [ ] 64. 🔒 Validate `update_hosts_file` — reject if `os.path.isfile()` is False
- [ ] 65. 🔒 Validate `update_hosts_file` — reject paths containing `..`
- [ ] 66. 🧹 Add custom 404 error page extending `base.html`
- [ ] 67. 🧹 Add custom 500 error page extending `base.html`
- [ ] 68. 🧹 Register `@app.errorhandler(404)` and `@app.errorhandler(500)`
- [ ] 69. 🎨 Add search/filter input above history table
- [ ] 70. 🎨 Add JS to filter history rows by text
- [ ] 71. 📝 Update LICENSE copyright year to 2024-2026
- [ ] 72. 🎨 Add mobile hamburger menu — sidebar links in `#navbarNav` collapse
- [ ] 73. 🎨 Add footer with version number and GitHub link to `base.html`
- [ ] 74. 🎨 Style footer for dark mode
- [ ] 75. 🎨 Improve active sidebar link: colored left border + background tint
- [ ] 76. 🎨 Style active sidebar link for dark mode
- [ ] 77. 🧪 Add test: `show_playbook` with valid playbook returns content
- [ ] 78. 🧪 Add test: `show_playbook` directory-as-playbook returns 400
- [ ] 79. 📝 Expand CONTRIBUTING.md with dev setup, test instructions, PR checklist
- [ ] 80. 🎨 Color-code history rows: green for `failed=0`, red for failed > 0
- [ ] 81. 🔒 Add `flask-limiter` to requirements
- [ ] 82. 🔒 Add rate limit `5/minute` on `/run_playbook`
- [ ] 83. 🧹 Extract `load_config`, `save_config` into `utils.py`
- [ ] 84. 🧹 Extract `load_history`, `save_history` into `utils.py`
- [ ] 85. 🧹 Extract `get_playbooks_dir`, `get_hosts_file` into `utils.py`
- [ ] 86. 🧹 Move constants (`BASE_DIR`, `CONFIG_FILE`, etc.) into `utils.py`
- [ ] 87. 🎨 Add empty state with icon when no playbooks exist
- [ ] 88. 🎨 Add "configure directory in Settings →" link in empty state
- [ ] 89. 🐳 Add `Makefile` with `run`, `test`, `lint`, `docker-build`, `docker-up`, `clean`
- [ ] 90. 🔒 Add `app.config['MAX_CONTENT_LENGTH'] = 5MB` for upload limit
- [ ] 91. 🔒 Add `@app.errorhandler(413)` for oversized uploads
- [ ] 92. 🎨 Color-code playbook run output: green ok, yellow changed, red failed
- [ ] 93. 🧪 Add test: `update_playbooks_dir` with valid directory
- [ ] 94. 🧪 Add test: `update_playbooks_dir` with nonexistent path returns 400
- [ ] 95. 🧹 Standardize all error responses to `{"error": "message"}` format
- [ ] 96. 🧹 Fix `update_playbooks_dir` response to match standard format
- [ ] 97. 🧹 Fix `update_hosts_file` response to match standard format
- [ ] 98. 🎨 Add relative timestamps ("5 minutes ago") in history with JS
- [ ] 99. 🎨 Keep original timestamp as tooltip on hover
- [ ] 100. 🧹 Add docstring to `load_config()` and `save_config()`
- [ ] 101. 🧹 Add docstring to `load_history()` and `save_history()`
- [ ] 102. 🧹 Add docstring to `run_playbook()` and `show_playbook()`
- [ ] 103. 🧹 Add docstrings to remaining route functions
- [ ] 104. 🎨 Add client-side pagination to history — 20 rows per page
- [ ] 105. 🎨 Add Previous/Next buttons and "Page X of Y" indicator
- [ ] 106. 🧹 Add `ruff` to requirements-dev
- [ ] 107. 🐳 Add lint job to CI running `ruff check`
- [ ] 108. 🧹 Create `ruff.toml` with `line-length = 120`
- [ ] 109. 🧹 Fix all ruff lint issues
- [ ] 110. 🎨 Add `Content-Security-Policy` header for known CDN sources
- [ ] 111. 🎨 Add `X-Content-Type-Options: nosniff` header
- [ ] 112. 🎨 Add `Referrer-Policy` header
- [ ] 113. 🎨 Add path validity indicator (✅/❌) next to playbooks dir input
- [ ] 114. ✨ Add `GET /settings/check_path?path=...` endpoint
- [ ] 115. 🎨 Debounce path check to 500ms on keystroke
- [ ] 116. 🧪 Add test: `save_hosts` writes content correctly
- [ ] 117. 🧪 Add test: `clear_history` empties history
- [ ] 118. 🧪 Add test: `system_status` returns cpu and memory
- [ ] 119. 🧪 Add test: `toggle_dark_mode` flips session value
- [ ] 120. 🎨 Add "Re-run" button on each history row
- [ ] 121. ✨ Add `DELETE /history/<index>` endpoint for single entry delete
- [ ] 122. 🎨 Add delete button (🗑) on each history row
- [ ] 123. 🧹 Create `create_app()` factory function
- [ ] 124. 🧹 Move blueprint registration inside `create_app()`
- [ ] 125. 🧹 Keep module-level `app = create_app()` for Gunicorn compat
- [ ] 126. 🎨 Reorganize settings page into Bootstrap tabs
- [ ] 127. 🎨 Tab sections: Hosts, System, Paths, Data
- [ ] 128. ✨ Add execution time tracking in `run_playbook`
- [ ] 129. ✨ Save `"duration"` field to history entries
- [ ] 130. 🎨 Show duration column in history table
- [ ] 131. 📝 Add CI status badge to README
- [ ] 132. 📝 Add license and Python version badges to README
- [ ] 133. 📝 Create `CHANGELOG.md` with v1.0.0
- [ ] 134. 🎨 Make history table headers clickable for sorting
- [ ] 135. 🎨 Toggle ascending/descending on repeated click
- [ ] 136. 🎨 Show sort direction arrow (▲/▼) on active column
- [ ] 137. 🎨 Replace "No history available." with icon + helpful message
- [ ] 138. 🧹 Add env var override `ANSIBLEPOWER_PLAYBOOKS_DIR`
- [ ] 139. 🧹 Add env var override `ANSIBLEPOWER_HOSTS_FILE`
- [ ] 140. 🎨 Add auto-refresh toggle for system status (poll every 5s)
- [ ] 141. ✨ Add disk usage to system status via `psutil.disk_usage('/')`
- [ ] 142. ✨ Add system uptime via `psutil.boot_time()`
- [ ] 143. 🎨 Format uptime as "2d 5h 30m" in JS
- [ ] 144. 🧪 Add test: `import_history` with valid JSON
- [ ] 145. 🧪 Add test: `import_history` with valid CSV
- [ ] 146. 🧪 Add test: `import_history` with unsupported file type returns 400
- [ ] 147. 🧪 Add test: `export_history` JSON format
- [ ] 148. 🧪 Add test: `export_history` CSV format
- [ ] 149. 🧹 Add `pre-commit` config with black, ruff, trailing-whitespace
- [ ] 150. 🧹 Run `black` on all Python files
- [ ] 151. 🎨 Add `aria-label` to Run, Show, dark mode, and other icon-only buttons
- [ ] 152. 🎨 Add `role="status"` and `aria-live="polite"` to output elements
- [ ] 153. 🎨 Add `:focus-visible` outline styles for all interactive elements
- [ ] 154. 🐳 Add pip caching with `actions/cache` to CI
- [ ] 155. 🐳 Add Python version matrix (3.9–3.12) to unit-tests CI job
- [ ] 156. 🐳 Add Docker build step to CI
- [ ] 157. 🎨 Define CSS custom properties at `:root` for all colors
- [ ] 158. 🎨 Override custom properties in `.dark` selector
- [ ] 159. 🎨 Replace all hardcoded colors with `var(--color-xxx)`
- [ ] 160. 🧹 Cap history at 1,000 entries — auto-trim in `save_history()`
- [ ] 161. 🎨 Add monospace font + dark background to hosts textarea
- [ ] 162. 🎨 Add line numbers next to hosts textarea
- [ ] 163. 🎨 Add "Reset" button to reload hosts from server
- [ ] 164. 🧹 Add type hints to all functions in `utils.py`
- [ ] 165. 🧹 Add type hints to all route functions
- [ ] 166. 🎨 Add breadcrumb nav to `base.html`
- [ ] 167. 🎨 Set breadcrumb in each child template
- [ ] 168. 🧹 Add `import re` to top of file
- [ ] 169. 🔒 Limit imported history to max 10,000 records
- [ ] 170. 🎨 Return file size and mtime from `homepage()` alongside filenames
- [ ] 171. 🎨 Show file size (KB) and last modified date below each playbook
- [ ] 172. 🎨 Add sort dropdown for playbooks: Name, Modified, Size
- [ ] 173. 🎨 Add sort JS logic using `data-*` attributes
- [ ] 174. 🎨 Show "Last run" timestamp from history next to each playbook
- [ ] 175. 🎨 Add "Collapse all / Expand all" toggle for playbook outputs
- [ ] 176. 🐳 Create `.github/dependabot.yml` for pip and actions
- [ ] 177. 🐳 Create `.github/pull_request_template.md`
- [ ] 178. 🐳 Create `.github/ISSUE_TEMPLATE/bug_report.md`
- [ ] 179. 🐳 Create `.github/ISSUE_TEMPLATE/feature_request.md`
- [ ] 180. 🧪 Add test: `run_playbook` timeout returns friendly error
- [ ] 181. 🧪 Add test: `_find_ansible_playbook` env override
- [ ] 182. 🧪 Add test: `_find_ansible_playbook` venv path
- [ ] 183. 🧪 Add test: `_find_ansible_playbook` fallback to PATH
- [ ] 184. 🧪 Add test: `/health` endpoint returns 200
- [ ] 185. 🧪 Add `pytest --cov` to CI with `--cov-fail-under=40`
- [ ] 186. 🧹 Create `routes/` directory with `__init__.py`
- [ ] 187. 🧹 Move `main_bp` routes to `routes/main.py`
- [ ] 188. 🧹 Move `history_bp` routes to `routes/history.py`
- [ ] 189. 🧹 Move `settings_bp` routes to `routes/settings.py`
- [ ] 190. 🧹 Import blueprints from route modules in `ansiblePower.py`
- [ ] 191. 🧪 Verify all tests pass after blueprint separation
- [ ] 192. 🎨 Add keyboard shortcut `/` to focus search box
- [ ] 193. 🎨 Add `Ctrl+D` to toggle dark mode
- [ ] 194. 🎨 Add `Escape` to close expanded outputs
- [ ] 195. 🎨 Add shortcut hint tooltip via `?` icon
- [ ] 196. 🧹 Split `main.js` into `playbook.js`
- [ ] 197. 🧹 Split `main.js` into `settings.js`
- [ ] 198. 🧹 Split `main.js` into `theme.js`
- [ ] 199. 🧹 Split `main.js` into `utils.js`
- [ ] 200. 🧹 Add `defer` to all `<script>` tags in `base.html`
- [ ] 201. 🧹 Create `pyproject.toml` with project metadata
- [ ] 202. 🧹 Add black + ruff config to `pyproject.toml`
- [ ] 203. ⚡ Add `Flask-Compress` for gzip compression
- [ ] 204. ⚡ Add HTTP caching headers for static files
- [ ] 205. ✨ Add `--check` dry-run button next to Run
- [ ] 206. ✨ Pass `--check` flag to subprocess when dry-run
- [ ] 207. ✨ Show "[DRY RUN]" badge on output, skip history save
- [ ] 208. ✨ Add verbose level selector (`-v`, `-vv`, `-vvv`)
- [ ] 209. ✨ Add `--extra-vars` input field for playbook runs
- [ ] 210. ✨ Add `--limit` host pattern input
- [ ] 211. ✨ Add playbook upload button + `POST /upload_playbook` endpoint
- [ ] 212. ✨ Validate upload: extension, filename regex, size < 1MB
- [ ] 213. ✨ Add playbook delete button + `POST /delete_playbook` endpoint
- [ ] 214. ✨ Apply path validation to delete endpoint
- [ ] 215. 📝 Create `docs/API.md` documenting all endpoints
- [ ] 216. ✨ Add "About" page with version, Python, Ansible, dependencies
- [ ] 217. ✨ Add "About" link to sidebar
- [ ] 218. 🎨 Add `@media print` stylesheet — hide sidebar, nav, buttons
- [ ] 219. ⚡ Self-host Bootstrap CSS/JS in `static/vendor/`
- [ ] 220. ⚡ Self-host FontAwesome in `static/vendor/`
- [ ] 221. 🧹 Add `mypy` to CI
- [ ] 222. ✨ Add dashboard page with summary widgets
- [ ] 223. ✨ Add dashboard link to sidebar
- [ ] 224. 🎨 Add in-browser playbook editor (CodeMirror)
- [ ] 225. ✨ Add `POST /save_playbook` endpoint
- [ ] 226. ✨ Add YAML syntax validation before save

---

## 🔮 Future Plans

### Real-time & Async
- Stream playbook output live using `subprocess.Popen` + Server-Sent Events
- "Stop running playbook" button (SIGTERM to subprocess)
- Concurrent playbook queue (threading or Celery)
- Scheduled playbook runs (APScheduler)

### Multi-host & Inventory
- Multiple inventory files — manage and switch between them
- Inventory selection per playbook run
- Host ping test (`ansible -m ping`)
- Visual inventory manager — form-based host/group editor

### Notifications & Integration
- Webhook notifications on playbook finish (Slack, email)
- Playbook favorites/bookmarks
- Playbook tags and categories

### Data & Storage
- Migrate history from JSON to SQLite
- File locking (`filelock`) for concurrent JSON writes
- Structured JSON logging for aggregators
- Request ID in log messages

### Framework Upgrades
- Bootstrap 4 → 5 (drops jQuery, modern grid)
- FontAwesome 5 → 6 (SVG, more icons)
- Gunicorn config file with worker tuning

### Advanced Testing
- Playwright end-to-end browser tests
- JavaScript unit tests (Jest/Vitest)
- Coverage badge via Codecov

### Deployment
- GitHub release workflow on version tags
- Helm chart for Kubernetes
- ARM Docker image for Raspberry Pi

---

## 📊 Progress

**0 / 226 done**
