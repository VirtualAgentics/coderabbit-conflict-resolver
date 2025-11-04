# Configuration Reference

This document explains how to configure the CodeRabbit Conflict Resolver for different use cases and environments.

## Overview

Configuration is done through preset configurations or custom configuration dictionaries. Presets provide ready-made setups for common scenarios, while custom configurations allow fine-grained control.

## Configuration Presets

The resolver provides four preset configurations optimized for different use cases.

### Conservative Preset

**Use case:** Critical systems requiring manual review of all conflicts

```python
from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.config import PresetConfig

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
- Skips all conflicting changes
- Requires manual review for every conflict
- Safe default for production systems
- No automatic resolution

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
- Automatically resolves conflicts using priority rules
- Supports semantic merging for compatible changes
- User selections override other suggestions
- Security fixes have high priority
- Best balance between automation and safety

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
- Maximizes automation with minimal user intervention
- User selections always override other changes
- Applies as many changes as possible
- Best for rapid development with trusted reviews

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
- Focuses on structured files (JSON, YAML, TOML)
- Structure-aware merging for compatible changes
- Key-level conflict detection and resolution
- Best for configuration and package management files

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
|-----------|------|---------|-------------|
| `mode` | str | "balanced" | Configuration mode identifier |
| `skip_all_conflicts` | bool | False | Skip all conflicting changes |
| `manual_review_required` | bool | False | Require manual review before applying |
| `semantic_merging` | bool | True | Enable semantic merging |
| `priority_system` | bool | True | Enable priority-based resolution |

### Priority Rules

Priority rules determine the order in which conflicting changes are applied. Higher values take precedence.

| Rule | Default | Description |
|------|---------|-------------|
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
|------|-------|-------------|
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
|----------|------|---------|-------------|
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
|------|------|-------------|
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
from pr_conflict_resolver.config.runtime_config import RuntimeConfig, ApplicationMode

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
- Parallel processing uses ThreadPoolExecutor for I/O-bound operations
- Thread-safe collections ensure data integrity
- Maintains result order across parallel execution
- Recommended workers: 4-8 (higher values may not improve performance)
- **Experimental:** May affect logging order

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
|----------|------|-------------|
| `GITHUB_TOKEN` | string | GitHub personal access token (legacy alias) |
| `PR_CONFLICT_RESOLVER_CONFIG` | string | Path to configuration file (legacy) |
| `PR_CONFLICT_RESOLVER_LOG_LEVEL` | string | Logging level (legacy) |

**Note:** New projects should use the `CR_*` prefix for runtime configuration and `GITHUB_PERSONAL_ACCESS_TOKEN` for authentication.

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
from pr_conflict_resolver import ConflictResolver

try:
    resolver = ConflictResolver(config={
        "mode": "test",
        "skip_all_conflicts": "invalid",  # Should be bool
    })
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Best Practices

1. **Start with Balanced** - Use the balanced preset as a starting point
2. **Adjust for Your Workflow** - Customize priority rules to match your team's needs
3. **Test Configuration** - Use dry-run mode to test configuration changes
4. **Document Custom Configs** - Document any custom configurations for your team
5. **Version Control** - Store custom configurations in version control
6. **Monitor Results** - Track success rates and adjust configuration as needed

## Troubleshooting

### Configuration not applied

**Problem:** Configuration seems to be ignored

**Solution:** Verify configuration format and check for validation errors

### Unexpected resolution behavior

**Problem:** Conflicts resolved in unexpected ways

**Solution:** Review priority rules and adjust according to your needs

### Handler options not working

**Problem:** Handler-specific options seem ignored

**Solution:** Check handler documentation and ensure options are valid for file type

## See Also

- [Resolution Strategies](resolution-strategies.md) - How strategies use configuration
- [Conflict Types](conflict-types.md) - Understanding what gets configured
- [Getting Started](getting-started.md) - Basic configuration setup
