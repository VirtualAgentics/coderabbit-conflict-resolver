# Parallel Processing Guide

The Review Bot Automator supports parallel processing to significantly speed up change application for large PRs. This guide explains how parallel processing works, when to use it, and how to optimize performance.

## Table of Contents

* [Overview](#overview)
* [How It Works](#how-it-works)
* [When to Use Parallel Processing](#when-to-use-parallel-processing)
* [Usage](#usage)
* [Configuration](#configuration)
* [Performance Optimization](#performance-optimization)
* [Architecture](#architecture)
* [Safety and Thread Safety](#safety-and-thread-safety)
* [Benchmarking](#benchmarking)
* [Use Cases](#use-cases)
* [Troubleshooting](#troubleshooting)
* [Best Practices](#best-practices)
* [Limitations](#limitations)

## Overview

Parallel processing enables the resolver to apply changes to multiple files concurrently, leveraging multiple CPU cores to dramatically reduce processing time for large PRs. Additionally, parallel comment parsing enables concurrent LLM processing of multiple comments, providing significant speedup for large PRs with many review comments.

### Key Features

**File-Level Parallelization:**

* **File-Level Parallelization**: Processes different files concurrently
* **Sequential Per-File Processing**: Changes to the same file applied sequentially (prevents race conditions)
* **Thread-Safe**: Uses locks and thread-safe collections
* **Configurable Workers**: Adjust worker count based on workload
* **Exception Handling**: Propagates exceptions from worker threads
* **Compatible with Rollback**: Works seamlessly with rollback system

**Comment Parsing Parallelization (LLM):**

* **Parallel Comment Parsing**: Processes multiple comments concurrently using ThreadPoolExecutor
* **Rate Limiting**: Prevents API throttling with configurable requests per second
* **Progress Tracking**: Real-time progress updates via Rich progress bar
* **Circuit Breaker Integration**: Automatically falls back to sequential when circuit breaker is open
* **Partial Failure Handling**: Individual comment failures don't stop other comments
* **Order Preservation**: Results returned in same order as input comments

### Performance Improvements

Parallel processing provides significant speedup for large PRs:

| PR Size | Sequential | Parallel (4 workers) | Parallel (8 workers) | Speedup |
| --------- | ----------- | --------------------- | --------------------- | --------- |
| 10 files | 5s | 4s | 4s | 1.25x |
| 30 files | 15s | 5s | 4s | 3.75x |
| 100 files | 50s | 15s | 10s | 5x |
| 300 files | 150s | 40s | 22s | 6.8x |

**Note**: Actual performance depends on system resources, file sizes, and change complexity.

### Parallel Comment Parsing Performance

Parallel comment parsing provides significant speedup for large PRs with many review comments:

| Comment Count | Sequential | Parallel (4 workers) | Speedup |
| ------------- | ---------- | -------------------- | ------- |
| 5 comments    | 10s        | 10s                  | 1.0x    |
| 10 comments   | 20s        | 6s                   | 3.3x    |
| 20 comments   | 40s        | 12s                  | 3.3x    |
| 50 comments   | 100s       | 25s                  | 4.0x    |

**Note**: Parallel comment parsing requires LLM parsing to be enabled and is only used for PRs with 5+ comments. Rate limiting prevents API throttling but may reduce speedup for very high comment counts.

## How It Works

### Parallel Comment Parsing (LLM)

When LLM parsing is enabled and parallel comment parsing is configured, the system processes multiple comments concurrently:

**Flag Relationship:** The `--llm` flag alone enables LLM comment parsing in sequential mode (default). The `--llm-parallel-parsing` flag is an opt-in modifier that requires `--llm` to be set and switches parsing to parallel mode; it will be ignored if `--llm` is not provided. For future simplification, consider consolidating to a single `--llm` flag with `--llm-mode {sequential|parallel}`.

1. **Check Circuit Breaker**: Verify circuit breaker is not open (falls back to sequential if open)
2. **Create Worker Pool**: ThreadPoolExecutor with configurable workers (default: 4)
3. **Submit Comment Tasks**: Each comment submitted as separate task
4. **Apply Rate Limiting**: Rate limiter ensures requests don't exceed API limits
5. **Process Comments in Parallel**: Multiple comments parsed concurrently
6. **Collect Results**: Results collected in completion order, then reordered to match input
7. **Handle Failures**: Individual comment failures don't stop other comments

**Rate Limiting:**

* Configurable requests per second (default: 10.0 req/s)
* Thread-safe rate limiter prevents API throttling
* Sleeps between requests to maintain rate limit

**Progress Tracking:**

* Real-time progress updates via callback
* Rich progress bar in CLI shows completion status
* Thread-safe progress counter

### File-Level Parallelization

The parallel processing system uses a **file-level parallelization** model:

1. **Group Changes by File**: All changes are grouped by file path
2. **Create Worker Pool**: ThreadPoolExecutor with configurable workers
3. **Submit File Tasks**: Each file's changes submitted as one task
4. **Process Files in Parallel**: Different files processed concurrently
5. **Process Changes Sequentially**: Changes to same file applied in order
6. **Collect Results**: Thread-safe accumulation of applied/skipped/failed changes

### Why File-Level Parallelization?

**Prevents Race Conditions:**

* Multiple concurrent modifications to same file would cause conflicts
* Sequential processing per file ensures consistency
* Different files are independent, safe to process concurrently

**Maintains Change Order:**

* Changes to same file applied in original order
* Dependencies between changes in same file preserved
* No risk of out-of-order application

### Thread Safety Mechanisms

1. **Thread-Safe Collections**: Separate locks for applied, skipped, failed lists
2. **File Grouping**: No concurrent access to same file
3. **Exception Propagation**: Worker thread exceptions caught and reported
4. **Future Tracking**: Maps futures to changes for proper error attribution

## When to Use Parallel Processing

### Enable Parallel Processing

✅ **Large PRs (30+ files)**

* Significant speedup from concurrent file processing
* Worker overhead amortized over many files

✅ **Independent File Changes**

* Changes don't depend on each other across files
* No cross-file dependencies

✅ **I/O-Bound Workloads**

* File reading/writing dominates processing time
* Multiple threads reduce I/O wait time

✅ **Time-Critical Resolutions**

* Need to apply changes quickly
* Willing to trade resource usage for speed

✅ **Sufficient System Resources**

* 4+ CPU cores available
* Adequate memory for worker threads

### Disable Parallel Processing

❌ **Small PRs (< 10 files)**

* Worker overhead exceeds benefits
* Sequential processing is faster

❌ **Dependent Changes Across Files**

* Changes in one file depend on changes in another
* Sequential processing ensures correct order

❌ **Debugging Sessions**

* Sequential execution easier to trace
* Logging order is clearer

❌ **Limited System Resources**

* System has < 4 CPU cores
* Memory constrained environment

❌ **Single-File PRs**

* All changes to one file (no parallelization possible)
* Sequential processing required

## Usage

### CLI Usage

#### Enable Parallel File Processing

```bash
# Enable with default 4 workers
pr-resolve apply --pr 123 --owner myorg --repo myrepo --parallel

# Enable with custom worker count
pr-resolve apply --pr 123 --owner myorg --repo myrepo --parallel --max-workers 8

# Enable with other options
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --mode conflicts-only \
  --parallel \
  --max-workers 16 \
  --rollback \
  --validation

```

#### Enable Parallel Comment Parsing (LLM)

```bash
# Enable parallel comment parsing with LLM
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --llm \
  --llm-parallel-parsing \
  --llm-parallel-workers 4 \
  --llm-rate-limit 10.0

# Enable with custom rate limit (for high-volume APIs)
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --llm \
  --llm-parallel-parsing \
  --llm-parallel-workers 8 \
  --llm-rate-limit 20.0

# Combine with file-level parallel processing
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --parallel --max-workers 8 \
  --llm --llm-parallel-parsing --llm-parallel-workers 4

```

#### Disable Parallel Processing (Default)

```bash
# Parallel disabled by default
pr-resolve apply --pr 123 --owner myorg --repo myrepo

# Can explicitly specify sequential (not necessary)
pr-resolve apply --pr 123 --owner myorg --repo myrepo --max-workers 1

```

### Environment Variables

```bash
# Enable parallel file processing
export CR_PARALLEL="true"
export CR_MAX_WORKERS="8"

# Enable parallel comment parsing (LLM)
export CR_LLM_ENABLED="true"
export CR_LLM_PARALLEL_PARSING="true"
export CR_LLM_PARALLEL_WORKERS="4"
export CR_LLM_RATE_LIMIT="10.0"

pr-resolve apply --pr 123 --owner myorg --repo myrepo

```

### Configuration File

**YAML:**

```yaml
# config.yaml
parallel:
  enabled: true
  max_workers: 8

llm:
  enabled: true
  parallel_parsing: true
  parallel_max_workers: 4
  rate_limit: 10.0

```

**TOML:**

```toml
# config.toml
[parallel]
enabled = true
max_workers = 8

[llm]
enabled = true
parallel_parsing = true
parallel_max_workers = 4
rate_limit = 10.0

```

```bash
pr-resolve apply --pr 123 --owner myorg --repo myrepo --config config.yaml

```

### Python API

#### Using ConflictResolver

```python
from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig

# Initialize resolver
resolver = ConflictResolver(config=PresetConfig.BALANCED)

# Apply with parallel processing
results = resolver.resolve_pr_conflicts(
    owner="myorg",
    repo="myrepo",
    pr_number=123,
    parallel=True,      # Enable parallel processing
    max_workers=8       # 8 worker threads
)

print(f"Applied: {results.applied_count} changes")
print(f"Time: {results.elapsed_time:.2f}s")

```

#### Using apply_changes Directly

```python
from review_bot_automator import ConflictResolver

resolver = ConflictResolver()

# Apply changes with parallel processing
applied, skipped, failed = resolver.apply_changes(
    changes=my_changes,
    validate=True,
    parallel=True,
    max_workers=8
)

print(f"Applied: {len(applied)}")
print(f"Skipped: {len(skipped)}")
print(f"Failed: {len(failed)}")

```

## Configuration

### Configuration Precedence

Configuration sources (highest to lowest priority):

1. **CLI flags** (`--parallel --max-workers N`)
2. **Environment variables** (`CR_PARALLEL`, `CR_MAX_WORKERS`)
3. **Configuration file** (`parallel.enabled`, `parallel.max_workers`)
4. **Defaults** (parallel disabled, 4 workers)

### Configuration Options

**File Processing:**

| Option | Type | CLI | Environment | Config File | Default |
| -------- | ------ | ----- | ------------- | ------------- | --------- |
| Enable | boolean | `--parallel` | `CR_PARALLEL` | `parallel.enabled` | `false` |
| Workers | integer | `--max-workers N` | `CR_MAX_WORKERS` | `parallel.max_workers` | `4` |

**Comment Parsing (LLM):**

| Option | Type | CLI | Environment | Config File | Default |
| -------- | ------ | ----- | ------------- | ------------- | --------- |
| Enable | boolean | `--llm-parallel-parsing` | `CR_LLM_PARALLEL_PARSING` | `llm.parallel_parsing` | `false` |
| Workers | integer | `--llm-parallel-workers N` | `CR_LLM_PARALLEL_WORKERS` | `llm.parallel_max_workers` | `4` |
| Rate Limit | float | `--llm-rate-limit N` | `CR_LLM_RATE_LIMIT` | `llm.rate_limit` | `10.0` |

### Worker Count Guidelines

#### By PR Size

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

#### By CPU Cores

```bash
# Conservative: Match CPU core count
WORKERS=$(nproc)
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers $WORKERS

# Aggressive: 2x CPU cores (for I/O-bound workloads)
WORKERS=$(($(nproc) * 2))
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers $WORKERS

# Maximum: 4x CPU cores (only for very large PRs with heavy I/O)
WORKERS=$(($(nproc) * 4))
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers $WORKERS

```

### Configuration Examples

#### Example 1: Development Environment

```yaml
# dev-config.yaml - Optimize for debugging
mode: all
parallel:
  enabled: false  # Disable for easier debugging
rollback:
  enabled: true
logging:
  level: DEBUG

```

#### Example 2: Production Environment

```yaml
# prod-config.yaml - Balance speed and safety
mode: conflicts-only
parallel:
  enabled: true
  max_workers: 8  # Moderate parallelism
rollback:
  enabled: true   # Always enable safety
validation:
  enabled: true
logging:
  level: INFO

```

#### Example 3: High-Performance Environment

```yaml
# perf-config.yaml - Maximum speed
mode: all
parallel:
  enabled: true
  max_workers: 32  # High parallelism
rollback:
  enabled: true    # Keep safety enabled
validation:
  enabled: false   # Disable for speed
logging:
  level: WARNING   # Minimal logging overhead

```

## Performance Optimization

### Optimal Worker Count

The optimal worker count depends on several factors:

#### System Resources

```bash
# Check CPU core count
nproc

# Check available memory (ensure ~100MB per worker)
free -h

# Recommended formula for I/O-bound work
WORKERS=$(($(nproc) * 2))

```

#### PR Characteristics

| PR Characteristic | Recommended Workers | Rationale |
| ------------------ | ------------------- | ----------- |
| 10-30 small files | 2-4 | Low parallelization benefit |
| 30-100 medium files | 4-8 | Good parallelization benefit |
| 100-300 large files | 8-16 | High parallelization benefit |
| 300+ files | 16-32 | Maximum parallelization |
| Files with conflicts | Reduce by 25% | Conflict resolution overhead |
| Large files (1MB+) | Reduce by 50% | I/O becomes bottleneck |

### Benchmarking Your Configuration

Test different worker counts to find optimal performance:

```bash
#!/bin/bash
# benchmark.sh - Test different worker counts

PR_NUMBER=123
OWNER=myorg
REPO=myrepo

echo "Benchmarking parallel processing..."
echo "PR: #$PR_NUMBER"
echo "=================================="

for workers in 1 2 4 8 16 32; do
    echo -n "Workers: $workers ... "

    # Run with time measurement
    START=$(date +%s)
    pr-resolve apply --pr $PR_NUMBER --owner $OWNER --repo $REPO \
        --mode dry-run \
        --parallel \
        --max-workers $workers \
        --log-level WARNING \
        > /dev/null 2>&1
    END=$(date +%s)

    DURATION=$((END - START))
    echo "${DURATION}s"
done

echo "=================================="
echo "Choose the worker count with lowest duration"

```

### Performance Tips

#### 1. Match Workers to Workload

```bash
# Count files in PR first
FILE_COUNT=$(gh pr view 123 --json files --jq '.files | length')

# Choose workers based on file count
if [ $FILE_COUNT -lt 30 ]; then
    WORKERS=4
elif [ $FILE_COUNT -lt 100 ]; then
    WORKERS=8
else
    WORKERS=16
fi

pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers $WORKERS

```

#### 2. Disable Validation for Performance

```bash
# Validation adds overhead per change
# Use rollback for safety instead
pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel --max-workers 16 \
  --no-validation \  # Disable validation
  --rollback         # Use rollback for safety

```

#### 3. Reduce Logging Overhead

```bash
# Debug logging significantly impacts performance
pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel --max-workers 16 \
  --log-level WARNING  # Minimal logging

```

#### 4. Use Staged Application

```bash
# Stage 1: Non-conflicts in parallel (fastest)
pr-resolve apply --pr 123 --owner org --repo repo \
  --mode non-conflicts-only \
  --parallel --max-workers 16 \
  --no-validation

# Stage 2: Conflicts sequentially (more careful)
pr-resolve apply --pr 123 --owner org --repo repo \
  --mode conflicts-only \
  --validation

```

### Performance Monitoring

Monitor system resources during execution:

```bash
# Terminal 1: Run resolver
pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel --max-workers 16

# Terminal 2: Monitor resources
watch -n 1 'ps aux | grep pr-resolve | grep -v grep'

# Or use htop for real-time CPU/memory monitoring
htop -p $(pgrep pr-resolve)

```

## Architecture

### Component Overview

```text
┌────────────────────────────────────────────────────────────┐
│              ConflictResolver                              │
│                                                            │
│  resolve_pr_conflicts(parallel=True, max_workers=8)       │
│                        │                                    │
│                        ▼                                    │
│  apply_changes(parallel=True, max_workers=8)              │
│                        │                                    │
│                        ▼                                    │
│  _apply_changes_parallel(changes, validate, max_workers)  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 1. Group Changes by File Path                        │ │
│  │    changes_by_file[path] = [change1, change2, ...]   │ │
│  └──────────────────────────────────────────────────────┘ │
│                        │                                    │
│                        ▼                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 2. Create Thread Pool                                │ │
│  │    ThreadPoolExecutor(max_workers=8)                 │ │
│  └──────────────────────────────────────────────────────┘ │
│                        │                                    │
│                        ▼                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 3. Submit Tasks (one per file)                       │ │
│  │    future = executor.submit(process_file_changes)    │ │
│  │    future_to_changes[future] = file_changes          │ │
│  └──────────────────────────────────────────────────────┘ │
│                        │                                    │
│          ┌─────────────┴─────────────┐                     │
│          ▼                           ▼                     │
│   ┌────────────┐             ┌────────────┐               │
│   │  Worker 1  │             │  Worker 2  │    ...        │
│   │  File A    │             │  File B    │               │
│   │  ┌──────┐  │             │  ┌──────┐  │               │
│   │  │Change│  │             │  │Change│  │               │
│   │  │  1   │  │             │  │  1   │  │               │
│   │  ├──────┤  │             │  ├──────┤  │               │
│   │  │Change│  │             │  │Change│  │               │
│   │  │  2   │  │             │  │  2   │  │               │
│   │  └──────┘  │             │  └──────┘  │               │
│   └────────────┘             └────────────┘               │
│          │                           │                     │
│          └─────────────┬─────────────┘                     │
│                        ▼                                    │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 4. Collect Results (Thread-Safe)                     │ │
│  │    applied (with lock)                                │ │
│  │    skipped (with lock)                                │ │
│  │    failed (with lock)                                 │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘

```

### Thread Pool Architecture

```python
# Simplified implementation
def _apply_changes_parallel(changes, validate, max_workers):
    # 1. Group changes by file
    changes_by_file = group_by_file(changes)

    # 2. Thread-safe result collections
    applied_lock = threading.Lock()
    applied = []
    # ... similar for skipped, failed

    # 3. Worker function
    def process_file_changes(file_changes):
        for change in file_changes:
            # Apply change sequentially within file
            success = apply_change(change)
            if success:
                with applied_lock:
                    applied.append(change)

    # 4. Execute in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit one task per file
        future_to_changes = {}
        for file_changes in changes_by_file.values():
            future = executor.submit(process_file_changes, file_changes)
            future_to_changes[future] = file_changes

        # Wait for completion and handle exceptions
        for future in as_completed(future_to_changes):
            try:
                future.result()  # Propagate exceptions
            except Exception as e:
                # Handle worker thread exception
                affected_changes = future_to_changes[future]
                mark_as_failed(affected_changes, str(e))

    return applied, skipped, failed

```

### Data Flow

```text
Input: List[Change]
    │
    ▼
Group by File: Dict[str, List[Change]]
    │
    ├─ File A: [Change1, Change2, Change3]
    ├─ File B: [Change4, Change5]
    └─ File C: [Change6]
    │
    ▼
ThreadPoolExecutor
    │
    ├─ Worker 1 → Process File A → [Applied, Skipped, Failed]
    ├─ Worker 2 → Process File B → [Applied, Skipped, Failed]
    └─ Worker 3 → Process File C → [Applied, Skipped, Failed]
    │
    ▼
Thread-Safe Accumulation
    │
    ├─ applied: [Change1, Change2, Change4, Change5, Change6]
    ├─ skipped: [Change3]
    └─ failed: []
    │
    ▼
Output: Tuple[List[Change], List[Change], List[Tuple[Change, str]]]

```

## Safety and Thread Safety

### Thread Safety Mechanisms

#### 1. File-Level Serialization

**Problem**: Concurrent modifications to same file cause conflicts

**Solution**: Group changes by file, process each file sequentially

```python
# Group changes by file path
changes_by_file = defaultdict(list)
for change in changes:
    changes_by_file[change.path].append(change)

# Each file processed by one worker only
for file_changes in changes_by_file.values():
    executor.submit(process_file_changes, file_changes)

```

#### 2. Thread-Safe Collections

**Problem**: Multiple threads appending to same list causes race conditions

**Solution**: Use locks for all shared collections

```python
# Separate locks for each collection
applied_lock = threading.Lock()
skipped_lock = threading.Lock()
failed_lock = threading.Lock()

# Thread-safe append
def add_applied(change):
    with applied_lock:
        applied.append(change)

```

#### 3. Exception Propagation

**Problem**: Worker thread exceptions silently fail

**Solution**: Track futures, call `.result()` to propagate exceptions

```python
# Map futures to changes for error attribution
future_to_changes = {}
for file_changes in changes_by_file.values():
    future = executor.submit(process_file, file_changes)
    future_to_changes[future] = file_changes

# Propagate exceptions from workers
for future in as_completed(future_to_changes):
    try:
        future.result()  # Raises if worker had exception
    except Exception as e:
        affected_changes = future_to_changes[future]
        mark_as_failed(affected_changes, str(e))

```

### Compatibility with Rollback

Parallel processing works seamlessly with the rollback system:

```bash
# Parallel processing with rollback protection
pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel --max-workers 8 \
  --rollback

# If any worker thread fails
# 1. Exception propagated to main thread
# 2. Rollback system triggers
# 3. All changes rolled back (both sequential and parallel)
# 4. Working directory restored to checkpoint

```

**How it works:**

1. Checkpoint created before any worker starts
2. Workers apply changes concurrently
3. If any worker fails, exception propagated
4. Rollback system catches exception
5. All changes (from all workers) rolled back

### Data Integrity

**Guaranteed:**

* ✅ No concurrent modifications to same file
* ✅ Changes to same file applied in order
* ✅ Thread-safe result accumulation
* ✅ Exception propagation from workers
* ✅ Compatible with rollback

**Not Guaranteed:**

* ❌ Result order (changes accumulated in completion order, not input order)
* ❌ Logging order (log messages may be interleaved)
* ❌ Cross-file dependencies (files processed independently)

## Benchmarking

### Simple Benchmark

```bash
#!/bin/bash
# simple-benchmark.sh

PR=123
OWNER=myorg
REPO=myrepo

echo "Sequential processing:"
time pr-resolve apply --pr $PR --owner $OWNER --repo $REPO --mode dry-run

echo "Parallel processing (4 workers):"
time pr-resolve apply --pr $PR --owner $OWNER --repo $REPO --mode dry-run --parallel --max-workers 4

echo "Parallel processing (8 workers):"
time pr-resolve apply --pr $PR --owner $OWNER --repo $REPO --mode dry-run --parallel --max-workers 8

```

### Comprehensive Benchmark

```bash
#!/bin/bash
# comprehensive-benchmark.sh

PR=123
OWNER=myorg
REPO=myrepo
RESULTS_FILE="benchmark-results.csv"

echo "workers,duration_seconds,files_processed" > $RESULTS_FILE

for workers in 1 2 4 8 16 32; do
    echo "Testing with $workers workers..."

    START=$(date +%s.%N)
    OUTPUT=$(pr-resolve apply --pr $PR --owner $OWNER --repo $REPO \
        --mode dry-run \
        --parallel \
        --max-workers $workers \
        --log-level WARNING 2>&1)
    END=$(date +%s.%N)

    DURATION=$(echo "$END - $START" | bc)
    FILES=$(echo "$OUTPUT" | grep -c "Applied change")

    echo "$workers,$DURATION,$FILES" >> $RESULTS_FILE
    echo "  Duration: ${DURATION}s, Files: $FILES"
done

echo "Results saved to $RESULTS_FILE"

# Plot results (requires gnuplot)
gnuplot <<EOF
set terminal png size 800,600
set output 'benchmark-results.png'
set xlabel 'Worker Count'
set ylabel 'Duration (seconds)'
set title 'Parallel Processing Performance'
set grid
plot '$RESULTS_FILE' using 1:2 with linespoints title 'Duration'
EOF

echo "Chart saved to benchmark-results.png"

```

### Analyzing Results

```python
#!/usr/bin/env python3
# analyze-benchmark.py

import pandas as pd
import matplotlib.pyplot as plt

# Load results
df = pd.read_csv('benchmark-results.csv')

# Calculate speedup
baseline = df[df['workers'] == 1]['duration_seconds'].values[0]
df['speedup'] = baseline / df['duration_seconds']

# Calculate efficiency
df['efficiency'] = df['speedup'] / df['workers'] * 100

# Print summary
print("Benchmark Summary:")
print(df[['workers', 'duration_seconds', 'speedup', 'efficiency']])

# Find optimal worker count
optimal = df.loc[df['efficiency'].idxmax()]
print(f"\nOptimal configuration:")
print(f"  Workers: {optimal['workers']}")
print(f"  Duration: {optimal['duration_seconds']:.2f}s")
print(f"  Speedup: {optimal['speedup']:.2f}x")
print(f"  Efficiency: {optimal['efficiency']:.1f}%")

# Plot
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# Duration plot
ax1.plot(df['workers'], df['duration_seconds'], 'o-')
ax1.set_xlabel('Worker Count')
ax1.set_ylabel('Duration (seconds)')
ax1.set_title('Processing Duration')
ax1.grid(True)

# Speedup plot
ax2.plot(df['workers'], df['speedup'], 'o-', label='Actual')
ax2.plot(df['workers'], df['workers'], '--', label='Ideal')
ax2.set_xlabel('Worker Count')
ax2.set_ylabel('Speedup')
ax2.set_title('Parallel Speedup')
ax2.legend()
ax2.grid(True)

plt.tight_layout()
plt.savefig('benchmark-analysis.png')
print("\nAnalysis chart saved to benchmark-analysis.png")

```

## Use Cases

### Use Case 1: Large PR in Production

**Scenario**: Applying 150 changes from large PR to production

```bash
# Benchmark first to find optimal worker count
./benchmark.sh  # Find optimal: 16 workers

# Apply with optimal configuration
pr-resolve apply --pr 456 --owner myorg --repo production \
  --mode conflicts-only \
  --parallel --max-workers 16 \
  --rollback \
  --validation \
  --log-level INFO \
  --log-file /var/log/pr-resolver/prod-$(date +%Y%m%d-%H%M%S).log

# Result: 150 changes applied in 22s (vs 150s sequential)
# Speedup: 6.8x faster

```

### Use Case 2: CI/CD Pipeline Optimization

**Scenario**: Automated PR resolution in CI/CD needs to be fast

```yaml
# .github/workflows/auto-resolve.yml
* name: Resolve PR Conflicts
  run: |
    # Enable parallel processing for speed
    export CR_PARALLEL="true"
    export CR_MAX_WORKERS="8"

    # Apply with parallel processing
    pr-resolve apply \
      --pr ${{ github.event.pull_request.number }} \
      --owner ${{ github.repository_owner }} \
      --repo ${{ github.event.repository.name }} \
      --mode conflicts-only \
      --parallel --max-workers 8 \
      --rollback \
      --log-file /tmp/pr-resolve.log
  timeout-minutes: 5  # Reduced from 15 with parallel processing

```

### Use Case 3: Staged Application

**Scenario**: Apply large PR in stages, optimize each stage

```bash
# Stage 1: Non-conflicts (safe, fast, high parallelism)
pr-resolve apply --pr 789 --owner myorg --repo myrepo \
  --mode non-conflicts-only \
  --parallel --max-workers 32 \
  --no-validation \
  --log-level WARNING

# Stage 2: Conflicts (risky, careful, moderate parallelism)
pr-resolve apply --pr 789 --owner myorg --repo myrepo \
  --mode conflicts-only \
  --parallel --max-workers 8 \
  --validation \
  --rollback \
  --log-level INFO

```

### Use Case 4: Development Workflow

**Scenario**: Developer testing changes locally, wants fast feedback

```bash
# Development: Disable parallel for easier debugging
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --mode dry-run \
  --log-level DEBUG

# Production: Enable parallel for speed
pr-resolve apply --pr 123 --owner myorg --repo myrepo \
  --parallel --max-workers 8 \
  --rollback

```

### Use Case 5: Dynamic Worker Scaling

**Scenario**: Automatically adjust workers based on PR size

```python
#!/usr/bin/env python3
# smart-apply.py

import subprocess
import sys

def get_pr_file_count(owner, repo, pr_number):
    """Get number of files changed in PR."""
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number),
         "--repo", f"{owner}/{repo}",
         "--json", "files", "--jq", ".files | length"],
        capture_output=True, text=True, check=True
    )
    return int(result.stdout.strip())

def determine_workers(file_count):
    """Determine optimal worker count based on file count."""
    if file_count < 10:
        return 1  # Sequential
    elif file_count < 30:
        return 4
    elif file_count < 100:
        return 8
    elif file_count < 300:
        return 16
    else:
        return 32

def main():
    owner, repo, pr = sys.argv[1:4]

    # Get PR size
    file_count = get_pr_file_count(owner, repo, pr)
    print(f"PR has {file_count} files")

    # Determine workers
    workers = determine_workers(file_count)
    print(f"Using {workers} workers")

    # Build command
    cmd = [
        "pr-resolve", "apply",
        "--pr", pr,
        "--owner", owner,
        "--repo", repo,
        "--rollback"
    ]

    if workers > 1:
        cmd.extend(["--parallel", "--max-workers", str(workers)])

    # Execute
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()

```

Usage:

```bash
./smart-apply.py myorg myrepo 123
# Automatically uses optimal worker count

```

## Troubleshooting

### Issue 1: Parallel Processing Slower Than Sequential

**Symptoms:**

* `--parallel` is slower than without it
* High worker overhead
* No performance improvement

**Causes:**

* Too many workers for small PR
* Worker overhead exceeds benefits
* I/O contention on slow disk

**Solutions:**

```bash
# 1. Reduce worker count
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 2

# 2. Disable parallel for small PRs
FILE_COUNT=$(gh pr view 123 --json files --jq '.files | length')
if [ $FILE_COUNT -lt 30 ]; then
    pr-resolve apply --pr 123 --owner org --repo repo  # No parallel
else
    pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 8
fi

# 3. Benchmark to find optimal worker count
./benchmark.sh  # Test 1, 2, 4, 8, 16, 32 workers

```

### Issue 2: Worker Thread Exceptions

**Symptoms:**

* Error: "Worker thread exception"
* Changes marked as failed
* Unexpected failures

**Causes:**

* Exception in worker thread
* File access issues
* Memory constraints

**Solutions:**

```bash
# 1. Check logs for details
pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel --max-workers 8 \
  --log-level DEBUG \
  --log-file /tmp/worker-errors.log

grep -i "worker\|exception" /tmp/worker-errors.log

# 2. Reduce worker count
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 4

# 3. Disable parallel temporarily
pr-resolve apply --pr 123 --owner org --repo repo

# 4. Check system resources
free -h  # Check memory
df -h    # Check disk space

```

### Issue 3: High Memory Usage

**Symptoms:**

* System slowdown
* High memory consumption
* Out of memory errors

**Causes:**

* Too many workers
* Large files loaded into memory
* Memory leak (report as bug)

**Solutions:**

```bash
# 1. Reduce worker count
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 4

# 2. Monitor memory usage
watch -n 1 'ps aux | grep pr-resolve'

# 3. Check memory per worker
# Rule of thumb: ~100MB per worker
AVAILABLE_MB=$(free -m | awk 'NR==2 {print $7}')
MAX_WORKERS=$((AVAILABLE_MB / 100))
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers $MAX_WORKERS

```

### Issue 4: Logging Order Confusion

**Symptoms:**

* Log messages interleaved
* Difficult to trace execution
* Unclear failure source

**Causes:**

* Multiple worker threads logging concurrently
* No log ordering guarantee with parallel processing

**Solutions:**

```bash
# 1. Use timestamps in logs
pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel --max-workers 8 \
  --log-level INFO | ts '[%Y-%m-%d %H:%M:%.S]'

# 2. Disable parallel for debugging
pr-resolve apply --pr 123 --owner org --repo repo --log-level DEBUG

# 3. Filter logs by file
pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel --max-workers 8 \
  --log-file /tmp/parallel.log

grep "file_path.py" /tmp/parallel.log

```

### Issue 5: No Speedup on Multi-Core System

**Symptoms:**

* Have 8 CPU cores
* No speedup with `--parallel`
* All workers run on one core

**Causes:**

* Python GIL (Global Interpreter Lock) for CPU-bound work
* File I/O not concurrent
* Disk bottleneck

**Solutions:**

```bash
# 1. Verify I/O-bound workload
# Parallel helps only for I/O-bound work (file operations)
# Not for CPU-bound work (heavy computation)

# 2. Check CPU usage
htop  # Should see multiple cores utilized

# 3. Check disk I/O
iostat -x 1  # Should see disk activity

# 4. If truly CPU-bound, parallel won't help
# Example: Complex conflict resolution algorithms
# Consider sequential processing instead

```

## Best Practices

### 1. Benchmark Before Production Use

```bash
# Always benchmark to find optimal worker count
./benchmark.sh > benchmark-$(date +%Y%m%d).txt

# Use results to configure production

```

### 2. Match Workers to Workload

```bash
# Small PRs: Sequential or 2-4 workers
# Medium PRs: 4-8 workers
# Large PRs: 8-16 workers
# Very large PRs: 16-32 workers

```

### 3. Combine with Rollback for Safety

```bash
# Always enable rollback with parallel processing
pr-resolve apply --pr 123 --owner org --repo repo \
  --parallel --max-workers 8 \
  --rollback  # Safety net for worker failures

```

### 4. Monitor System Resources

```bash
# Check resources before running
free -h  # Memory
df -h    # Disk
nproc    # CPU cores

# Monitor during execution
htop -p $(pgrep pr-resolve)

```

### 5. Use Staged Application for Large PRs

```bash
# Stage 1: Non-conflicts (high parallelism)
pr-resolve apply --pr 123 --owner org --repo repo \
  --mode non-conflicts-only \
  --parallel --max-workers 16

# Stage 2: Conflicts (moderate parallelism)
pr-resolve apply --pr 123 --owner org --repo repo \
  --mode conflicts-only \
  --parallel --max-workers 8

```

### 6. Disable Parallel for Debugging

```bash
# Development: Sequential for easier debugging
pr-resolve apply --pr 123 --owner org --repo repo --log-level DEBUG

# Production: Parallel for speed
pr-resolve apply --pr 123 --owner org --repo repo --parallel --max-workers 8

```

### 7. Configure Per Environment

```yaml
# dev-config.yaml
parallel:
  enabled: false  # Easier debugging

# prod-config.yaml
parallel:
  enabled: true
  max_workers: 16  # Optimized for performance

```

## Limitations

### 1. No Cross-File Dependency Handling

**Limitation**: Changes in different files processed independently

**Impact**: If changes in File A depend on changes in File B, may apply in wrong order

**Workaround**: Disable parallel processing for PRs with cross-file dependencies

### 2. Result Ordering Not Preserved

**Limitation**: Results accumulated in completion order, not input order

**Impact**: Applied changes list may be in different order than input

**Note**: This doesn't affect correctness, only result order

### 3. Logging Order Not Guaranteed

**Limitation**: Log messages from different workers may interleave

**Impact**: Logs harder to read with parallel processing

**Workaround**: Use timestamps or disable parallel for debugging

### 4. Python GIL Limits CPU-Bound Parallelism

**Limitation**: Python's Global Interpreter Lock prevents true CPU parallelism

**Impact**: Only I/O-bound work benefits from parallel processing

**Note**: File operations are I/O-bound, so parallel processing still helps significantly

### 5. Memory Usage Scales with Workers

**Limitation**: Each worker consumes memory (~100MB per worker)

**Impact**: High worker counts may exhaust memory on constrained systems

**Solution**: Adjust worker count based on available memory

### 6. Overhead for Small PRs

**Limitation**: Thread pool creation and management adds overhead

**Impact**: Parallel processing slower than sequential for small PRs (< 10 files)

**Solution**: Disable parallel processing for small PRs

### 7. No Dynamic Worker Scaling

**Limitation**: Worker count fixed at start, doesn't adapt during execution

**Impact**: Can't optimize worker count for varying file sizes within PR

**Solution**: Choose worker count based on PR size estimation

## See Also

* [Configuration Reference](configuration.md) - Parallel processing configuration
* [Rollback System](rollback-system.md) - Combining rollback with parallel processing
* [Getting Started](getting-started.md) - Basic parallel processing usage
* [API Reference](api-reference.md) - Python API for parallel processing
* [Troubleshooting](troubleshooting.md) - General troubleshooting guide
