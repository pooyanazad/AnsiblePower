# AnsiblePower — developer convenience targets
# Usage: make <target>
# Requires: Python 3.9+, pip, Docker, docker compose

.PHONY: help run test lint docker-build docker-up docker-down clean

# Default target — print help
help:
	@echo ""
	@echo "  ⚡ AnsiblePower — available make targets"
	@echo ""
	@echo "  make run           Start the app locally (Flask dev server)"
	@echo "  make test          Run the full test suite with pytest"
	@echo "  make lint          Run flake8 on application source files"
	@echo "  make docker-build  Build the Docker image"
	@echo "  make docker-up     Build and start via docker compose (detached)"
	@echo "  make docker-down   Stop and remove docker compose containers"
	@echo "  make clean         Remove __pycache__, .pyc files, and coverage data"
	@echo ""

# ---------------------------------------------------------------------------
# Local development
# ---------------------------------------------------------------------------

## Install dev dependencies into the active Python environment
install-dev:
	pip install -r requirements-dev.txt

## Start the Flask development server (auto-reloads on code changes)
run:
	FLASK_DEBUG=true python ansiblePower.py

## Run the full pytest test suite with coverage report
test:
	pytest tests/ -v --tb=short

## Run flake8 linter on the main source files
lint:
	flake8 ansiblePower.py utils.py --max-line-length=120 --extend-ignore=E501

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

## Build the Docker image tagged as ansiblepower:latest
docker-build:
	docker build -t ansiblepower:latest .

## Build the image (if needed) and start all services in the background
docker-up:
	docker compose up -d --build

## Stop and remove all docker compose containers (data volumes preserved)
docker-down:
	docker compose down

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

## Remove Python bytecode caches and coverage artefacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -f .coverage
	rm -rf .pytest_cache htmlcov
