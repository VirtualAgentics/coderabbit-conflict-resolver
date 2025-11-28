# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported |
| ------- | ------------------ |
| 2.x | :white_check_mark: |
| 0.1.x | :x: (pre-release, upgrade to 2.x) |
| < 0.1 | :x: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. Thank you for improving the security of Review Bot Automator.

### How to Report

Please report security vulnerabilities through the following channels:

1. **Private Disclosure (Recommended)**: Use GitHub's private vulnerability reporting feature
   - Go to the repository's "Security" tab
   - Click "Report a vulnerability"
   - Fill out the private report form

2. **Email**: Send details to <bdc@virtualagentics.ai>
   - Use a descriptive subject line
   - Include detailed steps to reproduce
   - Provide your contact information

3. **GitHub Issues**: For non-critical security issues, you may create a public issue
   - Use the "Security" label
   - Do not include sensitive details in the issue description

### What to Include

Please include the following information in your report:

- **Description**: Clear description of the vulnerability
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Impact**: Potential impact of the vulnerability
- **Environment**: OS, Python version, package version
- **Proof of Concept**: If applicable, include a minimal proof of concept
- **Suggested Fix**: If you have ideas for fixing the issue

### What to Expect

- **Acknowledgment**: You will receive an acknowledgment within 48 hours
- **Initial Assessment**: We will provide an initial assessment within 1 week
- **Regular Updates**: We will provide regular updates on our progress
- **Disclosure**: We will coordinate with you on public disclosure timing

## Disclosure Policy

We follow responsible disclosure practices:

1. **Private Investigation**: We will investigate the report privately
2. **Fix Development**: We will develop and test a fix
3. **Coordinated Release**: We will coordinate with you on the release timing
4. **Public Disclosure**: We will publicly disclose the vulnerability after the fix is released

### Timeline

- **Critical vulnerabilities**: 72 hours for initial response, 7 days for fix
- **High severity**: 1 week for initial response, 2 weeks for fix
- **Medium/Low severity**: 2 weeks for initial response, 1 month for fix

## Security Best Practices

When using Review Bot Automator:

1. **Keep Dependencies Updated**: Regularly update all dependencies
2. **Use Virtual Environments**: Always use virtual environments for isolation
3. **Review Changes**: Carefully review all automated changes before applying
4. **Backup Files**: Always backup files before running conflict resolution
5. **Test in Staging**: Test conflict resolution in a staging environment first
6. **Monitor Logs**: Monitor application logs for suspicious activity

## Security Architecture

For a comprehensive overview of our security posture, see:

- **[Security Architecture](docs/security-architecture.md)**: Detailed security design, principles, and threat model
- **[Threat Model](docs/security/threat-model.md)**: STRIDE analysis, attack scenarios, and risk assessment
- **[Compliance Guide](docs/security/compliance.md)**: GDPR, OWASP Top 10, SOC2, and OpenSSF compliance

## Security Controls Reference

Review Bot Automator implements multiple layers of security controls:

### Core Security Components

1. **InputValidator** (`src/review_bot_automator/security/input_validator.py`)
   - Path traversal prevention
   - File path validation and normalization
   - URL validation (GitHub API)
   - Content validation (JSON, YAML, TOML)
   - Symlink detection and rejection

2. **SecretScanner** (`src/review_bot_automator/security/secret_scanner.py`)
   - 17 secret pattern types detected
   - GitHub tokens, AWS keys, OpenAI API keys
   - JWT tokens, private keys, database credentials
   - False positive filtering
   - Pre-commit secret scanning

3. **SecureFileHandler** (`src/review_bot_automator/security/secure_file_handler.py`)
   - Atomic file operations (os.replace)
   - File permission preservation
   - TOCTOU prevention
   - Rollback capabilities
   - Workspace containment enforcement

4. **SecurityConfig** (`src/review_bot_automator/security/config.py`)
   - Secure defaults configuration
   - Feature toggles for security controls
   - Configurable security policies

### Safe Parsing

- **YAML**: `yaml.safe_load()` prevents code execution
- **JSON**: Duplicate key detection, no eval()
- **TOML**: Safe parsing with structure validation

### CI/CD Security

- **ClusterFuzzLite**: Continuous fuzzing (address & UB sanitizers)
- **CodeQL**: Semantic security analysis
- **Trivy**: SBOM generation and CVE scanning
- **TruffleHog**: Git history secret scanning
- **OpenSSF Scorecard**: Security best practices evaluation
- **Bandit**: Python security linting
- **pip-audit**: Dependency vulnerability scanning

### Release Signing (SLSA Provenance)

All releases are cryptographically signed using **SLSA Level 3** provenance:

- **Signing mechanism**: [SLSA GitHub Generator](https://github.com/slsa-framework/slsa-github-generator) generates cryptographic provenance attestations
- **Provenance file**: Each release includes a `.intoto.jsonl` provenance file
- **Verification**: Users can verify release integrity using [slsa-verifier](https://github.com/slsa-framework/slsa-verifier)

**How to verify a release:**

```bash
# Install slsa-verifier
go install github.com/slsa-framework/slsa-verifier/v2/cli/slsa-verifier@latest

# Download release and provenance from GitHub Releases
# Verify the artifact
slsa-verifier verify-artifact \
  review_bot_automator-2.0.1-py3-none-any.whl \
  --provenance-path review_bot_automator-2.0.1-py3-none-any.whl.intoto.jsonl \
  --source-uri github.com/VirtualAgentics/review-bot-automator \
  --source-tag v2.0.1
```

**Why SLSA instead of GPG?**

- SLSA provenance is automatically generated in CI (no manual key management)
- Proves the artifact was built from the claimed source repository
- Provides stronger supply chain security guarantees
- Supported by PyPI and major package registries

See `.github/workflows/release.yml` for implementation details.

## Secure Usage Guidelines

### Best Practices for Users

1. **Always Review Changes**: Carefully review all automated changes before accepting
2. **Use Dry-Run Mode**: Test changes with `--dry-run` flag before applying
3. **Keep Dependencies Updated**: Regularly update all dependencies
4. **Use Virtual Environments**: Always use virtual environments for isolation
5. **Backup Files**: Backup important files before running conflict resolution
6. **Test in Staging**: Test conflict resolution in a staging environment first
7. **Monitor Logs**: Monitor application logs for suspicious activity
8. **Verify Sources**: Only use trusted CodeRabbit suggestions
9. **Check Permissions**: Ensure file permissions are preserved
10. **Use Version Control**: Always commit changes to Git for rollback capability

### Security Testing

For developers and contributors, see:

- **[Security Testing Guide](docs/security/security-testing.md)**: How to run security tests locally, add new tests, and perform security reviews

**Quick Start**:

```bash
# Run all security tests
pytest tests/security/ -v

# Run with coverage
pytest tests/security/ --cov=src/review_bot_automator/security

# Run fuzzing locally
docker run --rm -v $(pwd):/src gcr.io/oss-fuzz-base/base-builder-python \
  python3 /src/fuzz/fuzz_input_validator.py
```

## Security Metrics

Our security posture is continuously monitored and measured:

### Test Coverage

- **Overall Coverage**: 82%+ (target: 80%)
- **Security Module Coverage**: 95%+
- **Test Suite**: 609+ tests (2 skipped)

### Continuous Fuzzing (ClusterFuzzLite)

- **Fuzz Targets**: 3 active targets
- **Execution**: Every PR + Weekly deep fuzzing
- **Sanitizers**: Address Sanitizer (ASan), Undefined Behavior Sanitizer (UBSan)
- **Coverage**: Expanding with each fuzzing cycle

### Vulnerability Scanning

- **pip-audit**: Daily dependency vulnerability checks
- **Trivy**: Container and filesystem CVE scanning
- **CodeQL**: Semantic analysis for code vulnerabilities
- **TruffleHog**: Git history secret scanning
- **Bandit**: Python security issue detection

### OpenSSF Scorecard

- **Current Score**: View at <https://github.com/VirtualAgentics/review-bot-automator/security>
- **Checks**: 15+ security best practice checks
- **Status**: Monitored continuously in CI/CD

### Security Incidents

- **Total Reported**: 0 (as of 2025-11-03)
- **Resolved**: 0
- **Average Response Time**: N/A (no incidents)
- **Public Advisories**: 0

## Security Features

Review Bot Automator includes several security features:

- **Input Validation**: All inputs are validated before processing
- **Safe File Operations**: Atomic file operations with rollback capabilities
- **Permission Checks**: Proper file permission validation
- **Secure Defaults**: Secure configuration defaults
- **Audit Logging**: Comprehensive logging for security auditing
- **Secret Detection**: Pre-commit secret scanning
- **Path Traversal Prevention**: Multiple layers of path validation
- **Code Injection Prevention**: Safe parsers for YAML, JSON, TOML
- **Fuzzing**: Continuous fuzzing with ClusterFuzzLite
- **Dependency Scanning**: Automated vulnerability detection

## Contact

For security-related questions or concerns:

- **Email**: <bdc@virtualagentics.ai>
- **GitHub**: Use private vulnerability reporting
- **Response Time**: We aim to respond within 48 hours

## Acknowledgments

We appreciate the security research community's efforts in keeping our software secure. We will acknowledge security researchers who responsibly disclose vulnerabilities (unless they prefer to remain anonymous).

## Legal

By reporting a vulnerability, you agree to:

- Allow us to reproduce and investigate the vulnerability
- Keep the vulnerability confidential until we publicly disclose it
- Not access or modify data beyond what's necessary to demonstrate the vulnerability
- Not disrupt our services or systems

This security policy is effective as of the date of the last update and may be updated at any time.
