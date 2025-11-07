# MCP Servers Quick Reference

Quick reference guide for MCP server commands and operations.

**Last Updated**: 2025-11-07
**Active Servers**: 7 (all connected ✓)

## Commands Cheat Sheet

### MCP Management Commands

```bash
# List all MCP servers and their status
claude mcp list

# Add a server (user scope - persistent across projects)
claude mcp add --scope user <server-name>

# Add a server with JSON config
claude mcp add-json --scope user <name> '{"command":"...","args":[...]}'

# Remove a server
claude mcp remove <server-name>

# Get details about a specific server
claude mcp get <server-name>

# Reset project server approval choices
claude mcp reset-project-choices
```

### Verification

```bash
# Check which servers are connected
claude mcp list

# Expected: 7 servers with "✓ Connected" status
```

## Installed Servers Overview

| Server | Scope | Type | Status | Purpose |
|--------|-------|------|--------|---------|
| github | User | Docker | ✓ | GitHub API integration |
| git | User | NPX | ✓ | Git operations |
| ollama | User | NPX | ✓ | Local LLM management |
| uv | User | uvx | ✓ | Python dependency management |
| analyzer | Project | Python | ✓ | RUFF + VULTURE analysis |
| python-lft | Project | Python | ✓ | Lint/Format/Test tools |
| sqlite | Project | Python | ✓ | Database operations |

## Configuration Locations

### User-Scoped Servers
**Location**: `~/.claude.json` (in mcpServers section)
**Scope**: Available in all projects

### Project-Scoped Servers
**Location**: `.mcp.json` (in project root)
**Scope**: Only this project

### ❌ Wrong Location
**`~/.config/claude-code/mcp.json`** - This is NOT used by Claude Code!

## Quick Setup Examples

### Adding User-Scoped Server

```bash
# Git server (simple)
claude mcp add-json --scope user git '{
  "command":"npx",
  "args":["-y","@cyanheads/git-mcp-server"]
}'

# GitHub server (with Docker --env-file)
claude mcp add-json --scope user github '{
  "command":"docker",
  "args":[
    "run","-i","--rm",
    "--env-file","/path/to/project/.env",
    "-e","GITHUB_TOOLSETS=repos,issues,pull_requests,actions,code_security",
    "ghcr.io/github/github-mcp-server:latest"
  ]
}'
```

### Project Server Configuration

Edit `.mcp.json` in project root:

```json
{
  "mcpServers": {
    "analyzer": {
      "command": ".venv/bin/python",
      "args": ["-m", "mcp_server_analyzer"],
      "description": "Code analysis"
    }
  }
}
```

## Security Quick Tips

### ✅ DO

- Store tokens in project `.env` file
- Use `chmod 600 .env` to secure the file
- Use Docker `--env-file` for passing credentials
- Add `.env` to `.gitignore`
- Use `--scope user` for persistent servers

### ❌ DON'T

- Put tokens in shell profile (`~/.bashrc`)
- Commit tokens to git
- Use `apiKeyHelper` for MCP env vars (it's for Anthropic API only)
- Store configs in `~/.config/claude-code/mcp.json`
- Forget to specify `--scope user` (defaults to temporary local scope)

## Server-Specific Commands

### GitHub MCP

**Requires**: Docker + `GITHUB_PERSONAL_ACCESS_TOKEN` in `.env`

Available operations through Claude Code:
- Fetch PR reviews and comments
- List/create/update issues
- Check GitHub Actions status
- Manage pull requests
- Security scanning

### Git MCP

**Requires**: Node.js/npx + Git

Available operations:
- Branch management
- Commit operations
- Diff and log viewing
- Merge operations
- Cherry-pick

### Ollama MCP

**Requires**: Ollama running on `localhost:11434`

Available operations:
- List models
- Run inference
- Manage models
- Test responses

### UV MCP

**Requires**: UV installed (`pip install uv`)

Available operations:
- Dependency management
- Package queries
- Environment introspection
- Fast package resolution

### Analyzer MCP

**Requires**: `mcp-server-analyzer` in project `.venv`

Available tools:
- `ruff-check` - Lint Python code
- `ruff-format` - Format Python code
- `vulture-scan` - Find dead code
- `analyze-code` - Combined analysis

### Python LFT MCP

**Requires**: `python-lft` in project `.venv`

Available tools:
- `detect_workspace_tools` - Analyze project config
- `lint` - Run project linters
- `format` - Run project formatters
- `test` - Run project tests

### SQLite MCP

**Requires**: `mcp-server-sqlite` in project `.venv`

Available operations:
- Execute SELECT queries
- Execute INSERT/UPDATE/DELETE
- Create tables
- List tables
- Describe schemas

## Troubleshooting Quick Fixes

### Problem: Servers not loading

```bash
# 1. Check configuration
claude mcp list

# 2. Reset project approvals
claude mcp reset-project-choices

# 3. Restart Claude Code
```

### Problem: Python servers fail

```bash
# Ensure packages installed in project .venv
source .venv/bin/activate
pip install mcp-server-analyzer python-lft mcp-server-sqlite

# Verify
pip list | grep -E "(mcp|python-lft)"
```

### Problem: GitHub server fails

```bash
# 1. Check Docker is running
docker ps

# 2. Verify token in .env
grep GITHUB_PERSONAL_ACCESS_TOKEN .env

# 3. Check file permissions
ls -la .env  # Should show: -rw-------

# 4. Secure if needed
chmod 600 .env
```

### Problem: Token exposed in apiKeyHelper error

The `apiKeyHelper` setting is for **Anthropic API keys only**, not MCP environment variables.

**Solution**: Remove `apiKeyHelper` from settings and use Docker `--env-file` instead.

## Scope Decision Guide

### Use User Scope When:
- Tool useful across all projects
- Personal preference (e.g., git, GitHub)
- Global utility (e.g., ollama, uv)

### Use Project Scope When:
- Project-specific tool (e.g., code analyzer)
- Team needs to share config
- Depends on project structure
- Version control desired

## Phase 3: REST API Server

**Status**: Not currently installed
**Reason**: Not needed for Phase 2 (provider implementation)
**When to add**: Phase 3 (API integration polish)

```bash
# How to add when needed
claude mcp add-json --scope user rest-api '{
  "command":"npx",
  "args":["-y","dkmaker-mcp-rest-api"],
  "env":{"REST_BASE_URL":"https://api.openai.com/v1"}
}'
```

## Further Reading

- [MCP Servers Setup Guide](./MCP_SERVERS_SETUP.md) - Complete setup instructions
- [MCP Environment Setup](./MCP_ENVIRONMENT_SETUP.md) - Secure credential management
- [MCP Troubleshooting](./MCP_TROUBLESHOOTING.md) - Detailed troubleshooting guide
- [Official Claude Code Docs](https://docs.claude.com/en/docs/claude-code/mcp)

---

**Quick Status Check**:
```bash
claude mcp list
# Expected: 7 servers, all "✓ Connected"
```
