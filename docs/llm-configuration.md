# LLM Configuration Guide

This guide covers advanced LLM configuration features including configuration files, presets, and environment variable interpolation.

> **See Also**: [Main Configuration Guide](configuration.md#llm-provider-configuration) for basic LLM setup and provider-specific documentation.

## Table of Contents

- [Configuration File Support](#configuration-file-support)
- [LLM Presets](#llm-presets)
- [Environment Variable Interpolation](#environment-variable-interpolation)
- [Configuration Precedence](#configuration-precedence)
- [API Key Security](#api-key-security)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## Configuration File Support

The resolver supports YAML and TOML configuration files for LLM settings. This allows you to:

- Store non-sensitive configuration in version control
- Share team-wide LLM settings
- Manage complex configurations more easily
- Use environment variable interpolation for secrets

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
  cost_budget: 5.0
```

Use with:

```bash
pr-resolve apply 123 --config config.yaml
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
cost_budget = 5.0
```

Use with:

```bash
pr-resolve apply 123 --config config.toml
```

### Configuration File Schema

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `llm.enabled` | boolean | `false` | Enable LLM-powered features |
| `llm.provider` | string | `claude-cli` | Provider name (`claude-cli`, `codex-cli`, `ollama`, `openai`, `anthropic`) |
| `llm.model` | string | provider-specific | Model identifier (e.g., `claude-sonnet-4-5`, `gpt-4o-mini`) |
| `llm.api_key` | string | `null` | **Must use `${VAR}` syntax** - direct keys are rejected |
| `llm.fallback_to_regex` | boolean | `true` | Fall back to regex parsing if LLM fails |
| `llm.cache_enabled` | boolean | `true` | Enable response caching |
| `llm.max_tokens` | integer | `2000` | Maximum tokens per LLM request |
| `llm.cost_budget` | float | `null` | Maximum cost per run in USD (optional) |
| `llm.ollama_base_url` | string | `http://localhost:11434` | Ollama server URL (Ollama only) |

## LLM Presets

Presets provide zero-config LLM setup with sensible defaults for common use cases.

### Available Presets

| Preset | Provider | Model | Cost | Requires |
|--------|----------|-------|------|----------|
| `codex-cli-free` | Codex CLI | `codex` | Free | GitHub Copilot subscription |
| `ollama-local` | Ollama | `qwen2.5-coder:7b` | Free | Local Ollama installation |
| `claude-cli-sonnet` | Claude CLI | `claude-sonnet-4-5` | Free | Claude subscription |
| `openai-api-mini` | OpenAI API | `gpt-4o-mini` | ~$0.15/1M tokens | API key ($5 budget) |
| `anthropic-api-balanced` | Anthropic API | `claude-haiku-4` | ~$0.25/1M tokens | API key ($5 budget) |

### Using Presets

#### CLI-Based Presets (Free)

No API key required:

```bash
# GitHub Codex (requires Copilot subscription)
pr-resolve apply 123 --llm-preset codex-cli-free

# Local Ollama (requires ollama installation)
pr-resolve apply 123 --llm-preset ollama-local

# Claude CLI (requires Claude subscription)
pr-resolve apply 123 --llm-preset claude-cli-sonnet
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

### List Available Presets

```bash
pr-resolve config show-presets
```

Output:

```
Available LLM Presets:

codex-cli-free: Free Codex CLI - Requires GitHub Copilot subscription
  Provider: codex-cli
  Model: codex
  Requires API key: No

ollama-local: Local Ollama - Free, private, offline
  Provider: ollama
  Model: qwen2.5-coder:7b
  Requires API key: No

...
```

## Environment Variable Interpolation

Configuration files support `${VAR_NAME}` syntax for injecting environment variables at runtime.

### Syntax

```yaml
llm:
  api_key: ${ANTHROPIC_API_KEY}
  model: ${LLM_MODEL:-claude-haiku-4}  # With default value (not yet supported)
```

### Behavior

- **Found**: Variable is replaced with its value
- **Not Found**: Placeholder remains (`${VAR_NAME}`) with warning logged
- **Security**: Only `${VAR}` syntax is allowed for API keys in config files

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

# Result:
# - provider: openai (from preset)
# - model: gpt-4o (CLI flag overrides env var)
# - api_key: sk-... (CLI flag)
# - max_tokens: 4000 (env var)
# - cost_budget: 5.0 (preset default)
```

### Precedence Table

| Setting | CLI Flag | Env Var | Config File | Preset | Default |
|---------|----------|---------|-------------|--------|---------|
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

```
ConfigError: SECURITY: API keys must NOT be stored in configuration files (config.yaml).
Use environment variables: CR_LLM_API_KEY or ${OPENAI_API_KEY}.
Example: api_key: ${ANTHROPIC_API_KEY}

Supported environment variables:
- CR_LLM_API_KEY (generic)
- OPENAI_API_KEY (OpenAI)
- ANTHROPIC_API_KEY (Anthropic)
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

## Examples

### Example 1: Free Local Setup (Ollama)

**Setup**:
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
```
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
```
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
```
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

### Cost Budget Exceeded

**Error**:
```
LLMProviderError: Cost budget exceeded: $5.23 > $5.00
```

**Solution**: Increase budget or optimize usage:
```yaml
llm:
  cost_budget: 10.0  # Increase budget
  max_tokens: 1000   # Reduce tokens per request
```

## See Also

- [Main Configuration Guide](configuration.md) - Basic LLM setup and provider documentation
- [Getting Started Guide](getting-started.md) - Quick start with LLM features
- [API Reference](api-reference.md) - Configuration API documentation
- [Security Architecture](security-architecture.md) - Security best practices
