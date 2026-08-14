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
    // Optional: Sidebar toggle functionality if you add a toggle button.
    const toggleBtn = document.getElementById("toggle-sidebar-btn");
    if(toggleBtn) {
        toggleBtn.addEventListener("click", function(){
            const sidebar = document.querySelector(".sidebar");
            sidebar.style.display = (sidebar.style.display === "none" || sidebar.style.display === "") ? "block" : "none";
        });
    }

    // Run playbook
    document.querySelectorAll(".run-btn").forEach(btn => {
        btn.addEventListener("click", function(){
            const playbook = btn.getAttribute("data-playbook");
            const index = btn.getAttribute("data-index");
            const outputEl = document.getElementById("output-" + index);

            // Task 22: confirm before running to prevent accidental execution
            if (!confirm("Run '" + playbook + "'?")) {
                return;
            }

            // Show spinner in output area
            outputEl.style.display = "block";
            outputEl.innerHTML =
                '<span class="output-spinner-wrapper">' +
                  '<span class="output-spinner"></span>' +
                  'Running <strong>' + playbook + '</strong>&hellip; please wait' +
                '</span>';

            // Disable button and show spinner inside it
            const originalHTML = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="run-spinner"></span>Running&hellip;';

            fetch("/run_playbook", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": csrfToken
                },
                body: "playbook=" + encodeURIComponent(playbook)
            })
            .then(res => res.json())
            .then(data => {
                setTimeout(() => {
                    outputEl.textContent = data.output || data.error;
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


    // Show playbook content
    document.querySelectorAll(".show-btn").forEach(btn => {
        btn.addEventListener("click", function(){
            const playbook = btn.getAttribute("data-playbook");
            const index = btn.getAttribute("data-index");
            const outputEl = document.getElementById("output-" + index);
            outputEl.style.display = "block";
            outputEl.textContent = "Loading...";

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

    // Hosts handling
    const showHostsBtn = document.getElementById("show-hosts-btn");
    const editHostsBtn = document.getElementById("edit-hosts-btn");
    const hostsBox = document.getElementById("hosts-box");
    const hostsContent = document.getElementById("hosts-content");
    const saveHostsBtn = document.getElementById("save-hosts-btn");
    const hostsError = document.getElementById("hosts-error");

    if(showHostsBtn && editHostsBtn && hostsBox && hostsContent && saveHostsBtn && hostsError) {
        showHostsBtn.addEventListener("click", function(){
            fetch("/settings/get_hosts")
            .then(r => r.json())
            .then(data => {
                if(data.content) {
                    hostsError.textContent = "";
                    hostsContent.value = data.content;
                    hostsContent.setAttribute("readonly", "readonly");
                    hostsBox.style.display = "block";
                    saveHostsBtn.style.display = "none";
                } else if(data.error) {
                    hostsBox.style.display = "none";
                    hostsError.textContent = data.error;
                }
            });
        });

        editHostsBtn.addEventListener("click", function(){
            fetch("/settings/get_hosts")
            .then(r => r.json())
            .then(data => {
                if(data.content) {
                    hostsError.textContent = "";
                    hostsContent.value = data.content;
                    hostsContent.removeAttribute("readonly");
                    hostsBox.style.display = "block";
                    saveHostsBtn.style.display = "inline-block";
                } else if(data.error) {
                    hostsBox.style.display = "none";
                    hostsError.textContent = data.error;
                }
            });
        });

        saveHostsBtn.addEventListener("click", function(){
            fetch("/settings/save_hosts", {
                method:"POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": csrfToken
                },
                body: "content=" + encodeURIComponent(hostsContent.value)
            })
            .then(r => r.json())
            .then(data => {
                if(data.status === "ok") {
                    showToast("Hosts saved successfully.", "success");
                } else if(data.error){
                    showToast(data.error, "error");
                }
            });
        });
    }

    // System status
    const statusBtn = document.getElementById("status-btn");
    const statusBox = document.getElementById("status-box");
    if(statusBtn && statusBox) {
        statusBtn.addEventListener("click", function(){
            fetch("/settings/system_status")
            .then(r => r.json())
            .then(data => {
                statusBox.style.display = "block";
                statusBox.textContent = "CPU: " + data.cpu + "% | Memory: " + data.memory + "%";
            });
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
                    showToast("History cleared.", "success");
                    setTimeout(() => location.reload(), 1000);
                }
            });
        });
    }

    // Toggle dark mode
    const toggleDarkModeBtn = document.getElementById("toggle-dark-mode");
    if(toggleDarkModeBtn) {
        toggleDarkModeBtn.addEventListener("click", function(){
            fetch("/settings/toggle_dark_mode", {
                method: "POST",
                headers: {"X-CSRFToken": csrfToken}
            })
            .then(r => r.json())
            .then(data => {
                location.reload();
            });
        });
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
                const name = item.querySelector("h5").textContent.toLowerCase();
                const show = name.includes(query);
                item.style.display = show ? "" : "none";
                if(show) anyVisible = true;
            });
            const noMatch = document.getElementById("no-playbook-match");
            if(noMatch) noMatch.style.display = anyVisible ? "none" : "";
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
});