document.addEventListener("DOMContentLoaded", function(){
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
            const outputEl = document.getElementById("output-" + playbook);
            outputEl.style.display = "block";
            outputEl.textContent = "Running, Please wait...";

            fetch("/run_playbook", {
                method: "POST",
                headers: {"Content-Type": "application/x-www-form-urlencoded"},
                body: "playbook=" + encodeURIComponent(playbook)
            })
            .then(res => res.json())
            .then(data => {
                setTimeout(() => {
                    outputEl.textContent = data.output || data.error;
                }, 1000);
            });
        });
    });

    // Show playbook content
    document.querySelectorAll(".show-btn").forEach(btn => {
        btn.addEventListener("click", function(){
            const playbook = btn.getAttribute("data-playbook");
            const outputEl = document.getElementById("output-" + playbook);
            outputEl.style.display = "block";
            outputEl.textContent = "Loading...";

            fetch("/show_playbook", {
                method: "POST",
                headers: {"Content-Type": "application/x-www-form-urlencoded"},
                body: "playbook=" + encodeURIComponent(playbook)
            })
            .then(res => res.json())
            .then(data => {
                outputEl.textContent = data.content || data.error || "Error fetching content.";
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
            fetch("/get_hosts")
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
            fetch("/get_hosts")
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
            fetch("/save_hosts", {
                method:"POST",
                headers: {"Content-Type": "application/x-www-form-urlencoded"},
                body: "content=" + encodeURIComponent(hostsContent.value)
            })
            .then(r => r.json())
            .then(data => {
                if(data.status === "ok") {
                    alert("Hosts saved.");
                } else if(data.error){
                    alert(data.error);
                }
            });
        });
    }

    // System status
    const statusBtn = document.getElementById("status-btn");
    const statusBox = document.getElementById("status-box");
    if(statusBtn && statusBox) {
        statusBtn.addEventListener("click", function(){
            fetch("/system_status")
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
            fetch("/clear_history", {method: "POST"})
            .then(r => r.json())
            .then(data => {
                if(data.status === "ok") {
                    alert("History cleared.");
                    location.reload();
                }
            });
        });
    }

    // Toggle dark mode
    const toggleDarkModeBtn = document.getElementById("toggle-dark-mode");
    if(toggleDarkModeBtn) {
        toggleDarkModeBtn.addEventListener("click", function(){
            fetch("/toggle_dark_mode", {method: "POST"})
            .then(r => r.json())
            .then(data => {
                location.reload();
            });
        });
    }
});