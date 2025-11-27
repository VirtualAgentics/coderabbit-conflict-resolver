# LLM Configuration Guide

> **✅ Production Status**: All 5 LLM providers are production-ready (Phase 2 Complete - Nov 9, 2025)
>
> * OpenAI API, Anthropic API, Claude CLI, Codex CLI, Ollama
> * All providers support retry logic, cost tracking, and health checks
> * GPU acceleration available for Ollama (NVIDIA, AMD, Apple Silicon)
> * HTTP connection pooling and model auto-download features included

This guide covers advanced LLM configuration features including configuration files, presets, and environment variable interpolation.

> **Note**: LLM features are supported by both `apply` and `analyze` commands with identical configuration options.
> **See Also**: [Main Configuration Guide](configuration.md#llm-provider-configuration) for basic LLM setup and provider-specific documentation.

## Table of Contents

* [Configuration File Support](#configuration-file-support)
* [LLM Effort Level](#llm-effort-level)
* [LLM Presets](#llm-presets)
* [Environment Variable Interpolation](#environment-variable-interpolation)
* [Configuration Precedence](#configuration-precedence)
* [API Key Security](#api-key-security)
* [Examples](#examples)
* [Troubleshooting](#troubleshooting)

## Configuration File Support

The resolver supports YAML and TOML configuration files for LLM settings. This allows you to:

* Store non-sensitive configuration in version control
* Share team-wide LLM settings
* Manage complex configurations more easily
* Use environment variable interpolation for secrets

### YAML Configuration

Create a `config.yaml` file:

```yaml
llm:
  enabled: true
  provider: anthropic
  model: claude-sonnet-4-5
  api_key: ${ANTHROPIC_API_KEY}  # Environment variable reference
  fallback_to_regex: true
  cache_enabled: true
  max_tokens: 2000
  confidence_threshold: 0.6  # Reject changes below 60% confidence
  cost_budget: 5.0  # Note: cost_budget is advisory and not currently enforced (see [Sub-Issue #225](../planning/ROADMAP.md))

```

Use with:

```bash
# With apply command
pr-resolve apply 123 --config config.yaml

# With analyze command
pr-resolve analyze --pr 123 --owner myorg --repo myrepo --config config.yaml

```

### TOML Configuration

Create a `config.toml` file:

```toml
[llm]
enabled = true
provider = "openai"
model = "gpt-4o-mini"
api_key = "${OPENAI_API_KEY}"  # Environment variable reference
fallback_to_regex = true
cache_enabled = true
max_tokens = 2000
confidence_threshold = 0.6  # Reject changes below 60% confidence
cost_budget = 5.0  # Note: cost_budget is advisory and not currently enforced.
                    # This field allows users to express intended spending limits and
                    # serves as a placeholder for future enforcement/alerts (see [Sub-Issue #225](../planning/ROADMAP.md)).

```

Use with:

```bash
pr-resolve apply 123 --config config.toml

```

### Configuration File Schema

| Field | Type | Default | Description |
| ------- | ------ | --------- | ------------- |
| `llm.enabled` | boolean | `false` | Enable LLM-powered features |
| `llm.provider` | string | `claude-cli` | Provider name (`claude-cli`, `codex-cli`, `ollama`, `openai`, `anthropic`) |
| `llm.model` | string | provider-specific | Model identifier (e.g., `claude-sonnet-4-5`, `gpt-4o-mini`) |
| `llm.api_key` | string | `null` | **Must use `${VAR}` syntax** - direct keys are rejected |
| `llm.fallback_to_regex` | boolean | `true` | Fall back to regex parsing if LLM fails |
| `llm.cache_enabled` | boolean | `true` | Enable response caching |
| `llm.max_tokens` | integer | `2000` | Maximum tokens per LLM request |
| `llm.confidence_threshold` | float | `0.5` | Minimum LLM confidence (0.0-1.0) required to accept changes |
| `llm.cost_budget` | float | `null` | Cost budget configuration (advisory only, not currently enforced). This field allows users to express intended spending limits and serves as a placeholder for future enforcement/alerts (see [Sub-Issue #225](../planning/ROADMAP.md)). |
| `llm.ollama_base_url` | string | `http://localhost:11434` | Ollama server URL (Ollama only) |
| `llm.effort` | string | `null` | Effort level for speed/cost vs accuracy tradeoff (`none`, `low`, `medium`, `high`) |

## LLM Effort Level

The `--llm-effort` option controls the speed/cost vs accuracy tradeoff for LLM providers that support extended reasoning capabilities.

### Effort Levels

| Level | Description | Use Case |
| ------- | ------------- | ---------- |
| `none` | Fastest, minimal reasoning | Quick parsing, cost-sensitive |
| `low` | Light reasoning | Balanced speed/accuracy |
| `medium` | Moderate reasoning | Complex comments |
| `high` | Most thorough reasoning | Maximum accuracy, complex parsing |

### Provider Support

| Provider | Parameter | Notes |
| ---------- | ----------- | ------- |
| **OpenAI** | `reasoning_effort` | Supported on GPT-5.x models |
| **Anthropic** | `effort` | Supported on Claude Opus 4.5 |
| **Ollama** | Not supported | Uses standard inference |
| **Claude CLI** | Not supported | Uses standard inference |
| **Codex CLI** | Not supported | Uses standard inference |

### Usage

**CLI flag:**

```bash
# Fast parsing (minimal reasoning)
pr-resolve apply 123 --llm-effort none

# Maximum accuracy (thorough reasoning)
pr-resolve apply 123 --llm-effort high

# With analyze command
pr-resolve analyze --pr 123 --owner myorg --repo myrepo --llm-effort medium
```

**Environment variable:**

```bash
export CR_LLM_EFFORT=medium
pr-resolve apply 123
```

**Configuration file:**

```yaml
llm:
  enabled: true
  provider: anthropic
  model: claude-opus-4-5
  api_key: ${ANTHROPIC_API_KEY}
  effort: high  # Maximum reasoning for complex parsing
```

### Cost Considerations

Higher effort levels typically increase:

* Response latency (more reasoning time)
* Token usage (reasoning tokens counted)
* Per-request cost

For cost-sensitive deployments, use `none` or `low` effort levels. Reserve `high` for complex parsing tasks where accuracy is critical.

## LLM Presets

Presets provide zero-config LLM setup with sensible defaults for common use cases.

### Available Presets

| Preset | Provider | Model | Status | Cost | Requires |
| -------- | ---------- | ------- | -------- | ------ | ---------- |
| `codex-cli-free` | Codex CLI | `codex` | ✅ Production | Free | GitHub Copilot subscription |
| `ollama-local` | Ollama | `qwen2.5-coder:7b` | ✅ Production + GPU | Free | Local Ollama + GPU (optional) |
| `claude-cli-sonnet` | Claude CLI | `claude-sonnet-4-5` | ✅ Production | Free | Claude subscription |
| `openai-api-mini` | OpenAI API | `gpt-4o-mini` | ✅ Production | ~$0.15/1M tokens | API key ($5 budget) |
| `anthropic-api-balanced` | Anthropic API | `claude-haiku-4` | ✅ Production | ~$0.25/1M tokens | API key ($5 budget) |

### Using Presets

#### CLI-Based Presets (Free)

No API key required:

```bash
# GitHub Codex (requires Copilot subscription)
pr-resolve apply 123 --llm-preset codex-cli-free
pr-resolve analyze --pr 123 --owner myorg --repo myrepo --llm-preset codex-cli-free

# Local Ollama (requires ollama installation)
pr-resolve apply 123 --llm-preset ollama-local
pr-resolve analyze --pr 123 --owner myorg --repo myrepo --llm-preset ollama-local

# Claude CLI (requires Claude subscription)
pr-resolve apply 123 --llm-preset claude-cli-sonnet
pr-resolve analyze --pr 123 --owner myorg --repo myrepo --llm-preset claude-cli-sonnet

```

#### API-Based Presets (Paid)

Require API key via environment variable or CLI flag:

```bash
# OpenAI (low-cost)
export OPENAI_API_KEY="sk-..."
pr-resolve apply 123 --llm-preset openai-api-mini

# Anthropic (balanced, with caching)
export ANTHROPIC_API_KEY="sk-ant-..."
pr-resolve apply 123 --llm-preset anthropic-api-balanced

# Or pass API key via CLI flag
pr-resolve apply 123 --llm-preset openai-api-mini --llm-api-key sk-...

```

### Available Presets (Provider-Specific)

The following LLM presets are available:

1. **codex-cli-free**: Free Codex CLI - Requires GitHub Copilot subscription
   * Provider: codex-cli
   * Model: codex
   * Requires API key: No

2. **ollama-local**: Local Ollama - Free, private, offline (recommended: qwen2.5-coder:7b)
   * Provider: ollama
   * Model: qwen2.5-coder:7b
   * Requires API key: No

3. **claude-cli-sonnet**: Claude CLI with Sonnet 4.5 - Requires Claude subscription
   * Provider: claude-cli
   * Model: claude-sonnet-4-5
   * Requires API key: No

4. **openai-api-mini**: OpenAI GPT-4o-mini - Low-cost API (requires API key)
   * Provider: openai
   * Model: gpt-4o-mini
   * Requires API key: Yes
   * Cost budget: $5.00

5. **anthropic-api-balanced**: Anthropic Claude Haiku 4 - Balanced cost/performance (requires API key)
   * Provider: anthropic
   * Model: claude-haiku-4
   * Requires API key: Yes
   * Cost budget: $5.00

## Privacy Considerations

Different LLM providers have significantly different privacy characteristics. Understanding these differences is crucial for choosing the right provider for your use case.

### Privacy Comparison

| Provider | LLM Vendor Exposure | GitHub API Required | Best For |
| ---------- | --------------------- | --------------------- | ---------- |
| **Ollama** | ✅ **None** (localhost) | ⚠️ Yes | Reducing third-party exposure, compliance |
| **OpenAI** | ❌ OpenAI (US) | ⚠️ Yes | Cost-effective, production |
| **Anthropic** | ❌ Anthropic (US) | ⚠️ Yes | Quality, caching benefits |
| **Claude CLI** | ❌ Anthropic (US) | ⚠️ Yes | Interactive, convenience |
| **Codex CLI** | ❌ GitHub/OpenAI | ⚠️ Yes | GitHub integration |

**Note**: All options require GitHub API access (internet required). The privacy difference is whether an LLM vendor also sees your review comments.

### Ollama: Reduced Third-Party Exposure 🔒

**When using Ollama** (`ollama-local` preset):

* ✅ **Local LLM processing** - Review comments processed locally (no LLM vendor)
* ✅ **No LLM vendor exposure** - OpenAI/Anthropic never see your comments
* ✅ **Simpler compliance** - One fewer data processor (no LLM vendor BAA/DPA)
* ✅ **Zero LLM costs** - Free after hardware investment
* ✅ **No LLM API keys required** - No credential management
* ⚠️ **GitHub API required** - Internet needed to fetch PR data (not offline/air-gapped)

**Reality Check**:

* ⚠️ Code is on GitHub (required for PR workflow)
* ⚠️ CodeRabbit has access (required for reviews)
* ✅ LLM vendor does NOT have access (eliminated)

**Recommended for**:

* Reducing third-party LLM vendor exposure
* Regulated industries wanting simpler compliance chain (GDPR, HIPAA, SOC2)
* Organizations with policies against cloud LLM services
* Cost-conscious usage (no per-request LLM fees)

**Learn more**:

* [Privacy Architecture](privacy-architecture.md) - Detailed privacy analysis
* [Local LLM Operation Guide](local-llm-operation-guide.md) - Setup instructions
* [Privacy FAQ](privacy-faq.md) - Common privacy questions

### API Providers: Convenience vs. Privacy Trade-off

**When using API providers** (OpenAI, Anthropic, etc.):

* ⚠️ **Data transmitted to cloud** - Review comments and code sent via HTTPS
* ⚠️ **Third-party data policies** - Subject to provider's retention and usage policies
* ⚠️ **Internet required** - No offline operation
* ⚠️ **Costs per request** - Ongoing usage fees
* ⚠️ **Compliance complexity** - May require Data Processing Agreements (DPA), Business Associate Agreements (BAA)

**Acceptable for**:

* Open source / public code repositories
* Organizations with enterprise LLM agreements
* Use cases where privacy trade-off is acceptable
* When highest model quality is required (GPT-4, Claude Opus)

**Privacy safeguards**:

* ✅ Data encrypted in transit (HTTPS/TLS)
* ✅ API keys never logged by pr-resolve
* ✅ Anthropic: No training on API data by default
* ✅ OpenAI: Can opt out of training data usage

### Privacy Verification

Verify Ollama's local-only operation:

```bash
# Run privacy verification script
./scripts/verify_privacy.sh

# Expected output
# ✅ Privacy Verification: PASSED
# ✅ No external network connections detected
# ✅ All Ollama traffic is localhost-only

```

The script monitors network traffic during Ollama inference and confirms no external LLM vendor connections are made.

**Note**: GitHub API connections will still appear (required for PR workflow).

**See**: [Local LLM Operation Guide - Privacy Verification](local-llm-operation-guide.md#privacy-verification) for details.

### Making the Right Choice

**Choose Ollama if you need**:

* ✅ Reduced third-party exposure (eliminate LLM vendor)
* ✅ Simpler compliance chain (one fewer data processor)
* ✅ Zero ongoing LLM costs
* ⚠️ **NOT for**: Offline/air-gapped operation (requires GitHub API)

**Choose API providers if**:

* ✅ Privacy trade-off is acceptable (public/open-source code)
* ✅ Enterprise agreements are in place (DPA, BAA)
* ✅ Highest model quality is priority
* ✅ Budget is available for per-request fees

For detailed privacy analysis and compliance considerations, see the [Privacy Architecture](privacy-architecture.md) documentation.

## Environment Variable Interpolation

Configuration files support `${VAR_NAME}` syntax for injecting environment variables at runtime.

### Syntax

```yaml
llm:
  api_key: ${ANTHROPIC_API_KEY}
  model: ${LLM_MODEL:-claude-haiku-4}  # With default value (not yet supported)

```

### Behavior

* **Found**: Variable is replaced with its value
* **Not Found**: Placeholder remains (`${VAR_NAME}`) with warning logged
* **Security**: Only `${VAR}` syntax is allowed for API keys in config files

### Examples

#### Basic Interpolation

```yaml
llm:
  provider: ${LLM_PROVIDER}
  model: ${LLM_MODEL}
  api_key: ${OPENAI_API_KEY}

```

```bash
export LLM_PROVIDER="openai"
export LLM_MODEL="gpt-4o-mini"
export OPENAI_API_KEY="sk-..."

pr-resolve apply 123 --config config.yaml

```

#### Multiple Variables

```toml
[llm]
provider = "${PROVIDER}"
api_key = "${API_KEY}"

[llm.ollama]
base_url = "${OLLAMA_URL}"

```

#### Nested Structures

```yaml
llm:
  enabled: true
  provider: anthropic
  api_key: ${ANTHROPIC_API_KEY}
  cache:
    enabled: ${CACHE_ENABLED}
    ttl: ${CACHE_TTL}

```

## Configuration Precedence

Configuration sources are applied in this order (highest to lowest priority):

1. **CLI Flags** - Command-line arguments (`--llm-provider openai`)
2. **Environment Variables** - `CR_LLM_*` variables
3. **Configuration File** - YAML/TOML file (`--config config.yaml`)
4. **LLM Presets** - Preset via `--llm-preset` flag
5. **Default Values** - Built-in defaults

### Example: Layering Configuration

```bash
# Start with preset
export LLM_PRESET="openai-api-mini"

# Override with env vars
export CR_LLM_MODEL="gpt-4"
export CR_LLM_MAX_TOKENS=4000

# Override with CLI flags
pr-resolve apply 123 \
  --llm-preset openai-api-mini \
  --llm-model gpt-4o \
  --llm-api-key sk-...

# Result
# - provider: openai (from preset)
# - model: gpt-4o (CLI flag overrides env var)
# - api_key: sk-... (CLI flag)
# - max_tokens: 4000 (env var)
# - cost_budget: 5.0 (preset default)

```

### Precedence Table

| Setting | CLI Flag | Env Var | Config File | Preset | Default |
| --------- | ---------- | --------- | ------------- | -------- | --------- |
| **Priority** | 1 (highest) | 2 | 3 | 4 | 5 (lowest) |
| **Scope** | Single run | Session | Project | Quick setup | Fallback |
| **Use Case** | Testing, overrides | Personal settings | Team config | Zero-config | Sensible defaults |

## API Key Security

### Security Rules

1. **Never commit API keys to version control**
2. **API keys MUST use environment variables**
3. **Config files MUST use `${VAR}` syntax for API keys**
4. **Direct API keys in config files are rejected**

### Valid Configuration

✅ **Allowed** - Environment variable reference:

```yaml
llm:
  api_key: ${ANTHROPIC_API_KEY}  # ✅ Valid

```

```toml
[llm]
api_key = "${OPENAI_API_KEY}"  # ✅ Valid

```

❌ **Rejected** - Direct API key:

```yaml
llm:
  api_key: sk-ant-real-key-12345  # ❌ REJECTED

```

```toml
[llm]
api_key = "sk-openai-real-key"  # ❌ REJECTED

```

### Error Message

When a real API key is detected in a config file:

```text
ConfigError: SECURITY: API keys must NOT be stored in configuration files (config.yaml).
Use environment variables: CR_LLM_API_KEY or ${OPENAI_API_KEY}.
Example: api_key: ${ANTHROPIC_API_KEY}

Supported environment variables:
* CR_LLM_API_KEY (generic)
* OPENAI_API_KEY (OpenAI)
* ANTHROPIC_API_KEY (Anthropic)
```

### Best Practices

1. **Use `.env` file for local development**:

   ```bash
   # .env (add to .gitignore)
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...

   ```

2. **Reference in config file**:

   ```yaml
   llm:
     api_key: ${OPENAI_API_KEY}

   ```

3. **Load environment variables**:

   ```bash
   source .env
   pr-resolve apply 123 --config config.yaml

   ```

## Ollama Auto-Download Feature

The Ollama provider supports automatic model downloading for streamlined setup.

### Quick Setup with Scripts

Use the automated setup scripts for the easiest Ollama installation:

```bash
# 1. Install and setup Ollama
./scripts/setup_ollama.sh

# 2. Download recommended model
./scripts/download_ollama_models.sh

# 3. Use with pr-resolve
pr-resolve apply 123 --llm-preset ollama-local

```

See the [Ollama Setup Guide](ollama-setup.md) for comprehensive documentation.

### Auto-Download via Python API

Enable automatic model downloads in Python code:

```python
from review_bot_automator.llm.providers.ollama import OllamaProvider

# Auto-download enabled - model will be downloaded if not available
provider = OllamaProvider(
    model="qwen2.5-coder:7b",
    auto_download=True  # Downloads model automatically (may take several minutes)
)

# Get model recommendations
models = OllamaProvider.list_recommended_models()
for model in models:
    print(f"{model['name']}: {model['description']}")

```

**Benefits**:

* No manual `ollama pull` required
* Automated CI/CD setup
* Seamless model switching

**Note**: Auto-download is not currently exposed via CLI flags. Use the interactive scripts or manual `ollama pull` for CLI usage.

## Examples

### Example 1: Free Local Setup (Ollama)

**Quick Setup (Recommended)**:

```bash
# Automated setup
./scripts/setup_ollama.sh
./scripts/download_ollama_models.sh

# Use preset
pr-resolve apply 123 --llm-preset ollama-local

```

**Manual Setup**:

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull model
ollama pull qwen2.5-coder:7b

```

**Option A: Preset**:

```bash
pr-resolve apply 123 --llm-preset ollama-local

```

**Option B: Config File**:

```yaml
# config.yaml
llm:
  enabled: true
  provider: ollama
  model: qwen2.5-coder:7b

```

```bash
pr-resolve apply 123 --config config.yaml

```

See [Ollama Setup Guide](ollama-setup.md) for detailed installation instructions, model recommendations, and troubleshooting.

### Example 2: Paid API Setup (OpenAI)

**config.yaml**:

```yaml
llm:
  enabled: true
  provider: openai
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}
  cost_budget: 5.0
  cache_enabled: true
  fallback_to_regex: true

```

**.env**:

```bash
OPENAI_API_KEY=sk-...

```

**Usage**:

```bash
source .env
pr-resolve apply 123 --config config.yaml

```

### Example 3: Team Configuration

**team-config.yaml** (committed to repo):

```yaml
llm:
  enabled: true
  provider: anthropic
  model: claude-haiku-4
  api_key: ${ANTHROPIC_API_KEY}  # Each dev sets their own key
  fallback_to_regex: true
  cache_enabled: true
  max_tokens: 2000
  cost_budget: 10.0

```

**Each developer**:

```bash
# Set personal API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Use team config
pr-resolve apply 123 --config team-config.yaml

```

### Example 4: Override Preset Settings

```bash
# Start with preset, override specific settings
pr-resolve apply 123 \
  --llm-preset openai-api-mini \
  --llm-model gpt-4 \
  --llm-max-tokens 4000 \
  --llm-cost-budget 10.0

```

### Example 5: Multi-Environment Setup

**dev.yaml**:

```yaml
llm:
  enabled: true
  provider: ollama
  model: qwen2.5-coder:7b

```

**staging.yaml**:

```yaml
llm:
  enabled: true
  provider: anthropic
  model: claude-haiku-4
  api_key: ${STAGING_API_KEY}
  cost_budget: 5.0

```

**prod.yaml**:

```yaml
llm:
  enabled: true
  provider: anthropic
  model: claude-sonnet-4-5
  api_key: ${PROD_API_KEY}
  cost_budget: 20.0

```

**Usage**:

```bash
# Development
pr-resolve apply 123 --config dev.yaml

# Staging
export STAGING_API_KEY="sk-ant-staging-..."
pr-resolve apply 123 --config staging.yaml

# Production
export PROD_API_KEY="sk-ant-prod-..."
pr-resolve apply 123 --config prod.yaml

```

## Retry & Resilience Configuration

### Rate Limit Retry (Phase 5)

Configure automatic retry behavior for rate limit and transient errors:

| Variable | Default | Description |
|----------|---------|-------------|
| `CR_LLM_RETRY_ON_RATE_LIMIT` | `true` | Enable retry on rate limit errors |
| `CR_LLM_RETRY_MAX_ATTEMPTS` | `3` | Maximum retry attempts (>=1) |
| `CR_LLM_RETRY_BASE_DELAY` | `2.0` | Base delay in seconds for exponential backoff |

**Example YAML configuration:**

```yaml
llm:
  retry_on_rate_limit: true
  retry_max_attempts: 5
  retry_base_delay: 3.0
```

**Exponential backoff formula:**

```text
delay = base_delay * 2^attempt + random_jitter
```

For example, with `retry_base_delay: 2.0`:

* Attempt 1: ~2s delay
* Attempt 2: ~4s delay
* Attempt 3: ~8s delay

### Circuit Breaker

Prevents cascading failures by temporarily disabling failing providers:

| Variable | Default | Description |
|----------|---------|-------------|
| `CR_LLM_CIRCUIT_BREAKER_ENABLED` | `true` | Enable circuit breaker pattern |
| `CR_LLM_CIRCUIT_BREAKER_THRESHOLD` | `5` | Consecutive failures before circuit opens |
| `CR_LLM_CIRCUIT_BREAKER_COOLDOWN` | `60.0` | Seconds before attempting recovery |

**Circuit breaker states:**

1. **CLOSED** (normal): Requests pass through
2. **OPEN** (failing): Requests fail immediately without calling provider
3. **HALF_OPEN** (recovery): Single test request to check if provider recovered

## Cache Warming

Pre-populate the cache for cold start optimization:

```python
from review_bot_automator.llm.cache.prompt_cache import PromptCache

cache = PromptCache()
entries = [
    {
        "prompt": "Parse this CodeRabbit comment...",
        "provider": "anthropic",
        "model": "claude-sonnet-4-5",
        "response": "..."
    },
    # ... more entries
]
loaded, skipped = cache.warm_cache(entries)
print(f"Loaded {loaded} entries, skipped {skipped}")
```

**Benefits:**

* Eliminates cold start latency
* O(n) bulk loading (optimized, no per-entry eviction checks)
* Skips duplicates automatically
* Thread-safe for concurrent access

**Via CachingProvider:**

```python
from review_bot_automator.llm.providers.caching_provider import CachingProvider

cached_provider = CachingProvider(base_provider)
loaded, skipped = cached_provider.warm_up(entries)
```

## Troubleshooting

### Environment Variable Not Interpolated

**Symptom**: Config shows `${VAR_NAME}` instead of value.

**Cause**: Environment variable not set.

**Solution**:

```bash
# Check if variable is set
echo $ANTHROPIC_API_KEY

# Set the variable
export ANTHROPIC_API_KEY="sk-ant-..."

# Verify
pr-resolve apply 123 --config config.yaml --dry-run

```

### API Key Rejected in Config File

**Error**:

```text
ConfigError: SECURITY: API keys must NOT be stored in configuration files

```

**Cause**: Real API key in config file instead of `${VAR}` syntax.

**Solution**:

```yaml
# ❌ Wrong
llm:
  api_key: sk-ant-real-key

# ✅ Correct
llm:
  api_key: ${ANTHROPIC_API_KEY}

```

### Preset Not Found

**Error**:

```text
ConfigError: Unknown preset 'invalid-preset'

```

**Solution**: List available presets:

```bash
pr-resolve config show-presets

```

### Configuration Not Applied

**Symptom**: Settings from config file ignored.

**Cause**: CLI flags or environment variables have higher precedence.

**Solution**: Check precedence order:

1. Remove conflicting CLI flags
2. Unset conflicting environment variables (`unset CR_LLM_PROVIDER`)
3. Verify config file syntax (`--config config.yaml --dry-run`)

### LLM Still Disabled After Configuration

**Cause**: API-based provider without API key.

**Solution**:

```bash
# Check configuration
pr-resolve config show

# Ensure API key is set
export OPENAI_API_KEY="sk-..."

# Or use CLI-based preset (no API key needed)
pr-resolve apply 123 --llm-preset codex-cli-free

```

### Ollama Connection Failed

**Error**:

```text
LLMProviderError: Failed to connect to Ollama at http://localhost:11434

```

**Solution**:

```bash
# Check Ollama is running
ollama list

# Start Ollama if needed
ollama serve

# Or specify custom URL
export OLLAMA_BASE_URL="http://ollama-server:11434"
pr-resolve apply 123 --config config.yaml

```

## Performance Considerations

### Choosing the Right Provider

Different LLM providers have different characteristics in terms of latency, cost, accuracy, and privacy. Consider these factors when choosing a provider:

**For Speed-Critical Applications:**

* OpenAI and Anthropic APIs typically offer the lowest latency (1-3s mean)
* Best for real-time workflows and interactive use cases

**For Cost-Sensitive Deployments:**

* Ollama (local) has zero per-request cost but requires hardware
* OpenAI's gpt-4o-mini offers good balance of cost and performance
* Anthropic with prompt caching can reduce costs by 50-90%

**For Privacy-First Requirements:**

* Ollama eliminates LLM vendor exposure (no OpenAI/Anthropic)
* Simplifies compliance for HIPAA, GDPR (one fewer data processor)
* Note: GitHub/CodeRabbit still have access (required)
* Trade-off: Higher latency, especially on CPU-only systems

**For High-Volume Production:**

* Anthropic with prompt caching (50-90% cost reduction on repeated prompts)
* Connection pooling and retry logic built-in for all providers

### Performance Benchmarking

Comprehensive performance benchmarks comparing all providers are available in the [Performance Benchmarks](performance-benchmarks.md) document. The benchmarks measure:

* **Latency**: Mean, median, P95, P99 response times
* **Throughput**: Requests per second
* **Accuracy**: Parsing success rates vs ground truth
* **Cost**: Per-request and monthly estimates at scale

**Run your own benchmarks:**

```bash
# Benchmark all providers (requires API keys)
python scripts/benchmark_llm.py --iterations 100

# Benchmark specific providers
python scripts/benchmark_llm.py --providers ollama openai --iterations 50

# Custom dataset
python scripts/benchmark_llm.py --dataset my_comments.json --output my_report.md

```

See `python scripts/benchmark_llm.py --help` for all options.

## See Also

* [LLM Provider Guide](llm-provider-guide.md) - Provider comparison and selection guide
* [Circuit Breaker](circuit-breaker.md) - Resilience pattern for handling provider failures
* [Metrics Guide](metrics-guide.md) - Understanding LLM metrics and export options
* [Cost Estimation](cost-estimation.md) - Pre-run cost estimation and budget configuration
* [Confidence Threshold](confidence-threshold.md) - Tuning LLM confidence for accuracy/coverage balance
* [Performance Benchmarks](performance-benchmarks.md) - Detailed performance comparison of all providers
* [Ollama Setup Guide](ollama-setup.md) - Comprehensive Ollama installation and setup guide
* [Main Configuration Guide](configuration.md) - Basic LLM setup and provider documentation
* [Getting Started Guide](getting-started.md) - Quick start with LLM features
* [Troubleshooting](troubleshooting.md) - Common issues and solutions
* [API Reference](api-reference.md) - Configuration API documentation
* [Security Architecture](security-architecture.md) - Security best practices
