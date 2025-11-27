# Testing Guide

## Table of Contents

* [Overview](#overview)
* [Test Organization](#test-organization)
* [Writing Tests](#writing-tests)
  * [Unit Tests](#unit-tests)
  * [Integration Tests](#integration-tests)
  * [Security Tests](#security-tests)
  * [Using Subtests](#using-subtests)
  * [Parametrization](#parametrization)
* [Running Tests](#running-tests)
* [Coverage Best Practices](#coverage-best-practices)
* [Property-Based Testing](#property-based-testing)
* [CI/CD Integration](#cicd-integration)
* [Troubleshooting](#troubleshooting)

## Overview

This project uses **pytest 9.0.0** with native subtests support for comprehensive testing. Our testing philosophy emphasizes:

* **High coverage** (minimum 80%, currently 86.92%)
* **Test isolation** - Each test should be independent
* **Clear failure reporting** - Tests should clearly indicate what failed and why
* **Maintainability** - Tests should be easy to read, write, and update

### Testing Framework

* **pytest 9.0.0** - Testing framework with native subtests
* **pytest-cov** - Coverage reporting
* **pytest-xdist** - Parallel test execution
* **Hypothesis** - Property-based testing

### Test Types

1. **Unit Tests** (`tests/unit/`) - Test individual components in isolation
2. **Integration Tests** (`tests/integration/`) - Test component interactions
3. **Security Tests** (`tests/security/`) - Test security features and attack prevention
4. **Fuzzing Tests** (`tests/fuzzing/`) - Property-based testing with Hypothesis

## Test Organization

### Directory Structure

```text
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Unit tests
│   ├── test_handlers.py     # Handler tests
│   ├── test_cli_validation.py
│   ├── test_runtime_config.py
│   └── utils/               # Utility tests
├── integration/             # Integration tests
│   └── test_e2e_workflow.py
├── security/                # Security tests
│   ├── test_path_traversal.py
│   ├── test_input_validation.py
│   └── test_cli_security.py
└── fuzzing/                 # Property-based tests
    └── test_fuzzing.py

```

### Test File Naming

* Unit tests: `test_<module_name>.py`
* Integration tests: `test_<feature>_integration.py`
* Security tests: `test_<security_aspect>.py`

### Test Class Organization

Group related tests in classes:

```python
class TestJSONHandler:
    """Tests for JSON file handler."""

    def test_can_handle_json_files(self) -> None:
        """Test JSON file detection."""
        # Test implementation

    def test_validates_json_syntax(self) -> None:
        """Test JSON syntax validation."""
        # Test implementation

```

## Writing Tests

### Unit Tests

Unit tests verify individual components in isolation using mocks for dependencies.

**Example:**

```python
from unittest.mock import Mock, patch
import pytest

def test_github_comment_extraction() -> None:
    """Test GitHub comment extraction with mocked API."""
    with patch('review_bot_automator.integrations.github.requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"comments": []}

        extractor = GitHubCommentExtractor("owner", "repo", 123)
        comments = extractor.fetch_pr_comments()

        assert comments == []
        mock_get.assert_called_once()

```

### Integration Tests

Integration tests verify that components work together correctly.

**Example:**

```python
def test_end_to_end_conflict_resolution(tmp_path: Path) -> None:
    """Test complete conflict resolution workflow."""
    # Setup test files
    test_file = tmp_path / "config.toml"
    test_file.write_text('key = "value"')

    # Create resolver
    resolver = ConflictResolver()

    # Create changes
    changes = [
        Change(path=str(test_file), content='key = "new_value"', ...)
    ]

    # Detect and resolve conflicts
    conflicts = resolver.detect_conflicts(changes)
    results = resolver.resolve_conflicts(conflicts)

    assert len(results) > 0

```

### Security Tests

Security tests verify attack prevention and input validation.

**Example:**

```python
def test_rejects_path_traversal() -> None:
    """Test that path traversal attempts are rejected."""
    handler = JsonHandler()

    # Path traversal should be rejected
    result = handler.apply_change(
        "../../../etc/passwd",
        '{"key": "value"}',
        1, 1
    )

    assert not result, "Path traversal should be rejected"

```

### Using Subtests

**Subtests** allow you to run multiple test cases within a single test method, with each case reported independently.

#### When to Use Subtests

Use subtests when:

* Testing the same logic with multiple input variations
* You have a dynamic list of test cases (e.g., from a file or API)
* You want all cases to run even if one fails
* Test cases share expensive setup/teardown

**Example:**

```python
def test_path_validation_rejects_unsafe_paths(self, subtests: pytest.Subtests) -> None:
    """Test that various unsafe paths are rejected using subtests."""
    unsafe_paths = [
        ("Unix traversal", "../../../etc/passwd"),
        ("Windows traversal", "..\\..\\..\\windows\\system32"),
        ("Absolute path", "/etc/passwd"),
        ("Null byte", "file\x00.txt"),
    ]

    for description, path in unsafe_paths:
        with subtests.test(msg=f"{description}: {path}", path=path):
            assert not InputValidator.validate_file_path(path)

```

**Benefits:**

* All subtests run even if one fails
* Clear failure reporting with context
* Easy to add new test cases
* Less boilerplate than separate test methods

#### Subtest Pattern

```python
def test_name(self, subtests: pytest.Subtests) -> None:
    """Test description using subtests."""
    test_cases = [...]  # List of test cases

    for case in test_cases:
        with subtests.test(msg=f"Description: {case}", **context):
            # Test assertion
            assert expected_result

```

**Key points:**

* Inject `subtests: pytest.Subtests` fixture
* Use `with subtests.test(msg=..., **context)` context manager
* Provide descriptive `msg` for failure reporting
* Include context variables for debugging

### Parametrization

**Parametrization** is ideal for testing the same logic with a small, static set of inputs.

#### When to Use Parametrize

Use `@pytest.mark.parametrize` when:

* You have a small, fixed set of test cases (typically < 4)
* Test cases are statically defined
* You want each case to be a separate test in reports
* No expensive setup is needed

**Example:**

```python
@pytest.mark.parametrize("value,expected", [
    ("true", True),
    ("false", False),
    ("1", True),
])
def test_boolean_parsing(value: str, expected: bool) -> None:
    """Test boolean value parsing."""
    result = parse_boolean(value)
    assert result == expected

```

#### Subtests vs Parametrize: Decision Matrix

| Scenario | Use Subtests | Use Parametrize |
| ---------- | ------------- | ---------------- |
| Static, small set (< 4 cases) | ❌ | ✅ |
| Static, large set (≥ 4 cases) | ✅ | ❌ |
| Dynamic test cases (from file/API) | ✅ | ❌ |
| Expensive setup/teardown | ✅ | ❌ |
| Want all cases to run on failure | ✅ | ⚠️ |
| Want separate test per case in report | ❌ | ✅ |

## Running Tests

### Quick Reference

```bash
# Run all tests
make test

# Run tests without coverage (faster)
make test-fast

# Run specific test file
pytest tests/unit/test_handlers.py

# Run specific test method
pytest tests/unit/test_handlers.py::TestJSONHandler::test_validates_json_syntax

# Run with verbose output
pytest -v

# Run tests in parallel (4 workers)
pytest -n 4

# Run only unit tests
pytest tests/unit/

# Run only security tests
pytest tests/security/

```

### Test Markers

Use markers to categorize and selectively run tests:

```bash
# Run only slow tests
pytest -m slow

# Skip slow tests
pytest -m "not slow"

# Run only integration tests
pytest -m integration

# Run fuzzing tests (dev profile: 50 examples)
make test-fuzz

# Run extended fuzzing (1000 examples)
make test-fuzz-extended

```

### Coverage Reports

```bash
# Run tests with coverage report
make test

# Generate HTML coverage report
pytest --cov=src --cov-report=html
# Opens in htmlcov/index.html

# Show missing lines in terminal
pytest --cov=src --cov-report=term-missing

```

### Watch Mode (Development)

```bash
# Install pytest-watch
pip install pytest-watch

# Run tests on file changes
ptw tests/ src/

```

## Coverage Best Practices

### Coverage Requirements

* **Minimum:** 80% overall coverage (enforced in CI)
* **Current:** 86.92% coverage
* **Goal:** 90%+ coverage for critical components

### What to Cover

**High Priority (aim for 95%+):**

* Security-critical code (input validation, path handling)
* Core business logic (conflict resolution, handlers)
* Error handling and edge cases

**Medium Priority (aim for 85%+):**

* CLI commands and argument parsing
* Configuration loading and validation
* Utility functions

**Lower Priority:**

* Simple getters/setters
* Debug logging
* Obvious code paths

### Coverage Exclusions

Mark code that shouldn't be covered:

```python
if TYPE_CHECKING:  # pragma: no cover
    from typing import Protocol

def debug_only_function():  # pragma: no cover
    """This function is only for debugging."""
    pass

```

### Improving Coverage

1. **Identify gaps:**

   ```bash
   pytest --cov=src --cov-report=html
   # Open htmlcov/index.html to see uncovered lines

   ```

2. **Focus on branches:**
   * Cover both `if` and `else` branches
   * Test exception handling paths
   * Test early returns

3. **Don't game the metrics:**
   * Coverage != quality
   * Focus on meaningful tests
   * Test behavior, not implementation

## Property-Based Testing

We use **Hypothesis** for property-based testing (fuzzing).

### What is Property-Based Testing?

Instead of writing specific test cases, you define **properties** that should always hold true, and Hypothesis generates hundreds of test cases automatically.

**Example:**

```python
from hypothesis import given
from hypothesis import strategies as st

@given(st.text(), st.text())
def test_concatenation_length(s1: str, s2: str) -> None:
    """Test that concatenation length equals sum of lengths."""
    result = s1 + s2
    assert len(result) == len(s1) + len(s2)

```

### Our Fuzzing Tests

Located in `tests/fuzzing/test_fuzzing.py`:

```bash
# Run with dev profile (50 examples)
make test-fuzz

# Run with CI profile (100 examples)
make test-fuzz-ci

# Run extended fuzzing (1000 examples)
make test-fuzz-extended

```

### Writing Fuzzing Tests

```python
from hypothesis import given, strategies as st

@given(
    path=st.text(min_size=1, max_size=100),
    content=st.text(min_size=0, max_size=1000)
)
def test_handler_never_crashes(path: str, content: str) -> None:
    """Test that handler doesn't crash on any input."""
    handler = JsonHandler()

    # Should not raise exception
    try:
        handler.validate_change(path, content, 1, 1)
    except Exception as e:
        # Expected exceptions are OK
        assert isinstance(e, (ValueError, TypeError))

```

### Fuzzing Best Practices

1. **Test invariants** - Properties that should always hold
2. **Test for crashes** - Code should handle all inputs gracefully
3. **Use appropriate strategies** - Match input types to domain
4. **Set reasonable limits** - Max sizes prevent slow tests
5. **Use examples** - Supplement with `@example()` for known edge cases

## CI/CD Integration

### GitHub Actions Workflow

Tests run automatically on:

* Every push to any branch
* Every pull request
* Scheduled runs (daily)

### CI Test Commands

```yaml
# In .github/workflows/ci.yml
* name: Run tests
  run: |
    pytest tests/ \
      --cov=src \
      --cov-report=xml \
      --cov-report=html \
      --cov-report=term-missing \
      --cov-fail-under=80

```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pre-commit install

```

Hooks run on every commit:

* Trim trailing whitespace
* Fix end of files
* Check YAML/JSON/TOML syntax
* Black (code formatting)
* Ruff (linting)
* Mypy (type checking)
* Bandit (security checks)
* Markdownlint (markdown documentation)

### Pre-push Hooks

Run full test suite before push:

```bash
# Install pre-push hooks
pre-commit install --hook-type pre-push

# Tests run automatically before git push
git push

```

### Markdown Linting

The project enforces markdown quality standards using markdownlint-cli2.

**Configuration**: `.markdownlint.yaml`

**Enabled rules**:

* MD022 - Blank lines around headings
* MD031 - Blank lines around fenced code blocks
* MD032 - Blank lines around lists
* MD004 - Consistent unordered list style (asterisks)
* MD040 - Fenced code blocks must have language
* And many more (see [markdownlint rules](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md))

**Disabled rules** (project-specific):

* MD013 (line length) - Allows long lines for code blocks and URLs
* MD033 (inline HTML) - Permits badges and centered images
* MD041 (first line heading) - README has badges before first heading

**Run manually**:

```bash
# Check all markdown files
pre-commit run markdownlint-cli2 --all-files

# Or via make (if available)
make lint-markdown
```

## Troubleshooting

### Common Issues

#### Tests Pass Locally but Fail in CI

**Causes:**

* Different Python version
* Missing dependencies
* Environment variables not set
* Timezone differences
* File permissions

**Solutions:**

* Check Python version in CI config
* Verify all dependencies in `requirements-dev.txt`
* Use `monkeypatch` or `mock.patch.dict` for env vars
* Use UTC for time-sensitive tests
* Don't rely on specific file permissions

#### Flaky Tests

**Symptoms:** Tests pass sometimes, fail other times

**Common causes:**

* Time-dependent code without mocking
* Race conditions in parallel tests
* Random data without seeds
* External service dependencies
* Shared state between tests

**Solutions:**

```python
# Mock time
from unittest.mock import patch
with patch('time.time', return_value=1234567890):
    # Test code

# Seed random
import random
random.seed(42)

# Isolate tests
@pytest.fixture(autouse=True)
def reset_state():
    # Reset global state
    yield
    # Cleanup

```

#### Slow Tests

**Identify slow tests:**

```bash
pytest --durations=10

```

**Solutions:**

* Use mocks instead of real I/O
* Use `tmp_path` fixture instead of real files
* Run expensive setup once with `@pytest.fixture(scope="module")`
* Use `pytest-xdist` for parallel execution
* Mark slow tests with `@pytest.mark.slow`

#### Import Errors

**Error:** `ModuleNotFoundError: No module named 'review_bot_automator'`

**Solutions:**

```bash
# Install in editable mode
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

```

### Debugging Tests

#### Print Debugging

```python
def test_something():
    result = function()
    print(f"Result: {result}")  # Visible with pytest -s
    assert result == expected

```

Run with `-s` to see print output:

```bash
pytest -s tests/unit/test_handlers.py

```

#### PDB Debugging

```python
def test_something():
    result = function()
    import pdb; pdb.set_trace()  # Breakpoint
    assert result == expected

```

Or use `--pdb` flag:

```bash
pytest --pdb  # Drop into debugger on failure

```

#### Verbose Output

```bash
# Show all test names
pytest -v

# Show even more detail
pytest -vv

# Show local variables on failure
pytest -l

```

### Getting Help

* **Documentation:** See `docs/testing/` directory
* **Issues:** Check existing issues on GitHub
* **Contributing:** See `CONTRIBUTING.md` for testing guidelines
* **Examples:** Look at existing tests for patterns

## Related Documentation

* [pytest 9.0 Migration Guide](PYTEST_9_MIGRATION.md) - Migration overview and benefits
* [Subtests Guide](SUBTESTS_GUIDE.md) - Detailed subtests documentation
* [Security Testing](../security/security-testing.md) - Security-specific testing practices
* [CONTRIBUTING.md](../../CONTRIBUTING.md) - General contribution guidelines
