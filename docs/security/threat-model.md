# Threat Model

## Executive Summary

This document provides a comprehensive threat model for the Review Bot Automator project. It identifies assets, threat actors, attack vectors, and specific threat scenarios with risk ratings and mitigations based on the **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege).

**Purpose**: Enable security teams, auditors, and maintainers to understand the security landscape and evaluate risk posture.

**Last Updated**: 2025-11-25
**Next Review**: Quarterly or after major architectural changes

---

## Asset Identification

### Critical Assets

#### 1. Source Code Files

**Description**: Local source code files that the system reads and modifies.

**Value**: HIGH
**Justification**: Contains intellectual property, business logic, and potentially sensitive data.

**Protection Mechanisms**:

* Path traversal prevention (`InputValidator.validate_file_path()`)
* Atomic file operations (`SecureFileHandler`)
* Backup and rollback capabilities
* Secret scanning before modifications (`SecretScanner`)

---

#### 2. Git Repositories

**Description**: Version control system containing project history and code.

**Value**: HIGH
**Justification**: Maintains integrity of code history, enables collaboration, critical for audit trails.

**Protection Mechanisms**:

* Read-only operations by default
* Commit signing support
* Git hook validation (future)
* Branch integrity verification

---

#### 3. GitHub API Tokens

**Description**: Authentication tokens for accessing GitHub API and repositories.

**Value**: CRITICAL
**Justification**: Provides access to private repositories, can be used for unauthorized actions.

**Protection Mechanisms**:

* Token validation (`InputValidator.validate_github_token()`)
* Secure token storage (environment variables, not in code)
* Secret scanning to prevent accidental exposure
* Token-based authentication with minimum required scopes

---

#### 4. User Data and PII

**Description**: Minimal user data collected (GitHub usernames, email addresses from commits).

**Value**: MEDIUM
**Justification**: Subject to GDPR and privacy regulations, but limited collection.

**Protection Mechanisms**:

* Data minimization (collect only what's necessary)
* No persistent storage of personal data
* Secure logging (no PII in logs)
* User consent for data processing

---

#### 5. File System Access

**Description**: Local file system where repositories are stored and modified.

**Value**: HIGH
**Justification**: Compromise could lead to data loss, malware installation, or system access.

**Protection Mechanisms**:

* Workspace containment (`resolve_file_path()` with `enforce_containment=True`)
* Symlink prevention
* Permission checks before file operations
* Restricted file system scope

---

#### 6. CI/CD Pipeline

**Description**: GitHub Actions workflows that run security scans, tests, and fuzzing.

**Value**: HIGH
**Justification**: Compromise could inject malicious code, bypass security controls, or expose secrets.

**Protection Mechanisms**:

* Pinned action versions (commit SHA)
* Step Security Harden Runner
* Restricted workflow permissions
* Secret scanning in workflows
* CodeQL analysis for workflow vulnerabilities

---

## Threat Actors

### 1. Malicious External Users

**Capability**: LOW to MEDIUM
**Motivation**: Exploit vulnerabilities for data theft, system compromise, or reputation damage.

**Attack Vectors**:

* Malicious code suggestions via compromised CodeRabbit API
* Social engineering to trick users into applying malicious changes
* Exploiting publicly disclosed vulnerabilities

**Typical Attacks**: Path traversal, code injection, secret leakage

---

### 2. Compromised Dependencies

**Capability**: MEDIUM to HIGH
**Motivation**: Supply chain attack to inject malware, steal credentials, or backdoor systems.

**Attack Vectors**:

* Typosquatting on PyPI
* Compromised legitimate packages
* Dependency confusion attacks

**Typical Attacks**: Remote code execution, data exfiltration, persistent backdoors

---

### 3. Insider Threats (Low Trust)

**Capability**: MEDIUM
**Motivation**: Malicious insiders with access to codebase or CI/CD.

**Attack Vectors**:

* Direct code commits bypassing security reviews
* Modification of security configurations
* Disabling security controls

**Typical Attacks**: Logic bombs, backdoors, data theft

---

### 4. Automated Attack Tools

**Capability**: LOW
**Motivation**: Automated scanning for known vulnerabilities.

**Attack Vectors**:

* Vulnerability scanners
* Exploit frameworks (Metasploit, etc.)
* Botnet attacks

**Typical Attacks**: Known CVE exploitation, brute force, DoS

---

## STRIDE Threat Analysis

### Spoofing (Identity Forgery)

#### T1: GitHub API Spoofing

**Description**: Attacker impersonates GitHub API to provide malicious code suggestions.

**Impact**: HIGH
**Likelihood**: MEDIUM
**Risk Rating**: HIGH

**Attack Scenario**:

1. Attacker performs MITM attack on network
2. Intercepts GitHub API calls
3. Provides malicious responses with crafted code suggestions
4. System applies malicious suggestions

**Mitigations**:

* ✅ HTTPS enforcement for all API calls (security.yml:348-350)
* ✅ Certificate validation (`InputValidator.validate_github_url()`)
* ⏳ Certificate pinning (planned)
* ✅ Token-based authentication

**Residual Risk**: LOW (with HTTPS and token auth)

---

#### T2: Git Commit Spoofing

**Description**: Attacker creates commits with forged author information.

**Impact**: MEDIUM
**Likelihood**: MEDIUM
**Risk Rating**: MEDIUM

**Attack Scenario**:

1. Attacker modifies git config
2. Sets fake author identity
3. Creates malicious commits with trusted identity
4. Commits appear to come from legitimate developers

**Mitigations**:

* ⏳ Git commit signing support (planned Phase 0.8)
* ✅ Audit logging of all operations
* ✅ Read-only git operations by default

**Residual Risk**: MEDIUM (until commit signing implemented)

---

### Tampering (Data Modification)

#### T3: Path Traversal Attack

**Description**: Attacker crafts file paths to access/modify files outside repository.

**Impact**: CRITICAL
**Likelihood**: HIGH
**Risk Rating**: CRITICAL

**Attack Scenario**:

1. Attacker provides suggestion with path: `../../etc/passwd`
2. System resolves path outside workspace
3. Attacker reads sensitive system files
4. Potential overwrite of critical files

**Mitigations**:

* ✅ **IMPLEMENTED**: `InputValidator.validate_file_path()` (input_validator.py:131-230)
* ✅ Path normalization and resolution
* ✅ Workspace containment enforcement (`enforce_containment=True`)
* ✅ Symlink detection and rejection
* ✅ Relative path validation

**Implementation Reference**:

```python
# json_handler.py:92-109
if not InputValidator.validate_file_path(
    path, allow_absolute=True, base_dir=str(self.workspace_root)
):
    self.logger.error(f"Invalid file path rejected: {path}")
    return False

file_path = resolve_file_path(
    path, self.workspace_root,
    allow_absolute=True, validate_workspace=True,
    enforce_containment=True
)

```

**Residual Risk**: VERY LOW (multiple layers of protection)

---

#### T4: Code Injection via YAML/JSON/TOML

**Description**: Attacker injects executable code through configuration files.

**Impact**: CRITICAL
**Likelihood**: MEDIUM
**Risk Rating**: HIGH

**Attack Scenario**:

1. Attacker crafts malicious YAML:

   ```yaml
   key: !!python/object/apply:os.system ["rm -rf /"]

   ```

2. System parses YAML with unsafe parser
3. Code executes during parsing
4. System compromise

**Mitigations**:

* ✅ **IMPLEMENTED**: Safe YAML parser (`yaml.safe_load()`) in input_validator.py:332-362
* ✅ Safe JSON parser with duplicate key detection (json_handler.py:442-465)
* ✅ Safe TOML parser (toml_handler.py)
* ✅ Whitelist of allowed data types
* ✅ No dynamic code execution

**Implementation Reference**:

```python
# input_validator.py:348-362
try:
    yaml_data = yaml.safe_load(content)  # safe_load prevents !!python/
    if not isinstance(yaml_data, dict):
        return False, "YAML must be a dictionary at top level"
    return True, "Valid YAML"
except yaml.YAMLError as e:
    return False, f"Invalid YAML: {e}"

```

**Residual Risk**: VERY LOW (safe parsers enforced)

---

#### T5: File System Race Conditions (TOCTOU)

**Description**: Time-of-check to time-of-use vulnerabilities in file operations.

**Impact**: MEDIUM
**Likelihood**: LOW
**Risk Rating**: LOW

**Attack Scenario**:

1. System checks file permissions
2. Attacker replaces file with malicious version
3. System operates on malicious file
4. Data corruption or unauthorized access

**Mitigations**:

* ✅ **IMPLEMENTED**: Atomic file operations (secure_file_handler.py:96-215)
* ✅ Temporary file with atomic rename (os.replace)
* ✅ File locking where applicable
* ✅ Transaction-like semantics

**Implementation Reference**:

```python
# json_handler.py:169-188
with tempfile.NamedTemporaryFile(..., delete=False) as temp_file:
    temp_path = Path(temp_file.name)
    temp_file.write(json.dumps(merged_data, indent=2) + "\n")
    temp_file.flush()
    os.fsync(temp_file.fileno())  # Ensure written to disk

os.replace(temp_path, file_path)  # Atomic operation

```

**Residual Risk**: VERY LOW (atomic operations enforced)

---

### Repudiation (Denying Actions)

#### T6: Audit Log Tampering

**Description**: Attacker modifies or deletes logs to hide malicious activity.

**Impact**: MEDIUM
**Likelihood**: LOW
**Risk Rating**: LOW

**Attack Scenario**:

1. Attacker gains access to log files
2. Deletes or modifies incriminating log entries
3. Malicious activity goes undetected
4. Forensic investigation hampered

**Mitigations**:

* ✅ Secure logging (no secrets in logs)
* ✅ Structured logging with timestamps
* ⏳ Centralized log aggregation (future)
* ⏳ Immutable log storage (future)

**Residual Risk**: MEDIUM (until centralized logging)

---

### Information Disclosure (Data Leakage)

#### T7: Secret Leakage in Code Suggestions

**Description**: Attacker tricks system into applying suggestions containing secrets.

**Impact**: HIGH
**Likelihood**: MEDIUM
**Risk Rating**: HIGH

**Attack Scenario**:

1. Attacker crafts suggestion with embedded API key
2. System applies suggestion without detection
3. Secret committed to repository
4. Secret exposed in public repository

**Mitigations**:

* ✅ **IMPLEMENTED**: `SecretScanner` with 17 pattern types (secret_scanner.py:73-140)
* ✅ Pre-application secret scanning
* ✅ False positive filtering
* ✅ TruffleHog scanning in CI/CD
* ✅ GitGuardian integration (future)

**Implementation Reference**:

```python
# secret_scanner.py:154-194
def scan_content(content: str, stop_on_first: bool = False) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for finding in SecretScanner.scan_content_generator(content):
        findings.append(finding)
        if stop_on_first:
            break  # Early exit on first secret
    return findings

```

**Patterns Detected**:

* GitHub personal/OAuth/server/refresh tokens
* AWS access keys and secret keys
* OpenAI API keys
* JWT tokens
* Private keys (RSA, SSH, etc.)
* Slack tokens
* Google OAuth
* Azure connection strings
* Database URLs with passwords
* Generic API keys, passwords, secrets, tokens

**Residual Risk**: LOW (comprehensive scanning)

---

#### T8: Sensitive Data in Error Messages

**Description**: Error messages leak sensitive file paths, content, or system info.

**Impact**: LOW
**Likelihood**: MEDIUM
**Risk Rating**: LOW

**Attack Scenario**:

1. Attacker triggers error conditions
2. Error messages reveal internal paths
3. Attacker maps file system structure
4. Information used for further attacks

**Mitigations**:

* ✅ Sanitized error messages (no stack traces in production)
* ✅ No file content in error output
* ✅ Generic error messages for users
* ✅ Detailed errors only in debug logs

**Residual Risk**: VERY LOW (sanitized errors)

---

### Denial of Service (Availability)

#### T9: Large File Processing DoS

**Description**: Attacker provides extremely large files to exhaust system resources.

**Impact**: MEDIUM
**Likelihood**: MEDIUM
**Risk Rating**: MEDIUM

**Attack Scenario**:

1. Attacker submits suggestion for 1GB file
2. System attempts to load entire file into memory
3. Out-of-memory condition
4. System crash or hang

**Mitigations**:

* ✅ File size limits (configurable)
* ✅ Memory-efficient streaming for large files (where applicable)
* ✅ Timeout mechanisms
* ⏳ Rate limiting (future)

**Residual Risk**: MEDIUM (file size limits configurable)

---

#### T10: Algorithmic Complexity Attacks

**Description**: Attacker exploits worst-case performance of algorithms.

**Impact**: LOW
**Likelihood**: LOW
**Risk Rating**: LOW

**Attack Scenario**:

1. Attacker crafts pathological input
2. System uses O(n²) or worse algorithm
3. CPU exhaustion
4. Service degradation

**Mitigations**:

* ✅ Efficient algorithms (e.g., line-sweep for overlap calculation)
* ✅ ClusterFuzzLite fuzzing for performance regression detection
* ✅ Timeout mechanisms

**Residual Risk**: VERY LOW (efficient algorithms, fuzzing)

---

### Elevation of Privilege (Unauthorized Access)

#### T11: Privilege Escalation via File Permissions

**Description**: Attacker exploits improper file permissions to gain elevated access.

**Impact**: HIGH
**Likelihood**: LOW
**Risk Rating**: MEDIUM

**Attack Scenario**:

1. Attacker provides suggestion modifying file permissions
2. System applies suggestion without validation
3. Critical files made world-writable
4. Attacker gains unauthorized access

**Mitigations**:

* ✅ File permission preservation (json_handler.py:164-166, 183-185)
* ✅ Permission checks before operations
* ✅ No arbitrary file permission modifications
* ✅ Restricted file system scope

**Implementation Reference**:

```python
# json_handler.py:164-166
if file_path.exists():
    original_mode = os.stat(file_path).st_mode

# ...after writing..
# json_handler.py:183-185
if original_mode is not None:
    os.chmod(temp_path, stat.S_IMODE(original_mode))

```

**Residual Risk**: LOW (permission preservation)

---

#### T12: Dependency Confusion Attack

**Description**: Attacker publishes malicious package with same name to public repository.

**Impact**: HIGH
**Likelihood**: LOW
**Risk Rating**: MEDIUM

**Attack Scenario**:

1. Attacker identifies internal package name
2. Publishes malicious version to PyPI
3. Build system installs malicious package
4. Code execution and compromise

**Mitigations**:

* ✅ Dependency pinning (requirements-dev.txt with hashes)
* ✅ `pip-compile --generate-hashes` for integrity verification
* ✅ Dependency scanning (pip-audit + Trivy SBOM scanning)
* ✅ OpenSSF Scorecard monitoring for dependency hygiene
* ✅ Automatic Dependency Submission workflow

**Residual Risk**: LOW (multiple layers of dependency protection)

---

### LLM-Specific Threats (Phase 5)

#### T13: LLM Data Exfiltration via PR Comments

**Description**: Sensitive data (secrets, credentials) in PR comments sent to external LLM APIs.

**Impact**: HIGH
**Likelihood**: MEDIUM
**Risk Rating**: HIGH

**Attack Scenario**:

1. User posts PR comment containing API keys or credentials
2. Comment body is processed by LLM parser
3. Secrets are sent to external LLM API (Anthropic/OpenAI)
4. Credentials exposed to third-party service

**Mitigations**:

* ✅ **IMPLEMENTED**: `SecretScanner.scan_content()` before LLM calls (parser.py:147-158)
* ✅ **IMPLEMENTED**: `LLMSecretDetectedError` raised when secrets detected
* ✅ 17 secret detection patterns covering major providers
* ✅ Configurable `scan_for_secrets` parameter (default: True)

**Residual Risk**: LOW (comprehensive pre-LLM secret scanning)

---

#### T14: Prompt Injection Attack

**Description**: Malicious PR comments containing prompts designed to manipulate LLM responses.

**Impact**: MEDIUM
**Likelihood**: MEDIUM
**Risk Rating**: MEDIUM

**Attack Scenario**:

1. Attacker crafts PR comment with embedded instructions
2. Comment processed by LLM parser
3. LLM follows injected instructions instead of parsing intent
4. Malicious code suggestions generated

**Mitigations**:

* ✅ Structured JSON output format enforced
* ✅ Schema validation on all ParsedChange objects
* ✅ Confidence threshold filtering (default: 0.5)
* ✅ Invalid JSON responses rejected

**Residual Risk**: MEDIUM (inherent LLM limitation, multiple validation layers)

---

#### T15: LLM Cache Poisoning

**Description**: Attacker attempts to poison prompt cache with malicious responses.

**Impact**: MEDIUM
**Likelihood**: LOW
**Risk Rating**: LOW

**Attack Scenario**:

1. Attacker crafts comment that generates specific cache key
2. Malicious response cached
3. Future identical prompts return poisoned response
4. Malicious code suggestions served from cache

**Mitigations**:

* ✅ SHA-256 hash-based cache keys (collision-resistant)
* ✅ Cache stores prompt hash, not actual prompt text
* ✅ Cache files have 0600 permissions (owner-only)
* ✅ Cache directory has 0700 permissions

**Residual Risk**: VERY LOW (cryptographic hash prevents practical collision attacks)

---

#### T16: LLM Cost Exhaustion Attack

**Description**: Attacker triggers excessive LLM API calls to exhaust budget or cause financial harm.

**Impact**: LOW
**Likelihood**: LOW
**Risk Rating**: LOW

**Attack Scenario**:

1. Attacker creates many PR comments
2. Each comment triggers LLM API call
3. Budget exhausted rapidly
4. Financial impact or denial of service

**Mitigations**:

* ✅ **IMPLEMENTED**: `CostTracker` with configurable budget
* ✅ **IMPLEMENTED**: `LLMCostExceededError` when budget exceeded
* ✅ Warning at configurable threshold (default: 80%)
* ✅ Graceful fallback to regex parsing
* ✅ Rate limiting in `ParallelLLMParser`

**Residual Risk**: LOW (budget enforcement with graceful degradation)

---

#### T17: API Key Exposure in Error Messages

**Description**: API keys or secrets leaked in error messages or logs.

**Impact**: HIGH
**Likelihood**: MEDIUM
**Risk Rating**: MEDIUM

**Attack Scenario**:

1. LLM provider returns error containing request details
2. Error message includes API key or sensitive data
3. Error logged or displayed to user
4. Credentials exposed

**Mitigations**:

* ✅ **IMPLEMENTED**: `ResilientLLMProvider` sanitizes exception messages
* ✅ **IMPLEMENTED**: `SecretScanner.has_secrets()` checks error strings
* ✅ Secrets in errors replaced with "(details redacted)"
* ✅ API keys stored in environment variables, not code

**Residual Risk**: LOW (automatic sanitization of error messages)

---

## Risk Matrix

| Threat ID | Threat | Impact | Likelihood | Risk | Status |
| ----------- | -------- | -------- | ------------ | ------ | -------- |
| T1 | GitHub API Spoofing | HIGH | MEDIUM | HIGH | ✅ Mitigated |
| T2 | Git Commit Spoofing | MEDIUM | MEDIUM | MEDIUM | ⏳ Partial |
| T3 | Path Traversal Attack | CRITICAL | HIGH | CRITICAL | ✅ Mitigated |
| T4 | Code Injection (YAML/JSON/TOML) | CRITICAL | MEDIUM | HIGH | ✅ Mitigated |
| T5 | File System Race Conditions | MEDIUM | LOW | LOW | ✅ Mitigated |
| T6 | Audit Log Tampering | MEDIUM | LOW | LOW | ⏳ Partial |
| T7 | Secret Leakage | HIGH | MEDIUM | HIGH | ✅ Mitigated |
| T8 | Sensitive Data in Errors | LOW | MEDIUM | LOW | ✅ Mitigated |
| T9 | Large File DoS | MEDIUM | MEDIUM | MEDIUM | ⏳ Partial |
| T10 | Algorithmic Complexity | LOW | LOW | LOW | ✅ Mitigated |
| T11 | Privilege Escalation | HIGH | LOW | MEDIUM | ✅ Mitigated |
| T12 | Dependency Confusion | HIGH | LOW | MEDIUM | ✅ Mitigated |
| T13 | LLM Data Exfiltration | HIGH | MEDIUM | HIGH | ✅ Mitigated |
| T14 | Prompt Injection | MEDIUM | MEDIUM | MEDIUM | ⏳ Partial |
| T15 | LLM Cache Poisoning | MEDIUM | LOW | LOW | ✅ Mitigated |
| T16 | LLM Cost Exhaustion | LOW | LOW | LOW | ✅ Mitigated |
| T17 | API Key in Errors | HIGH | MEDIUM | MEDIUM | ✅ Mitigated |

**Legend**:

* ✅ Mitigated: Controls fully implemented
* ⏳ Partial: Controls partially implemented or planned
* ❌ Unmitigated: No controls in place

---

## Security Control Mapping

| Control | Threats Addressed | Implementation | Effectiveness |
| --------- | ------------------- | ---------------- | --------------- |
| InputValidator | T1, T3, T4, T7 | input_validator.py | HIGH |
| SecretScanner | T7 | secret_scanner.py | HIGH |
| SecureFileHandler | T3, T5, T11 | secure_file_handler.py | HIGH |
| Safe Parsers | T4 | yaml.safe_load, json.loads | HIGH |
| Atomic File Operations | T5 | os.replace, tempfile | HIGH |
| Path Resolution | T3 | path_utils.py | HIGH |
| Dependency Scanning | T12 | pip-audit, Trivy, OpenSSF Scorecard | HIGH |
| Fuzzing | T9, T10 | ClusterFuzzLite | MEDIUM |
| Secret Scanning (CI) | T7 | TruffleHog, Scorecard | HIGH |
| HTTPS Enforcement | T1 | GitHub API client | HIGH |
| LLM Pre-Scan | T13, T17 | parser.py, SecretScanner | HIGH |
| CostTracker | T16 | cost_tracker.py | HIGH |
| ResilientLLMProvider | T17 | resilient_provider.py | HIGH |
| PromptCache | T15 | cache/prompt_cache.py | HIGH |
| ParallelLLMParser | T16 | parallel_parser.py | HIGH |

---

## Recommendations

### Immediate Actions (0-30 days)

1. **Implement commit signing**: Add GPG commit signing support (addresses T2)
2. **Centralized logging**: Implement immutable log aggregation (addresses T6)
3. **Rate limiting**: Add configurable rate limits for API calls and file operations (addresses T9)

### Short-term (1-3 months)

1. **Certificate pinning**: Implement cert pinning for GitHub API (addresses T1)
2. **Sandboxing**: Explore containerized execution for additional isolation (addresses T4, T11)
3. **Audit trail**: Implement cryptographic audit trail for all operations (addresses T6)

### Long-term (3-6 months)

1. **Penetration testing**: Regular third-party security audits
2. **Bug bounty program**: Public bug bounty to incentivize security research
3. **Security monitoring**: Real-time security event monitoring and alerting

---

## References

* **STRIDE Methodology**: <https://learn.microsoft.com/en-us/security/compass/applications-services-threat-modeling>
* **OWASP Threat Modeling**: <https://owasp.org/www-community/Threat_Modeling>
* **CWE Top 25**: <https://cwe.mitre.org/top25/>
* **Security Architecture**: [docs/security-architecture.md](../security-architecture.md)
* **Implementation**: [src/review_bot_automator/security/](../../src/review_bot_automator/security/)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-25
**Next Review**: 2026-02-03 (Quarterly)
**Owner**: Security Team
**Approval**: Pending
