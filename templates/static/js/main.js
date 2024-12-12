document.addEventListener("DOMContentLoaded", function(){
    const sidebar = document.querySelector(".sidebar");
    const toggleBtn = document.getElementById("toggle-sidebar-btn");
    let sidebarVisible = true;

    if(toggleBtn) {
        toggleBtn.addEventListener("click", function(){
            if(sidebarVisible){
                sidebar.style.transform = "translateX(-200px)";
            } else {
                sidebar.style.transform = "translateX(0)";
            }
            sidebarVisible = !sidebarVisible;
        });
    }

    // Run playbook with a "Running for 1sec" message before showing output
    document.querySelectorAll(".run-btn").forEach(btn=>{
        btn.addEventListener("click", function(){
            const playbook = btn.getAttribute("data-playbook");
            const outputEl = document.getElementById("output-"+playbook);
            outputEl.style.display="block";
            outputEl.textContent = "Running, Please wait...";

            fetch("/run_playbook", {
                method: "POST",
                headers:{"Content-Type":"application/x-www-form-urlencoded"},
                body: "playbook="+encodeURIComponent(playbook)
            })
            .then(res=>res.json())
            .then(data=>{
                // Wait about 1 second to simulate running time
                setTimeout(() => {
                    if(data.output) {
                        outputEl.textContent = data.output;
                    } else if(data.error) {
                        outputEl.textContent = data.error;
                    }
                }, 1000);
            });
        });
    });

    // Show playbook content
    document.querySelectorAll(".show-btn").forEach(btn=>{
        btn.addEventListener("click", function(){
            const playbook = btn.getAttribute("data-playbook");
            const outputEl = document.getElementById("output-"+playbook);
            outputEl.style.display="block";
            outputEl.textContent = "Loading...";

            fetch("/show_playbook", {
                method: "POST",
                headers:{"Content-Type":"application/x-www-form-urlencoded"},
                body: "playbook="+encodeURIComponent(playbook)
            })
            .then(res=>res.json())
            .then(data=>{
                if(data.content) {
                    outputEl.textContent = data.content;
                } else {
                    outputEl.textContent = data.error || "Error fetching content.";
                }
            });
        });
    });

    // Settings page
    const showHostsBtn = document.getElementById("show-hosts-btn");
    const editHostsBtn = document.getElementById("edit-hosts-btn");
    const hostsBox = document.getElementById("hosts-box");
    const hostsContent = document.getElementById("hosts-content");
    const saveHostsBtn = document.getElementById("save-hosts-btn");
    const statusBtn = document.getElementById("status-btn");
    const statusBox = document.getElementById("status-box");
    const clearHistoryBtn = document.getElementById("clear-history-btn");
    const toggleDarkModeBtn = document.getElementById("toggle-dark-mode");
    const hostsError = document.getElementById("hosts-error");

    if(showHostsBtn && editHostsBtn && hostsBox && hostsContent && saveHostsBtn && hostsError) {
        showHostsBtn.addEventListener("click", function(){
            fetch("/get_hosts")
            .then(r=>r.json())
            .then(data=>{
                if(data.content) {
                    hostsError.textContent = "";
                    hostsContent.value = data.content;
                    hostsContent.setAttribute("readonly","readonly");
                    hostsBox.style.display = "block";
                    saveHostsBtn.style.display = "none";
                } else if(data.error) {
                    hostsBox.style.display="none";
                    hostsError.textContent = data.error;
                }
            });
        });

        editHostsBtn.addEventListener("click", function(){
            fetch("/get_hosts")
            .then(r=>r.json())
            .then(data=>{
                if(data.content) {
                    hostsError.textContent = "";
                    hostsContent.value = data.content;
                    hostsContent.removeAttribute("readonly");
                    hostsBox.style.display = "block";
                    saveHostsBtn.style.display = "inline-block";
                } else if(data.error) {
                    hostsBox.style.display="none";
                    hostsError.textContent = data.error;
                }
            });
        });

        saveHostsBtn.addEventListener("click", function(){
            fetch("/save_hosts", {
                method:"POST",
                headers:{"Content-Type":"application/x-www-form-urlencoded"},
                body:"content="+encodeURIComponent(hostsContent.value)
            })
            .then(r=>r.json())
            .then(data=>{
                if(data.status=="ok") {
                    alert("Hosts saved.");
                } else if(data.error){
                    alert(data.error);
                }
            });
        });
    }

    if(statusBtn && statusBox) {
        statusBtn.addEventListener("click", function(){
            fetch("/system_status")
            .then(r=>r.json())
            .then(data=>{
                statusBox.style.display="block";
                statusBox.textContent = "CPU: "+data.cpu+"% | Memory: "+data.memory+"%";
            });
        });
    }

    if(clearHistoryBtn) {
        clearHistoryBtn.addEventListener("click", function(){
            fetch("/clear_history", {method:"POST"})
            .then(r=>r.json())
            .then(data=>{
                if(data.status=="ok") {
                    alert("History cleared.");
                    location.reload();
                }
            });
        });
    }

    if(toggleDarkModeBtn) {
        toggleDarkModeBtn.addEventListener("click", function(){
            fetch("/toggle_dark_mode", {method:"POST"})
            .then(r=>r.json())
            .then(data=>{
                location.reload();
            });
        });
    }
});
