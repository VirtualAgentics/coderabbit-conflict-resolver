# Resolution Strategies

This document explains the different strategies used by Review Bot Automator to automatically resolve conflicts between PR suggestions.

## Overview

Resolution strategies determine how conflicts between multiple suggestions are handled. The resolver supports several strategies, each with different behaviors and use cases.

## Strategy Types

### Priority-Based Strategy (Default)

**Purpose:** Apply the highest-priority change based on configured priority rules.

**Priority Levels (default):**

* `user_selections`: 100 - User-identified options take highest priority
* `security_fixes`: 90 - Security-related changes override others
* `syntax_errors`: 80 - Syntax fixes have high priority
* `regular_suggestions`: 50 - Standard suggestions
* `formatting`: 10 - Formatting changes have lowest priority

**How it works:**

1. Calculate priority for each conflicting change
2. Select the highest-priority change
3. Apply that change and skip all others
4. If multiple changes have the same priority, apply the first one

**Example:**

```python
# Conflict: Two changes to same lines
Change 1: Security fix (priority 90)
Change 2: Formatting change (priority 10)

Result: Apply security fix, skip formatting

```

**Configuration:**

```python
from review_bot_automator import PriorityStrategy

strategy = PriorityStrategy(config={
    "priority_rules": {
        "user_selections": 100,
        "security_fixes": 90,
        "syntax_errors": 80,
        "regular_suggestions": 50,
        "formatting": 10
    }
})

```

### Skip Strategy (Conservative)

**Purpose:** Skip all conflicting changes, requiring manual review.

**How it works:**

* When conflicts are detected, skip all involved changes
* Return a resolution with `success=False`
* Log conflicts for manual review
* Safe default for uncertain situations

**Use case:** When you want to review all conflicts manually before applying any changes.

### Override Strategy (Aggressive)

**Purpose:** Always apply user-selected options, overriding all other suggestions.

**How it works:**

1. Check if any change has a user selection (`option_label` in metadata)
2. Apply user selections and skip all other changes
3. If no user selections exist, fall back to priority-based resolution

**Use case:** When you trust user selections completely and want maximum automation.

### Merge Strategy (Semantic Combining)

**Purpose:** Combine multiple non-conflicting changes intelligently.

**How it works:**

1. Analyze changes for semantic compatibility
2. For structured files (JSON/YAML/TOML), merge at the key/property level
3. For code files, merge sequential changes when possible
4. Detect and handle conflicting modifications

**Supported file types:**

* JSON: Key-level merging
* YAML: Structure-aware merging with comment preservation
* TOML: Section-based merging

**Example:**

```json
// Suggestion 1
{"name": "my-app"}

// Suggestion 2
{"version": "1.0.0"}

// Result: Merged
{"name": "my-app", "version": "1.0.0"}

```

**Limitations:**

* Only works for compatible changes
* May fail for complex code changes
* Requires semantic analysis

### Sequential Strategy (Ordered Application)

**Purpose:** Apply changes in a specific order to minimize conflicts.

**How it works:**

1. Order changes by some criteria (timestamp, author, file type)
2. Apply changes one by one in sequence
3. Skip changes that would conflict with already-applied changes
4. Continue until all compatible changes are applied

**Ordering options:**

* Chronological (oldest first or newest first)
* Priority-based (highest priority first)
* File-based (apply all changes to one file, then move to next)

**Use case:** When you want to apply as many changes as possible while maintaining order.

### Defer Strategy (Manual Review)

**Purpose:** Escalate complex conflicts to manual review.

**How it works:**

1. Detect complex conflicts (high severity, many changes)
2. Generate a detailed report with all options
3. Skip automatic resolution
4. Return resolution with `success=False` and detailed conflict information

**Use case:** When conflicts are too complex for automatic resolution.

## Strategy Selection

### Automatic Selection

The resolver can automatically select a strategy based on:

* Conflict type and severity
* Configuration preset
* Number of changes in conflict
* File type

### Manual Selection

Explicitly specify a strategy when using the CLI or API:

```bash
pr-resolve apply --pr 123 --strategy priority

```

```python
resolver = ConflictResolver(
    config=PresetConfig.BALANCED,
    strategy="priority"
)

```

## Configuration Presets

Presets combine specific strategies with configuration:

### Conservative Preset

* **Strategy:** Skip all conflicts
* **Approach:** Manual review required
* **Best for:** Critical systems, strict compliance

```python
config = PresetConfig.CONSERVATIVE

```

### Balanced Preset (Default)

* **Strategy:** Priority-based + semantic merging
* **Approach:** Automated resolution with safety checks
* **Best for:** Most development workflows

```python
config = PresetConfig.BALANCED

```

### Aggressive Preset

* **Strategy:** Override + priority
* **Approach:** Maximum automation, trust user selections
* **Best for:** High-confidence environments

```python
config = PresetConfig.AGGRESSIVE

```

### Semantic Preset

* **Strategy:** Merge + sequential
* **Approach:** Structure-aware merging for config files
* **Best for:** Configuration file management

```python
config = PresetConfig.SEMANTIC

```

## Custom Strategy Implementation

You can implement custom resolution strategies:

```python
from review_bot_automator.core.models import Conflict, Resolution

class CustomStrategy:
    """Custom resolution strategy."""

    def resolve(self, conflict: Conflict) -> Resolution:
        """Resolve a conflict using custom logic.

        Args:
            conflict: The conflict to resolve

        Returns:
            Resolution object describing what was applied and skipped
        """
        # Your custom logic here
        return Resolution(
            strategy="custom",
            applied_changes=[...],
            skipped_changes=[...],
            success=True,
            message="Custom resolution applied"
        )

# Use the custom strategy
resolver = ConflictResolver(
    config=PresetConfig.BALANCED,
    strategy=CustomStrategy()
)

```

## Strategy Comparison

| Strategy | Automation | Safety | Speed | Best For |
| ---------- | ------------ | -------- | ------- | ---------- |
| Priority | High | Medium | Fast | Most cases |
| Skip | Low | High | Fast | Critical systems |
| Override | Very High | Medium | Fast | User-trusted workflows |
| Merge | High | High | Medium | Config files |
| Sequential | Medium | Medium | Medium | Ordered changes |
| Defer | Low | Very High | Fast | Complex conflicts |

## Best Practices

1. **Start with Balanced** - Default preset works for most scenarios
2. **Use Dry-Run** - Test strategies before applying changes
3. **Review Skipped Changes** - Check what was skipped and why
4. **Monitor Success Rate** - Track how well strategies are working
5. **Adjust Configuration** - Customize priority rules for your needs
6. **Handle Edge Cases** - Use conservative preset for critical systems

## Troubleshooting

### Strategy not applying changes

**Problem:** Strategy returns `success=False` with skipped changes.

**Solution:** Check conflict details, consider using a different strategy or manual review.

### Wrong changes applied

**Problem:** Strategy applies unexpected changes.

**Solution:** Review priority rules, check metadata, consider using conservative preset.

### Performance issues

**Problem:** Strategy is slow for large conflicts.

**Solution:** Use simpler strategies (skip, priority), consider conflict caching.

## See Also

* [Configuration Reference](configuration.md) - Configure strategy behavior
* [Conflict Types](conflict-types.md) - Understand conflict types
* [API Reference](api-reference.md) - Programmatic strategy usage
