FROM python:3.12-slim

# Install Ansible and SSH client (needed to run playbooks against remote hosts)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ansible \
        openssh-client \
        sshpass \
    && rm -rf /var/lib/apt/lists/*

# Run as non-root for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Install Python dependencies first (separate layer for Docker cache —
# only re-runs when requirements.txt changes, not on every code change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories and set ownership
RUN mkdir -p data logs playbooks && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

# Use Gunicorn instead of Flask dev server
# 2 workers, 120s timeout for long-running playbook executions
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "ansiblePower:app"]
