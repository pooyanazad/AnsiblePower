AnsiblePower

AnsiblePower is a lightweight web interface inspired by Ansible Tower. It allows users to manage Ansible playbooks, view and edit host configurations, and monitor system performance via a modern and intuitive web interface.
Features

    Homepage:
        Lists available Ansible playbooks.
        Buttons to:
            Run: Executes a playbook and shows the output.
            Show: Displays the content of a playbook.

    History:
        Displays a table of previously run playbooks with timestamps and actions.

    Settings:
        Hosts Management:
            View and edit /etc/ansible/hosts file.
            Shows appropriate error messages if the user lacks read/write permissions.
        Master Node Status:
            Displays CPU and memory usage.
        Clear History:
            Option to delete all playbook execution history.
        Dark Mode Toggle:
            Switch between light and dark modes.

    User-Friendly Interface:
        Modern design with rounded buttons, smooth animations, and responsive layout.
        Sidebar with toggle functionality for better navigation.

Requirements

    Python 3.x
    Flask (pip install flask)
    psutil (pip install psutil)
    Ansible installed and accessible via ansible-playbook.

Installation

    Clone the repository:

git clone https://github.com/your-repo/ansiblepower.git
cd ansiblepower

Install dependencies:

pip install flask psutil

Set up directories:

    Ensure your playbooks are in /home/pooyan/ansible/playbooks.
    Ensure /etc/ansible/hosts exists and has the necessary permissions.

(Optional) Initialize the history file:

    mkdir data
    echo "[]" > data/history.json

Running the Application

    Start the Flask server:

python app.py

Access the app in your browser:

    http://127.0.0.1:5000

Notes

    If you encounter permission issues with /etc/ansible/hosts, adjust the file permissions:

# Add read permission
chmod +r /etc/ansible/hosts

# Add write permission
chmod +w /etc/ansible/hosts

Make sure ansible-playbook is installed and available in your system's PATH.
