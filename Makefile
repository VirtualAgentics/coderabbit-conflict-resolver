.PHONY: all help setup test lint format type-check clean install-dev install-docs docs build publish install-hooks

all: lint format type-check test build ## Default target - run all checks

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies and setup development environment
	@echo "Setting up development environment..."
	python -m venv .venv
	@echo "Virtual environment created. Activate it with:"
	@echo "  source .venv/bin/activate"
	@echo ""
	@echo "Then run: make install-dev"

install-dev: install-hooks ## Install development dependencies
	pip install --upgrade pip
	pip install -e ".[dev]"
	pre-commit install
	@echo "Development environment ready!"

install-docs: ## Install documentation dependencies
	pip install -r docs/requirements.txt

test: ## Run tests with coverage
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

test-fast: ## Run tests without coverage (faster)
	pytest tests/ -v

.ONESHELL:
lint: ## Run all linters
	set -e
	@echo "Running Black..."
	black --check src/ tests/
	@echo "Running Ruff..."
	ruff check src/ tests/
	@echo "Running MyPy..."
	mypy src/
	@echo "Running Bandit..."
	bandit -r src/ -f json -o bandit-report.json
	@echo "Running Safety..."
	safety check --json --save-json safety-report.json

format: ## Auto-format code with Black and Ruff
	black src/ tests/
	ruff check src/ tests/ --fix

type-check: ## Run type checking with MyPy
	mypy src/

security: ## Run security checks
	bandit -r src/ -f json -o bandit-report.json
	safety check --json --output safety-report.json

docs: ## Build documentation
	cd docs && make html

docs-serve: ## Serve documentation locally
	cd docs/_build/html && python -m http.server 8000

build: ## Build package
	python -m build

publish: ## Publish to PyPI (requires PyPI credentials)
	twine upload dist/*

clean: ## Clean build artifacts
	./scripts/clean.py

check-all: lint test security ## Run all checks (lint, test, security)

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	pre-commit autoupdate

ci: ## Run CI checks locally
	@echo "Running CI checks..."
	make lint
	make test
	make security
	@echo "All CI checks passed!"

install-hooks: ## Install git hooks for quality checks
	./scripts/install-hooks.sh

dev-setup: setup install-dev ## Complete development setup
	@echo "Development setup complete!"
	@echo "Run 'make check-all' to verify everything works."
