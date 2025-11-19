# Conflict Types Explained

This document explains all conflict categories detected by the Review Bot Automator and how they are identified.

## Overview

Conflicts occur when multiple suggestions target overlapping or conflicting areas in the same file. The resolver categorizes conflicts into several types based on:

* Line overlap patterns
* Semantic equivalence
* Content similarity
* Structural conflicts

## Overlap-Based Conflicts

These conflicts are detected by analyzing line ranges where changes overlap.

### Exact Overlap

**Definition:** Two suggestions target the exact same lines (same start and end positions).

**Detection:** `start1 == start2 and end1 == end2`

**Example:**

```text
Suggestion 1: Lines 10-15 → Replace function with optimized version
Suggestion 2: Lines 10-15 → Add error handling to function

```

**Severity:** High - Requires manual intervention to choose the correct change.

### Major Overlap

**Definition:** Overlap covers ≥80% of the combined range.

**Detection:** `overlap_percentage = (overlap_size / total_size) * 100 >= 80`

**Example:**

```text
Suggestion 1: Lines 10-20 → Refactor loop
Suggestion 2: Lines 12-22 → Optimize loop

```

**Severity:** High - Significant conflict that may affect functionality.

### Partial Overlap

**Definition:** Overlap covers 50-80% of the combined range.

**Detection:** `50 <= overlap_percentage < 80`

**Example:**

```text
Suggestion 1: Lines 10-25 → Add new feature
Suggestion 2: Lines 18-30 → Fix bug in same area

```

**Severity:** Medium - May be resolvable with careful merging.

### Minor Overlap

**Definition:** Overlap covers <50% of the combined range.

**Detection:** `overlap_percentage < 50`

**Example:**

```text
Suggestion 1: Lines 10-20 → Update variable names
Suggestion 2: Lines 18-25 → Add documentation

```

**Severity:** Low - Partial overlap that may be safely merged.

## Semantic Conflicts

These conflicts are detected by analyzing the semantic content of suggestions rather than just line numbers.

### Semantic Duplicate

**Definition:** Two suggestions contain equivalent semantic content despite different formatting.

**Detection:**

1. Normalize whitespace and formatting
2. Compare normalized content
3. For structured data (JSON/YAML), compare parsed structures
4. Return True if semantically equivalent

**Example:**

```text
Suggestion 1:

```json

{"name": "test", "value": 42}

```text

Suggestion 2:

```json

{
  "name": "test",
  "value": 42
}

```text

```

**Severity:** Low - Can safely merge, likely same intent with different formatting.

## Disjoint-Key Conflicts (Structured Files)

For structured files like JSON, YAML, or TOML, additional conflict types exist.

### Disjoint Keys Conflict

**Definition:** Multiple suggestions modify different keys in the same file without overlap.

**Example:**

```json
Original:
{
  "name": "project",
  "version": "1.0.0"
}

Suggestion 1: {"name": "my-project"}  → Update name
Suggestion 2: {"version": "2.0.0"}   → Update version

```

**Resolution:** Both can be applied safely (semantic merge).

### Conflicting Value Updates

**Definition:** Multiple suggestions update the same key with different values.

**Example:**

```json
Suggestion 1: {"version": "1.1.0"}
Suggestion 2: {"version": "2.0.0"}

```

**Resolution:** Priority-based - user selection, security fix, syntax error, or regular.

## Detection Algorithm

The conflict detection process follows these steps:

### 1. Fingerprinting

Each change is assigned a unique fingerprint based on:

* File path
* Line range
* Content hash (normalized)

### 2. Overlap Detection

```python
def detect_overlap(change1, change2):
    # Check exact overlap
    if same_lines(change1, change2):
        return "exact"

    # Calculate overlap percentage
    overlap_percentage = calculate_overlap(change1, change2)

    if overlap_percentage >= 80:
        return "major"
    elif overlap_percentage >= 50:
        return "partial"
    elif overlap_percentage > 0:
        return "minor"

    return None  # No overlap

```

### 3. Semantic Analysis

```python
def is_semantic_duplicate(change1, change2):
    # Normalize whitespace
    norm1 = normalize_content(change1.content)
    norm2 = normalize_content(change2.content)

    # Exact match
    if norm1 == norm2:
        return True

    # Structured content comparison
    if is_structured(change1.content) and is_structured(change2.content):
        return compare_parsed_structures(change1.content, change2.content)

    return False

```

### 4. Conflict Grouping

Changes are grouped into conflicts by:

* File path (same file)
* Overlap detection (overlapping ranges)
* Semantic analysis (related content)

### 5. Severity Assessment

Each conflict is assigned a severity based on:

* Conflict type (exact > major > partial > minor > duplicate)
* Number of changes involved
* File type (configs vs. code)
* Presence of user selections

## Conflict Severity

### Critical

* Exact overlaps with user selections
* Security-related conflicts
* Syntax errors conflicting with fixes

### High

* Exact overlaps without resolution
* Major overlaps affecting functionality
* Breaking changes in critical files

### Medium

* Partial overlaps
* Configuration conflicts
* Comment/documentation conflicts

### Low

* Minor overlaps
* Semantic duplicates
* Formatting-only conflicts

## Examples

### Example 1: Exact Overlap

```python
# Suggestion 1 (Lines 10-12)
def calculate_total(items):
    return sum(items)

# Suggestion 2 (Lines 10-12)
def calculate_total(items):
    return sum(items) + tax(items)

```

**Type:** Exact overlap
**Severity:** High
**Resolution:** Priority-based (user selection wins)

### Example 2: Semantic Duplicate

```python
# Suggestion 1
result = { "status": "ok", "data": items }

# Suggestion 2
result = {
    "status": "ok",
    "data": items
}

```

**Type:** Semantic duplicate
**Severity:** Low
**Resolution:** Merge automatically

### Example 3: Major Overlap

```python
# Suggestion 1 (Lines 15-30)
for item in items:
    if item.valid:
        process(item)
    else:
        log_error(item)

# Suggestion 2 (Lines 18-28)
for item in items:
    if item.valid:
        process_optimized(item)

```

**Type:** Major overlap (>80%)
**Severity:** High
**Resolution:** Requires careful manual review or priority-based selection

### Example 4: Disjoint Keys (JSON)

```json
// Original
{
  "name": "app",
  "version": "1.0",
  "author": "dev"
}

// Suggestion 1
{
  "version": "2.0"
}

// Suggestion 2
{
  "author": "team"
}

```

**Type:** Disjoint keys
**Severity:** Low
**Resolution:** Both can be applied (semantic merge)

## Best Practices

1. **Review exact overlaps first** - These require manual intervention
2. **Trust user selections** - User-identified options take highest priority
3. **Merge semantic duplicates** - Safe to combine
4. **Be cautious with major overlaps** - May require code review
5. **Use dry-run** - Test resolutions before applying

## See Also

* [Resolution Strategies](resolution-strategies.md) - How conflicts are resolved
* [Configuration Reference](configuration.md) - Configure conflict handling
* [API Reference](api-reference.md) - Programmatic conflict detection
