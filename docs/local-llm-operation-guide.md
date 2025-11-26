# Local LLM Operation Guide

Complete guide for running Review Bot Automator with local LLM inference using Ollama to reduce third-party exposure.

> **See Also**: [Privacy Architecture](privacy-architecture.md) for privacy benefits and [Ollama Setup Guide](ollama-setup.md) for installation instructions.

## Table of Contents

* [Overview](#overview)
* [Prerequisites](#prerequisites)
* [Setup Process](#setup-process)
* [Privacy Verification](#privacy-verification)
* [Troubleshooting](#troubleshooting)
* [Maintenance and Updates](#maintenance-and-updates)

---

## Overview

### Why Local LLM Operation

Local LLM operation with Ollama provides:

* ✅ **Reduced Third-Party Exposure**: LLM vendors (OpenAI/Anthropic) never see your code
* ✅ **Simpler Compliance**: One fewer data processor in your chain (no LLM vendor BAA/DPA)
* ✅ **Cost Savings**: Zero per-request LLM fees after hardware investment
* ✅ **Control**: You manage model updates and data retention
* ✅ **No LLM Rate Limits**: Process as many reviews as your hardware allows

### Important Limitations

**This tool is NOT air-gapped and CANNOT operate offline**:

* ❌ **Requires Internet**: Must fetch PR comments from GitHub API
* ⚠️ **GitHub Has Access**: Your code is on GitHub (required for PR workflow)
* ⚠️ **CodeRabbit Has Access**: Review bot processes your code (required)
* ✅ **LLM Processing Local**: Only the LLM inference step is local

**What Ollama Actually Does**: Processes review comments locally instead of sending them to OpenAI/Anthropic. This eliminates LLM vendor exposure but does not eliminate GitHub or CodeRabbit access.

### What Works Locally

After setup, these features use local LLM inference:

* ✅ LLM-powered comment parsing (via local Ollama)
* ✅ Code review suggestion application
* ✅ Conflict resolution
* ✅ All pr-resolve commands (`apply`, `analyze`)

### What Requires Internet

Internet is always required for:

* ✅ **GitHub API**: Fetching PR data and review comments
* ✅ **GitHub Push**: Pushing resolved changes back to PR
* ⚠️ **Initial Setup**: Downloading Ollama, models, and Review Bot Automator package (provides the `pr-resolve` CLI)

---

## Prerequisites

Before starting local LLM operation, you need:

### System Requirements

* **OS**: Linux, macOS, or Windows (with WSL2)
* **RAM**: Minimum 8GB (16GB+ recommended)
* **Disk**: 10-20GB free space (for models)
* **Internet**: Required for GitHub API access
* **Optional**: GPU (NVIDIA, AMD, or Apple Silicon) for faster inference

### Software Requirements

* **Ollama**: Latest version
* **Python 3.12+**: With pip and venv
* **Review Bot Automator**: Latest version from PyPI (provides the `pr-resolve` CLI)
* **LLM Model**: At least one model (qwen2.5-coder:7b recommended)
* **GitHub Token**: For API access

---

## Setup Process

Follow these steps to set up local LLM operation:

### Step 1: Install Ollama

```bash
# Linux / macOS
curl -fsSL https://ollama.ai/install.sh | sh

# Verify installation
ollama --version

# Start Ollama service
ollama serve

```

For detailed installation instructions, see [Ollama Setup Guide](ollama-setup.md).

### Step 2: Download LLM Model

```bash
# Recommended: Qwen2.5 Coder (best quality/speed balance)
ollama pull qwen2.5-coder:7b

# Alternative: CodeLlama
ollama pull codellama:7b

# Verify model downloaded
ollama list

```

**Storage Note**: Models are stored in `~/.ollama/models/` and can be 4-8GB each.

### Step 3: Install Review Bot Automator

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate    # Windows

# Install review-bot-automator (provides the pr-resolve CLI)
pip install review-bot-automator

# Verify installation
pr-resolve --version

```

### Step 4: Configure Local LLM

Create or update your configuration file:

**config.yaml**:

```yaml
llm:
  enabled: true
  provider: ollama
  model: qwen2.5-coder:7b
  ollama_base_url: http://localhost:11434
  fallback_to_regex: true

github:
  token: ${GITHUB_TOKEN}  # Set via environment variable

```

### Step 5: Set GitHub Token

```bash
# Set GitHub token (required for API access)
export GITHUB_TOKEN=ghp_your_token_here

# Verify GitHub API access
gh auth status

```

### Step 6: Test Local LLM Operation

```bash
# Test with actual PR
pr-resolve apply 123 --llm-preset ollama-local

# Or use custom config
pr-resolve apply 123 --config config.yaml

```

### Step 7: Verify Privacy

```bash
# Run privacy verification script
./scripts/verify_privacy.sh

# Expected output
# ✅ Privacy Verification: PASSED
# ✅ No external LLM connections detected
# ⚠️  GitHub API connections detected (expected)

```

**Note**: The verification script confirms that Ollama only uses localhost for LLM inference. GitHub API calls will still appear in network traffic (this is expected and required).

---

## Privacy Verification

### Automated Verification

Use the provided script to verify Ollama's localhost-only operation:

```bash
# Run privacy verification
./scripts/verify_privacy.sh

# Generates report: privacy-verification-report.md

```

**What This Verifies**:

* ✅ Ollama only communicates on localhost (127.0.0.1:11434)
* ✅ No connections to OpenAI or Anthropic LLM APIs
* ⚠️ GitHub API calls are not blocked (expected behavior)

**What This Does NOT Verify**:

* ❌ Does not prevent GitHub API access (required for tool to function)
* ❌ Does not verify air-gapped operation (not possible with this tool)
* ❌ Does not prevent CodeRabbit from accessing your code

### Manual Verification

You can manually verify Ollama's local operation:

#### Linux

```bash
# Monitor network connections during inference
# (Filter out GitHub API connections)
sudo lsof -i -n -P | grep -v "api.github.com"

# Run inference
pr-resolve apply 123 --llm-preset ollama-local

# Check connections again - should only see localhost:11434

```

#### macOS

```bash
# Monitor network connections
lsof -i -n -P | grep -v "api.github.com"

# Run inference
pr-resolve apply 123 --llm-preset ollama-local

# Verify no new LLM vendor connections (OpenAI/Anthropic)

```

### Understanding Network Traffic

When using pr-resolve with Ollama, you will see:

✅ **Expected Connections**:

* `localhost:11434` (Ollama LLM inference)
* `api.github.com:443` (Fetching PR data)
* `github.com:443` (Pushing changes)

❌ **Connections That Should NOT Appear**:

* `api.openai.com` (OpenAI LLM vendor)
* `api.anthropic.com` (Anthropic LLM vendor)

---

## Troubleshooting

### Issue: "Connection refused to localhost:11434"

**Cause**: Ollama service not running

**Fix**:

```bash
# Start Ollama
ollama serve

# Or use systemd (Linux)
sudo systemctl start ollama

# Verify it's running
curl http://localhost:11434/api/version

```

### Issue: "Model not found"

**Cause**: Model not downloaded or wrong name

**Fix**:

```bash
# List available models
ollama list

# Pull missing model
ollama pull qwen2.5-coder:7b

# Verify in config
cat config.yaml | grep model

```

### Issue: "GitHub API rate limit exceeded"

**Cause**: Too many GitHub API requests

**Fix**:

```bash
# Use authenticated token for higher rate limits
export GITHUB_TOKEN=ghp_your_token_here

# Check rate limit status
gh api rate_limit

```

### Issue: "Out of memory error"

**Cause**: Model too large for available RAM

**Fix**:

```bash
# Use smaller model
ollama pull qwen2.5-coder:3b  # Smaller version

# Update config
# model: qwen2.5-coder:3b

# Or add swap space (Linux)
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

```

### Issue: "Slow inference speed"

**Cause**: CPU inference without GPU acceleration

**Solutions**:

1. **Use GPU** if available (automatic with NVIDIA/AMD/Apple Silicon)
2. **Use smaller model** (3B instead of 7B)
3. **Increase RAM** allocation
4. **Close other applications** to free resources

```bash
# Check if GPU is being used
ollama ps

# Expected output shows GPU usage
# NAME              ... SIZE    PROCESSOR
# qwen2.5-coder:7b  ... 4.7GB   100% GPU

```

---

## Maintenance and Updates

### Updating Ollama

```bash
# Linux/macOS: Re-run installer
curl -fsSL https://ollama.ai/install.sh | sh

# Restart Ollama service
sudo systemctl restart ollama  # Linux
# Or restart manually: ollama serve

```

### Updating Models

```bash
# Pull latest version of model
ollama pull qwen2.5-coder:7b

# Old version is automatically replaced
ollama list

```

### Managing Model Storage

```bash
# List all models with sizes
ollama list

# Remove unused models
ollama rm codellama:7b

# Check disk usage
du -sh ~/.ollama/models/

```

### Updating Review Bot Automator

```bash
# Update review-bot-automator (provides the pr-resolve CLI)
pip install --upgrade review-bot-automator

# Verify new version
pr-resolve --version

```

### Monitoring Resource Usage

```bash
# Monitor Ollama memory/CPU usage
ollama ps

# Linux: Monitor with htop
htop

# macOS: Monitor with Activity Monitor
open -a "Activity Monitor"

```

---

## Best Practices

### Security

1. ✅ **Keep Ollama localhost-only** (default: 127.0.0.1:11434)
2. ✅ **Don't expose Ollama port** to external network
3. ✅ **Use encrypted disk** for model storage (optional)
4. ✅ **Keep GitHub token secure** (use environment variable)

### Performance

1. ✅ **Use GPU acceleration** when available
2. ✅ **Choose model size** based on RAM (7B for 16GB+, 3B for 8GB)
3. ✅ **Monitor resource usage** during inference
4. ✅ **Close unnecessary applications** during LLM processing

### Compliance

1. ✅ **Document data flows** for audits (GitHub → local LLM → GitHub)
2. ✅ **Keep privacy verification reports** (`privacy-verification-report.md`)
3. ✅ **Review model provenance** (use official Ollama registry only)
4. ⚠️ **Understand limitations** (GitHub/CodeRabbit still have access)

---

## Related Documentation

### Setup & Configuration

* [Ollama Setup Guide](ollama-setup.md) - Detailed Ollama installation
* [LLM Configuration Guide](llm-configuration.md) - Provider setup and presets
* [Configuration Guide](configuration.md) - General configuration options

### Privacy & Security

* [Privacy Architecture](privacy-architecture.md) - Comprehensive privacy analysis
* [Privacy FAQ](privacy-faq.md) - Common privacy questions answered
* [Security Architecture](security-architecture.md) - Overall security design

### Performance (Best Practices)

* [Performance Benchmarks](performance-benchmarks.md) - Provider performance comparison

---

## Frequently Asked Questions

### Q: Is this air-gapped operation?

**A: No.** This tool requires internet access to fetch PR comments from GitHub API. Air-gapped operation is not possible because:

* Your code is already on GitHub (required for PR workflow)
* CodeRabbit processes your code (required for review comments)
* pr-resolve must fetch comments from GitHub API

**What Ollama does**: Eliminates LLM vendor (OpenAI/Anthropic) exposure by processing review comments locally.

### Q: What data does GitHub see?

**A: Everything.** Your code is hosted on GitHub, and GitHub's terms of service apply. Review Bot Automator uses GitHub API to fetch PR data.

### Q: What data does CodeRabbit see?

**A: Everything.** CodeRabbit (or any review bot) needs access to your code to generate review comments. This is required for the tool to function.

### Q: What data does Ollama/Local LLM see?

**A: Review comments and code context.** Ollama processes the review comments locally on your machine. The data never leaves localhost.

### Q: What's the actual privacy benefit?

**A: Eliminating LLM vendor exposure.** Instead of:

* GitHub (has access) + CodeRabbit (has access) + OpenAI/Anthropic (has access)

You get:

* GitHub (has access) + CodeRabbit (has access) + Local LLM (localhost only)

This reduces third-party exposure by one entity (the LLM vendor).

### Q: Can I use this offline?

**A: No.** Internet is required to:

* Fetch PR comments from GitHub API
* Push resolved changes back to GitHub

Ollama inference runs locally, but the overall workflow requires internet connectivity.

### Q: Is this compliant with GDPR/HIPAA/SOC2?

**A: It helps, but doesn't solve everything.** Using Ollama:

* ✅ Reduces the number of data processors (one fewer)
* ✅ Simplifies BAA/DPA chain (no LLM vendor agreement)
* ⚠️ Still requires agreements with GitHub and CodeRabbit

Your code being on GitHub is the primary compliance consideration, not the LLM provider choice.

---

**For more privacy details, see [Privacy Architecture](privacy-architecture.md).**
