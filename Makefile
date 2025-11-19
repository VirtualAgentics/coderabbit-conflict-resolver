.PHONY: all help setup test test-fuzz test-fuzz-ci test-fuzz-extended lint format type-check clean install-dev install-docs docs build publish install-hooks

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

test-fuzz: ## Run property-based fuzzing tests (dev profile: 50 examples)
	HYPOTHESIS_PROFILE=dev pytest tests/ -m fuzz -v --tb=short --no-cov

test-fuzz-ci: ## Run fuzzing tests with CI profile (100 examples)
	HYPOTHESIS_PROFILE=ci pytest tests/ -m fuzz -v --tb=short --no-cov

test-fuzz-extended: ## Run extended fuzzing tests (1000 examples)
	HYPOTHESIS_PROFILE=fuzz pytest tests/ -m fuzz -v --tb=short --no-cov

test-all: ## Run all tests including fuzzing
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing -v

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
	@echo "Running Markdownlint..."
	pre-commit run markdownlint-cli2 --all-files
	@echo "✅ Linting complete (dependency scanning handled by Renovate)"

lint-markdown: ## Run markdown linting
	@echo "Running Markdownlint..."
	@if [ -d .venv ]; then \
		. .venv/bin/activate && pre-commit run markdownlint-cli2 --all-files; \
	else \
		pre-commit run markdownlint-cli2 --all-files; \
	fi

format: ## Auto-format code with Black and Ruff
	black src/ tests/
	ruff check src/ tests/ --fix

type-check: ## Run type checking with MyPy
	mypy src/

security: ## Run security checks (source code + dependencies)
	set -e
	@echo "Running Bandit (source code analysis)..."
	bandit -r src/ -f json -o bandit-report.json
	@echo "Note: Dependency vulnerability scanning runs in CI via pip-audit"

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

check-all: lint test test-fuzz security ## Run all checks (lint, test, fuzzing, security)

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	pre-commit autoupdate

ci: ## Run CI checks locally
	@echo "Running CI checks..."
	make lint
	make test
	make test-fuzz-ci
	make security
	@echo "All CI checks passed!"

install-hooks: ## Install git hooks for quality checks
	./scripts/install-hooks.sh

dev-setup: setup install-dev ## Complete development setup
	@echo "Development setup complete!"
	@echo "Run 'make check-all' to verify everything works."
