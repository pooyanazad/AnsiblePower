// task 53: Color-code Ansible playbook output lines.
// Returns an HTML string safe to assign to element.innerHTML.
function colorizeAnsibleOutput(text) {
    // Escape HTML to prevent XSS before we inject span tags.
    function escapeHtml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    var lines = text.split('\n');
    var result = lines.map(function(line) {
        var escaped = escapeHtml(line);
        var trimmed = line.trimStart();

        if (/^(fatal|failed|unreachable)[\s:\[]/i.test(trimmed) || /\b(?:failed|unreachable)=\d*[1-9]\d*\b/.test(trimmed)) {
            return '<span class="ap-out-fatal">' + escaped + '</span>';
        }
        if (/^PLAY RECAP\b/i.test(trimmed)) {
            return '<span class="ap-out-recap">' + escaped + '</span>';
        }
        if (/^PLAY \[/i.test(trimmed)) {
            return '<span class="ap-out-play">' + escaped + '</span>';
        }
        if (/^TASK \[/i.test(trimmed)) {
            return '<span class="ap-out-task">' + escaped + '</span>';
        }
        if (/^(ok|ok=)[\s:]/i.test(trimmed) || /\bok=\d+\b/.test(trimmed)) {
            return '<span class="ap-out-ok">' + escaped + '</span>';
        }
        if (/^changed[\s:]/i.test(trimmed) || /\bchanged=\d*[1-9]\d*\b/.test(trimmed)) {
            return '<span class="ap-out-changed">' + escaped + '</span>';
        }
        return escaped;
    });
    return result.join('\n');
}

// Only persisted lifecycle state determines outcome presentation.
function jobPresentation(job) {
    const outcomes = {
        queued: ['Queued', 'info'], running: ['Running', 'info'],
        succeeded: ['Succeeded', 'success'], failed: ['Failed', 'danger'],
        launch_error: ['Launch error', 'danger'], blocked: ['Blocked', 'danger'],
        timed_out: ['Timed out', 'danger'], canceled: ['Canceled', 'warning'],
        interrupted: ['Interrupted', 'warning'], uncertain: ['Uncertain', 'warning']
    };
    const [label, tone] = outcomes[job.state] || ['Unknown', 'secondary'];
    return {label, tone, active: job.state === 'queued' || job.state === 'running',
            toast: job.state === 'succeeded' ? 'success' : (tone === 'danger' ? 'error' : 'info')};
}

// Keep retries attached to one durable job, including history re-runs.
async function submitPlaybook(playbook, mode, csrfToken) {
    const pendingKey = 'pending-run:' + mode + ':' + playbook;
    const submissionId = sessionStorage.getItem(pendingKey) ||
        (window.crypto && crypto.randomUUID ? crypto.randomUUID() : Date.now() + '-' + Math.random().toString(36).slice(2));
    sessionStorage.setItem(pendingKey, submissionId);
    const response = await fetch('/run_playbook', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken,
            'Idempotency-Key': submissionId
        },
        body: 'playbook=' + encodeURIComponent(playbook) + '&execution_mode=' + encodeURIComponent(mode)
    });
    const data = await response.json();
    // A lost or uncertain server response must keep the key for reconciliation.
    if (response.status < 500) sessionStorage.removeItem(pendingKey);
    if (!response.ok) return {error: data.error || 'Could not submit run.', repair: data.repair};
    return data;
}

window.showToast = function(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `custom-toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    // Trigger reflow
    void toast.offsetWidth;
    toast.classList.add('show');

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode === container) {
                container.removeChild(toast);
            }
        }, 300);
    }, 3000);
};

document.addEventListener("DOMContentLoaded", function(){
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
    // Run playbook
    document.querySelectorAll(".run-btn").forEach(btn => {
        btn.addEventListener("click", function(){
            const playbook = btn.getAttribute("data-playbook");
            const index = btn.getAttribute("data-index");
            const wrapperEl = document.getElementById("wrapper-" + index);
            const outputEl  = document.getElementById("output-"  + index);
            const mode = document.getElementById("execution-mode").value;

            // Task 22: confirm before running to prevent accidental execution
            if (!confirm("Run '" + playbook + "' on " + (mode === "local" ? "this control node" : "the configured inventory") + "?")) {
                return;
            }

            // Show spinner in output area
            wrapperEl.hidden = false;
            const spinner = document.createElement('span');
            spinner.className = 'output-spinner';
            spinner.setAttribute('aria-hidden', 'true');
            outputEl.replaceChildren(spinner, document.createTextNode('Submitting ' + playbook + '…'));

            // Disable button and show spinner inside it
            const originalHTML = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="run-spinner"></span>Running&hellip;';

            submitPlaybook(playbook, mode, csrfToken)
            .then(data => {
                if (data.url) {
                    window.location.assign(data.url);
                    return;
                }
                setTimeout(() => {
                    // task 53: render color-coded output instead of plain text
                    outputEl.innerHTML = colorizeAnsibleOutput(data.output || data.error || '');
                    if (data.repair) {
                        const repair = document.createElement('a');
                        repair.href = data.repair.url;
                        repair.textContent = data.repair.label;
                        outputEl.appendChild(document.createTextNode('\n'));
                        outputEl.appendChild(repair);
                    }
                    btn.disabled = false;
                    btn.innerHTML = originalHTML;
                }, 1000);
            })
            .catch(err => {
                outputEl.textContent = "Error: Could not connect to server. " + err.message;
                btn.disabled = false;
                btn.innerHTML = originalHTML;
            });
        });
    });

    function showTimestamp(id, value, fallback) {
        const element = document.getElementById(id);
        const time = value ? new Date(value) : null;
        element.textContent = time && !Number.isNaN(time.getTime())
            ? new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'medium'}).format(time)
            : value || fallback;
        element.title = value || '';
    }

    const jobDetail = document.getElementById('job-detail');
    if (jobDetail) {
        let announced = false;
        const cancelForm = document.getElementById('job-cancel');
        const cancelButton = cancelForm.querySelector('button');
        const repair = document.getElementById('job-repair');
        const poll = async () => {
            try {
                const response = await fetch(jobDetail.dataset.statusUrl, {headers: {'Accept': 'application/json'}});
                if (!response.ok) throw new Error('Could not read run status. Refresh to try again.');
                const job = await response.json();
                const view = jobPresentation(job);
                const badge = document.getElementById('job-state');
                badge.textContent = view.label;
                badge.className = 'badge badge-' + view.tone;
                showTimestamp('job-started', job.started_at, 'Not started');
                showTimestamp('job-finished', job.finished_at, '—');
                const duration = document.getElementById('job-duration');
                duration.textContent = job.duration == null ? '—' : Number(Number(job.duration).toFixed(2)) + ' s';
                duration.title = job.duration == null ? '' : job.duration + ' s';
                document.getElementById('job-exit').textContent = job.exit_code == null ? 'Unknown' : job.exit_code;
                const emptyOutput = view.active ? (job.state === 'running' ? 'Playbook is running…' : 'Waiting for the runner…') : 'No output recorded.';
                document.getElementById('job-output').innerHTML = colorizeAnsibleOutput(job.output || emptyOutput);
                document.getElementById('job-review').hidden = !job.needs_review;
                cancelForm.hidden = !view.active;
                if (repair) repair.hidden = job.state !== 'blocked';
                cancelButton.disabled = !!job.cancel_requested;
                cancelButton.textContent = job.cancel_requested ? 'Cancellation requested…' : 'Cancel run';
                if (view.active) {
                    setTimeout(poll, 1000);
                } else if (!announced) {
                    showToast(view.label + ': ' + job.playbook, view.toast);
                    announced = true;
                }
            } catch (error) {
                showToast(error.message, 'error');
                setTimeout(poll, 3000);
            }
        };
        cancelForm.addEventListener('submit', async event => {
            event.preventDefault();
            cancelButton.disabled = true;
            try {
                const response = await fetch(cancelForm.action, {
                    method: 'POST', headers: {'X-CSRFToken': csrfToken, 'Accept': 'application/json'},
                    body: new FormData(cancelForm)
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Could not cancel run.');
                cancelButton.textContent = 'Cancellation requested…';
                showToast(data.state === 'canceled' ? 'Run canceled.' : 'Cancellation requested.', 'info');
            } catch (error) {
                showToast(error.message, 'error');
                cancelButton.disabled = false;
            }
        });
        poll();
    }


    // Show playbook content
    document.querySelectorAll(".show-btn").forEach(btn => {
        btn.addEventListener("click", function(){
            const playbook = btn.getAttribute("data-playbook");
            const index = btn.getAttribute("data-index");
            const wrapperEl = document.getElementById("wrapper-" + index);
            const outputEl  = document.getElementById("output-"  + index);
            const expanded = btn.getAttribute('aria-expanded') === 'true';
            wrapperEl.hidden = expanded;
            btn.setAttribute('aria-expanded', String(!expanded));
            btn.querySelector('span').textContent = expanded ? 'View YAML' : 'Hide YAML';
            if (expanded) return;

            outputEl.textContent = 'Loading…';

            fetch("/show_playbook", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": csrfToken
                },
                body: "playbook=" + encodeURIComponent(playbook)
            })
            .then(res => res.json())
            .then(data => {
                outputEl.textContent = data.content || data.error || "Error fetching content.";
            })
            .catch(err => {
                outputEl.textContent = "Error: Could not connect to server. " + err.message;
            });
        });
    });

    // Copy-to-clipboard for playbook output (improvement #32)
    document.querySelectorAll(".copy-output-btn").forEach(btn => {
        btn.addEventListener("click", function() {
            const index    = btn.getAttribute("data-index");
            const outputEl = document.getElementById("output-" + index);
            const text     = outputEl.textContent || "";

            if (!text.trim()) return;

            if (!navigator.clipboard) {
                showToast('Select the output to copy it manually.', 'info');
                return;
            }

            navigator.clipboard.writeText(text).then(() => {
                btn.textContent = 'Copied';
                setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
            }).catch(() => showToast('Could not copy. Select the output to copy it manually.', 'error'));
        });
    });

    const settingsNav = document.getElementById('settings-sections');
    if (settingsNav) {
        const links = [...settingsNav.querySelectorAll('a')];
        function showSettingsSection() {
            const active = links.find(link => link.hash === window.location.hash) || links[0];
            links.forEach(link => {
                const selected = link === active;
                if (selected) link.setAttribute('aria-current', 'location');
                else link.removeAttribute('aria-current');
                document.getElementById(link.hash.slice(1)).hidden = !selected;
            });
        }
        window.addEventListener('hashchange', showSettingsSection);
        showSettingsSection();
    }

    // Inventory editor
    const showHostsBtn = document.getElementById('show-hosts-btn');
    const editHostsBtn = document.getElementById('edit-hosts-btn');
    const hostsBox = document.getElementById('hosts-box');
    const hostsContent = document.getElementById('hosts-content');
    const saveHostsBtn = document.getElementById('save-hosts-btn');
    const hostsError = document.getElementById('hosts-error');

    if (hostsBox) {
        async function loadHosts(editing) {
            showHostsBtn.disabled = editHostsBtn.disabled = true;
            try {
                const response = await fetch('/settings/get_hosts');
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Could not read the inventory.');
                hostsError.textContent = '';
                hostsContent.value = data.content;
                hostsContent.readOnly = !editing;
                hostsBox.hidden = false;
                saveHostsBtn.hidden = !editing;
                if (editing) hostsContent.focus();
            } catch (error) {
                hostsBox.hidden = true;
                hostsError.textContent = error.message;
            } finally {
                showHostsBtn.disabled = editHostsBtn.disabled = false;
            }
        }

        showHostsBtn.addEventListener('click', () => loadHosts(false));
        editHostsBtn.addEventListener('click', () => loadHosts(true));
        saveHostsBtn.addEventListener('click', async () => {
            saveHostsBtn.disabled = true;
            try {
                const response = await fetch('/settings/save_hosts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': csrfToken
                    },
                    body: new URLSearchParams({content: hostsContent.value})
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Could not save the inventory.');
                showToast(data.message || 'Inventory saved.', 'success');
            } catch (error) {
                showToast(error.message, 'error');
            } finally {
                saveHostsBtn.disabled = false;
            }
        });
    }

    const statusBtn = document.getElementById('status-btn');
    const statusBox = document.getElementById('status-box');
    if (statusBtn) {
        statusBtn.addEventListener('click', async () => {
            statusBtn.disabled = true;
            statusBox.textContent = 'Reading system metrics…';
            try {
                const response = await fetch('/settings/system_status');
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Could not read system metrics.');

                statusBox.innerHTML = [['CPU', data.cpu], ['Memory', data.memory]].map(([label, value]) => {
                    const percent = Math.max(0, Math.min(100, Number(value) || 0)).toFixed(1);
                    const tone = percent < 60 ? 'success' : percent < 80 ? 'warning' : 'danger';
                    return '<div><div class="metric-label"><span>' + label + '</span><strong>' + percent + '%</strong></div>'
                        + '<div class="progress"><div class="progress-bar bg-' + tone + '" role="progressbar" '
                        + 'style="width:' + percent + '%" aria-label="' + label + '" aria-valuenow="' + percent + '" '
                        + 'aria-valuemin="0" aria-valuemax="100"></div></div></div>';
                }).join('');
            } catch (error) {
                statusBox.textContent = error.message;
            } finally {
                statusBtn.disabled = false;
            }
        });
    }

    // Clear history
    const clearHistoryBtn = document.getElementById("clear-history-btn");
    if(clearHistoryBtn) {
        clearHistoryBtn.addEventListener("click", function(){
            // Task 23: confirm before clearing — destructive action
            if (!confirm("Delete all history? This cannot be undone.")) {
                return;
            }
            fetch("/settings/clear_history", {
                method: "POST",
                headers: {"X-CSRFToken": csrfToken}
            })
            .then(r => r.json())
            .then(data => {
                if(data.status === "ok") {
                    showToast(data.message || "History cleared.", "success");
                    setTimeout(() => location.reload(), 1000);
                } else if(data.error) {
                    showToast(data.error, "error");
                }
            });
        });
    }

    const toggleDarkModeBtn = document.getElementById('toggle-dark-mode');
    if (toggleDarkModeBtn) {
        const label = document.getElementById('dark-mode-label');
        const root = document.documentElement;
        function syncThemeLabel() {
            label.textContent = root.classList.contains('dark') ? 'Light mode' : 'Dark mode';
        }
        toggleDarkModeBtn.addEventListener('click', () => {
            const isDark = root.classList.toggle('dark');
            try { localStorage.setItem('darkMode', String(isDark)); } catch { /* Theme still applies. */ }
            syncThemeLabel();
        });
        syncThemeLabel();
    }

    // Playbooks directory form — used on index page (prompt_for_dir) AND settings page
    const playbooksDirForm = document.getElementById("playbooks-dir-form");
    if(playbooksDirForm) {
        playbooksDirForm.addEventListener("submit", function(e) {
            e.preventDefault();
            const playbooksDir = document.getElementById("playbooks_dir").value;

            fetch("/settings/update_playbooks_dir", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": csrfToken
                },
                body: "playbooks_dir=" + encodeURIComponent(playbooksDir)
            })
            .then(r => r.json())
            .then(data => {
                if(data.status === "ok") {
                    // On the index page, reload so the playbook list appears
                    if(window.location.pathname === "/" || window.location.pathname === "") {
                        window.location.reload();
                    } else {
                        showToast(data.message, "success");
                    }
                } else {
                    showToast(data.error || "Error updating directory.", "error");
                }
            })
            .catch(err => {
                showToast("An error occurred while updating the playbooks directory.", "error");
            });
        });
    }

    // Playbook search filter (index page)
    const playbookSearch = document.getElementById("playbook-search");
    if(playbookSearch) {
        playbookSearch.addEventListener("input", function() {
            const query = this.value.toLowerCase();
            const items = document.querySelectorAll("#playbook-list .playbook-item");
            let anyVisible = false;
            items.forEach(function(item) {
                const name = item.querySelector('.playbook-name').textContent.toLowerCase();
                const show = name.includes(query);
                item.hidden = !show;
                if(show) anyVisible = true;
            });
            const noMatch = document.getElementById("no-playbook-match");
            if (noMatch) noMatch.hidden = anyVisible;
        });
    }

    // Settings: Hosts file path form
    const hostsFileForm = document.getElementById("hosts-file-form");
    if(hostsFileForm) {
        hostsFileForm.addEventListener("submit", function(e) {
            e.preventDefault();
            const hostsFile = document.getElementById("hosts_file").value;

            fetch("/settings/update_hosts_file", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": csrfToken
                },
                body: "hosts_file=" + encodeURIComponent(hostsFile)
            })
            .then(r => r.json())
            .then(data => {
                if(data.status === "ok") {
                    showToast(data.message, "success");
                } else {
                    showToast(data.error, "error");
                }
            })
            .catch(err => {
                showToast("An error occurred while updating the hosts file path.", "error");
            });
        });
    }

    // Task 39: History output Show more / Show less toggle
    document.querySelectorAll('.history-output').forEach(function(pre) {
        var wrapper = pre.closest('.history-output-wrapper');
        if (!wrapper) return;
        var btn = wrapper.querySelector('.history-toggle-btn');
        if (!btn) return;

        // The output wrapper is horizontally scrollable on narrow screens.
        if (pre.scrollHeight > pre.clientHeight) {
            btn.hidden = false;
            btn.addEventListener('click', function() {
                var expanded = pre.classList.toggle('expanded');
                btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
                btn.textContent = expanded ? 'Show less' : 'Show more';
            });
        }
    });

    // Task 44 + 57: History search and client-side pagination (20 rows/page)
    var HISTORY_PAGE_SIZE = 20;
    var historyPage = 1;
    var historySearch = document.getElementById('history-search');

    function renderHistoryPage() {
        var rows = Array.prototype.slice.call(document.querySelectorAll('#history-tbody .history-row'));
        if (!historySearch) return;
        var query = historySearch ? historySearch.value.toLowerCase().trim() : '';
        var matched = rows.filter(function(row) {
            var playbook = (row.cells[1] ? row.cells[1].textContent : '').toLowerCase();
            var output = row.querySelector('.history-output').textContent.toLowerCase();
            return !query || playbook.includes(query) || output.includes(query);
        });
        var totalPages = Math.max(1, Math.ceil(matched.length / HISTORY_PAGE_SIZE));
        historyPage = Math.min(Math.max(historyPage, 1), totalPages);
        var start = (historyPage - 1) * HISTORY_PAGE_SIZE;
        var visible = matched.slice(start, start + HISTORY_PAGE_SIZE);
        rows.forEach(function(row) {
            row.hidden = !visible.includes(row);
        });

        var noMatch = document.getElementById('history-no-match');
        if (noMatch) {
            noMatch.hidden = matched.length > 0;
            noMatch.textContent = query ? 'No runs match your search.' : 'No history yet.';
        }

        var pager = document.getElementById('history-pagination');
        if (pager) {
            pager.hidden = matched.length <= HISTORY_PAGE_SIZE;
            document.getElementById('history-page-info').textContent = 'Page ' + historyPage + ' of ' + totalPages;
            document.getElementById('history-prev').disabled = historyPage <= 1;
            document.getElementById('history-next').disabled = historyPage >= totalPages;
        }
    }

    if (historySearch) {
        historySearch.addEventListener('input', function() {
            historyPage = 1;
            renderHistoryPage();
        });
    }
    var historyPrev = document.getElementById('history-prev');
    var historyNext = document.getElementById('history-next');
    if (historyPrev) historyPrev.addEventListener('click', function() { historyPage--; renderHistoryPage(); });
    if (historyNext) historyNext.addEventListener('click', function() { historyPage++; renderHistoryPage(); });
    // Task 58: sortable history columns (click header to toggle ▲ / ▼)
    var historySort = { col: null, dir: 'asc' };
    document.querySelectorAll('#history-table th.history-sortable').forEach(function(th) {
        th.addEventListener('click', function() {
            var col = parseInt(th.getAttribute('data-sort-col'), 10);
            historySort.dir = (historySort.col === col && historySort.dir === 'asc') ? 'desc' : 'asc';
            historySort.col = col;
            var isTime = th.getAttribute('data-sort-type') === 'time';
            var tbody = document.getElementById('history-tbody');
            var rows = Array.prototype.slice.call(tbody.querySelectorAll('.history-row'));
            var factor = historySort.dir === 'asc' ? 1 : -1;
            function keyOf(row) {
                var cell = row.cells[col];
                if (isTime) return new Date((cell.getAttribute('data-time') || '').replace(' ', 'T')).getTime() || 0;
                return cell.textContent.trim().toLowerCase();
            }
            rows.sort(function(a, b) {
                var ka = keyOf(a), kb = keyOf(b);
                return (ka < kb ? -1 : ka > kb ? 1 : 0) * factor;
            });
            rows.forEach(function(row) { tbody.appendChild(row); });
            document.querySelectorAll('#history-table th.history-sortable').forEach(function(h) {
                var ind = h.querySelector('.sort-indicator');
                if (ind) ind.textContent = (h === th) ? (historySort.dir === 'asc' ? '▲' : '▼') : '';
                if (h === th) h.setAttribute('aria-sort', historySort.dir === 'asc' ? 'ascending' : 'descending');
                else h.removeAttribute('aria-sort');
            });
            historyPage = 1;
            renderHistoryPage();
        });
    });
    // Task 59: re-run a playbook from its history row
    document.querySelectorAll('.history-rerun-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var playbook = btn.getAttribute('data-playbook');
            const selector = document.getElementById('history-execution-mode');
            const mode = selector ? selector.value : 'inventory';
            if (!confirm("Run '" + playbook + "' again on " + (mode === 'local' ? 'this control node' : 'the configured inventory') + "?")) return;
            var originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = 'Running…';
            submitPlaybook(playbook, mode, csrfToken)
            .then(function(data) {
                if (data.url) {
                    showToast('Opening run status…', 'info');
                    window.location.assign(data.url);
                } else {
                    showToast(data.error || 'Could not submit run.', 'error');
                    btn.disabled = false;
                    btn.textContent = originalText;
                }
            })
            .catch(function(error) {
                showToast(error.message || 'Could not connect to server.', 'error');
                btn.disabled = false;
                btn.textContent = originalText;
            });
        });
    });

    // Task 60: delete a single history entry from its history row
    document.querySelectorAll('.history-delete-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var recordId = btn.getAttribute('data-record-id');
            if (!confirm('Delete this history entry? This cannot be undone.')) return;
            btn.disabled = true;
            fetch('/history/delete/' + encodeURIComponent(recordId), {
                method: 'POST',
                headers: {'X-CSRFToken': csrfToken}
            })
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data.status === 'ok') {
                    showToast('History entry deleted.', 'success');
                    // Remove the row from the DOM without a full page reload
                    var row = btn.closest('tr');
                    if (row) row.remove();
                    renderHistoryPage();
                } else {
                    showToast(data.error || 'Could not delete entry.', 'error');
                    btn.disabled = false;
                }
            })
            .catch(function() {
                showToast('Could not connect to server.', 'error');
                btn.disabled = false;
            });
        });
    });

    const importForm = document.getElementById('import-history-form');
    if (importForm) {
        importForm.addEventListener('submit', async event => {
            event.preventDefault();
            const button = importForm.querySelector('button[type="submit"]');
            button.disabled = true;
            try {
                const response = await fetch(importForm.action, {method: 'POST', body: new FormData(importForm)});
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Could not import history.');
                showToast(data.message, 'success');
                setTimeout(() => window.location.reload(), 1000);
            } catch (error) {
                showToast(error.message, 'error');
                button.disabled = false;
            }
        });
    }

    renderHistoryPage();

    // Task 56: relative timestamps ("5 minutes ago") with the original as tooltip
    function timeAgo(dateStr) {
        var then = new Date(String(dateStr).replace(' ', 'T'));
        if (isNaN(then.getTime())) return dateStr;
        var seconds = Math.floor((Date.now() - then.getTime()) / 1000);
        if (seconds < 5) return 'just now';
        var units = [
            ['year', 31536000], ['month', 2592000], ['day', 86400],
            ['hour', 3600], ['minute', 60], ['second', 1]
        ];
        for (var i = 0; i < units.length; i++) {
            var n = Math.floor(seconds / units[i][1]);
            if (n >= 1) return n + ' ' + units[i][0] + (n > 1 ? 's' : '') + ' ago';
        }
        return 'just now';
    }

    function refreshTimestamps() {
        document.querySelectorAll('.history-time, .recent-time').forEach(function(element) {
            const raw = element.getAttribute('datetime') || element.getAttribute('data-time');
            element.title = raw;
            element.textContent = timeAgo(raw);
        });
    }
    refreshTimestamps();
    if (document.querySelector('.history-time, .recent-time')) setInterval(refreshTimestamps, 60000);
});
