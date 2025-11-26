# Rollback System

The Review Bot Automator includes a robust, git-based rollback system that provides automatic recovery when things go wrong. This document explains how the rollback system works, how to use it, and how to troubleshoot issues.

## Table of Contents

* [Overview](#overview)
* [How It Works](#how-it-works)
* [Usage](#usage)
  * [CLI Usage](#cli-usage)
  * [Python API Usage](#python-api-usage)
  * [Context Manager Pattern](#context-manager-pattern)
* [Configuration](#configuration)
* [Architecture](#architecture)
* [Safety Features](#safety-features)
* [Use Cases](#use-cases)
* [Troubleshooting](#troubleshooting)
* [Best Practices](#best-practices)
* [Limitations](#limitations)

## Overview

The rollback system provides **automatic recovery** from failures during change application. When enabled (default), it creates a checkpoint before applying changes and automatically restores the previous state if any error occurs.

### Key Features

* **Git-based Checkpointing**: Uses `git stash` for reliable state capture
* **Automatic Recovery**: Rolls back on any exception during application
* **Tracked and Untracked Files**: Preserves both tracked changes and untracked files
* **Context Manager Support**: Pythonic API with automatic cleanup
* **Configurable**: Enable/disable per execution
* **Safe Defaults**: Enabled by default for maximum safety

### When to Use Rollback

**Always Enable (Default):**

* Production environments
* Critical systems
* Unfamiliar PRs
* Large PRs with many changes
* When validation is disabled

**Consider Disabling:**

* When you have external backup systems
* Testing environments with disposable state
* When performance is absolutely critical
* You want to manually inspect failed state

## How It Works

The rollback system operates in three phases:

### Phase 1: Checkpoint Creation

Before applying any changes, the system:

1. **Checks for uncommitted changes** in the working directory
2. **Creates a git stash** using `git stash push --include-untracked`
   * Captures all tracked modifications
   * Captures untracked files (new files not in .gitignore)
   * Does NOT capture ignored files (respects .gitignore)
3. **Immediately reapplies changes** using `git stash apply`
   * Restores working directory to original state
   * Keeps stash reference for potential rollback
4. **Stores checkpoint ID** (`stash@{0}`) for later use

**Result**: Working directory unchanged, but state saved for rollback

### Phase 2: Change Application

The resolver applies changes with the checkpoint in place:

1. **Applies resolved changes** to files
2. **Monitors for exceptions** during application
3. **Tracks success/failure** of each change

### Phase 3: Commit or Rollback

After change application completes:

#### On Success (Commit)

1. **Drops the git stash** using `git stash drop stash@{0}`
2. **Clears checkpoint reference**
3. **Keeps all applied changes**

#### On Failure (Rollback)

1. **Resets working directory** using `git reset --hard HEAD`
2. **Removes untracked files** using `git clean -fd`
3. **Applies checkpoint state** using `git stash apply stash@{0}`
4. **Drops the stash** after successful rollback
5. **Clears checkpoint reference**

**Result**: Working directory restored to pre-application state

## Usage

### CLI Usage

The rollback system is controlled via the `--rollback` / `--no-rollback` flags.

#### Enable Rollback (Default)

```bash
# Rollback enabled by default
pr-resolve apply --pr 123 --owner myorg --repo myrepo

# Explicitly enable rollback
pr-resolve apply --pr 123 --owner myorg --repo myrepo --rollback

```

#### Disable Rollback

```bash
# Disable rollback (not recommended for production)
pr-resolve apply --pr 123 --owner myorg --repo myrepo --no-rollback

```

#### Environment Variable

```bash
# Enable via environment variable
export CR_ENABLE_ROLLBACK="true"
pr-resolve apply --pr 123 --owner myorg --repo myrepo

# Disable via environment variable
export CR_ENABLE_ROLLBACK="false"
pr-resolve apply --pr 123 --owner myorg --repo myrepo

```

#### Configuration File

```yaml
# config.yaml
rollback:
  enabled: true  # Enable rollback

```

```bash
pr-resolve apply --pr 123 --owner myorg --repo myrepo --config config.yaml

```

### Python API Usage

#### Basic Usage

```python
from pathlib import Path
from review_bot_automator.core.rollback import RollbackManager

# Initialize manager
manager = RollbackManager(Path("/path/to/repo"))

# Create checkpoint
checkpoint_id = manager.create_checkpoint()
print(f"Created checkpoint: {checkpoint_id}")

try:
    # Apply changes
    apply_changes(changes)

    # If successful, commit (keep changes)
    manager.commit()
    print("Changes applied successfully")

except Exception as e:
    # If error, rollback (restore previous state)
    manager.rollback()
    print(f"Error occurred, rolled back: {e}")
    raise

```

#### Using ConflictResolver

```python
from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig

# Initialize resolver
resolver = ConflictResolver(config=PresetConfig.BALANCED)

# Resolve with rollback enabled (default)
results = resolver.resolve_pr_conflicts(
    owner="myorg",
    repo="myrepo",
    pr_number=123,
    enable_rollback=True  # Default: True
)

# Check results
if results.success_rate < 100:
    print(f"Some changes failed, but rollback protected working directory")

```

### Context Manager Pattern

The most Pythonic way to use the rollback system:

```python
from pathlib import Path
from review_bot_automator.core.rollback import RollbackManager

# Automatic rollback on exception
with RollbackManager(Path("/path/to/repo")) as manager:
    # Apply changes here
    apply_changes(changes)

    # Explicitly commit on success (optional, auto-commits if no exception)
    manager.commit()

# If exception occurs, automatically rolls back
# If no exception, automatically commits

```

**Behavior:**

* **On exception**: Automatically calls `rollback()`, then propagates exception
* **On success (no exception)**: Automatically calls `commit()`
* **Explicit commit**: Can call `manager.commit()` before block ends

#### Advanced Context Manager Usage

```python
from pathlib import Path
from review_bot_automator.core.rollback import RollbackManager, RollbackError

def apply_changes_safely(changes, repo_path):
    """Apply changes with automatic rollback."""
    try:
        with RollbackManager(repo_path) as manager:
            for change in changes:
                # Apply each change
                apply_single_change(change)

            # All succeeded, commit
            manager.commit()
            return True

    except RollbackError as e:
        print(f"Rollback failed: {e}")
        return False
    except Exception as e:
        print(f"Changes failed, rolled back: {e}")
        return False

```

## Configuration

### Configuration Precedence

Configuration sources (highest to lowest priority):

1. **CLI flags** (`--rollback` / `--no-rollback`)
2. **Environment variables** (`CR_ENABLE_ROLLBACK`)
3. **Configuration file** (`rollback.enabled`)
4. **Defaults** (rollback enabled)

### Configuration Options

#### CLI Flags

| Flag | Description | Default |
| ------ | ------------- | --------- |
| `--rollback` | Enable automatic rollback on failure | Enabled |
| `--no-rollback` | Disable automatic rollback | - |

#### Environment Variables

| Variable | Type | Values | Default |
| ---------- | ------ | -------- | --------- |
| `CR_ENABLE_ROLLBACK` | boolean | `true`, `false`, `1`, `0`, `yes`, `no` | `true` |

#### Configuration File

**YAML:**

```yaml
rollback:
  enabled: true

```

**TOML:**

```toml
[rollback]
enabled = true

```

### Configuration Examples

#### Example 1: Maximum Safety (Production)

```yaml
# prod-config.yaml
mode: conflicts-only
rollback:
  enabled: true  # Always enable in production
validation:
  enabled: true  # Defense in depth
logging:
  level: INFO
  file: /var/log/pr-resolver/production.log

```

#### Example 2: Performance Optimized

```yaml
# perf-config.yaml
mode: all
rollback:
  enabled: true  # Keep safety enabled
validation:
  enabled: false  # Disable validation for speed, rely on rollback
parallel:
  enabled: true
  max_workers: 16

```

#### Example 3: Testing Environment

```bash
# Disable rollback in disposable testing environment
export CR_ENABLE_ROLLBACK="false"
pr-resolve apply --pr 123 --owner myorg --repo myrepo

```

## Architecture

### Component Overview

```text
┌─────────────────────────────────────────────────────────┐
│              RollbackManager                            │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 1. create_checkpoint()                            │ │
│  │    • git stash push --include-untracked           │ │
│  │    • git stash apply                              │ │
│  │    • Store reference: stash@{0}                   │ │
│  └───────────────────────────────────────────────────┘ │
│                         │                               │
│                         ▼                               │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 2. Change Application                             │ │
│  │    • Monitor for exceptions                       │ │
│  │    • Track success/failure                        │ │
│  └───────────────────────────────────────────────────┘ │
│                         │                               │
│         ┌───────────────┴───────────────┐              │
│         ▼                               ▼              │
│  ┌──────────────┐               ┌──────────────┐      │
│  │ 3a. commit() │               │ 3b. rollback()│      │
│  │   Success    │               │    Failure    │      │
│  │              │               │               │      │
│  │ • Drop stash │               │ • reset --hard│      │
│  │ • Keep changes│              │ • clean -fd   │      │
│  │              │               │ • apply stash │      │
│  │              │               │ • drop stash  │      │
│  └──────────────┘               └──────────────┘      │
└─────────────────────────────────────────────────────────┘

```

### Class Structure

```python
class RollbackManager:
    """Git-based rollback manager for safe change application."""

    # Initialization
    def __init__(self, repo_path: str | Path) -> None

    # Core Operations
    def create_checkpoint(self) -> str
    def rollback(self) -> bool
    def commit(self) -> None

    # Status Checking
    def has_checkpoint(self) -> bool

    # Context Manager
    def __enter__(self) -> "RollbackManager"
    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]

    # Internal Methods
    def _is_git_available(self) -> bool
    def _is_git_repo(self) -> bool
    def _run_git_command(self, args: list[str]) -> CompletedProcess[str]

```

### Git Commands Used

The rollback system uses these git commands:

1. **`git status --porcelain`** - Check for uncommitted changes
2. **`git stash push --include-untracked -m "RollbackManager checkpoint"`** - Create checkpoint
3. **`git rev-parse stash@{0}`** - Get stash SHA for logging
4. **`git stash apply stash@{0}`** - Restore checkpoint state
5. **`git stash drop stash@{0}`** - Clean up checkpoint
6. **`git reset --hard HEAD`** - Reset tracked files
7. **`git clean -fd`** - Remove untracked files/directories

### State Diagram

```text
                    ┌──────────────┐
                    │  No Checkpoint│
                    └───────┬──────┘
                            │
                    create_checkpoint()
                            │
                            ▼
                    ┌──────────────┐
                    │   Checkpoint  │
                    │    Active     │
                    └───────┬──────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
         Success                         Exception
            │                               │
            ▼                               ▼
    ┌──────────────┐               ┌──────────────┐
    │   commit()   │               │  rollback()  │
    │              │               │              │
    │ Drop stash   │               │ Restore state│
    │ Keep changes │               │ Drop stash   │
    └───────┬──────┘               └───────┬──────┘
            │                               │
            └───────────────┬───────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │  No Checkpoint│
                    └──────────────┘

```

## Safety Features

### 1. Checkpoint Protection

* **Single checkpoint enforcement**: Cannot create new checkpoint while one exists
* **Atomic operations**: Checkpoint creation is all-or-nothing
* **Immediate verification**: Verifies stash creation before proceeding

### 2. Error Handling

* **Rollback on any exception**: Catches all exceptions during application
* **Cleanup on rollback failure**: Attempts to drop stash even if rollback fails
* **Detailed logging**: All operations logged for audit trail

### 3. State Validation

* **Git availability check**: Verifies git command is available
* **Repository validation**: Confirms path is a valid git repository
* **Path validation**: Checks path exists and is a directory

### 4. Recovery Mechanisms

* **Manual rollback support**: Can call `rollback()` explicitly if auto-rollback fails
* **Stash reference tracking**: Stores `stash@{0}` reference for reliable operations
* **Non-fatal stash drop**: Continues even if stash drop fails (already cleaned up)

## Use Cases

### Use Case 1: Production Deployment

**Scenario**: Applying PR changes to production codebase

```bash
# Maximum safety configuration
pr-resolve apply --pr 456 --owner myorg --repo production \
  --mode conflicts-only \
  --rollback \
  --validation \
  --log-level INFO \
  --log-file /var/log/pr-resolver/prod-$(date +%Y%m%d-%H%M%S).log

```

**What happens:**

1. Checkpoint created before any changes
2. Only conflicting changes applied
3. All changes validated before application
4. If any error: automatic rollback to pre-application state
5. If success: checkpoint committed, changes kept
6. Full audit trail in log file

### Use Case 2: Experimental Changes

**Scenario**: Testing changes from untrusted source

```python
from pathlib import Path
from review_bot_automator.core.rollback import RollbackManager

def test_experimental_changes(changes, repo_path):
    """Apply experimental changes with easy rollback."""
    with RollbackManager(repo_path) as manager:
        print("Applying experimental changes...")
        apply_changes(changes)

        # Prompt user for confirmation
        response = input("Keep changes? (yes/no): ")
        if response.lower() != "yes":
            # Explicit rollback
            manager.rollback()
            print("Changes rolled back")
            return False

        # Commit if user approves
        manager.commit()
        print("Changes kept")
        return True

```

### Use Case 3: Large PR Processing

**Scenario**: Applying 100+ changes from large PR

```bash
# Apply in stages with rollback protection
# Stage 1: Non-conflicting changes (safer)
pr-resolve apply --pr 789 --owner myorg --repo myrepo \
  --mode non-conflicts-only \
  --rollback \
  --parallel --max-workers 8

# Stage 2: Conflicting changes (riskier, more careful)
pr-resolve apply --pr 789 --owner myorg --repo myrepo \
  --mode conflicts-only \
  --rollback \
  --validation

```

**Benefits:**

* Each stage independently protected by rollback
* If stage 2 fails, stage 1 changes remain
* Can recover from partial application

### Use Case 4: CI/CD Pipeline

**Scenario**: Automated PR resolution in CI/CD

```yaml
# .github/workflows/auto-resolve.yml
* name: Resolve PR Conflicts
  run: |
    # Enable rollback for safety
    export CR_ENABLE_ROLLBACK="true"
    export CR_LOG_LEVEL="INFO"

    # Apply with rollback protection
    pr-resolve apply \
      --pr ${{ github.event.pull_request.number }} \
      --owner ${{ github.repository_owner }} \
      --repo ${{ github.event.repository.name }} \
      --mode conflicts-only \
      --rollback \
      --log-file /tmp/pr-resolve.log

    # Upload logs even on failure
  continue-on-error: true

* name: Upload Logs
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: resolution-logs
    path: /tmp/pr-resolve.log

```

### Use Case 5: Manual Recovery

**Scenario**: Rollback fails, need manual intervention

```python
from pathlib import Path
from review_bot_automator.core.rollback import RollbackManager, RollbackError

def apply_with_fallback(changes, repo_path):
    """Apply changes with multiple recovery levels."""
    manager = RollbackManager(repo_path)

    try:
        # Create checkpoint
        checkpoint = manager.create_checkpoint()
        print(f"Checkpoint: {checkpoint}")

        # Apply changes
        apply_changes(changes)
        manager.commit()
        return True

    except Exception as e:
        print(f"Application failed: {e}")

        # Try automatic rollback
        try:
            manager.rollback()
            print("Automatic rollback successful")
            return False
        except RollbackError as rollback_error:
            print(f"Automatic rollback failed: {rollback_error}")

            # Manual recovery
            print("Attempting manual recovery...")
            manual_recovery(repo_path, checkpoint)
            return False

def manual_recovery(repo_path, checkpoint_id):
    """Manual recovery when automatic rollback fails."""
    import subprocess

    print("Manual recovery steps:")
    print(f"1. cd {repo_path}")
    print(f"2. git stash list  # Find your stash")
    print(f"3. git reset --hard HEAD")
    print(f"4. git clean -fd")
    print(f"5. git stash apply {checkpoint_id}")

    # Or attempt programmatic recovery
    try:
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=repo_path, check=True)
        subprocess.run(["git", "clean", "-fd"], cwd=repo_path, check=True)
        subprocess.run(["git", "stash", "apply", checkpoint_id], cwd=repo_path, check=True)
        print("Manual recovery successful")
    except subprocess.CalledProcessError as e:
        print(f"Manual recovery failed: {e}")
        print("Please recover manually using git commands")

```

## Troubleshooting

### Common Issues

#### 1. Rollback Not Triggering

**Symptoms:**

* Changes applied but errors occur
* No rollback happens
* Working directory left in failed state

**Causes:**

* Rollback disabled in configuration
* Not using context manager or explicit try/catch
* Exception caught and suppressed before rollback

**Solutions:**

```bash
# 1. Verify rollback is enabled
pr-resolve apply --pr 123 --owner org --repo repo --rollback --log-level DEBUG

# 2. Check configuration
echo $CR_ENABLE_ROLLBACK  # Should be "true"
cat config.yaml | grep -A 2 "rollback:"

# 3. Use Python API correctly
with RollbackManager(repo_path) as manager:
    apply_changes()  # Will auto-rollback on exception
    manager.commit()

```

#### 2. Rollback Fails to Restore

**Symptoms:**

* Rollback attempted but fails
* Files not restored to previous state
* `RollbackError` exception raised

**Causes:**

* Uncommitted changes existed before running
* Git stash conflicts with current changes
* Repository in detached HEAD state
* Stash was manually deleted

**Solutions:**

```bash
# 1. Check git status BEFORE running resolver
git status
# If uncommitted changes exist, commit or stash them first

# 2. Verify git repository state
git branch -v  # Should show current branch, not detached HEAD
git log -1  # Should show recent commit

# 3. Check stash list
git stash list
# If stash exists, manually apply it
git reset --hard HEAD
git clean -fd
git stash apply stash@{0}

# 4. If stash is missing, check git reflog
git reflog stash
git stash apply stash@{N}  # Where N is the stash index

```

#### 3. Repository Left Dirty After Rollback

**Symptoms:**

* Rollback completes
* `git status` shows uncommitted changes
* Changes don't match pre-application state

**Causes:**

* Normal behavior - rollback restores to checkpoint state
* Untracked files not captured (in .gitignore)
* File permissions changed
* Symbolic links modified

**Solutions:**

```bash
# 1. Check what changed
git status
git diff

# 2. If expected (rollback worked correctly)
# These are the changes that existed when checkpoint was created

# 3. If unexpected, manual cleanup
git reset --hard HEAD  # Reset tracked files
git clean -fd  # Remove untracked files

# 4. Check logs for rollback details
pr-resolve apply --pr 123 --owner org --repo repo --log-level DEBUG 2>&1 | grep -i rollback

```

#### 4. Git Not Found

**Symptoms:**

* `RollbackError: git command not found`
* Cannot initialize RollbackManager

**Causes:**

* Git not installed on system
* Git not in PATH
* Running in restricted environment

**Solutions:**

```bash
# 1. Verify git is installed
which git
git --version

# 2. Install git if missing
# Ubuntu/Debian
sudo apt-get install git

# macOS
brew install git

# 3. Add git to PATH if installed but not found
export PATH="/usr/bin:$PATH"

# 4. Or disable rollback if git unavailable (not recommended)
pr-resolve apply --pr 123 --owner org --repo repo --no-rollback

```

#### 5. Stash Apply Conflicts

**Symptoms:**

* Rollback fails with "stash apply" conflicts
* Git reports merge conflicts during rollback

**Causes:**

* Changes applied by resolver conflict with checkpoint state
* File was deleted then recreated differently
* Binary file conflicts

**Solutions:**

```bash
# 1. Abort the conflicted stash apply
git reset --hard HEAD
git clean -fd

# 2. Try applying stash with different strategy
git stash apply stash@{0} --index

# 3. Or manually resolve conflicts
git stash apply stash@{0}
# Resolve conflicts manually
git add .
git stash drop stash@{0}

# 4. If unrecoverable, inspect stash contents
git stash show -p stash@{0}  # See what's in the stash

```

### Debugging Rollback Issues

#### Enable Debug Logging

```bash
# Maximum logging detail
pr-resolve apply --pr 123 --owner org --repo repo \
  --rollback \
  --log-level DEBUG \
  --log-file /tmp/rollback-debug-$(date +%Y%m%d-%H%M%S).log

# Review rollback-specific logs
grep -i "rollback\|checkpoint\|stash" /tmp/rollback-debug-*.log

```

#### Python API Debugging

```python
import logging
from pathlib import Path
from review_bot_automator.core.rollback import RollbackManager

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Create manager with verbose output
manager = RollbackManager(Path("/path/to/repo"))

# Check checkpoint status
print(f"Has checkpoint: {manager.has_checkpoint()}")
print(f"Checkpoint ID: {manager.checkpoint_id}")

# Create checkpoint with debug output
try:
    checkpoint = manager.create_checkpoint()
    print(f"Created: {checkpoint}")
except Exception as e:
    print(f"Failed: {e}")
    import traceback
    traceback.print_exc()

```

#### Manual Inspection

```bash
# 1. Check git repository state
git status
git log --oneline -5
git branch -v

# 2. Check stash list
git stash list
git stash show stash@{0}

# 3. Inspect stash contents
git stash show -p stash@{0}  # Full diff

# 4. Test stash apply manually
git stash apply stash@{0} --dry-run  # Test without applying

```

### Getting Help

When reporting rollback issues, include:

1. **Full command used**

   ```bash
   pr-resolve apply --pr 123 --owner org --repo repo --rollback --log-level DEBUG

   ```

2. **Debug log file**

   ```bash
   --log-file /tmp/rollback-issue.log

   ```

3. **Git repository state**

   ```bash
   git status
   git stash list
   git log -5 --oneline
   git branch -v

   ```

4. **Error messages**
   * Full exception stack trace
   * Git command errors from log

5. **Environment details**
   * OS and version
   * Git version: `git --version`
   * Python version: `python --version`

## Best Practices

### 1. Always Enable Rollback in Production

```yaml
# production-config.yaml
rollback:
  enabled: true  # Never disable in production

```

**Rationale**: Even with validation, unexpected errors can occur. Rollback provides a last line of defense.

### 2. Use Context Manager in Python

```python
# Good: Automatic rollback
with RollbackManager(repo_path) as manager:
    apply_changes()
    manager.commit()

# Avoid: Manual try/catch (easy to forget)
manager = RollbackManager(repo_path)
manager.create_checkpoint()
try:
    apply_changes()
    manager.commit()
except Exception:
    manager.rollback()  # Easy to forget

```

### 3. Clean Working Directory Before Running

```bash
# Check for uncommitted changes first
git status

# If changes exist, commit or stash them
git stash push -m "Before PR resolver"

# Then run resolver
pr-resolve apply --pr 123 --owner org --repo repo --rollback

```

**Rationale**: Clean working directory ensures checkpoint captures only resolver changes.

### 4. Combine with Validation

```bash
# Defense in depth: validation + rollback
pr-resolve apply --pr 123 --owner org --repo repo \
  --validation \  # Catch errors early
  --rollback      # Recover if validation misses something

```

### 5. Log to File for Audit Trail

```bash
# Create audit trail
mkdir -p logs
pr-resolve apply --pr 123 --owner org --repo repo \
  --rollback \
  --log-level INFO \
  --log-file logs/pr-123-$(date +%Y%m%d-%H%M%S).log

# Review logs later
grep -i "rollback\|checkpoint" logs/*.log

```

### 6. Test Rollback in Non-Production First

```bash
# Test in development environment
pr-resolve apply --pr 123 --owner org --repo test-repo --rollback

# Verify rollback works by intentionally causing failure
# Then apply to production with confidence

```

### 7. Monitor Rollback Frequency

```bash
# Track how often rollback triggers
grep "Rolling back" logs/*.log | wc -l

# If rollback triggers frequently, investigate root causes

```

## Limitations

### 1. Requires Git Repository

* **Limitation**: Only works in git repositories
* **Workaround**: Not available for non-git projects
* **Alternative**: Use external backup systems

### 2. Untracked Files in .gitignore Not Saved

* **Limitation**: Files matching .gitignore patterns not captured
* **Workaround**: Temporarily unignore critical files
* **Example**:

  ```bash
  # Temporarily remove from .gitignore
  echo "!critical-file.log" >> .gitignore

  ```

### 3. Performance Impact

* **Limitation**: Checkpoint creation adds overhead
* **Impact**: ~1-2 seconds for small repos, 5-10 seconds for large repos
* **Mitigation**: Disable for performance-critical operations (not recommended)

### 4. Requires Git Installed

* **Limitation**: `git` command must be available
* **Workaround**: Install git or disable rollback
* **Check**: `which git` and `git --version`

### 5. Single Checkpoint at a Time

* **Limitation**: Cannot create nested checkpoints
* **Workaround**: Commit or rollback before creating new checkpoint
* **Example**:

  ```python
  manager.create_checkpoint()
  # ... apply some changes ...
  manager.commit()  # Must commit before new checkpoint
  manager.create_checkpoint()  # Now can create new one

  ```

### 6. No Cross-Branch Rollback

* **Limitation**: Rollback within same branch only
* **Impact**: Cannot rollback across branch switches
* **Example**: If changes cause branch switch, rollback may not restore correctly

### 7. Large Repository Performance

* **Limitation**: Stash operations slow on large repos (1M+ files)
* **Impact**: Checkpoint creation may take 30+ seconds
* **Mitigation**: Use `--no-rollback` only if performance critical

## See Also

* [Configuration Reference](configuration.md) - Rollback configuration options
* [Getting Started](getting-started.md) - Basic rollback usage
* [API Reference](api-reference.md) - RollbackManager API documentation
* [Parallel Processing](parallel-processing.md) - Combining rollback with parallel execution
* [Troubleshooting](troubleshooting.md) - General troubleshooting guide
