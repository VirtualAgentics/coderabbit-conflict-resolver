# MCP Python Package Installation Guide

This guide provides instructions for installing the Python packages required by the MCP servers configured in this project.

## Required Packages

The following Python packages are needed for the project-level MCP servers (defined in `.mcp.json`):

| Package | MCP Server | Purpose |
|---------|------------|---------|
| `mcp-server-analyzer` | analyzer | RUFF linting + VULTURE dead code detection |
| `python-lft` | python-lft | Python Lint, Format, Test tools |
| `mcp-server-sqlite` | sqlite | SQLite database operations |
| `semgrep` | semgrep | Security scanning and code analysis |

## Installation Status

Current status (as of 2025-11-07 - Updated):
- ✅ `mcp-server-analyzer` - INSTALLED (v0.1.1)
- ✅ `python-lft-mcp` - INSTALLED (v1.0.0)
- ✅ `mcp-server-sqlite` - INSTALLED (v2025.4.25)
- ✅ `semgrep` - INSTALLED (v1.142.1) - ⚠️ Has known dependency conflicts

## Installation Methods

### Method 1: Install in Project .venv (REQUIRED for This Project) ✅

**IMPORTANT**: MCP Python packages MUST be installed in the project's `.venv` virtual environment. Claude Code automatically activates this venv via `preRunCommands` in `.claude/settings.json`.

```bash
# Navigate to project root
cd /home/bofh/projects/review-bot-automator

# Activate the project virtual environment (REQUIRED)
source .venv/bin/activate

# Verify you're in the correct venv
which python  # Should show: /home/bofh/projects/review-bot-automator/.venv/bin/python

# Install all required packages
pip install mcp-server-analyzer python-lft mcp-server-sqlite semgrep

# Verify installation in .venv
python -m pip list | grep -E "(mcp|python-lft|semgrep)"
```

**Why .venv is Required**:
- Claude Code's `preRunCommands` automatically activates `.venv/bin/activate`
- MCP servers use Python from the activated environment
- System-wide installations won't be accessible to MCP servers
- All `commandTemplates` in settings.json activate .venv before running

### Method 2: Install via uv (Alternative for .venv)

If you have `uv` installed (already configured at `/home/bofh/.local/bin/uvx`):

```bash
# Navigate to project root
cd /home/bofh/projects/review-bot-automator

# Activate venv first
source .venv/bin/activate

# Install with uv
uv pip install mcp-server-analyzer python-lft mcp-server-sqlite semgrep
```

### ❌ DO NOT Install System-Wide

**DO NOT** install these packages system-wide or in a different virtual environment:
```bash
# ❌ WRONG - System-wide installation
pip install mcp-server-analyzer  # Won't work with MCP servers

# ❌ WRONG - Different venv
python3 -m venv other_env
source other_env/bin/activate
pip install mcp-server-analyzer  # Won't work with this project
```

## Verification

After installation, verify that all packages are installed correctly **in the project .venv**:

```bash
# Ensure you're in the correct venv
source .venv/bin/activate

# Verify installation location
pip show mcp-server-analyzer | grep Location
# Should show: Location: /home/bofh/projects/review-bot-automator/.venv/lib/python3.XX/site-packages

# Check if packages are importable
python -c "import mcp_server_analyzer; print('✓ mcp-server-analyzer installed in .venv')"
python -c "import mcp_server_sqlite; print('✓ mcp-server-sqlite installed in .venv')"
python -c "import python_lft; print('✓ python-lft installed in .venv')"
python -c "import semgrep; print('✓ semgrep installed in .venv')"

# List all MCP-related packages in .venv
pip list | grep -E "(mcp|python-lft|semgrep)"
```

## Known Issues

### Semgrep Dependency Conflicts

The `semgrep` package has known dependency conflicts with this project. Use with caution and consider:
1. Installing it in a separate virtual environment
2. Using it via Docker instead: `docker run -v $(pwd):/src semgrep/semgrep scan --config=auto`
3. Disabling it temporarily if it causes issues

## Package Documentation

- **mcp-server-analyzer**: [PyPI](https://pypi.org/project/mcp-server-analyzer/)
- **python-lft**: [PyPI](https://pypi.org/project/python-lft/)
- **mcp-server-sqlite**: [PyPI](https://pypi.org/project/mcp-server-sqlite/)
- **semgrep**: [Official Docs](https://semgrep.dev/docs/)

## Troubleshooting

### Package Not Found

If a package is not found on PyPI, check:
1. Package name spelling and case
2. Package availability on PyPI
3. Alternative installation methods (e.g., from GitHub)

### Import Errors After Installation

If packages are installed but imports fail:
1. Verify you're using the correct Python interpreter
2. Check that the virtual environment is activated
3. Ensure package names match module names (they may differ)

### Virtual Environment Issues

**Issue**: Claude Code/MCP servers can't find installed packages

**Solutions**:
1. **Verify packages are in project .venv**:
   ```bash
   source .venv/bin/activate
   pip show mcp-server-analyzer | grep Location
   # Must show the project .venv path
   ```

2. **Check preRunCommands in .claude/settings.json**:
   ```json
   {
     "preRunCommands": [
       "test -f .env && set -a && source .env && set +a || true",
       "test -d .venv && source .venv/bin/activate || true"
     ]
   }
   ```

3. **Restart Claude Code completely** after installing packages

4. **Verify Python path**:
   ```bash
   source .venv/bin/activate
   which python  # Should point to .venv/bin/python
   ```

**Issue**: Packages installed in wrong location (system or different venv)

**Solutions**:
1. **Remove wrong installation**:
   ```bash
   # If installed system-wide
   pip uninstall mcp-server-analyzer python-lft mcp-server-sqlite semgrep
   ```

2. **Reinstall in project .venv**:
   ```bash
   cd /home/bofh/projects/review-bot-automator
   source .venv/bin/activate
   pip install mcp-server-analyzer python-lft mcp-server-sqlite semgrep
   ```

## Next Steps

After installing the packages:
1. Restart Claude Code to load the MCP servers
2. Run `/mcp` to verify servers are loaded
3. Test each server's functionality
4. Update this document with any issues or solutions you discover
