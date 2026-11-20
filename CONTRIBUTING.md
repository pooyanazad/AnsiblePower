# Contributing to ansible-power

Check the open issues and comment on the one you want to work on. Wait for a
maintainer to assign it before starting. If you’re new to open source, pick one
issue labeled `good first issue`. After your first pull request merges, leave
other issues with that label for new contributors. [Open issues](https://github.com/pooyanazad/ansible-power/issues)

## Develop locally

Fork the repository and create a branch for your change. Use Python 3.12 and
install the development dependencies in a virtual environment. Install Node.js
to run the browser JavaScript regression tests invoked by pytest.

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Use `make run` and `make worker` in separate terminals to work on the app locally.
For changes to deployment, verify startup with Docker Compose as well. [Quick start](README.md#quick-start)

## Open a pull request

Use the pull request template. Link the issue, describe what changed, and report
the checks you ran. Include screenshots for UI changes when they help reviewers.
