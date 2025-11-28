# Security Testing Guide

## Executive Summary

This guide provides comprehensive instructions for security testing of the Review Bot Automator. It covers local testing, adding new security tests, CI/CD integration, and security review procedures for contributors.

**Audience**: Developers, security engineers, contributors

**Last Updated**: 2025-11-03

---

## Quick Start

### Running All Security Tests Locally

```bash
# Activate virtual environment
source .venv/bin/activate

# Run security-specific tests
pytest tests/security/ -v

# Run with coverage
pytest tests/security/ --cov=src/review_bot_automator/security --cov-report=html

# Run specific security test file
pytest tests/security/test_secret_scanner.py -v

```

---

## Test Structure

### Security Test Organization

```text
tests/security/
├── __init__.py
├── conftest.py                          # Shared fixtures
├── test_input_validator_security.py     # Path traversal, validation
├── test_secret_scanner.py               # Secret detection
├── test_secure_file_handler.py          # File operations
├── test_json_handler_security.py        # JSON injection tests
├── test_yaml_handler_security.py        # YAML injection tests
└── test_toml_handler_security.py        # TOML injection tests

```

---

## Running Security Tests

### 1. Input Validation Tests

**Purpose**: Test path traversal prevention, URL validation, content sanitization

```bash
# Run all input validation tests
pytest tests/security/test_input_validator_security.py -v

# Run specific test class
pytest tests/security/test_input_validator_security.py::TestPathTraversalPrevention -v

# Run with verbose output
pytest tests/security/test_input_validator_security.py -vv

```

#### Key Test Cases

* Path traversal with `../` sequences
* Absolute path validation
* Symlink detection
* URL validation (GitHub URLs)
* Content size limits

**Expected Coverage**: >95% for `input_validator.py`

---

### 2. Secret Scanner Tests

**Purpose**: Verify detection of secrets in code, configuration files

```bash
# Run all secret scanner tests
pytest tests/security/test_secret_scanner.py -v

# Test specific secret types
pytest tests/security/test_secret_scanner.py::TestSecretPatternDetection -v

```

**Tested Secret Types** (17 patterns):

* GitHub tokens (personal, OAuth, server, refresh)
* AWS keys (access key, secret key)
* OpenAI API keys
* JWT tokens
* Private keys (RSA, SSH)
* Slack tokens
* Google OAuth
* Azure connection strings
* Database URLs with passwords
* Generic API keys, passwords, secrets, tokens

**Expected Coverage**: >98% for `secret_scanner.py`

---

### 3. Secure File Handler Tests

**Purpose**: Test atomic operations, rollback, permissions

```bash
# Run file handler security tests
pytest tests/security/test_secure_file_handler.py -v

```

#### Key Test Cases

* Atomic file writes (os.replace)
* Permission preservation
* Rollback on errors
* TOCTOU prevention
* Concurrent access handling

**Expected Coverage**: >97% for `secure_file_handler.py`

---

### 4. Handler Security Tests (Injection Prevention)

#### JSON Handler

```bash
pytest tests/security/test_json_handler_security.py -v

```

#### Tests

* Path traversal in file paths
* Symlink rejection
* Large content handling
* Duplicate key detection
* Safe JSON parsing (no code execution)

---

#### YAML Handler

```bash
pytest tests/security/test_yaml_handler_security.py -v

```

#### Tests: (InputValidator)

* `!!python/object` injection prevention
* Safe YAML loading (`yaml.safe_load`)
* Path traversal prevention
* Symlink rejection
* Large content handling

---

#### TOML Handler

```bash
pytest tests/security/test_toml_handler_security.py -v

```

#### Tests: (SecureFileHandler)

* Path traversal prevention
* Symlink rejection
* Large content handling
* Safe TOML parsing

---

## Fuzzing

### ClusterFuzzLite Integration

**Purpose**: Continuous fuzzing to detect crashes, memory issues, edge cases

#### Running Fuzzing Locally

```bash
# Build fuzzing Docker image
cd .clusterfuzzlite
docker build -t clusterfuzzlite-build .

# Run fuzz targets
docker run --rm -v $(pwd):/src clusterfuzzlite-build bash -c \
  "python3 /src/fuzz/fuzz_input_validator.py"

```

#### Fuzz Targets

##### 1. fuzz_input_validator.py

* **Tests**: `InputValidator.validate_file_path()`, `validate_github_url()`, `validate_json/yaml/toml()`
* **Coverage**: Path traversal, null bytes, special characters, URL spoofing, token format bypasses
* **Corpus**: Automatically generated
* **Max length**: 4096 bytes
* **Timeout**: 60 seconds per input

#### 2. fuzz_handlers.py

* **Tests**: JSON, YAML, TOML parsing, validation, modification
* **Coverage**: Parser crashes, injection attacks, path traversal, resource exhaustion
* **Focus**: Malformed/malicious inputs across all file handlers
* **Handlers**: JsonHandler, YamlHandler, TomlHandler

#### 3. fuzz_secret_scanner.py

* **Tests**: `SecretScanner.scan_content()`, `has_secrets()`, `_is_false_positive()`, `_redact_secret()`, `scan_content_generator()`
* **Coverage**: ReDoS vulnerabilities (17 regex patterns), Unicode edge cases, false positive logic, redaction safety
* **Focus**: Regular expression denial of service, secret detection edge cases
* **Max length**: 10KB per input (prevent timeout)
* **Key Vulnerabilities Tested**:
  * ReDoS (catastrophic backtracking in regex patterns)
  * Unicode normalization issues
  * Null byte injection (`\x00`)
  * Boundary conditions (empty strings, extremely long inputs)
  * False positive detection logic errors

#### CI/CD Fuzzing

**PR Fuzzing** (`.github/workflows/clusterfuzzlite.yml`):

* Runs on every pull request
* Address sanitizer (detects memory corruption)
* Undefined behavior sanitizer
* 600 second max total time

**Scheduled Fuzzing** (`.github/workflows/fuzz-extended.yml`):

* Runs weekly on main branch
* Extended fuzzing (1 hour per target)
* Coverage-guided mutation

---

## Static Analysis Security Testing (SAST)

### 1. Bandit (Python Security Linter)

**Purpose**: Detect common Python security issues

```bash
# Run Bandit locally
bandit -r src/ -c pyproject.toml

# Run with verbose output
bandit -r src/ -v -ll

# Generate report
bandit -r src/ -f json -o bandit-report.json

```

#### Checks

* Hard-coded passwords/secrets
* Use of `eval()`, `exec()`
* SQL injection patterns
* Shell injection
* Insecure random number generation
* Insecure deserialization

**CI Integration**: `.github/workflows/security.yml` (security-scan job)

---

### 2. CodeQL (Semantic Analysis)

**Purpose**: Deep semantic analysis for security vulnerabilities

**Queries**: `security-extended` suite

```bash
# CodeQL runs automatically in CI
# To run locally (requires CodeQL CLI)
codeql database create /tmp/codeql-db --language=python
codeql database analyze /tmp/codeql-db \
  --format=sarif-latest --output=codeql-results.sarif

```

#### Detected Vulnerabilities

* Code injection
* Path traversal
* SQL injection
* XSS (if web components added)
* Insecure cryptography
* Information disclosure

**CI Integration**: `.github/workflows/security.yml` (codeql job)

---

### 3. Semgrep (Fast Pattern Matching)

**Purpose**: Fast, customizable security patterns

```bash
# Run Semgrep locally
semgrep --config=auto src/

# Run specific rulesets
semgrep --config=p/security-audit src/
semgrep --config=p/owasp-top-ten src/

```

#### Rulesets

* OWASP Top 10
* Security audit
* Secrets detection

---

## Dependency Scanning

### 1. pip-audit (Python Package Vulnerabilities)

```bash
# Scan for vulnerabilities
pip-audit

# Scan requirements file
pip-audit -r requirements-dev.txt

# Generate JSON report
pip-audit --format=json -o pip-audit-report.json

```

**CI Integration**: `.github/workflows/security.yml` (security-scan job)

---

### 2. Trivy (SBOM and CVE Scanning)

```bash
# Scan current directory
trivy fs .

# Generate SBOM
trivy fs --format cyclonedx --output sbom.json .

# Scan Docker images
trivy image gcr.io/oss-fuzz-base/base-builder-python

```

**CI Integration**: `.github/workflows/security.yml` (trivy-scan job)

---

### 3. Dependency Submission & OpenSSF Scorecard

```bash
# Generate dependency snapshot for GitHub advisories
python -m pip install --upgrade pip
pip install pip-audit
pip-audit --generate-sbom cyclonedx.json

```

* Dependency snapshots flow through `.github/workflows/dependency-submission.yml`
* OpenSSF Scorecard validates dependency pinning, branch protections, and workflow hardening
* Findings appear under **Security → Code scanning alerts → Scorecard**

**CI Integration**: `.github/workflows/dependency-submission.yml`, `.github/workflows/security.yml` (scorecard job)

---

## Secret Scanning

### 1. TruffleHog (Git History Scanning)

```bash
# Scan entire git history
trufflehog filesystem . --only-verified

# Scan since specific commit
trufflehog filesystem . --since-commit <commit-hash>

# Use .truffleignore to exclude paths
# File located at: .truffleignore

```

**CI Integration**: `.github/workflows/security.yml` (trufflehog-scan job)

---

### 2. OpenSSF Scorecard

**Purpose**: Evaluate security best practices

```bash
# Run Scorecard (requires installation)
scorecard --repo=github.com/VirtualAgentics/review-bot-automator

# View results
# Results automatically published to GitHub Security tab

```

#### Checks

* Branch protection
* CI tests
* Code review
* Dependency updates
* Fuzzing
* Pinned dependencies
* SAST
* Security policy
* Signed releases
* Token permissions
* Vulnerabilities

**CI Integration**: `.github/workflows/security.yml` (scorecard job)

---

## Adding New Security Tests

### Test Template

```python
"""Security tests for [component name]."""

import pytest
from pathlib import Path

from review_bot_automator.security.input_validator import InputValidator

class TestComponentSecurity:
    """Security tests for component."""

    def test_path_traversal_prevention(self, tmp_path: Path) -> None:
        """Test that path traversal attempts are blocked."""
        # Arrange
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "./../sensitive.txt",
        ]

        # Act & Assert
        for path in malicious_paths:
            assert not InputValidator.validate_file_path(
                path, allow_absolute=False
            ), f"Path traversal not blocked: {path}"

    def test_secret_detection(self) -> None:
        """Test that secrets are detected in content."""
        # Arrange
        from review_bot_automator.security.secret_scanner import SecretScanner

        malicious_content = """
        api_key = "ghp_1234567890abcdefghijklmnopqrstuvwxyz12"
        """

        # Act
        findings = SecretScanner.scan_content(malicious_content)

        # Assert
        assert len(findings) > 0, "Secret not detected"
        assert findings[0].secret_type == "github_personal_token"

    def test_code_injection_prevention(self) -> None:
        """Test that code injection is prevented."""
        # Arrange
        import yaml

        malicious_yaml = """
        key: !!python/object/apply:os.system
          args: ["rm -rf /"]
        """

        # Act & Assert
        # yaml.safe_load should not execute code
        with pytest.raises(yaml.constructor.ConstructorError):
            yaml.safe_load(malicious_yaml)

```

### Test Naming Conventions

* **Test files**: `test_<component>_security.py`
* **Test classes**: `Test<Component>Security`
* **Test methods**: `test_<vulnerability_type>`

#### Examples

* `test_path_traversal_prevention`
* `test_code_injection_blocked`
* `test_secret_detection`
* `test_symlink_rejection`

---

## Security Review Checklist for PRs

### Code Review Security Checklist

#### Input Validation

* [ ] All external inputs validated
* [ ] File paths checked for traversal
* [ ] URLs validated for allowed domains
* [ ] Content size limits enforced

#### Secret Handling

* [ ] No hard-coded secrets
* [ ] Environment variables used for tokens
* [ ] Secrets not logged
* [ ] Secret scanning passes

#### File Operations

* [ ] Atomic operations used
* [ ] Permissions preserved
* [ ] Symlinks rejected
* [ ] Workspace containment enforced

#### Parser Safety

* [ ] Safe parsers used (`yaml.safe_load`, `json.loads`)
* [ ] No dynamic code execution
* [ ] Input sanitized before parsing

#### Error Handling

* [ ] No sensitive data in error messages
* [ ] Errors logged securely
* [ ] No stack traces exposed to users

#### Dependencies

* [ ] New dependencies justified
* [ ] Vulnerabilities checked (`pip-audit`)
* [ ] Version pinned in requirements

#### Tests

* [ ] Security tests added for new features
* [ ] Regression tests for fixes
* [ ] Fuzz tests if applicable

---

## CI/CD Security Integration

### Workflow Files

#### `.github/workflows/security.yml`

* **CodeQL**: Semantic analysis
* **Bandit**: Python security linting
* **Trivy**: SBOM and CVE scanning
* **TruffleHog**: Secret scanning
* **Scorecard**: Security best practices
* **pip-audit**: Dependency vulnerabilities

#### `.github/workflows/ci.yml`

* **pytest**: Unit and integration tests (including security tests)
* **Coverage**: Minimum 80% required

#### `.github/workflows/clusterfuzzlite.yml`

* **pr-fuzz**: Fuzzing on pull requests
* **Address Sanitizer**: Memory corruption detection
* **Undefined Behavior Sanitizer**: UB detection

#### `.github/workflows/dependency-submission.yml`

* **SBOM Generation**: Automatic dependency graph submission
* **Dependency Review**: Alerts on new vulnerabilities

---

## Common Vulnerabilities to Test For

### OWASP Top 10 Mapping

| OWASP | Vulnerability | Test Method | Example Test |
| ------- | --------------- | ------------- | -------------- |
| A01 | Broken Access Control | Path traversal tests | `test_path_traversal_prevention` |
| A02 | Cryptographic Failures | Secret detection | `test_secret_detection` |
| A03 | Injection | Parser safety tests | `test_yaml_code_injection_blocked` |
| A04 | Insecure Design | Architecture review | Threat model validation |
| A05 | Security Misconfiguration | Config validation | `test_secure_defaults` |
| A06 | Vulnerable Components | Dependency scanning | `pip-audit`, Trivy |
| A07 | Authentication Failures | Token validation | `test_token_validation` |
| A08 | Data Integrity Failures | Atomic operations | `test_atomic_file_write` |
| A09 | Logging Failures | Log security | `test_no_secrets_in_logs` |

---

## Performance and Security

### Testing for DoS Vulnerabilities

```python
def test_large_file_handling(tmp_path: Path) -> None:
    """Test that large files are handled safely."""
    # Create large content (10MB)
    large_content = "x" * (10 * 1024 * 1024)

    # Should complete within reasonable time
    # Should not crash or hang
    handler = JsonHandler(workspace_root=tmp_path)

    # Assert timeout or size limit enforced
    with pytest.raises((ValueError, OSError)):
        handler.apply_change("file.json", large_content, 1, 1)

```

### Testing Algorithmic Complexity

```python
def test_pathological_input_performance() -> None:
    """Test that pathological inputs don't cause performance issues."""
    # Create deeply nested structure
    nested = {"a": {"b": {"c": {"d": {"e": "value"}}}}}

    # Should complete in reasonable time
    import time
    start = time.time()

    handler.process(nested)

    duration = time.time() - start
    assert duration < 1.0, "Performance regression detected"

```

---

## Security Metrics and Reporting

### Coverage Metrics

#### Minimum Requirements

* Overall test coverage: ≥80%
* Security module coverage: ≥95%
* Handler security tests: ≥90%

```bash
# Generate coverage report
pytest --cov=src/review_bot_automator --cov-report=html

# View report
open htmlcov/index.html

```

### Security Scan Results

#### Viewing CI Results

1. Go to GitHub Security tab
2. Filter by tool:
   * CodeQL
   * Trivy
   * Scorecard
3. Review findings and remediation steps

**OpenSSF Scorecard**: <https://api.securityscorecards.dev/projects/github.com/VirtualAgentics/review-bot-automator>

---

## References

* **Security Architecture**: [docs/security-architecture.md](../security-architecture.md)
* **Threat Model**: [docs/security/threat-model.md](threat-model.md)
* **Incident Response**: [docs/security/incident-response.md](incident-response.md)
* **Compliance**: [docs/security/compliance.md](compliance.md)
* **OWASP Testing Guide**: <https://owasp.org/www-project-web-security-testing-guide/>
* **Python Security**: <https://python.org/community/security/>

---

**Document Version**: 1.0
**Last Updated**: 2025-11-03
**Next Review**: Quarterly
**Owner**: Security Team
