# Safety CLI Setup Guide

## Overview
This project uses the official [Safety GitHub Action](https://github.com/pyupio/safety-action) for vulnerability scanning in CI/CD.

## Authentication

The `SAFETY_API_KEY` secret has been configured for this repository.

### For Repository Maintainers

If you need to rotate or update the API key:

1. **Generate a new API key:**
   ```bash
   pip install -U safety
   safety auth login
   ```
   Then visit [Safety Platform](https://platform.safetycli.com/) > **Organization Settings** > **API Keys** > **Generate New API Key**

2. **Update GitHub Secret:**
   - Go to repository **Settings** > **Secrets and variables** > **Actions**
   - Update `SAFETY_API_KEY` with the new value

## Local Development

To run Safety scans locally:

```bash
# Install Safety (already in dev dependencies)
source .venv/bin/activate
pip install -e ".[dev]"

# Authenticate (one-time setup)
safety auth login

# Run scan
safety scan
```

## CI/CD Integration

The Security workflow (`.github/workflows/security.yml`) automatically:
- Runs Safety scans on all pull requests
- Checks for CRITICAL severity vulnerabilities
- Uploads scan reports as artifacts
- Fails CI if CRITICAL vulnerabilities are found

## References

- [Safety GitHub Action](https://github.com/pyupio/safety-action)
- [Safety CLI Documentation](https://docs.safetycli.com)
- [Safety Platform](https://platform.safetycli.com/)
