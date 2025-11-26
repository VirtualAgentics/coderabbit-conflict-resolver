# Configuration Reference

This document explains how to configure the Review Bot Automator for different use cases and environments.

## Overview

Configuration is done through preset configurations or custom configuration dictionaries. Presets provide ready-made setups for common scenarios, while custom configurations allow fine-grained control.

## Configuration Presets

The resolver provides four preset configurations optimized for different use cases.

### Conservative Preset

**Use case:** Critical systems requiring manual review of all conflicts

```python
from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig

resolver = ConflictResolver(config=PresetConfig.CONSERVATIVE)

```

**Configuration:**

```python
{
    "mode": "conservative",
    "skip_all_conflicts": True,
    "manual_review_required": True,
    "semantic_merging": False,
    "priority_system": False,
}

```

**Behavior:**

* Skips all conflicting changes
* Requires manual review for every conflict
* Safe default for production systems
* No automatic resolution

### Balanced Preset (Default)

**Use case:** Most development workflows with automated conflict resolution

```python
resolver = ConflictResolver(config=PresetConfig.BALANCED)

```

**Configuration:**

```python
{
    "mode": "balanced",
    "skip_all_conflicts": False,
    "manual_review_required": False,
    "semantic_merging": True,
    "priority_system": True,
    "priority_rules": {
        "user_selections": 100,
        "security_fixes": 90,
        "syntax_errors": 80,
        "regular_suggestions": 50,
        "formatting": 10,
    },
}

```

**Behavior:**

* Automatically resolves conflicts using priority rules
* Supports semantic merging for compatible changes
* User selections override other suggestions
* Security fixes have high priority
* Best balance between automation and safety

### Aggressive Preset

**Use case:** High-confidence environments with trusted automation

```python
resolver = ConflictResolver(config=PresetConfig.AGGRESSIVE)

```

**Configuration:**

```python
{
    "mode": "aggressive",
    "skip_all_conflicts": False,
    "manual_review_required": False,
    "semantic_merging": True,
    "priority_system": True,
    "max_automation": True,
    "user_selections_always_win": True,
}

```

**Behavior:**

* Maximizes automation with minimal user intervention
* User selections always override other changes
* Applies as many changes as possible
* Best for rapid development with trusted reviews

### Semantic Preset

**Use case:** Configuration file management with structure-aware merging

```python
resolver = ConflictResolver(config=PresetConfig.SEMANTIC)

```

**Configuration:**

```python
{
    "mode": "semantic",
    "skip_all_conflicts": False,
    "manual_review_required": False,
    "semantic_merging": True,
    "priority_system": False,
    "focus_on_structured_files": True,
    "structure_aware_merging": True,
}

```

**Behavior:**

* Focuses on structured files (JSON, YAML, TOML)
* Structure-aware merging for compatible changes
* Key-level conflict detection and resolution
* Best for configuration and package management files

## Custom Configuration

You can create custom configurations by modifying preset configurations or starting from scratch.

### Basic Custom Configuration

```python
custom_config = {
    "mode": "custom",
    "skip_all_conflicts": False,
    "semantic_merging": True,
    "priority_system": True,
    "priority_rules": {
        "user_selections": 100,
        "security_fixes": 95,  # Custom priority
        "syntax_errors": 80,
        "regular_suggestions": 60,  # Custom priority
        "formatting": 20,  # Custom priority
    },
}

resolver = ConflictResolver(config=custom_config)

```

### Advanced Custom Configuration

```python
advanced_config = {
    "mode": "custom",
    "skip_all_conflicts": False,
    "manual_review_required": False,
    "semantic_merging": True,
    "priority_system": True,
    "priority_rules": {
        "user_selections": 100,
        "security_fixes": 90,
        "syntax_errors": 80,
        "regular_suggestions": 50,
        "formatting": 10,
    },
    "handler_options": {
        "json": {
            "preserve_comments": True,
            "merge_arrays": True,
        },
        "yaml": {
            "preserve_comments": True,
            "preserve_anchors": True,
        },
    },
    "conflict_thresholds": {
        "min_overlap_percentage": 10,
        "max_conflicts_per_file": 10,
    },
}

```

## Configuration Parameters

### Core Parameters

| Parameter | Type | Default | Description |
| ----------- | ------ | --------- | ------------- |
| `mode` | str | "balanced" | Configuration mode identifier |
| `skip_all_conflicts` | bool | False | Skip all conflicting changes |
| `manual_review_required` | bool | False | Require manual review before applying |
| `semantic_merging` | bool | True | Enable semantic merging |
| `priority_system` | bool | True | Enable priority-based resolution |

### Priority Rules

Priority rules determine the order in which conflicting changes are applied. Higher values take precedence.

| Rule | Default | Description |
| ------ | --------- | ------------- |
| `user_selections` | 100 | User-identified options (highest priority) |
| `security_fixes` | 90 | Security-related changes |
| `syntax_errors` | 80 | Syntax fixes and corrections |
| `regular_suggestions` | 50 | Standard suggestions |
| `formatting` | 10 | Formatting changes (lowest priority) |

### Handler Options

Handler-specific options control how different file types are processed.

**JSON Handler:**

```python
"handler_options": {
    "json": {
        "preserve_comments": True,  # Not supported in standard JSON
        "merge_arrays": True,  # Merge arrays when compatible
    }
}

```

**YAML Handler:**

```python
"handler_options": {
    "yaml": {
        "preserve_comments": True,  # Preserve YAML comments
        "preserve_anchors": True,  # Preserve YAML anchors and aliases
        "multi_document": True,  # Support multi-document YAML
    }
}

```

**TOML Handler:**

```python
"handler_options": {
    "toml": {
        "preserve_comments": True,  # Preserve TOML comments
        "merge_tables": True,  # Merge table sections
    }
}

```

## Runtime Configuration

As of version 0.2.0, the resolver includes a comprehensive runtime configuration system that supports multiple configuration sources with proper precedence handling.

### Configuration Precedence

Configuration values are loaded in the following order (later sources override earlier ones):

1. **Defaults** - Safe, sensible defaults built into the application
2. **Config File** - YAML or TOML configuration files (if specified)
3. **Environment Variables** - Environment variables with `CR_` prefix
4. **CLI Flags** - Command-line flags (highest priority)

### Application Modes

The runtime configuration introduces four application modes that control which changes are applied:

| Mode | Value | Description |
| ------ | ------- | ------------- |
| All | `all` | Apply both conflicting and non-conflicting changes (default) |
| Conflicts Only | `conflicts-only` | Apply only changes that have conflicts (after resolution) |
| Non-Conflicts Only | `non-conflicts-only` | Apply only non-conflicting changes |
| Dry Run | `dry-run` | Analyze conflicts without applying any changes |

### Configuration File Format

Create a configuration file in YAML or TOML format:

**YAML Example** (`config.yaml`):

```yaml
# Application mode
mode: all  # all, conflicts-only, non-conflicts-only, dry-run

# Safety features
rollback:
  enabled: true  # Enable automatic rollback on failure

validation:
  enabled: true  # Enable pre-application validation

# Parallel processing (experimental)
parallel:
  enabled: false  # Enable parallel processing
  max_workers: 4  # Maximum number of worker threads

# Logging configuration
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file:  # Optional log file path (leave empty for stdout only)

```

**TOML Example** (`config.toml`):

```toml
# Application mode
mode = "conflicts-only"

# Safety features
[rollback]
enabled = true

[validation]
enabled = true

# Parallel processing
[parallel]
enabled = true
max_workers = 8

# Logging
[logging]
level = "DEBUG"
file = "/var/log/pr-resolver/resolver.log"

```

### Environment Variables

Set these environment variables for runtime configuration:

| Variable | Type | Default | Description |
| ---------- | ------ | --------- | ------------- |
| `CR_MODE` | string | `all` | Application mode |
| `CR_ENABLE_ROLLBACK` | boolean | `true` | Enable automatic rollback on failure |
| `CR_VALIDATE` | boolean | `true` | Enable pre-application validation |
| `CR_PARALLEL` | boolean | `false` | Enable parallel processing |
| `CR_MAX_WORKERS` | integer | `4` | Maximum number of worker threads |
| `CR_LOG_LEVEL` | string | `INFO` | Logging level |
| `CR_LOG_FILE` | string | (empty) | Log file path (optional) |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | string | (required) | GitHub API token |

**Boolean Values:** Accept `true`/`false`, `1`/`0`, `yes`/`no`, `on`/`off` (case-insensitive)

**Example:**

```bash
# Set environment variables
export CR_MODE="dry-run"
export CR_ENABLE_ROLLBACK="true"
export CR_VALIDATE="true"
export CR_PARALLEL="false"
export CR_MAX_WORKERS="4"
export CR_LOG_LEVEL="INFO"
export GITHUB_PERSONAL_ACCESS_TOKEN="your_token_here"

# Run the resolver (will use env vars)
pr-resolve apply --pr 123 --owner myorg --repo myrepo

```

### CLI Configuration Flags

Command-line flags provide the highest priority configuration:

```bash
# Basic usage with mode
pr-resolve apply --pr 123 --owner myorg --repo myrepo --mode dry-run

# Apply only conflicting changes with parallel processing
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --mode conflicts-only \
  --parallel \
  --max-workers 8

# Load configuration from file and override specific settings
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --config /path/to/config.yaml \
  --log-level DEBUG

# Disable safety features (not recommended)
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --no-rollback \
  --no-validation

# Enable logging to file
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --log-level DEBUG \
  --log-file /tmp/resolver.log

```

### CLI Flag Reference

| Flag | Type | Description |
| ------ | ------ | ------------- |
| `--mode` | choice | Application mode (all, conflicts-only, non-conflicts-only, dry-run) |
| `--config` | path | Path to configuration file (YAML or TOML) |
| `--no-rollback` | flag | Disable automatic rollback on failure |
| `--no-validation` | flag | Disable pre-application validation |
| `--parallel` | flag | Enable parallel processing of changes |
| `--max-workers` | int | Maximum number of worker threads (default: 4) |
| `--log-level` | choice | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `--log-file` | path | Path to log file (default: stdout only) |

### Configuration Precedence Example

```bash
# config.yaml contains: mode=all, max_workers=4
# Environment has: CR_MODE=conflicts-only, CR_MAX_WORKERS=8
# CLI provides: --mode dry-run

# Result: mode=dry-run (CLI wins), max_workers=8 (env wins over file)
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --config config.yaml \
  --mode dry-run

```

### Python API Usage

```python
from pathlib import Path
from review_bot_automator.config.runtime_config import RuntimeConfig, ApplicationMode

# Load from defaults
config = RuntimeConfig.from_defaults()

# Load from environment variables
config = RuntimeConfig.from_env()

# Load from configuration file
config = RuntimeConfig.from_file(Path("config.yaml"))

# Apply CLI overrides
config = config.merge_with_cli(
    mode=ApplicationMode.DRY_RUN,
    parallel_processing=True,
    max_workers=16
)

# Access configuration values
print(f"Mode: {config.mode}")
print(f"Rollback enabled: {config.enable_rollback}")
print(f"Parallel: {config.parallel_processing}")

```

### Safety Features

#### Automatic Rollback

When `enable_rollback` is `true` (default), the resolver creates a git stash checkpoint before applying changes. If any error occurs, all changes are automatically rolled back.

```bash
# Rollback enabled (default)
pr-resolve apply --pr 123 --owner myorg --repo myrepo

# Rollback disabled (not recommended)
pr-resolve apply --pr 123 --owner myorg --repo myrepo --no-rollback

```

#### Pre-Application Validation

When `validate_before_apply` is `true` (default), all changes are validated before being applied to catch errors early.

```bash
# Validation enabled (default)
pr-resolve apply --pr 123 --owner myorg --repo myrepo

# Validation disabled (for performance, not recommended)
pr-resolve apply --pr 123 --owner myorg --repo myrepo --no-validation

```

### Parallel Processing (Experimental)

Enable parallel processing for improved performance on large PRs with many changes:

```bash
# Enable parallel processing with default workers (4)
pr-resolve apply --pr 123 --owner myorg --repo myrepo --parallel

# Enable with custom worker count
pr-resolve apply --pr 123 --owner myorg --repo myrepo --parallel --max-workers 16

```

**Notes:**

* Parallel processing uses ThreadPoolExecutor for I/O-bound operations
* Thread-safe collections ensure data integrity
* Maintains result order across parallel execution
* Recommended workers: 4-8 (higher values may not improve performance)
* **Experimental:** May affect logging order

### Configuration Examples

#### Example 1: Development Environment

```yaml
# dev-config.yaml
mode: all
rollback:
  enabled: true
validation:
  enabled: true
parallel:
  enabled: true
  max_workers: 8
logging:
  level: DEBUG
  file: /tmp/pr-resolver-dev.log

```

```bash
pr-resolve apply --pr 123 --owner myorg --repo myrepo --config dev-config.yaml

```

#### Example 2: Production Environment

```yaml
# prod-config.yaml
mode: conflicts-only  # Only resolve actual conflicts
rollback:
  enabled: true  # Always enable in production
validation:
  enabled: true  # Always validate in production
parallel:
  enabled: false  # Disable for predictable behavior
logging:
  level: WARNING  # Less verbose logging
  file: /var/log/pr-resolver/production.log

```

#### Example 3: CI/CD Pipeline

```bash
# Set via environment variables in CI/CD
export CR_MODE="dry-run"  # Analyze only, don't apply
export CR_LOG_LEVEL="INFO"
export GITHUB_PERSONAL_ACCESS_TOKEN="${GITHUB_TOKEN}"  # From CI secrets

pr-resolve apply --pr $PR_NUMBER --owner $REPO_OWNER --repo $REPO_NAME

```

#### Example 4: Quick Dry-Run

```bash
# Fastest way to analyze without applying
pr-resolve apply --pr 123 --owner myorg --repo myrepo --mode dry-run

```

### Legacy Environment Variables

For backwards compatibility, these environment variables are also supported:

| Variable | Type | Description |
| ---------- | ------ | ------------- |
| `GITHUB_TOKEN` | string | GitHub personal access token (legacy alias) |
| `PR_CONFLICT_RESOLVER_CONFIG` | string | Path to configuration file (legacy) |
| `PR_CONFLICT_RESOLVER_LOG_LEVEL` | string | Logging level (legacy) |

**Note:** New projects should use the `CR_*` prefix for runtime configuration and `GITHUB_PERSONAL_ACCESS_TOKEN` for authentication.

## LLM Provider Configuration

The resolver supports multiple LLM providers for AI-powered conflict resolution and code analysis. Each provider has different characteristics, costs, and setup requirements.

### Supported Providers

| Provider | Type | API Key Required | Cost | Best For |
| ---------- | ------ | ------------------ | ------ | ---------- |
| `openai` | API | Yes | $$ | Production, high accuracy |
| `anthropic` | API | Yes | $$ | Advanced reasoning, long context |
| `claude-cli` | CLI | No (subscription) | Subscription | Development, debugging |
| `codex-cli` | CLI | No (subscription) | Subscription | Code-specific tasks |
| `ollama` | Local | No | Free | Privacy, offline use, experimentation |

### Environment Variables (Runtime Configuration)

Configure LLM providers using these environment variables:

| Variable | Type | Default | Description |
| ---------- | ------ | --------- | ------------- |
| `CR_LLM_ENABLED` | boolean | `false` | Enable LLM-powered features |
| `CR_LLM_PROVIDER` | string | `claude-cli` | Provider name (openai, anthropic, claude-cli, codex-cli, ollama) |
| `CR_LLM_MODEL` | string | provider-specific | Model identifier (optional, uses provider defaults) |
| `CR_LLM_API_KEY` | string | (required for API providers) | API key for openai/anthropic |
| `CR_LLM_TIMEOUT` | integer | provider-specific | Request timeout in seconds |
| `CR_LLM_CONFIDENCE_THRESHOLD` | float | `0.5` | Min confidence (0.0-1.0) to accept changes |
| `CR_LLM_RETRY_ON_RATE_LIMIT` | boolean | `true` | Retry on rate limit errors |
| `CR_LLM_RETRY_MAX_ATTEMPTS` | integer | `3` | Max retry attempts (>=1) |
| `CR_LLM_RETRY_BASE_DELAY` | float | `2.0` | Base delay for exponential backoff |
| `CR_LLM_CIRCUIT_BREAKER_ENABLED` | boolean | `true` | Enable circuit breaker pattern |
| `CR_LLM_CIRCUIT_BREAKER_THRESHOLD` | integer | `5` | Failures before circuit opens |
| `CR_LLM_CIRCUIT_BREAKER_COOLDOWN` | float | `60.0` | Seconds before recovery attempt |

**Boolean Values:** Accept `true`/`false`, `1`/`0`, `yes`/`no` (case-insensitive)

### Provider-Specific Configuration

#### OpenAI (API Provider)

**Models**: GPT-4, GPT-4 Turbo, GPT-4o
**Default Model**: `gpt-4`

```bash
# Set up OpenAI provider
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="openai"
export CR_LLM_MODEL="gpt-4"  # Optional, defaults to gpt-4
export CR_LLM_API_KEY="sk-..."  # Get from https://platform.openai.com/api-keys

# Run resolver with OpenAI
pr-resolve apply --pr 123 --owner myorg --repo myrepo

```

**Cost**: Pay-per-token
**Latency**: Low (200-500ms)
**Context**: Up to 128K tokens (GPT-4 Turbo)

#### Anthropic (API Provider)

**Models**: Claude Sonnet 4.5, Claude Opus 4, Claude Haiku 4
**Default Model**: `claude-sonnet-4`

```bash
# Set up Anthropic provider
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="anthropic"
export CR_LLM_MODEL="claude-sonnet-4-5"  # Optional
export CR_LLM_API_KEY="sk-ant-..."  # Get from https://console.anthropic.com/

# Run resolver with Anthropic
pr-resolve apply --pr 123 --owner myorg --repo myrepo

```

**Cost**: Pay-per-token with prompt caching (50-90% cost reduction)
**Latency**: Low (200-500ms)
**Context**: Up to 200K tokens
**Features**: Advanced reasoning, strong code understanding

#### Claude CLI (CLI Provider)

**Requirement**: Claude CLI must be installed and authenticated
**Cost**: Included with Claude subscription

```bash
# Install Claude CLI (if not already installed)
# Follow instructions at https://docs.anthropic.com/claude/cli

# Set up Claude CLI provider (no API key needed)
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="claude-cli"
export CR_LLM_MODEL="claude-sonnet-4-5"  # Optional

# Run resolver with Claude CLI
pr-resolve apply --pr 123 --owner myorg --repo myrepo

```

**Cost**: $0 (subscription-based)
**Latency**: Medium (1-3s, includes CLI overhead)
**Best For**: Development, debugging, learning

#### Codex CLI (CLI Provider)

**Requirement**: GitHub Copilot subscription with Codex CLI access
**Cost**: Included with Copilot subscription

```bash
# Set up Codex CLI provider (no API key needed)
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="codex-cli"
export CR_LLM_MODEL="codex"  # Optional

# Run resolver with Codex CLI
pr-resolve apply --pr 123 --owner myorg --repo myrepo

```

**Cost**: $0 (subscription-based)
**Latency**: Medium (1-3s)
**Best For**: Code-specific tasks, GitHub integration

#### Ollama (Local Provider)

**Requirement**: Ollama must be installed and running
**Models**: llama3.3:70b, codellama, mistral, and many more
**Cost**: Free (runs locally)

```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama3.3:70b

# Set up Ollama provider
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="ollama"
export CR_LLM_MODEL="llama3.3:70b"  # Required

# Run resolver with Ollama
pr-resolve apply --pr 123 --owner myorg --repo myrepo

```

**Cost**: $0 (local inference)
**Latency**: High (5-30s, depends on hardware)
**Best For**: Privacy, offline use, experimentation, cost-sensitive environments

**Ollama Configuration:**

```bash
# Use custom Ollama base URL (default: http://localhost:11434)
export OLLAMA_BASE_URL="http://custom-host:11434"

# Or configure in Python
from review_bot_automator.llm import create_provider

provider = create_provider(
    "ollama",
    model="llama3.3:70b",
    base_url="http://custom-host:11434"
)

```

### Cost Comparison

| Provider | Input Cost | Output Cost | Context Size | Caching |
| ---------- | ----------- | ------------- | -------------- | --------- |
| OpenAI (GPT-4) | $0.03/1K | $0.06/1K | 8K-128K | No |
| Anthropic (Sonnet 4.5) | $0.003/1K | $0.015/1K | 200K | Yes (50-90% savings) |
| Anthropic (Opus 4) | $0.015/1K | $0.075/1K | 200K | Yes |
| Claude CLI | Subscription | Subscription | 200K | N/A |
| Codex CLI | Subscription | Subscription | Varies | N/A |
| Ollama (local) | $0 | $0 | Varies | No |

**Note**: Costs are approximate and may change. Check provider pricing pages for current rates.

### Provider Selection Guide

**Choose OpenAI if:**

* You need reliable, production-grade performance
* You're already using OpenAI in your stack
* You need fast response times
* Cost is secondary to accuracy

**Choose Anthropic if:**

* You need the best reasoning capabilities
* You process large context (>50K tokens)
* You want significant cost savings via prompt caching
* You need long-running context retention

**Choose Claude CLI if:**

* You're developing or debugging locally
* You have a Claude subscription
* You don't want to manage API keys
* You want interactive development experience

**Choose Codex CLI if:**

* You focus on code-specific tasks
* You have GitHub Copilot subscription
* You want tight GitHub integration

**Choose Ollama if:**

* Privacy is a primary concern
* You need offline operation
* You have capable hardware (GPU recommended)
* You want to experiment without cost
* You're in a cost-sensitive environment

### Python API Usage (Advanced)

```python
from review_bot_automator.llm import create_provider, validate_provider
from review_bot_automator.llm.config import LLMConfig

# Method 1: Create provider directly
provider = create_provider(
    provider="anthropic",
    model="claude-sonnet-4-5",
    api_key="sk-ant-...",
    timeout=30
)

# Method 2: Create from environment variables
config = LLMConfig.from_env()
provider = create_provider(
    provider=config.provider,
    model=config.model,
    api_key=config.api_key
)

# Method 3: Create from config object
config = LLMConfig(
    enabled=True,
    provider="ollama",
    model="llama3.3:70b",
    api_key=None  # Not needed for Ollama
)
provider = create_provider(
    provider=config.provider,
    model=config.model,
    api_key=config.api_key
)

# Validate provider before use
if validate_provider(provider):
    response = provider.generate("Explain this code conflict")
    print(f"Response: {response}")
else:
    print("Provider validation failed")

```

### Prompt Caching (Anthropic Only)

Anthropic providers support prompt caching for 50-90% cost reduction on repeated prompts:

```python
from review_bot_automator.llm.cache import PromptCache
from pathlib import Path

# Create cache instance
cache = PromptCache(
    cache_dir=Path.home() / ".pr-resolver" / "cache",
    ttl_seconds=7 * 24 * 60 * 60,  # 7 days
    max_size_bytes=100 * 1024 * 1024  # 100MB
)

# Cache is automatically used by Anthropic provider
# Prompts are hashed and cached for TTL duration
# LRU eviction when max size is reached

# Check cache statistics
stats = cache.get_stats()
print(f"Cache hit rate: {stats['hit_rate']}%")
print(f"Total size: {stats['total_size']} bytes")

```

### Troubleshooting LLM Providers

#### Provider not available

**Problem:** Provider reports as unavailable during health check

**Solutions:**

```bash
# For API providers: verify API key
echo $CR_LLM_API_KEY | cut -c1-10  # Check first 10 chars

# Test API key manually
# OpenAI
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $CR_LLM_API_KEY"

# Anthropic
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $CR_LLM_API_KEY" \
  -H "anthropic-version: 2023-06-01"

# For CLI providers: verify CLI is installed
which claude  # Should return path
which codex   # Should return path

# For Ollama: verify service is running
curl http://localhost:11434/api/tags
ollama list  # Should show installed models

```

#### Slow responses

**Problem:** LLM responses take too long

**Solutions:**

```bash
# Increase timeout
export CR_LLM_TIMEOUT="60"  # 60 seconds

# For Ollama: use smaller/faster model
export CR_LLM_MODEL="llama3.3:8b"  # Smaller than 70b

# For API providers: use faster model
export CR_LLM_MODEL="gpt-4-turbo"  # Faster than gpt-4
export CR_LLM_MODEL="claude-haiku-4"  # Faster than Sonnet/Opus

```

#### High costs

**Problem:** LLM API costs too high

**Solutions:**

```bash
# Switch to Anthropic with prompt caching
export CR_LLM_PROVIDER="anthropic"
# Caching provides 50-90% cost reduction

# Use smaller model
export CR_LLM_MODEL="claude-haiku-4"  # Much cheaper than Opus

# Switch to local Ollama
export CR_LLM_PROVIDER="ollama"
export CR_LLM_MODEL="llama3.3:70b"  # Free

# Switch to subscription-based CLI
export CR_LLM_PROVIDER="claude-cli"  # Fixed cost

```

## Configuration Examples

### Example 1: High-Priority Security Fixes

```python
security_config = {
    "mode": "security_focused",
    "priority_rules": {
        "user_selections": 100,
        "security_fixes": 99,  # Very high priority for security
        "syntax_errors": 70,
        "regular_suggestions": 40,
        "formatting": 5,
    },
    "semantic_merging": False,  # Disable for strict control
}

```

### Example 2: Formatting-First Configuration

```python
formatting_config = {
    "mode": "formatting_first",
    "priority_rules": {
        "user_selections": 100,
        "security_fixes": 90,
        "formatting": 75,  # Higher priority for formatting
        "syntax_errors": 70,
        "regular_suggestions": 50,
    },
    "semantic_merging": True,
}

```

### Example 3: Strict Manual Review

```python
strict_config = {
    "mode": "strict_manual",
    "skip_all_conflicts": True,  # Skip all conflicts
    "manual_review_required": True,
    "semantic_merging": False,
    "priority_system": False,
}

```

## Integration Examples

These examples demonstrate combining multiple features for real-world scenarios.

### Example 1: Full-Featured Production Workflow

Combining all safety features with parallel processing for a large PR:

```bash
# Create a comprehensive production configuration
cat > prod-workflow.yaml <<EOF
mode: conflicts-only
rollback:
  enabled: true
validation:
  enabled: true
parallel:
  enabled: true
  max_workers: 8
logging:
  level: INFO
  file: /var/log/pr-resolver/prod.log
EOF

# Apply with configuration file
pr-resolve apply --pr 456 --owner myorg --repo myproject --config prod-workflow.yaml

# Or use environment variables for CI/CD
export CR_MODE="conflicts-only"
export CR_ENABLE_ROLLBACK="true"
export CR_VALIDATE="true"
export CR_PARALLEL="true"
export CR_MAX_WORKERS="8"
export CR_LOG_LEVEL="INFO"
export CR_LOG_FILE="/var/log/pr-resolver/prod.log"

pr-resolve apply --pr 456 --owner myorg --repo myproject

```

### Example 2: Development Workflow with Debug Logging

Fast iteration with comprehensive logging for debugging:

```bash
# Quick dry-run with debug logging
pr-resolve apply --pr 789 --owner myorg --repo myproject \
  --mode dry-run \
  --log-level DEBUG \
  --log-file /tmp/debug-$(date +%Y%m%d-%H%M%S).log

# If dry-run looks good, apply with rollback protection
pr-resolve apply --pr 789 --owner myorg --repo myproject \
  --mode all \
  --rollback \
  --validation \
  --log-level DEBUG

```

### Example 3: High-Performance Large PR Processing

Optimized for very large PRs (100+ files):

```yaml
# perf-config.yaml
mode: all
rollback:
  enabled: true  # Keep safety enabled
validation:
  enabled: false  # Disable for speed (if confident)
parallel:
  enabled: true
  max_workers: 16  # High parallelism
logging:
  level: WARNING  # Reduce logging overhead

```

```bash
pr-resolve apply --pr 999 --owner myorg --repo myproject \
  --config perf-config.yaml \
  --parallel \
  --max-workers 16

```

### Example 4: Conservative Production with Manual Checkpoints

Maximum safety for critical production systems:

```bash
# Step 1: Analyze conflicts only
pr-resolve analyze --pr 111 --owner myorg --repo myproject

# Step 2: Dry-run to see what would be applied
pr-resolve apply --pr 111 --owner myorg --repo myproject --mode dry-run

# Step 3: Apply only non-conflicting changes first
pr-resolve apply --pr 111 --owner myorg --repo myproject \
  --mode non-conflicts-only \
  --rollback \
  --validation

# Step 4: Review and apply conflicting changes
pr-resolve apply --pr 111 --owner myorg --repo myproject \
  --mode conflicts-only \
  --rollback \
  --validation \
  --log-level INFO \
  --log-file /var/log/conflicts-$(date +%Y%m%d).log

```

### Example 5: CI/CD Integration with Precedence Chain

Using all configuration sources together:

```bash
# 1. Create base configuration file (lowest priority)
cat > ci-base.yaml <<EOF
rollback:
  enabled: true
validation:
  enabled: true
parallel:
  enabled: false
logging:
  level: INFO
EOF

# 2. Set environment variables (medium priority)
export CR_MODE="dry-run"  # Default to dry-run in CI
export CR_LOG_LEVEL="DEBUG"  # More verbose in CI

# 3. Use CLI flags for job-specific overrides (highest priority)
# For PR validation job: analyze only
pr-resolve apply --pr $PR_NUMBER --owner $ORG --repo $REPO \
  --config ci-base.yaml \
  --mode dry-run

# For auto-apply job: apply with parallel processing
pr-resolve apply --pr $PR_NUMBER --owner $ORG --repo $REPO \
  --config ci-base.yaml \
  --mode conflicts-only \
  --parallel \
  --max-workers 8

```

### Example 6: Python API with Dynamic Configuration

Building configuration programmatically:

```python
from pathlib import Path
from review_bot_automator import ConflictResolver
from review_bot_automator.config.runtime_config import RuntimeConfig, ApplicationMode
from review_bot_automator.config import PresetConfig

# Start with preset configuration
base_config = PresetConfig.BALANCED

# Load runtime configuration with precedence
runtime_config = RuntimeConfig.from_file(Path("base-config.yaml"))
runtime_config = runtime_config.merge_with_env()

# Determine mode based on PR size
pr_size = 150  # files changed
if pr_size > 100:
    runtime_config = runtime_config.merge_with_cli(
        parallel_processing=True,
        max_workers=16,
        validate_before_apply=False  # Skip validation for speed
    )
elif pr_size < 10:
    runtime_config = runtime_config.merge_with_cli(
        parallel_processing=False,
        validate_before_apply=True
    )

# Initialize resolver with both configurations
resolver = ConflictResolver(config=base_config)

# Apply with runtime configuration
results = resolver.resolve_pr_conflicts(
    owner="myorg",
    repo="myproject",
    pr_number=123,
    mode=runtime_config.mode,
    validate=runtime_config.validate_before_apply,
    parallel=runtime_config.parallel_processing,
    max_workers=runtime_config.max_workers,
    enable_rollback=runtime_config.enable_rollback
)

print(f"Applied: {results.applied_count}/{results.total_count}")
print(f"Success rate: {results.success_rate}%")

```

## Performance Tuning

### Understanding Performance Characteristics

The resolver's performance is affected by several factors:

1. **PR Size**: Number of files and changes
2. **Conflict Complexity**: Semantic analysis overhead
3. **I/O Operations**: File reading/writing
4. **Validation**: Pre-application checks
5. **Logging**: Debug logging overhead

### Parallel Processing Guidelines

#### When to Enable Parallel Processing

**Enable for:**

* Large PRs (30+ files)
* Independent file changes
* I/O-bound workloads
* Time-critical resolutions

**Disable for:**

* Small PRs (< 10 files)
* Dependent changes across files
* Debugging sessions (easier to trace)
* Systems with limited CPU cores (< 4)

#### Optimal Worker Count

The optimal number of workers depends on your system and workload:

**General Guidelines:**

```bash
# Small PRs (10-30 files): 2-4 workers
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 4

# Medium PRs (30-100 files): 4-8 workers
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 8

# Large PRs (100-300 files): 8-16 workers
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 16

# Very large PRs (300+ files): 16-32 workers
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 32

```

**CPU-Based Guidelines:**

```bash
# Rule of thumb: 2x CPU cores for I/O-bound work
WORKERS=$(($(nproc) * 2))
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers $WORKERS

# Conservative: Match CPU cores
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers $(nproc)

```

#### Benchmarking Your Configuration

Test different configurations to find optimal settings:

```bash
# Benchmark script
#!/bin/bash
PR_NUMBER=123
OWNER=myorg
REPO=myrepo

echo "Testing different worker counts..."
for workers in 1 4 8 16 32; do
    echo "Testing with $workers workers..."
    time pr-resolve apply --pr $PR_NUMBER --owner $OWNER --repo $REPO \
        --mode dry-run \
        --parallel \
        --max-workers $workers \
        --log-level WARNING
done

```

### Validation Trade-offs

**Pre-application validation** catches errors early but adds overhead:

```bash
# Maximum safety (slower): validation enabled
pr-resolve apply --pr 123 --owner org --repo repo --validation

# Performance optimized (faster, riskier): validation disabled
pr-resolve apply --pr 123 --owner org --repo repo --no-validation --rollback

```

**Recommendations:**

* **Enable validation** for: Production systems, critical changes, unfamiliar PRs
* **Disable validation** for: Trusted PRs, time-critical resolutions, when rollback is enabled

### Logging Performance Impact

Debug logging can significantly impact performance:

```bash
# Production: minimal logging overhead
pr-resolve apply --pr 123 --owner org --repo repo --log-level WARNING

# Development: detailed logging
pr-resolve apply --pr 123 --owner org --repo repo --log-level DEBUG

# Performance critical: log to file, not stdout
pr-resolve apply --pr 123 --owner org --repo repo \
  --log-level INFO \
  --log-file /var/log/pr-resolver/perf.log

```

**Performance Impact by Log Level:**

* `ERROR`: Minimal overhead (< 1%)
* `WARNING`: Low overhead (1-2%)
* `INFO`: Moderate overhead (2-5%)
* `DEBUG`: High overhead (10-20%)

### Optimization Strategies

#### Strategy 1: Staged Application

For very large PRs, apply in stages:

```bash
# Stage 1: Non-conflicting changes (fastest)
pr-resolve apply --pr 999 --owner org --repo repo \
  --mode non-conflicts-only \
  --parallel --max-workers 16 \
  --no-validation

# Stage 2: Conflicting changes (slower, more careful)
pr-resolve apply --pr 999 --owner org --repo repo \
  --mode conflicts-only \
  --parallel --max-workers 8 \
  --validation

```

#### Strategy 2: Configuration Caching

Reuse configuration across multiple PRs:

```bash
# Create optimized configuration once
cat > optimized.yaml <<EOF
parallel:
  enabled: true
  max_workers: 16
validation:
  enabled: false
rollback:
  enabled: true
logging:
  level: WARNING
EOF

# Reuse for multiple PRs
for pr in 100 101 102 103; do
    pr-resolve apply --pr $pr --owner org --repo repo --config optimized.yaml
done

```

#### Strategy 3: Resource Monitoring

Monitor system resources during execution:

```bash
# Run with resource monitoring
(pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel --max-workers 16 \
  --log-level INFO) &

PID=$!
# Monitor CPU and memory
while kill -0 $PID 2>/dev/null; do
    ps -p $PID -o %cpu,%mem,cmd
    sleep 1
done

```

## CLI Configuration

Specify configuration when using the CLI:

```bash
# Use balanced preset (default)
pr-resolve analyze --pr 123 --owner myorg --repo myrepo

# Use conservative preset
pr-resolve analyze --pr 123 --owner myorg --repo myrepo --config conservative

# Use aggressive preset
pr-resolve apply --pr 123 --owner myorg --repo myrepo --config aggressive

```

## Configuration Validation

The resolver validates configuration parameters:

```python
from review_bot_automator import ConflictResolver

try:
    resolver = ConflictResolver(config={
        "mode": "test",
        "skip_all_conflicts": "invalid",  # Should be bool
    })
except ValueError as e:
    print(f"Configuration error: {e}")

```

## Best Practices

### Configuration Organization

1. **Start with Balanced Preset**
   * Use the balanced preset as a starting point for most workflows
   * Override specific settings rather than creating from scratch
   * Understand each preset's trade-offs before switching

2. **Use Configuration Files for Persistence**

   ```bash
   # Store team configuration in version control
   mkdir -p .pr-resolver
   cat > .pr-resolver/team-config.yaml <<EOF
   mode: conflicts-only
   rollback:
     enabled: true
   validation:
     enabled: true
   parallel:
     enabled: true
     max_workers: 8
   EOF

   # Share with team
   git add .pr-resolver/team-config.yaml
   git commit -m "Add PR resolver team configuration"

   ```

3. **Use Environment Variables for Environment-Specific Settings**

   ```bash
   # Development environment
   cat >> ~/.bashrc <<EOF
   export CR_LOG_LEVEL="DEBUG"
   export CR_MAX_WORKERS="4"
   EOF

   # Production environment (via CI/CD)
   export CR_LOG_LEVEL="WARNING"
   export CR_MAX_WORKERS="16"
   export CR_MODE="conflicts-only"

   ```

4. **Use CLI Flags for One-Off Overrides**

   ```bash
   # Normal workflow: use team config
   pr-resolve apply --pr 123 --owner org --repo repo --config .pr-resolver/team-config.yaml

   # One-off: need extra debugging
   pr-resolve apply --pr 123 --owner org --repo repo \
     --config .pr-resolver/team-config.yaml \
     --log-level DEBUG

   ```

### Configuration Strategy by Environment

#### Development Environment

```yaml
# dev-config.yaml - Optimized for iteration speed
mode: all
rollback:
  enabled: true
validation:
  enabled: true
parallel:
  enabled: false  # Easier debugging
logging:
  level: DEBUG
  file: /tmp/pr-resolver-dev.log

```

#### CI/CD Environment

```yaml
# ci-config.yaml - Optimized for automated testing
mode: dry-run  # Analyze only by default
rollback:
  enabled: true
validation:
  enabled: true
parallel:
  enabled: true
  max_workers: 8
logging:
  level: INFO

```

#### Production Environment

```yaml
# prod-config.yaml - Optimized for safety
mode: conflicts-only
rollback:
  enabled: true  # Always enable
validation:
  enabled: true  # Always enable
parallel:
  enabled: true
  max_workers: 16
logging:
  level: WARNING
  file: /var/log/pr-resolver/production.log

```

### Testing Configuration Changes

1. **Always Test with Dry-Run First**

   ```bash
   # Test new configuration without applying changes
   pr-resolve apply --pr 123 --owner org --repo repo \
     --config new-config.yaml \
     --mode dry-run

   ```

2. **Use Non-Conflicts Only for Safe Testing**

   ```bash
   # Apply only safe changes to test configuration
   pr-resolve apply --pr 123 --owner org --repo repo \
     --config new-config.yaml \
     --mode non-conflicts-only

   ```

3. **Test on Small PRs First**

   ```bash
   # Find a small PR for testing
   gh pr list --limit 10 --json number,additions,deletions

   # Test on small PR
   pr-resolve apply --pr <small-pr> --owner org --repo repo \
     --config new-config.yaml

   ```

### Documentation and Maintenance

1. **Document Custom Configurations**

   ```yaml
   # team-config.yaml
   # Custom configuration for MyTeam
   # Optimized for large PRs with many conflicts
   # Last updated: 2025-01-15
   # Contact: team-lead@company.com

   mode: conflicts-only
   rollback:
     enabled: true
   # ... rest of configuration

   ```

2. **Version Control All Configurations**
   * Store in `.pr-resolver/` directory
   * Include comments explaining choices
   * Document changes in commit messages
   * Review configuration changes in PRs

3. **Monitor and Adjust**

   ```bash
   # Track success rates
   pr-resolve apply --pr 123 --owner org --repo repo \
     --config team-config.yaml \
     --log-file logs/pr-123-$(date +%Y%m%d).log

   # Review logs periodically
   grep "Success rate" logs/*.log
   grep "Rollback triggered" logs/*.log

   ```

### Common Patterns

#### Pattern 1: Progressive Enhancement

```bash
# Start conservative, gradually increase automation
# Week 1: Analyze only
pr-resolve apply --pr $PR --owner $ORG --repo $REPO --mode dry-run

# Week 2: Apply non-conflicts
pr-resolve apply --pr $PR --owner $ORG --repo $REPO --mode non-conflicts-only

# Week 3: Apply conflicts with validation
pr-resolve apply --pr $PR --owner $ORG --repo $REPO --mode conflicts-only --validation

# Week 4: Full automation with rollback
pr-resolve apply --pr $PR --owner $ORG --repo $REPO --mode all --rollback

```

#### Pattern 2: Defense in Depth

```bash
# Multiple safety layers
pr-resolve apply --pr 123 --owner org --repo repo \
  --rollback \          # Layer 1: Automatic rollback
  --validation \        # Layer 2: Pre-validation
  --log-level INFO \    # Layer 3: Detailed logging
  --log-file audit.log  # Layer 4: Audit trail

```

#### Pattern 3: Configuration Inheritance

```python
# Base configuration for all teams
from review_bot_automator.config import PresetConfig

base_config = PresetConfig.BALANCED

# Team A: Override for their needs
team_a_config = {
    **base_config,
    "priority_rules": {
        **base_config["priority_rules"],
        "security_fixes": 95,  # Higher priority
    }
}

# Team B: Different overrides
team_b_config = {
    **base_config,
    "semantic_merging": False,  # More conservative
}

```

### Security Considerations

1. **Protect GitHub Tokens**

   ```bash
   # Never commit tokens
   echo 'GITHUB_PERSONAL_ACCESS_TOKEN="***"' >> .gitignore

   # Use environment variables
   export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_xxx"

   # Or use secret managers in CI/CD
   # GitHub Actions: ${{ secrets.GITHUB_TOKEN }}
   # GitLab CI: $GITHUB_TOKEN

   ```

2. **Review Configuration Changes**
   * Treat configuration as code
   * Require PR reviews for config changes
   * Test in non-production first
   * Monitor for unexpected behavior

3. **Audit Logging**

   ```yaml
   # Enable comprehensive logging for auditing
   logging:
     level: INFO
     file: /var/log/pr-resolver/audit-${USER}-${DATE}.log

   ```

### Performance Best Practices

1. **Match Workers to Workload**
   * Small PRs: 2-4 workers
   * Medium PRs: 4-8 workers
   * Large PRs: 8-16 workers
   * Very large PRs: 16-32 workers

2. **Disable Validation Strategically**
   * Keep enabled for production
   * Disable for trusted automated PRs
   * Always enable rollback if validation is disabled

3. **Optimize Logging**
   * Use WARNING in production
   * Use DEBUG only for troubleshooting
   * Log to file for performance-critical operations

4. **Use Staged Application**
   * Apply non-conflicts first (fast)
   * Then apply conflicts (slower)
   * Reduces overall execution time

## Troubleshooting

### Configuration Issues

#### Configuration not applied

**Problem:** Configuration seems to be ignored

**Possible Causes:**

* Configuration file not found
* Invalid YAML/TOML syntax
* Incorrect precedence (CLI flags override config file)

**Solutions:**

```bash
# 1. Verify configuration file exists and is valid
cat config.yaml
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"

# 2. Use absolute path for config file
pr-resolve apply --pr 123 --owner org --repo repo --config /full/path/to/config.yaml

# 3. Check which configuration is being used
pr-resolve apply --pr 123 --owner org --repo repo \
  --config config.yaml \
  --log-level DEBUG \
  | grep -i "configuration"

# 4. Verify precedence - CLI flags override config file
# If you specify --mode dry-run, it will override mode in config file

```

#### Environment variables not recognized

**Problem:** Environment variables like `CR_MODE` seem ignored

**Possible Causes:**

* Typo in variable name
* Variable not exported
* Shell not sourced after setting

**Solutions:**

```bash
# 1. Verify variable is set
echo $CR_MODE
env | grep CR_

# 2. Ensure variable is exported
export CR_MODE="conflicts-only"

# 3. Check for typos - correct prefix is CR_
export CR_MODE="dry-run"  # Correct
export RESOLVER_MODE="dry-run"  # Wrong - will be ignored

# 4. Source your shell profile if you added to .bashrc
source ~/.bashrc

```

#### Configuration validation errors

**Problem:** Configuration rejected with validation error

**Possible Causes:**

* Invalid type (string instead of boolean)
* Invalid value (unknown mode)
* Missing required fields

**Solutions:**

```bash
# Check error message for details
pr-resolve apply --pr 123 --owner org --repo repo --config config.yaml 2>&1 | grep -i error

# Common fixes
# - Boolean values: use true/false, not "true"/"false"
# - Mode values: all, conflicts-only, non-conflicts-only, dry-run
# - Worker count: must be positive integer

```

**Valid Configuration:**

```yaml
mode: conflicts-only  # String, no quotes needed
rollback:
  enabled: true  # Boolean, no quotes
parallel:
  enabled: true
  max_workers: 8  # Integer, no quotes

```

### Runtime Configuration Issues

#### Unexpected resolution behavior

**Problem:** Conflicts resolved in unexpected ways

**Possible Causes:**

* Priority rules not configured correctly
* Mode filtering changes being applied
* Preset configuration not suitable for use case

**Solutions:**

```bash
# 1. Check what would be applied with dry-run
pr-resolve apply --pr 123 --owner org --repo repo --mode dry-run

# 2. Review priority rules in configuration
cat config.yaml | grep -A 10 "priority_rules"

# 3. Try different preset
pr-resolve apply --pr 123 --owner org --repo repo --config conservative

# 4. Enable debug logging to see decision-making
pr-resolve apply --pr 123 --owner org --repo repo --log-level DEBUG

```

#### Mode not filtering correctly

**Problem:** Wrong changes being applied for selected mode

**Possible Causes:**

* Misunderstanding of mode behavior
* Conflict detection not working correctly
* Changes incorrectly categorized

**Solutions:**

```bash
# 1. Analyze conflicts first
pr-resolve analyze --pr 123 --owner org --repo repo

# 2. Test each mode separately
pr-resolve apply --pr 123 --owner org --repo repo --mode dry-run
pr-resolve apply --pr 123 --owner org --repo repo --mode non-conflicts-only --dry-run
pr-resolve apply --pr 123 --owner org --repo repo --mode conflicts-only --dry-run

# 3. Check the resolution logic
# - all: applies everything
# - conflicts-only: applies ONLY changes that HAVE conflicts (after resolution)
# - non-conflicts-only: applies ONLY changes with NO conflicts
# - dry-run: applies nothing, analyzes only

```

### Rollback System Issues

#### Rollback not triggering

**Problem:** Errors occur but rollback doesn't activate

**Possible Causes:**

* Rollback disabled in configuration
* Git repository not initialized
* Insufficient git permissions

**Solutions:**

```bash
# 1. Verify rollback is enabled
pr-resolve apply --pr 123 --owner org --repo repo --rollback

# 2. Check git repository status
git status
git stash list  # See if stash is created

# 3. Verify git is configured
git config --list | grep user

# 4. Check permissions
ls -la .git/

```

#### Rollback fails to restore

**Problem:** Rollback attempted but files not restored

**Possible Causes:**

* Uncommitted changes before running
* Git stash conflicts
* Repository in detached HEAD state

**Solutions:**

```bash
# 1. Check for uncommitted changes BEFORE running resolver
git status

# 2. Commit or stash existing changes first
git stash push -m "Before PR resolver"

# 3. Check git state
git branch -v
git log -1

# 4. Manual rollback if automatic fails
git stash list
git stash apply stash@{0}  # Apply most recent stash

```

#### Rollback leaves repository dirty

**Problem:** After rollback, `git status` shows changes

**Possible Causes:**

* Normal behavior - rollback restores to pre-resolver state
* Some files were not tracked by git
* File permission changes

**Solutions:**

```bash
# 1. Check what changed
git status
git diff

# 2. If changes are expected (rollback worked)
# Files that were modified by resolver before failure

# 3. If unexpected, manually clean
git reset --hard HEAD
git clean -fd

# 4. Review resolver logs
pr-resolve apply --pr 123 --owner org --repo repo --log-level DEBUG

```

### Parallel Processing Issues

#### Parallel processing slower than sequential

**Problem:** Using `--parallel` makes execution slower

**Possible Causes:**

* Too many workers for small PR
* Worker overhead exceeds benefits
* I/O contention
* CPU-bound rather than I/O-bound

**Solutions:**

```bash
# 1. Reduce worker count
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 4

# 2. Disable parallel for small PRs
# Only use parallel for 30+ files
pr-resolve apply --pr 123 --owner org --repo repo  # No --parallel

# 3. Benchmark different worker counts
for workers in 1 4 8 16; do
  echo "Testing $workers workers..."
  time pr-resolve apply --pr 123 --owner org --repo repo \
    --mode dry-run --parallel --max-workers $workers
done

```

#### Thread safety errors

**Problem:** Errors related to threading or concurrent access

**Possible Causes:**

* Race condition in file operations
* Shared state corruption
* Log file contention

**Solutions:**

```bash
# 1. Disable parallel processing temporarily
pr-resolve apply --pr 123 --owner org --repo repo  # No --parallel

# 2. Reduce worker count
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 2

# 3. Use separate log files if needed
pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel \
  --log-file /tmp/resolver-$$.log  # $$ = process ID

```

#### Worker pool hangs

**Problem:** Execution hangs with parallel processing enabled

**Possible Causes:**

* Deadlock in worker threads
* Exception in worker not handled
* Resource exhaustion

**Solutions:**

```bash
# 1. Check system resources
top  # Look for high CPU or memory usage
ps aux | grep pr-resolve

# 2. Kill hung process
pkill -f pr-resolve

# 3. Reduce worker count
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 4

# 4. Disable parallel and report issue
pr-resolve apply --pr 123 --owner org --repo repo

```

### Validation Issues

#### Validation failing for valid changes

**Problem:** Pre-application validation rejects valid changes

**Possible Causes:**

* Overly strict validation rules
* File format differences
* Encoding issues

**Solutions:**

```bash
# 1. Check validation error details
pr-resolve apply --pr 123 --owner org --repo repo --validation --log-level DEBUG

# 2. Temporarily disable validation (with rollback)
pr-resolve apply --pr 123 --owner org --repo repo --no-validation --rollback

# 3. Review specific file causing validation failure
# Check logs for filename and error

# 4. Report issue with reproduction steps

```

#### Validation taking too long

**Problem:** Validation step significantly slows execution

**Possible Causes:**

* Large number of changes
* Complex semantic validation
* File I/O overhead

**Solutions:**

```bash
# 1. Disable validation for performance (use rollback instead)
pr-resolve apply --pr 123 --owner org --repo repo --no-validation --rollback

# 2. Use validation only for conflicts
pr-resolve apply --pr 123 --owner org --repo repo --mode non-conflicts-only --no-validation
pr-resolve apply --pr 123 --owner org --repo repo --mode conflicts-only --validation

# 3. Profile validation time
time pr-resolve apply --pr 123 --owner org --repo repo --validation --mode dry-run
time pr-resolve apply --pr 123 --owner org --repo repo --no-validation --mode dry-run

```

### Performance Issues

#### Extremely slow execution

**Problem:** Resolution takes much longer than expected

**Possible Causes:**

* Very large PR (100+ files)
* Complex conflicts requiring semantic analysis
* Debug logging enabled
* Sequential processing when parallel would help

**Solutions:**

```bash
# 1. Enable parallel processing
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 8

# 2. Reduce logging verbosity
pr-resolve apply --pr 123 --owner org --repo repo --log-level WARNING

# 3. Disable validation (use rollback instead)
pr-resolve apply --pr 123 --owner org --repo repo --no-validation --rollback

# 4. Apply in stages
pr-resolve apply --pr 123 --owner org --repo repo --mode non-conflicts-only --parallel
pr-resolve apply --pr 123 --owner org --repo repo --mode conflicts-only

# 5. Profile execution
time pr-resolve apply --pr 123 --owner org --repo repo --mode dry-run

```

#### High memory usage

**Problem:** Process uses excessive memory

**Possible Causes:**

* Very large files
* Too many parallel workers
* Memory leak

**Solutions:**

```bash
# 1. Reduce parallel workers
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 4

# 2. Disable parallel processing
pr-resolve apply --pr 123 --owner org --repo repo

# 3. Monitor memory usage
ps aux | grep pr-resolve
top -p $(pgrep pr-resolve)

# 4. Report issue with PR details

```

### GitHub API Issues

#### Authentication failures

**Problem:** GitHub API authentication fails

**Possible Causes:**

* Token not set or incorrect
* Token expired
* Insufficient token permissions

**Solutions:**

```bash
# 1. Verify token is set
echo $GITHUB_PERSONAL_ACCESS_TOKEN | cut -c1-10  # Show first 10 chars

# 2. Test token manually
curl -H "Authorization: token $GITHUB_PERSONAL_ACCESS_TOKEN" https://api.github.com/user

# 3. Regenerate token with correct scopes
# Required: repo, read:org

# 4. Use token inline for testing
GITHUB_PERSONAL_ACCESS_TOKEN="ghp_xxx" pr-resolve apply --pr 123 --owner org --repo repo

```

#### Rate limiting

**Problem:** GitHub API rate limit exceeded

**Solutions:**

```bash
# 1. Check current rate limit
curl -H "Authorization: token $GITHUB_PERSONAL_ACCESS_TOKEN" https://api.github.com/rate_limit

# 2. Wait for reset or use authenticated token (higher limits)

# 3. Reduce API calls by using dry-run once
pr-resolve apply --pr 123 --owner org --repo repo --mode dry-run  # Cache results

```

### General Troubleshooting

#### Getting detailed logs

```bash
# Enable maximum logging
pr-resolve apply --pr 123 --owner org --repo repo \
  --log-level DEBUG \
  --log-file /tmp/resolver-debug-$(date +%Y%m%d-%H%M%S).log

# Review logs
less /tmp/resolver-debug-*.log
grep -i error /tmp/resolver-debug-*.log
grep -i rollback /tmp/resolver-debug-*.log

```

#### Isolating the issue

```bash
# 1. Test with minimal configuration
pr-resolve apply --pr 123 --owner org --repo repo --mode dry-run

# 2. Test with safe defaults
pr-resolve apply --pr 123 --owner org --repo repo --rollback --validation

# 3. Test different modes
pr-resolve apply --pr 123 --owner org --repo repo --mode non-conflicts-only

# 4. Compare with analyze command
pr-resolve analyze --pr 123 --owner org --repo repo

```

#### Reporting issues

When reporting issues, include:

1. Full command used
2. Configuration file (if used)
3. Error message
4. Log file (with `--log-level DEBUG`)
5. PR details (size, complexity)
6. Environment (OS, Python version, git version)

## See Also

* [Resolution Strategies](resolution-strategies.md) - How strategies use configuration
* [Conflict Types](conflict-types.md) - Understanding what gets configured
* [Getting Started](getting-started.md) - Basic configuration setup
