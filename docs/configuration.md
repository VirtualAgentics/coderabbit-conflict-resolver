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

## Environment Variables

Set these environment variables for configuration:

### GITHUB_TOKEN

**Required:** GitHub personal access token for API access

```bash
export GITHUB_TOKEN="your_token_here"
```

### PR_CONFLICT_RESOLVER_CONFIG

**Optional:** Path to configuration file

```bash
export PR_CONFLICT_RESOLVER_CONFIG="/path/to/config.json"
```

### PR_CONFLICT_RESOLVER_LOG_LEVEL

**Optional:** Logging level (DEBUG, INFO, WARNING, ERROR)

```bash
export PR_CONFLICT_RESOLVER_LOG_LEVEL="INFO"
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
