# Troubleshooting Guide

This guide covers common issues and solutions for the Review Bot Automator, including LLM provider setup, privacy verification, and general usage problems.

## Table of Contents

* [GitHub Authentication Issues](#github-authentication-issues)
* [LLM Provider Issues](#llm-provider-issues)
  * [OpenAI API](#openai-api)
  * [Anthropic API](#anthropic-api)
  * [Claude CLI](#claude-cli)
  * [Codex CLI](#codex-cli)
  * [Ollama](#ollama)
* [Circuit Breaker Issues](#circuit-breaker-issues)
* [Cost and Budget Issues](#cost-and-budget-issues)
* [Parallel Processing Issues](#parallel-processing-issues)
* [Privacy Verification Issues](#privacy-verification-issues)
* [Performance Issues](#performance-issues)
* [Installation Issues](#installation-issues)
* [General Issues](#general-issues)

## GitHub Authentication Issues

### "Authentication failed" Error

**Problem:** GitHub API authentication fails.

**Symptoms:**

```text
Error: Authentication failed
HTTP 401: Unauthorized

```

**Solutions:**

1. **Verify token is set:**

   ```bash
   echo $GITHUB_PERSONAL_ACCESS_TOKEN
   # Should display your token (starts with ghp_)

   ```

2. **Check token permissions:**
   * Token must have `repo` scope (full control of private repositories)
   * For organization repos, token needs `read:org` scope
   * Regenerate token at: <https://github.com/settings/tokens>

3. **Set token correctly:**

   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
   # Or add to ~/.bashrc or ~/.zshrc for persistence

   ```

4. **Try alternative token environment variable:**

   ```bash
   export GITHUB_TOKEN="ghp_your_token_here"
   # GITHUB_TOKEN is supported for backward compatibility

   ```

### "Repository not found" Error

**Problem:** Cannot access repository.

**Symptoms:**

```text
Error: Repository not found
HTTP 404: Not Found

```

**Solutions:**

1. **Verify repository details:**

   ```bash
   # Check repository exists and is accessible
   gh repo view OWNER/REPO

   ```

2. **Check token scopes:**
   * Private repos require `repo` scope
   * Organization repos require `read:org` scope

3. **Verify owner and repo names:**
   * Owner is case-sensitive
   * Repository name must match exactly

## LLM Provider Issues

### OpenAI API

#### Authentication Failures

**Problem:** OpenAI API key rejected.

**Symptoms:**

```text
Error: Incorrect API key provided
AuthenticationError: Invalid API key

```

**Solutions:**

1. **Verify API key:**

   ```bash
   echo $CR_LLM_API_KEY
   # Should start with sk-

   ```

2. **Generate new API key:**
   * Visit: <https://platform.openai.com/api-keys>
   * Create new secret key
   * Copy and set immediately (can't view later)

3. **Set API key:**

   ```bash
   export CR_LLM_ENABLED="true"
   export CR_LLM_PROVIDER="openai"
   export CR_LLM_API_KEY="sk-..."

   ```

#### Rate Limiting

**Problem:** OpenAI API rate limits exceeded.

**Symptoms:**

```text
Error: Rate limit exceeded
RateLimitError: You exceeded your current quota

```

**Solutions:**

1. **Check usage limits:**
   * Visit: <https://platform.openai.com/usage>
   * Verify you have available credits

2. **Reduce request rate:**
   * The resolver has automatic retry with exponential backoff
   * Wait a few minutes and try again

3. **Upgrade OpenAI account:**
   * Add payment method if on free tier
   * Increase usage limits at: <https://platform.openai.com/account/billing>

### Anthropic API

#### Authentication Failures

**Problem:** Anthropic API key rejected.

**Symptoms:**

```text
Error: Invalid API key
AuthenticationError: x-api-key header is invalid

```

**Solutions:**

1. **Verify API key:**

   ```bash
   echo $CR_LLM_API_KEY
   # Should start with sk-ant-

   ```

2. **Generate new API key:**
   * Visit: <https://console.anthropic.com/settings/keys>
   * Create new key
   * Copy and set immediately

3. **Set API key:**

   ```bash
   export CR_LLM_ENABLED="true"
   export CR_LLM_PROVIDER="anthropic"
   export CR_LLM_API_KEY="sk-ant-..."

   ```

#### Model Not Found

**Problem:** Specified model doesn't exist or isn't available.

**Symptoms:**

```text
Error: model: claude-sonnet-4-5 does not exist

```

**Solutions:**

1. **Use correct model name:**

   ```bash
   # Correct model names (as of Nov 2025):
   export CR_LLM_MODEL="claude-sonnet-4-5"      # Recommended (aliases claude-sonnet-4-20250514)
   export CR_LLM_MODEL="claude-haiku-4-5"       # Budget option

   ```

2. **Check available models:**
   * Visit: <https://docs.anthropic.com/en/api/models-list>
   * Verify model name and availability

### Claude CLI

#### Command Not Found

**Problem:** `claude` command not available.

**Symptoms:**

```text
bash: claude: command not found

```

**Solutions:**

1. **Install Claude CLI:**

   ```bash
   npm install -g @anthropic-ai/claude-code

   ```

2. **Verify installation:**

   ```bash
   claude --version

   ```

3. **Check PATH:**

   ```bash
   which claude
   # Should show path to claude binary

   ```

#### Authentication Required

**Problem:** Claude CLI not authenticated.

**Symptoms:**

```text
Error: Not authenticated. Please run 'claude auth login'

```

**Solutions:**

1. **Authenticate:**

   ```bash
   claude auth login
   # Follow interactive prompts

   ```

2. **Verify authentication:**

   ```bash
   claude auth status

   ```

3. **Set provider:**

   ```bash
   export CR_LLM_ENABLED="true"
   export CR_LLM_PROVIDER="claude-cli"
   # No API key needed - uses CLI authentication

   ```

### Codex CLI

#### Command Not Found

**Problem:** `codex` command not available.

**Symptoms:**

```text
bash: codex: command not found

```

**Solutions:**

1. **Install GitHub Copilot CLI (standalone):**

   ```bash
   # Requires Node.js and npm
   npm install -g @github/copilot

   ```

   **Note:** The old `gh-copilot` extension for GitHub CLI was deprecated and stopped working on October 25, 2025. Use the standalone npm package instead.

2. **Verify installation:**

   ```bash
   github-copilot --version

   ```

3. **Set provider:**

   ```bash
   export CR_LLM_ENABLED="true"
   export CR_LLM_PROVIDER="codex-cli"
   # Authenticate with: github-copilot auth

   ```

#### Copilot Subscription Required

**Problem:** GitHub Copilot subscription not active.

**Symptoms:**

```text
Error: GitHub Copilot subscription required

```

**Solutions:**

1. **Subscribe to GitHub Copilot:**
   * Individual: <https://github.com/settings/copilot>
   * Organization: Contact your GitHub admin

2. **Verify subscription:**

   ```bash
   gh copilot explain "test"

   ```

### Ollama

#### Connection Refused

**Problem:** Cannot connect to Ollama server.

**Symptoms:**

```text
Error: Connection refused
Failed to connect to <http://localhost:11434>

```

**Solutions:**

1. **Start Ollama service:**

   ```bash
   # macOS/Linux
   ollama serve

   # Or check if already running:
   curl <http://localhost:11434/api/tags>

   ```

2. **Verify Ollama installation:**

   ```bash
   ollama --version

   ```

3. **Install Ollama if missing:**

   ```bash
   # Linux/macOS
   curl -fsSL <https://ollama.ai/install.sh> | sh

   # macOS (alternative)
   brew install ollama

   # Windows
   # Download from <https://ollama.ai/download>

   ```

4. **Check custom URL:**

   ```bash
   export OLLAMA_BASE_URL="<http://localhost:11434">

   ```

#### Model Not Found

**Problem:** Requested model not downloaded.

**Symptoms:**

```text
Error: model 'llama3.3:70b' not found

```

**Solutions:**

1. **Pull model:**

   ```bash
   ollama pull llama3.3:70b

   ```

2. **List available models:**

   ```bash
   ollama list

   ```

3. **Use auto-download script:**

   ```bash
   ./scripts/download_ollama_models.sh
   # Interactive script to download recommended models

   ```

4. **Recommended models:**

   ```bash
   # Best performance (requires 40GB+ RAM)
   ollama pull llama3.3:70b

   # Balanced (requires 8GB+ RAM)
   ollama pull llama3.1:8b

   # Lightweight (requires 4GB+ RAM)
   ollama pull llama3.2:3b

   ```

#### GPU Not Detected

**Problem:** Ollama not using GPU acceleration.

**Symptoms:**

```text
Warning: GPU not detected, using CPU inference
Inference is very slow

```

**Solutions:**

1. **Verify GPU availability:**

   ```bash
   # NVIDIA
   nvidia-smi

   # AMD (Linux)
   rocm-smi

   # Apple Silicon
   system_profiler SPDisplaysDataType | grep "Chipset Model"

   ```

2. **Install GPU drivers:**
   * **NVIDIA**: Install CUDA toolkit and drivers
   * **AMD**: Install ROCm
   * **Apple**: GPU support built-in (macOS 12+)

3. **Restart Ollama:**

   ```bash
   # Stop Ollama
   pkill ollama

   # Start again (should detect GPU)
   ollama serve

   ```

4. **Check GPU detection script:**

   ```bash
   # Run GPU detection test
   python -c "from review_bot_automator.llm.providers.gpu_detector import GPUDetector; print(GPUDetector.detect_gpu('<http://localhost:11434'>))"

   ```

## Circuit Breaker Issues

### CircuitBreakerOpen Error

**Problem:** Requests blocked by circuit breaker.

**Symptoms:**

```text
CircuitBreakerOpen: Circuit breaker is open, retry in 45.2s
```

**Causes:**

* 5+ consecutive LLM API failures triggered the circuit
* Provider experiencing outage or rate limiting
* Network connectivity issues

**Solutions:**

1. **Wait for cooldown:**

   ```bash
   # Default cooldown is 60 seconds
   # Check remaining time in error message
   ```

2. **Check provider status:**

   ```bash
   # OpenAI
   curl https://status.openai.com/api/v2/status.json

   # Anthropic
   curl https://status.anthropic.com/api/v2/status.json
   ```

3. **Review logs for root cause:**

   ```bash
   pr-resolve apply 123 --log-level DEBUG
   # Look for "Circuit breaker opening after X consecutive failures"
   ```

4. **Adjust threshold if too sensitive:**

   ```bash
   export CR_LLM_CIRCUIT_BREAKER_THRESHOLD=10  # Default: 5
   export CR_LLM_CIRCUIT_BREAKER_COOLDOWN=30.0  # Default: 60.0
   ```

5. **Disable circuit breaker (not recommended):**

   ```bash
   export CR_LLM_CIRCUIT_BREAKER_ENABLED=false
   ```

### Circuit Trips Too Often

**Problem:** Circuit breaker triggers on transient failures.

**Solutions:**

1. **Increase threshold:**

   ```yaml
   llm:
     circuit_breaker_threshold: 10  # Allow more failures
   ```

2. **Enable retry first:**

   ```yaml
   llm:
     retry_on_rate_limit: true
     retry_max_attempts: 5
   ```

3. **Check network stability:**

   ```bash
   ping api.openai.com
   ping api.anthropic.com
   ```

## Cost and Budget Issues

### Budget Exceeded Error

**Problem:** LLM requests blocked due to budget limit.

**Symptoms:**

```text
ERROR: LLM cost budget exceeded: $5.23 of $5.00 used
```

**Solutions:**

1. **Increase budget:**

   ```bash
   export CR_LLM_COST_BUDGET=10.0  # Increase from $5 to $10
   ```

2. **Check current usage:**

   ```bash
   pr-resolve apply 123 --llm-enabled --show-metrics
   # Review "Total cost" in output
   ```

3. **Use cheaper model:**

   ```bash
   # Anthropic: Use Haiku instead of Sonnet
   export CR_LLM_MODEL="claude-haiku-4-20250514"

   # OpenAI: Use mini instead of full GPT-4o
   export CR_LLM_MODEL="gpt-4o-mini"
   ```

4. **Enable caching:**

   ```yaml
   llm:
     cache_enabled: true  # Reuse responses for identical prompts
   ```

### Unexpected High Costs

**Problem:** LLM costs higher than expected.

**Solutions:**

1. **Enable metrics to track:**

   ```bash
   pr-resolve apply 123 --llm-enabled --show-metrics --metrics-output costs.json
   ```

2. **Review per-provider costs:**

   ```bash
   cat costs.json | jq '.provider_stats'
   ```

3. **Check cache hit rate:**

   ```text
   # Low cache hit rate = more API calls = higher cost
   # Target: > 30% cache hit rate
   ```

4. **Use free providers for development:**

   ```bash
   export CR_LLM_PROVIDER=ollama
   export CR_LLM_MODEL=qwen2.5-coder:7b
   ```

### Budget Warning Not Appearing

**Problem:** No warning before budget exceeded.

**Solutions:**

1. **Warning appears at 80% by default:**

   ```text
   WARNING: LLM cost budget warning: $4.12 of $5.00 used (82.4%)
   ```

2. **Check log level:**

   ```bash
   export CR_LOG_LEVEL=INFO  # Warning requires INFO or lower
   ```

## Parallel Processing Issues

### Race Conditions or Corrupted Output

**Problem:** Parallel processing produces inconsistent results.

**Symptoms:**

* Different results on each run
* Partial or corrupted output files
* Mixed content from different files

**Solutions:**

1. **Reduce worker count:**

   ```bash
   pr-resolve apply 123 --parallel --max-workers 2
   ```

2. **Disable parallel processing:**

   ```bash
   pr-resolve apply 123  # Sequential by default
   # Or explicitly:
   export CR_PARALLEL=false
   ```

3. **Check for file conflicts:**

   ```bash
   # If multiple comments target same file, conflicts may occur
   pr-resolve analyze 123 --log-level DEBUG
   ```

### Workers Exhausted or Hanging

**Problem:** Parallel workers timeout or hang.

**Symptoms:**

```text
Warning: Worker timeout waiting for response
Processing stalled at X%
```

**Solutions:**

1. **Reduce workers:**

   ```bash
   export CR_MAX_WORKERS=2  # Default: 4
   ```

2. **Check LLM provider health:**

   ```bash
   # Test provider directly
   curl http://localhost:11434/api/tags  # Ollama
   ```

3. **Increase timeout:**

   ```bash
   # Not configurable via env var - contact support
   ```

4. **Monitor system resources:**

   ```bash
   htop  # Check CPU/memory usage
   ```

### Out of Memory with Parallel Processing

**Problem:** System runs out of memory.

**Solutions:**

1. **Reduce workers:**

   ```bash
   export CR_MAX_WORKERS=2
   ```

2. **Use smaller Ollama model:**

   ```bash
   export CR_LLM_MODEL=llama3.2:3b  # Instead of 70b
   ```

3. **Process sequentially:**

   ```bash
   export CR_PARALLEL=false
   ```

4. **Monitor memory usage:**

   ```bash
   watch -n 1 free -h
   ```

## Privacy Verification Issues

### Privacy Script Fails

**Problem:** `verify_privacy.sh` script fails or reports errors.

**Symptoms:**

```text
Error: Ollama not running
Error: Test PR processing failed

```

**Solutions:**

1. **Start Ollama first:**

   ```bash
   ollama serve

   ```

2. **Pull required model:**

   ```bash
   ollama pull llama3.3:70b

   ```

3. **Set environment variables:**

   ```bash
   export CR_LLM_ENABLED="true"
   export CR_LLM_PROVIDER="ollama"
   export CR_LLM_MODEL="llama3.3:70b"
   export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_..."

   ```

4. **Run script with debug:**

   ```bash
   bash -x ./scripts/verify_privacy.sh

   ```

### Unexpected Network Connections

**Problem:** Privacy script detects connections to third-party LLM vendors.

**Symptoms:**

```text
ERROR: Detected connection to api.openai.com
Privacy violation detected!

```

**Solutions:**

1. **Verify Ollama provider is set:**

   ```bash
   echo $CR_LLM_PROVIDER
   # Should be "ollama"

   ```

2. **Check for conflicting environment variables:**

   ```bash
   env | grep CR_LLM
   # Remove any OpenAI/Anthropic API keys
   unset CR_LLM_API_KEY

   ```

3. **Restart with clean environment:**

   ```bash
   # Clear all LLM-related vars
   unset CR_LLM_API_KEY
   unset CR_LLM_PROVIDER
   unset CR_LLM_MODEL

   # Set only Ollama vars
   export CR_LLM_ENABLED="true"
   export CR_LLM_PROVIDER="ollama"
   export CR_LLM_MODEL="llama3.3:70b"

   ```

## Performance Issues

### Slow Processing

**Problem:** PR analysis takes too long.

**Symptoms:**

* Processing 10+ minutes for small PRs
* Timeout errors

**Solutions:**

1. **Enable parallel processing:**

   ```bash
   pr-resolve apply --pr 123 --owner myorg --repo myrepo \
     --parallel --max-workers 8

   ```

2. **Use faster model:**

   ```bash
   # Anthropic (fast with caching)
   export CR_LLM_MODEL="claude-haiku-4"

   # OpenAI (fast)
   export CR_LLM_MODEL="gpt-4o-mini"

   # Ollama (use smaller model)
   export CR_LLM_MODEL="llama3.1:8b"

   ```

3. **Check network connection:**

   ```bash
   # Test GitHub API speed
   time gh api user

   ```

### High Memory Usage

**Problem:** Tool uses too much memory.

**Symptoms:**

* System slowdown
* Out of memory errors

**Solutions:**

1. **Use smaller Ollama model:**

   ```bash
   # Instead of llama3.3:70b (40GB RAM)
   ollama pull llama3.1:8b    # 8GB RAM
   ollama pull llama3.2:3b    # 4GB RAM

   ```

2. **Reduce parallel workers:**

   ```bash
   pr-resolve apply --pr 123 --owner myorg --repo myrepo \
     --parallel --max-workers 2

   ```

3. **Process in batches:**

   ```bash
   # Process specific files instead of whole PR
   pr-resolve apply --pr 123 --owner myorg --repo myrepo \
     --mode non-conflicts-only  # Process only non-conflicting first

   ```

## Installation Issues

### Dependency Conflicts

**Problem:** pip reports dependency conflicts.

**Symptoms:**

```text
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed

```

**Solutions:**

1. **Use fresh virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install review-bot-automator

   ```

2. **Upgrade pip:**

   ```bash
   pip install --upgrade pip setuptools wheel

   ```

3. **Install from source:**

   ```bash
   git clone <https://github.com/VirtualAgentics/review-bot-automator.git>
   cd review-bot-automator
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"

   ```

### Python Version Incompatible

**Problem:** Python version too old.

**Symptoms:**

```text
ERROR: Package requires Python >=3.12

```

**Solutions:**

1. **Check Python version:**

   ```bash
   python --version
   # Should be 3.12 or higher

   ```

2. **Install Python 3.12+:**

   ```bash
   # macOS
   brew install python@3.12

   # Ubuntu
   sudo apt update
   sudo apt install python3.12 python3.12-venv

   # Or use pyenv
   pyenv install 3.12.0
   pyenv global 3.12.0

   ```

## General Issues

### "No conflicts detected" but comments exist

**Problem:** Analyzer reports no conflicts but PR has comments.

**Solutions:**

1. **Check comment format:**
   * Comments must be from CodeRabbit or supported format
   * Comments must contain change suggestions (not just reviews)

2. **Verify LLM parsing:**

   ```bash
   # Enable LLM parsing for better coverage
   export CR_LLM_ENABLED="true"
   export CR_LLM_PROVIDER="ollama"  # or other provider

   ```

3. **Check comment line numbers:**
   * Comments must be on lines that exist in current file
   * Outdated comments may be ignored

### Type Checking Errors

**Problem:** MyPy reports type errors during development.

**Solutions:**

1. **Run MyPy manually:**

   ```bash
   source .venv/bin/activate
   mypy src/ --strict

   ```

2. **Check MyPy configuration:**

   ```bash
   cat pyproject.toml | grep -A 10 "\[tool.mypy\]"

   ```

3. **Update type stubs:**

   ```bash
   pip install --upgrade types-requests types-PyYAML

   ```

### Tests Failing

**Problem:** pytest reports test failures.

**Solutions:**

1. **Run tests with verbose output:**

   ```bash
   source .venv/bin/activate
   pytest -v

   ```

2. **Run specific test:**

   ```bash
   pytest tests/test_specific.py::test_function_name -v

   ```

3. **Check test dependencies:**

   ```bash
   pip install -e ".[dev]"

   ```

4. **Clear pytest cache:**

   ```bash
   rm -rf .pytest_cache
   pytest --cache-clear

   ```

## Getting Additional Help

If your issue isn't covered here:

1. **Check existing issues:**
   * Visit: <https://github.com/VirtualAgentics/review-bot-automator/issues>
   * Search for similar problems

2. **Create new issue:**
   * Use issue templates
   * Include error messages, commands run, environment details
   * Provide minimal reproduction steps

3. **Join discussions:**
   * Visit: <https://github.com/VirtualAgentics/review-bot-automator/discussions>
   * Ask questions and share solutions

4. **Review documentation:**
   * [LLM Provider Guide](llm-provider-guide.md)
   * [Getting Started](getting-started.md)
   * [Configuration Guide](configuration.md)
   * [Privacy Architecture](privacy-architecture.md)
   * [API Reference](api-reference.md)

## Debug Mode

For any issue, enable debug logging for detailed output:

```bash
# CLI flag
pr-resolve apply --pr 123 --owner myorg --repo myrepo --log-level DEBUG

# Environment variable
export CR_LOG_LEVEL="DEBUG"

# With log file
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --log-level DEBUG --log-file debug.log

```

Then share the debug log when reporting issues.
