# LOA Blueprint - Build & Management Makefile

.PHONY: help setup start stop status test clean venv deps

# Variables
PYTHON := python3
PIP := $(PYTHON) -m pip
VENV := venv
VENV_BIN := $(VENV)/bin
DOCKER_COMPOSE := docker-compose -f blueprint/setup/docker-compose.yml

help: ## Show this help message
	@echo "LOA Blueprint Build System"
	@echo "=========================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

venv: ## Create virtual environment
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "Virtual environment created in $(VENV)"

deps: venv ## Install dependencies
	@echo "Installing dependencies..."
	$(VENV_BIN)/$(PIP) install --upgrade pip
	$(VENV_BIN)/$(PIP) install -r blueprint/setup/requirements.txt
	$(VENV_BIN)/$(PIP) install -r blueprint/setup/requirements-dev.txt
	$(VENV_BIN)/$(PIP) install -e ./blueprint

setup: deps ## Full project setup (venv, deps, and packages)
	@echo "Setup complete."

start: ## Start local services (Docker)
	@echo "Starting local services..."
	$(DOCKER_COMPOSE) up -d

stop: ## Stop local services
	@echo "Stopping local services..."
	$(DOCKER_COMPOSE) down

status: ## Check status of local services
	$(DOCKER_COMPOSE) ps

test: ## Run all tests
	@echo "Running tests..."
	./blueprint/run_tests.sh

clean: ## Clean up temporary files
	@echo "Cleaning up..."
	rm -rf $(VENV)
	rm -rf .pytest_cache
	rm -rf htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "Clean complete."
