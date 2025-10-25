# Workspace Optimization Guide

## Problem

Cursor workspace reloads occur frequently, causing AI assistant hangs and reduced productivity.

## Root Causes Identified

1. **Cache file generation**: Running tools like `mypy`, `ruff`, `pytest` creates cache files that trigger workspace reindexing
2. **Python bytecode compilation**: Importing modules creates `__pycache__` directories
3. **Batch file operations**: Using `sed` or similar tools to modify many files simultaneously overwhelms the file watcher
4. **Insufficient ignore patterns**: Not all generated files are properly excluded from workspace watching

## Solutions Implemented

### 1. Enhanced .cursorignore

- Added comprehensive patterns for all cache directories
- Excluded temporary files, build artifacts, and IDE files
- Prevents workspace from watching generated content

### 2. PYTHONDONTWRITEBYTECODE=1

- Prevents `.pyc` file generation during Python imports
- Reduces file system events that trigger workspace reloads

### 3. Makefile Cleanup Commands

Use the project's Makefile for cache cleanup:
- `make clean`: Removes all cache directories and temporary files

## Best Practices for File Editing

### ✅ DO

- Edit files sequentially rather than in parallel
- Use single-file edits instead of batch operations
- Clear caches before starting work sessions
- Use read-only tools (grep, read_file) for investigation before editing
- Run linting tools less frequently during iteration

### ❌ DON'T

- Use `sed` to modify multiple files simultaneously
- Run multiple tools that generate cache files at once
- Edit many files in rapid succession
- Leave cache directories uncleaned

## Workflow Optimization

### Before Starting Work

```bash
export PYTHONDONTWRITEBYTECODE=1
make clean
```

### During Development

1. Use single-file edits with `search_replace`
2. Avoid `MultiEdit` for large changes
3. Run tools individually rather than in batches
4. Clear caches between major operations

### After Work Session

```bash
make clean
```

## Monitoring and Debugging

### Manual Cache Cleanup

```bash
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name ".mypy_cache" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name ".ruff_cache" -type d -exec rm -rf {} + 2>/dev/null || true
```

## Expected Results

- Workspace reloads reduced by >75%
- No hangs during normal file editing operations
- Linting/type checking doesn't trigger reloads
- Batch operations complete without interruption

## Troubleshooting

### If workspace still reloads frequently

1. Check if new cache directories are being created
2. Verify `.cursorignore` patterns are comprehensive
3. Ensure `PYTHONDONTWRITEBYTECODE=1` is set
4. Use `make clean` to clear all caches

### If AI assistant still hangs

1. Clear all caches manually
2. Restart Cursor workspace
3. Check for large file operations in progress
4. Verify no batch operations are running
