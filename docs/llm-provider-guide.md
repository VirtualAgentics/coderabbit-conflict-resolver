# LLM Provider Guide

This guide helps you choose and configure the right LLM provider for your needs. Review Bot Automator supports 5 providers, from free local options to pay-per-use APIs.

## Quick Reference

| Provider | Cost | Privacy | Latency | Setup | Best For |
|----------|------|---------|---------|-------|----------|
| **Ollama** | Free | High (local) | Medium | Medium | Privacy-focused teams |
| **Claude CLI** | Free* | Medium | Fast | Easy | Claude subscribers |
| **Codex CLI** | Free* | Medium | Fast | Easy | Copilot subscribers |
| **OpenAI API** | Pay | Low | Fast | Easy | Pay-per-use flexibility |
| **Anthropic API** | Pay | Low | Fast | Easy | Prompt caching savings |

*Requires existing subscription (Claude Pro or GitHub Copilot)

## Provider Selection Flowchart

```text
Do you need maximum privacy (data never leaves your machine)?
├── YES → Use Ollama (local)
└── NO → Do you have an existing subscription?
          ├── Claude Pro → Use Claude CLI
          ├── GitHub Copilot → Use Codex CLI
          └── Neither → Do you want pay-per-use?
                        ├── YES → Use OpenAI API or Anthropic API
                        └── NO → Use Ollama (free, local)
```

## Provider Details

### 1. Ollama (Local, Free)

**Best for:** Privacy-focused teams, air-gapped environments, unlimited usage.

**Pros:**

* Completely free
* Data never leaves your machine
* No API keys needed
* Unlimited requests

**Cons:**

* Requires GPU for best performance (CPU works but slower)
* Initial model download (2-8GB)
* Slightly higher latency than cloud APIs

#### Quick Setup

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download recommended model
ollama pull qwen2.5-coder:7b

# Configure resolver
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="ollama"
export CR_LLM_MODEL="qwen2.5-coder:7b"

# Verify
ollama list
```

#### Recommended Models

| Model | VRAM | Quality | Speed |
|-------|------|---------|-------|
| `qwen2.5-coder:7b` | 8GB | Good | Fast |
| `qwen2.5-coder:14b` | 16GB | Better | Medium |
| `llama3.3:70b` | 48GB | Best | Slow |
| `codellama:7b` | 8GB | Good | Fast |

**See also:** [Ollama Setup Guide](ollama-setup.md) for GPU configuration and advanced options.

---

### 2. Claude CLI (Subscription, Free*)

**Best for:** Teams with existing Claude Pro/Team subscriptions.

**Pros:**

* No additional cost with subscription
* High-quality responses
* Fast response times
* Simple setup

**Cons:**

* Requires Claude Pro subscription ($20/month)
* Data sent to Anthropic servers

#### Quick Setup

```bash
# Install Claude CLI (requires Node.js)
npm install -g @anthropic-ai/claude-cli

# Authenticate (opens browser)
claude auth login

# Configure resolver
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="claude-cli"

# Verify
claude --version
```

#### Using Presets

```bash
# Zero-config preset
pr-resolve apply --owner org --repo repo --pr 123 \
  --llm-preset claude-cli-sonnet
```

---

### 3. Codex CLI (Subscription, Free*)

**Best for:** Teams with GitHub Copilot subscriptions.

**Pros:**

* No additional cost with Copilot subscription
* Optimized for code tasks
* Fast response times

**Cons:**

* Requires GitHub Copilot subscription ($10-19/month)
* Data sent to OpenAI servers

#### Quick Setup

```bash
# Install Codex CLI
npm install -g @openai/codex-cli

# Authenticate with GitHub
codex auth login

# Configure resolver
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="codex-cli"

# Verify
codex --version
```

#### Using Presets

```bash
# Zero-config preset
pr-resolve apply --owner org --repo repo --pr 123 \
  --llm-preset codex-cli-free
```

---

### 4. OpenAI API (Pay-per-use)

**Best for:** Teams wanting pay-per-use flexibility with latest models.

**Pros:**

* Only pay for what you use
* Access to latest GPT models
* Fast response times
* Simple API

**Cons:**

* Requires credit card
* Costs can add up for high-volume use
* Data sent to OpenAI servers

#### Quick Setup

```bash
# Get API key from <https://platform.openai.com/api-keys>

# Configure resolver
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="openai"
export CR_LLM_API_KEY="sk-..."
export CR_LLM_MODEL="gpt-4o-mini"  # or gpt-5-mini

# Verify
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $CR_LLM_API_KEY" | head
```

#### Model Options

| Model | Cost/1K tokens | Quality | Recommended |
|-------|----------------|---------|-------------|
| `gpt-5-nano` | ~$0.0001 | Good | Budget |
| `gpt-4o-mini` | ~$0.00015 | Good | Default |
| `gpt-5-mini` | ~$0.0003 | Better | Best value |
| `gpt-5.1` | ~$0.001 | Best | Premium |

#### Using Presets

```bash
# Zero-config preset
pr-resolve apply --owner org --repo repo --pr 123 \
  --llm-preset openai-api-mini \
  --llm-api-key sk-...
```

---

### 5. Anthropic API (Pay-per-use)

**Best for:** Teams wanting prompt caching for cost savings (50-90% reduction).

**Pros:**

* Excellent prompt caching (significant cost savings)
* High-quality Claude models
* Fast response times

**Cons:**

* Requires credit card
* Slightly higher base cost than OpenAI
* Data sent to Anthropic servers

#### Quick Setup

```bash
# Get API key from <https://console.anthropic.com/settings/keys>

# Configure resolver
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="anthropic"
export CR_LLM_API_KEY="sk-ant-..."
export CR_LLM_MODEL="claude-haiku-4-5"  # or claude-sonnet-4-5

# Verify
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $CR_LLM_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-haiku-4-5","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}'
```

#### Model Options

| Model | Cost/1K tokens | Quality | Recommended |
|-------|----------------|---------|-------------|
| `claude-haiku-4-5` | ~$0.0008 | Good | Budget |
| `claude-sonnet-4-5` | ~$0.003 | Better | Default |
| `claude-opus-4-5` | ~$0.005 | Best | Premium |

#### Using Presets

```bash
# Zero-config preset
pr-resolve apply --owner org --repo repo --pr 123 \
  --llm-preset anthropic-api-balanced \
  --llm-api-key sk-ant-...
```

---

## Cost Comparison

### Per-Comment Cost (Typical)

| Provider | Model | Cost/Comment |
|----------|-------|--------------|
| Ollama | qwen2.5-coder:7b | $0.0000 |
| Claude CLI | claude-sonnet-4-5 | $0.0000* |
| Codex CLI | codex | $0.0000* |
| OpenAI API | gpt-4o-mini | ~$0.0002 |
| Anthropic API | claude-haiku-4-5 | ~$0.0008 |

*Subscription required

### Monthly Projections (100 PRs, 20 comments each)

| Provider | Monthly Cost |
|----------|--------------|
| Ollama | $0.00 |
| Claude CLI | $0.00 (+ subscription) |
| OpenAI API (gpt-4o-mini) | ~$0.40 |
| Anthropic API (haiku) | ~$1.60 |

**See also:** [Cost Estimation Guide](cost-estimation.md) for detailed calculations and budget configuration.

---

## Troubleshooting Quick Reference

### Ollama

| Issue | Solution |
|-------|----------|
| `Ollama not running` | Run `ollama serve` |
| `Model not found` | Run `ollama pull <model>` |
| Slow responses | Enable GPU or use smaller model |

### Claude CLI / Codex CLI

| Issue | Solution |
|-------|----------|
| `command not found` | Install with `npm install -g <package>` |
| `Not authenticated` | Run `<cli> auth login` |
| Token expired | Re-authenticate |

### OpenAI / Anthropic API

| Issue | Solution |
|-------|----------|
| `Invalid API key` | Verify key starts with `sk-` or `sk-ant-` |
| `Rate limit exceeded` | Wait or reduce request rate |
| `Model not found` | Check model name spelling |

**See also:** [Troubleshooting Guide](troubleshooting.md) for detailed solutions.

---

## Configuration Reference

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CR_LLM_ENABLED` | Enable LLM parsing | `true` |
| `CR_LLM_PROVIDER` | Provider name | `ollama`, `anthropic`, etc. |
| `CR_LLM_MODEL` | Model identifier | `gpt-4o-mini` |
| `CR_LLM_API_KEY` | API key (for API providers) | `sk-...` |

### CLI Presets

| Preset | Provider | Model | Cost |
|--------|----------|-------|------|
| `ollama-local` | Ollama | qwen2.5-coder:7b | Free |
| `claude-cli-sonnet` | Claude CLI | claude-sonnet-4-5 | Free* |
| `codex-cli-free` | Codex CLI | codex | Free* |
| `openai-api-mini` | OpenAI | gpt-4o-mini | Pay |
| `anthropic-api-balanced` | Anthropic | claude-sonnet-4-5 | Pay |

**See also:** [LLM Configuration Guide](llm-configuration.md) for advanced options.

---

## See Also

* [Ollama Setup Guide](ollama-setup.md) - Detailed Ollama installation and GPU setup
* [LLM Configuration Guide](llm-configuration.md) - Advanced configuration options
* [Cost Estimation Guide](cost-estimation.md) - Detailed cost calculations
* [Troubleshooting Guide](troubleshooting.md) - Common issues and solutions
* [Privacy Architecture](privacy-architecture.md) - Data flow and privacy details
* [API Reference](api-reference.md) - Provider class documentation
