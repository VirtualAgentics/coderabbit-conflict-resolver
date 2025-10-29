# Contributing to CodeRabbit Conflict Resolver

Thank you for your interest in contributing to CodeRabbit Conflict Resolver! This document provides guidelines and information for contributors.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Development Setup

#### Prerequisites

- **Python 3.12.x** (required)
- **Git** for version control
- **Make** (optional, for convenience commands)

#### Quick Setup (Recommended)

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:

   ```bash
   git clone https://github.com/your-username/coderabbit-conflict-resolver.git
   cd coderabbit-conflict-resolver
   ```

3. **Run the automated setup script**:

   ```bash
   ./setup-dev.sh
   ```

4. **Activate the virtual environment**:

   ```bash
   source .venv/bin/activate
   ```

#### Manual Setup

If you prefer manual setup:

1. **Install Python 3.12.x**:

   ```bash
   # Using pyenv (recommended)
   pyenv install 3.12.8
   pyenv local 3.12.8

   # Or download from https://www.python.org/downloads/
   ```

2. **Create virtual environment**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   pre-commit install
   ./scripts/install-hooks.sh
   ```

4. **Verify setup**:

   ```bash
   make check-all  # Run all checks
   # or
   pytest tests/ --cov=src --cov-report=html
   mypy src/
   black --check src/ tests/
   ruff check src/ tests/
   ```

### Development Workflow

1. **Create a feature branch**:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the coding standards below

3. **Run all checks**:

   ```bash
   make check-all  # Runs lint, test, and security checks
   # or individually:
   make lint        # Run all linters
   make test        # Run tests with coverage
   make security    # Run security checks
   ```

4. **Auto-format code** (if needed):

   ```bash
   make format      # Auto-format with Black and Ruff
   ```

5. **Commit your changes** with a clear commit message:

   ```bash
   git add .
   git commit -m "feat: add new conflict resolution strategy"
   ```

6. **Push to your fork** and create a pull request:

   ```bash
   git push origin feature/your-feature-name
   ```

   **Note**: The pre-push hook will automatically run quality checks before pushing. If checks fail, you'll need to fix the issues or use `git push --no-verify` (not recommended).

### Available Commands

Use `make help` to see all available commands:

- `make setup` - Complete development setup
- `make test` - Run tests with coverage
- `make lint` - Run all linters (Black, Ruff, MyPy)
- `make format` - Auto-format code
- `make security` - Run security checks (Bandit, Safety)
- `make docs` - Build documentation
- `make clean` - Clean build artifacts
- `make check-all` - Run all checks (lint + test + security)
- `make install-hooks` - Install git hooks for quality checks

## Pre-Push Hook

This project uses a pre-push git hook to enforce quality checks before pushing to remote repositories. The hook runs automatically and ensures code quality standards are maintained.

### What Checks Are Run

The pre-push hook runs these quality checks in order:

1. **Black formatting** - Ensures code is properly formatted
2. **Ruff linting** - Checks for code style and quality issues
3. **MyPy type checking** - Validates type annotations
4. **Bandit security** - Scans for security vulnerabilities
5. **Test suite** - Runs tests with coverage requirements

### Installation

The hook is automatically installed when you run:

```bash
make install-dev
# or manually:
./scripts/install-hooks.sh
```

### Usage

The hook runs automatically when you push:

```bash
git push origin feature/your-branch
```

If any checks fail, you'll see a summary of what failed and how to fix it. You can then:

1. **Fix the issues** and push again
2. **Use `git push --no-verify`** to bypass checks (emergency only)

### Manual Hook Installation

If you need to install the hook manually:

```bash
./scripts/install-hooks.sh
```

### Running Checks Locally

You can run the same checks locally before pushing:

```bash
make check-all  # Run all quality checks
# or individually:
make lint       # Formatting and linting
make test       # Tests with coverage
make security   # Security checks
```

## Security Scanning with Safety

This project uses [Safety](https://safetycli.com/) for vulnerability scanning. To run scans locally:

```bash
# Authenticate (one-time setup)
source .venv/bin/activate
safety auth login

# Run vulnerability scan
safety scan
```

The CI/CD pipeline automatically runs Safety scans using the [official GitHub Action](https://github.com/pyupio/safety-action). See [`.github/SAFETY_SETUP.md`](.github/SAFETY_SETUP.md) for details.

## Coding Standards

### Python Code Style

- **Formatting**: Use [Black](https://black.readthedocs.io/) with line length 100
- **Linting**: Use [Ruff](https://docs.astral.sh/ruff/) for fast linting
- **Type hints**: Use [MyPy](https://mypy.readthedocs.io/) for type checking
- **Imports**: Sort imports with `ruff` (handled automatically)

### Code Organization

- **Modules**: Keep related functionality together
- **Classes**: Use clear, descriptive names
- **Functions**: Keep functions small and focused
- **Documentation**: Add docstrings for all public functions and classes

### Testing

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test component interactions
- **Coverage**: Maintain >80% test coverage (strictly enforced in CI)
- **Fixtures**: Use pytest fixtures for test data

#### Coverage Requirements

The project enforces an **80% minimum code coverage threshold** in both local development and CI:

- **Local enforcement**: The pre-push git hook will prevent pushing if coverage drops below 80%
- **CI enforcement**: Pull requests will fail if test coverage is below 80%
- **Coverage reporting**: Every CI run generates a coverage report visible in:
  - GitHub Actions workflow summary
  - Codecov dashboard (linked in README badge)
  - PR comments (automated by Codecov)

**Troubleshooting coverage failures:**

```bash
# Run tests with coverage report
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# View detailed HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Identify missing coverage
pytest tests/ --cov=src --cov-report=term-missing
```

The `--cov-report=term-missing` flag shows which lines are not covered by tests.

### Documentation

- **Docstrings**: Use Google-style docstrings
- **Type hints**: Include type hints for all function parameters and returns
- **Examples**: Include usage examples in docstrings
- **README**: Keep README.md updated with new features

## Pull Request Process

### Before Submitting

1. **Run all checks**: `make check-all`
2. **Update documentation** if needed
3. **Add tests** for new functionality
4. **Update CHANGELOG.md** with your changes
5. **Ensure all CI checks pass** (automatically checked on PR)

### Pull Request Template

When creating a pull request, please include:

- **Description**: What changes were made and why
- **Type**: Bug fix, feature, documentation, refactoring, etc.
- **Testing**: How the changes were tested
- **Breaking changes**: Any breaking changes and migration steps
- **Related issues**: Link to related issues

### Review Process

1. **Automated checks** must pass (CI/CD pipeline)
2. **Code review** by maintainers
3. **Testing** on multiple environments
4. **Documentation** review
5. **Approval** from at least one maintainer

## GitHub Actions Workflow Concurrency

Our project uses standardized concurrency patterns across all GitHub Actions workflows to prevent duplicate workflow runs, optimize CI/CD resource usage, and ensure consistent behavior.

### Standard Patterns

#### 1. Pull Request / Push Workflows (CI, Security, Docs, Labeler)

**Pattern:**
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true
```

**When to use:**
- Workflows triggered by `pull_request` or `push` events
- Testing, linting, security scanning, labeling workflows
- Any workflow where only the latest run matters

**Behavior:**
- Cancels previous runs when new commits are pushed
- Uses PR number for pull requests, falls back to `github.ref` for push events
- Prevents wasted CI resources on outdated code

**Examples:**
- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`
- `.github/workflows/docs.yml`
- `.github/workflows/labeler.yml`

#### 2. Deployment Workflows (Docs Deploy)

**Pattern:**
```yaml
concurrency:
  group: docs-deploy-main
  cancel-in-progress: false  # Queue deployments instead
```

**When to use:**
- Workflows that deploy to production environments
- Workflows where every run must complete
- Main branch only deployment workflows

**Behavior:**
- Queues deployments instead of canceling them
- Ensures all deployments complete in order
- Prevents deployment conflicts

**Examples:**
- `.github/workflows/docs-deploy.yml`

#### 3. Release Workflows

**Pattern:**
```yaml
concurrency:
  group: release-${{ github.ref_name }}
  cancel-in-progress: false
```

**When to use:**
- Release and package publishing workflows
- Version tagging workflows
- Any workflow that must complete once started

**Behavior:**
- Each release tag gets its own concurrency group
- Never cancels in-progress releases
- Prevents publishing conflicts

**Examples:**
- `.github/workflows/release.yml`

#### 4. Scheduled / Maintenance Workflows

**Pattern:**
```yaml
concurrency:
  group: ${{ github.workflow }}
  cancel-in-progress: false  # Queue maintenance tasks
```

**When to use:**
- Scheduled workflows (cron triggers)
- Maintenance workflows (stale issue marking, cleanup)
- Workflows that can be manually triggered

**Behavior:**
- Prevents overlapping scheduled runs
- Queues manual triggers instead of canceling
- Simple workflow-level grouping

**Examples:**
- `.github/workflows/stale.yml`

### Guidelines for New Workflows

When creating new GitHub Actions workflows, follow these guidelines:

1. **Always add a concurrency block** - Even if you think it's not needed, it prevents future issues

2. **Choose the right pattern:**
   - **PR/Push workflows** → Use standard pattern with `cancel-in-progress: true`
   - **Deployments** → Use deployment pattern with `cancel-in-progress: false`
   - **Releases** → Use release pattern with ref-specific grouping
   - **Scheduled** → Use workflow-level grouping with `cancel-in-progress: false`

3. **Include the fallback** - Always use `|| github.ref` for PR workflows to handle edge cases

4. **Test concurrency behavior:**
   ```bash
   # Push multiple commits rapidly to test cancellation
   git commit --allow-empty -m "test 1" && git push
   git commit --allow-empty -m "test 2" && git push
   git commit --allow-empty -m "test 3" && git push

   # Check GitHub Actions UI to verify only latest run completes
   ```

5. **Document exceptions** - If you need a non-standard pattern, document why in comments

### Common Mistakes to Avoid

- ❌ Forgetting the `|| github.ref` fallback for PR workflows
- ❌ Using `cancel-in-progress: true` for deployments or releases
- ❌ Not adding concurrency blocks to scheduled workflows
- ❌ Using PR-specific patterns for push-only workflows
- ❌ Hardcoding branch names instead of using `github.ref`

### Testing Concurrency Configuration

To verify concurrency configuration works correctly:

1. Create a test branch with slow workflow runs (add `sleep 60`)
2. Push multiple commits rapidly
3. Verify in GitHub Actions UI that old runs are cancelled
4. Remove test delays before merging

## Types of Contributions

### Bug Reports

When reporting bugs, please include:

- **Description**: Clear description of the bug
- **Steps to reproduce**: Detailed steps to reproduce the issue
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Environment**: OS, Python version, package version
- **Screenshots**: If applicable

### Feature Requests

When requesting features, please include:

- **Use case**: Why this feature would be useful
- **Proposed solution**: How you think it should work
- **Alternatives**: Other solutions you've considered
- **Additional context**: Any other relevant information

### Code Contributions

We welcome contributions in these areas:

- **Bug fixes**: Fixing existing issues
- **New features**: Adding new functionality
- **Performance**: Optimizing existing code
- **Documentation**: Improving documentation
- **Tests**: Adding or improving tests
- **Refactoring**: Improving code structure

## Development Areas

### Core Components

- **Conflict Detection**: `src/pr_conflict_resolver/analysis/`
- **Resolution Strategies**: `src/pr_conflict_resolver/strategies/`
- **File Handlers**: `src/pr_conflict_resolver/handlers/`
- **GitHub Integration**: `src/pr_conflict_resolver/integrations/`

### Testing

- **Unit Tests**: `tests/unit/`
- **Integration Tests**: `tests/integration/`
- **Fixtures**: `tests/fixtures/`

### Documentation

- **API Reference**: `docs/api-reference.md`
- **Architecture**: `docs/architecture.md`
- **Configuration**: `docs/configuration.md`
- **Examples**: `examples/`

## Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality in a backwards compatible manner
- **PATCH**: Backwards compatible bug fixes

### Release Steps

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with new features and fixes
3. **Create release tag**: `git tag v1.0.0`
4. **Push tag**: `git push origin v1.0.0`
5. **GitHub Actions** will automatically build and publish to PyPI

## Getting Help

### Questions and Support

- **GitHub Issues**: For bug reports and feature requests
- **Discussions**: For questions and general discussion
- **Documentation**: Check the docs/ directory for detailed information

### Community

- **Code of Conduct**: Please read and follow our code of conduct
- **Respect**: Be respectful and constructive in all interactions
- **Learning**: Help others learn and grow
- **Collaboration**: Work together to improve the project

## Recognition

Contributors will be recognized in:

- **CONTRIBUTORS.md**: List of all contributors
- **Release notes**: Mentioned in release announcements
- **GitHub**: Listed as contributors on the repository

Thank you for contributing to CodeRabbit Conflict Resolver! 🎉
