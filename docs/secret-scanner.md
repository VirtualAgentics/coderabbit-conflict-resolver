# Secret Scanner

The secret scanner detects potential secrets and sensitive data in code changes before they are applied, helping prevent accidental credential exposure.

## Overview

The secret scanner:

* Detects common secret patterns (API keys, passwords, tokens)
* Assigns severity levels (LOW, MEDIUM, HIGH)
* Integrates with the change application pipeline
* Supports custom pattern definitions

## Detected Secret Types

| Type | Pattern Examples | Severity |
|------|-----------------|----------|
| AWS Access Key | `AKIA...` | HIGH |
| AWS Secret Key | `aws_secret_access_key=...` | HIGH |
| GitHub Token | `ghp_...`, `gho_...`, `ghs_...` | HIGH |
| OpenAI API Key | `sk-...` | HIGH |
| Generic API Key | `api_key=...`, `apikey:...` | MEDIUM |
| Password | `password=...`, `passwd:...` | MEDIUM |
| Private Key | `-----BEGIN RSA PRIVATE KEY-----` | HIGH |
| Connection String | `postgresql://user:pass@host` | HIGH |

## How It Works

```text
┌─────────────────────────────────────────────────────────────────┐
│                      Change Detection                           │
│                            │                                    │
│                            ▼                                    │
│                   ┌─────────────────┐                           │
│                   │  Secret Scanner │                           │
│                   └─────────────────┘                           │
│                            │                                    │
│                            ▼                                    │
│                 ┌─────────────────────┐                         │
│                 │  Secrets Detected?  │                         │
│                 └─────────────────────┘                         │
│                      │          │                               │
│                     YES        NO                               │
│                      │          │                               │
│                      ▼          ▼                               │
│              ┌───────────┐  ┌───────────┐                       │
│              │   Warn    │  │  Apply    │                       │
│              │  + Block  │  │  Change   │                       │
│              └───────────┘  └───────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

## Usage

The secret scanner runs automatically during change application. No explicit configuration is required.

### Viewing Scan Results

When secrets are detected:

```text
WARNING: Potential secret detected in src/config.py:
  - Line 42: API key pattern detected (severity: HIGH)
  - Pattern: api_key = "sk-..."

Change application blocked. Review and remove secrets before proceeding.
```

### Severity Levels

| Severity | Action | Description |
|----------|--------|-------------|
| LOW | Log warning | Possible false positive, proceed with caution |
| MEDIUM | Log warning | Likely sensitive data, review recommended |
| HIGH | Block + warn | Strong indication of secret (API keys, private keys, AWS creds), manual review required |

## False Positive Handling

### Common False Positives

* Example/placeholder values in documentation
* Base64-encoded non-secret data
* Test fixtures with fake credentials
* UUIDs that match API key patterns

### Suppressing False Positives

Add a comment to suppress scanning for a specific line:

```python
# nosecret: This is an example API key for documentation
api_key = "sk-example-key-not-real"
```

Or for a block:

```python
# nosecret-begin
EXAMPLE_CONFIG = {
    "api_key": "sk-fake-key",
    "password": "example-password"
}
# nosecret-end
```

## Integration with Change Application

### Default Behavior

1. Scan all changes before application
2. Block changes with HIGH/CRITICAL severity secrets
3. Log warnings for LOW/MEDIUM severity
4. Continue if no secrets detected

### Configuration

Secret scanning is enabled by default. To disable (not recommended):

```yaml
security:
  secret_scanning_enabled: false  # Not recommended
```

## Programmatic Usage

```python
from review_bot_automator.security.secret_scanner import SecretScanner

scanner = SecretScanner()

# Scan a single file
results = scanner.scan_content(
    content="api_key = 'sk-123...'",
    filename="config.py"
)

for result in results:
    print(f"Line {result.line}: {result.pattern_name} ({result.severity})")
    print(f"  Match: {result.matched_text[:20]}...")
```

## Best Practices

### 1. Use Environment Variables

Instead of hardcoding secrets:

```python
# Bad
API_KEY = "sk-abc123..."

# Good
import os
API_KEY = os.getenv("API_KEY")
```

### 2. Use Secret Management

For production:

* AWS Secrets Manager
* HashiCorp Vault
* GitHub Secrets (for Actions)

### 3. Review All Warnings

Even LOW severity warnings may indicate:

* Accidental commit of real credentials
* Configuration that should use env vars
* Documentation that needs redaction

### 4. Gitignore Sensitive Files

Ensure `.gitignore` includes:

```text
.env
*.pem
*.key
credentials.json
secrets.yaml
```

## What to Do When Secrets Are Detected

### 1. Don't Commit

If the scanner blocks application, do not force it.

### 2. Rotate the Secret

If a real secret was exposed:

1. Immediately rotate/revoke the credential
2. Check git history for exposure
3. Use `git filter-branch` or BFG Repo-Cleaner to remove from history

### 3. Use Environment Variables

Replace hardcoded secrets:

```bash
# Set environment variable
export API_KEY="sk-real-key-here"
```

```python
# Use in code
api_key = os.getenv("API_KEY")
```

### 4. Update Documentation

If false positive in docs, use:

```python
# nosecret: Example only
API_KEY = "sk-example-placeholder"
```

## See Also

* [Security Architecture](security-architecture.md) - Overall security design
* [Configuration](configuration.md) - Environment variable configuration
* [Troubleshooting](troubleshooting.md) - Common issues and solutions
