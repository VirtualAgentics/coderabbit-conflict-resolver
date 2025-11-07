# MCP Servers Setup Guide

Complete guide to Model Context Protocol (MCP) servers configured in this project.

**Last Updated**: 2025-11-07
**Active Servers**: 7 (all connected ✓)

## Table of Contents

1. [Overview](#overview)
2. [Understanding Scopes](#understanding-scopes)
3. [Active MCP Servers](#active-mcp-servers)
4. [Setup Instructions](#setup-instructions)
5. [Security Considerations](#security-considerations)
6. [Future Servers](#future-servers)
7. [Common Mistakes](#common-mistakes)

## Overview

This project uses **7 active MCP servers** (all successfully connected):

- **4 User-Scoped Servers**: Available across all projects (github, git, ollama, uv)
- **3 Project-Scoped Servers**: Specific to this project (analyzer, python-lft, sqlite)

### What are MCP Servers?

MCP servers extend Claude Code with additional tools and capabilities. They run as separate processes that Claude Code communicates with to provide functionality like:
- Git operations
- GitHub API access
- Code analysis
- Local LLM inference
- Python package management
- Database operations

## Understanding Scopes

### User Scope

**Location**: `~/.claude.json` (stored in the `mcpServers` section)

**Characteristics**:
- Available in **all projects** on your system
- Global tools you use regularly
- Configured using `claude mcp add --scope user` (or just `claude mcp add`)
- Not version-controlled

**When to use**:
- Tools you want everywhere (git, GitHub integration)
- Personal preferences (local LLMs, dependency management)
- Cross-project utilities

### Project Scope

**Location**: `.mcp.json` in project root directory

**Characteristics**:
- Available only in **this specific project**
- Shared with team members (version-controlled)
- Project-specific tooling
- Requires approval before first use

**When to use**:
- Project-specific tools (code analyzers for this language)
- Team-shared configurations
- Tools that depend on project structure

### ❌ Common Misconception

**WRONG**: `~/.config/claude-code/mcp.json`
- This location is **NOT** used by Claude Code
- If you have servers defined here, they won't load

**CORRECT**:
- **User scope**: `~/.claude.json` (in the mcpServers section)
- **Project scope**: `.mcp.json` (in project root)

## Active MCP Servers

### User-Scoped Servers (4)

#### 1. GitHub (github) ✓

**Purpose**: Complete GitHub API integration for repos, PRs, issues, actions, and security

**Type**: Docker-based

**Current Status**: ✅ Connected

**Configuration**:
```json
{
  "command": "docker",
  "args": [
    "run", "-i", "--rm",
    "--env-file", "/home/bofh/projects/review-bot-automator/.env",
    "-e", "GITHUB_TOOLSETS=repos,issues,pull_requests,actions,code_security",
    "ghcr.io/github/github-mcp-server:latest"
  ]
}
```

**Requirements**:
- Docker installed and running
- `GITHUB_PERSONAL_ACCESS_TOKEN` in project `.env` file
- `.env` file permissions: `chmod 600 .env`

**Capabilities**:
- Create/manage repositories
- Work with issues and PRs
- Manage GitHub Actions
- Code security scanning
- Release management

**Setup**: See [Security Considerations](#security-considerations) section

---

#### 2. Git (git) ✓

**Purpose**: Complete Git operations including commits, branches, diffs, logs, and merge management

**Type**: NPX-based (Node.js)

**Current Status**: ✅ Connected

**Configuration**:
```json
{
  "command": "npx",
  "args": ["-y", "@cyanheads/git-mcp-server"]
}
```

**Requirements**:
- Node.js and npx installed
- Git installed and configured

**Capabilities**:
- Git status, diff, log
- Branch management
- Commit operations
- Merge and rebase
- Remote operations
- Tag management

---

#### 3. Ollama (ollama) ✓

**Purpose**: Local LLM management and interaction for cost-effective, privacy-first development

**Type**: NPX-based (Node.js)

**Current Status**: ✅ Connected

**Configuration**:
```json
{
  "command": "npx",
  "args": ["-y", "ollama-mcp"],
  "env": {
    "OLLAMA_BASE_URL": "http://localhost:11434"
  }
}
```

**Requirements**:
- Ollama installed and running
- Local models pulled (e.g., `ollama pull llama2`)

**Capabilities**:
- List available models
- Pull new models
- Run inference on local models
- Manage model lifecycle

---

#### 4. UV (uv) ✓

**Purpose**: Python dependency management, package queries, and environment introspection

**Type**: uvx-based (Python)

**Current Status**: ✅ Connected

**Configuration**:
```json
{
  "command": "/home/bofh/.local/bin/uvx",
  "args": ["uv-mcp"]
}
```

**Requirements**:
- uv installed (`pip install uv`)
- uvx available in PATH

**Capabilities**:
- Fast dependency resolution
- Package installation
- Virtual environment management
- Lock file management
- Package queries

---

### Project-Scoped Servers (3)

#### 5. Analyzer (analyzer) ✓

**Purpose**: RUFF + VULTURE code analysis for Python linting and dead code detection

**Type**: Python venv-based

**Current Status**: ✅ Connected

**Configuration**:
```json
{
  "command": "/home/bofh/projects/review-bot-automator/.venv/bin/python",
  "args": ["-m", "mcp_server_analyzer"]
}
```

**Requirements**:
- Project virtual environment activated
- Package installed: `pip install mcp-server-analyzer`

**Capabilities**:
- RUFF linting (PEP 8, type hints, imports)
- VULTURE dead code detection
- Combined analysis reports
- CI/CD integration formats

---

#### 6. Python LFT (python-lft) ✓

**Purpose**: Lint, Format, and Test tools for Python development

**Type**: Python venv-based

**Current Status**: ✅ Connected

**Configuration**:
```json
{
  "command": "/home/bofh/projects/review-bot-automator/.venv/bin/python",
  "args": ["-m", "python_lft"]
}
```

**Requirements**:
- Project virtual environment activated
- Package installed: `pip install python-lft`

**Capabilities**:
- Auto-detect project linters (ruff, mypy, pylint)
- Auto-detect formatters (black, isort, autopep8)
- Auto-detect test runners (pytest, unittest)
- Run tools with custom configurations

---

#### 7. SQLite (sqlite) ✓

**Purpose**: Database operations for application data storage

**Type**: Python venv-based

**Current Status**: ✅ Connected

**Configuration**:
```json
{
  "command": "/home/bofh/projects/review-bot-automator/.venv/bin/mcp-server-sqlite",
  "args": ["--db-path", "/home/bofh/projects/review-bot-automator/.mcp-cache/data.db"]
}
```

**Requirements**:
- Project virtual environment activated
- Package installed: `pip install mcp-server-sqlite`

**Capabilities**:
- Execute SELECT queries
- Execute INSERT/UPDATE/DELETE
- Create tables
- List tables
- Describe table schemas
- Transaction management

---

## Setup Instructions

### Installing User-Scoped Servers

User-scoped servers are added to `~/.claude.json` and available in all projects.

#### GitHub Server

```bash
# Add GitHub MCP server with secure credential handling
claude mcp add-json --scope user github '{
  "command":"docker",
  "args":[
    "run","-i","--rm",
    "--env-file","/absolute/path/to/your/project/.env",
    "-e","GITHUB_TOOLSETS=repos,issues,pull_requests,actions,code_security",
    "ghcr.io/github/github-mcp-server:latest"
  ]
}'
```

**Important**: Replace `/absolute/path/to/your/project/.env` with your actual project path.

#### Git Server

```bash
claude mcp add-json --scope user git '{
  "command":"npx",
  "args":["-y","@cyanheads/git-mcp-server"]
}'
```

#### Ollama Server

```bash
claude mcp add-json --scope user ollama '{
  "command":"npx",
  "args":["-y","ollama-mcp"],
  "env":{"OLLAMA_BASE_URL":"http://localhost:11434"}
}'
```

#### UV Server

```bash
# Find your uvx path first
which uvx

# Then add with your actual path
claude mcp add-json --scope user uv '{
  "command":"/home/yourusername/.local/bin/uvx",
  "args":["uv-mcp"]
}'
```

### Installing Project-Scoped Servers

Project-scoped servers are defined in `.mcp.json` in the project root and are version-controlled.

**File**: `.mcp.json`
```json
{
  "mcpServers": {
    "analyzer": {
      "command": ".venv/bin/python",
      "args": ["-m", "mcp_server_analyzer"],
      "description": "RUFF + VULTURE code analysis"
    },
    "python-lft": {
      "command": ".venv/bin/python",
      "args": ["-m", "python_lft"],
      "description": "Lint, Format, Test tools"
    },
    "sqlite": {
      "command": ".venv/bin/mcp-server-sqlite",
      "args": ["--db-path", ".mcp-cache/data.db"],
      "description": "SQLite database operations"
    }
  }
}
```

**Note**: Project servers require approval on first use. Claude Code will prompt you.

### Python Package Installation

For Python-based MCP servers, install in your project virtual environment:

```bash
# Activate virtual environment
source .venv/bin/activate

# Install MCP server packages
pip install mcp-server-analyzer python-lft mcp-server-sqlite
```

## Security Considerations

### GitHub PAT (Personal Access Token)

The GitHub MCP server requires a Personal Access Token for authentication.

#### ✅ Secure Method: Docker `--env-file`

**Why this is secure**:
- Token is read from `.env` file only by Docker container
- No system-wide environment variable exposure
- Token not visible in parent shell or other processes
- Container-isolated credential passing

**Setup**:

1. **Create/verify `.env` file** in project root:
   ```bash
   GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
   ```

2. **Secure the file**:
   ```bash
   chmod 600 .env
   ```

3. **Ensure it's gitignored** (already in `.gitignore`):
   ```bash
   grep -q "^.env$" .gitignore || echo ".env" >> .gitignore
   ```

4. **Configure GitHub MCP server** with `--env-file` flag pointing to absolute path

#### ❌ Insecure Methods (Avoid)

**Don't** put the token in:
- Shell profile (`~/.bashrc`, `~/.zshrc`) - exposes system-wide
- Settings files (`settings.json`) - plain text, easy to accidentally commit
- Environment variables globally - visible to all processes
- `apiKeyHelper` setting - this is for Anthropic API keys only, not MCP env vars

### File Permissions

Ensure sensitive files are properly secured:

```bash
# Secure .env file
chmod 600 .env

# Verify
ls -la .env
# Should show: -rw------- (owner read/write only)
```

### Token Best Practices

1. **Use Fine-Grained PATs**:
   - GitHub → Settings → Developer settings → Fine-grained tokens
   - Limit to specific repositories
   - Set minimal required permissions
   - Set expiration dates

2. **Minimal Scopes**:
   - Only enable: repos, issues, pull_requests, actions, code_security
   - Avoid `admin` or `delete` scopes unless absolutely needed

3. **Rotate Regularly**:
   - Set 90-day expiration on tokens
   - Rotate when team members leave
   - Rotate if token may have been exposed

4. **Monitor Usage**:
   - Check GitHub → Settings → Developer settings → Token usage
   - Review audit logs periodically

## Future Servers

### REST API Tester (rest-api) - Phase 3

**Status**: Not currently installed (planned for Phase 3 - API Integration Polish)

**Purpose**: Test and debug HTTP endpoints during LLM provider API integration

**Why Not Now**: Phase 2 focuses on provider implementation, not API debugging. REST API testing will be more valuable in Phase 3 when polishing and debugging API integrations.

**When to Add**: During Phase 3 when debugging OpenAI/Anthropic/Ollama API calls

**Recommended Package**: `dkmaker-mcp-rest-api` (simpler than `mcp-rest-api`)

**How to Add**:
```bash
claude mcp add-json --scope user rest-api '{
  "command":"npx",
  "args":["-y","dkmaker-mcp-rest-api"],
  "env":{"REST_BASE_URL":"https://api.openai.com/v1"}
}'
```

**Use Cases**:
- Test OpenAI API authentication
- Debug Anthropic API errors
- Validate Ollama API responses
- Inspect API cost tracking endpoints

## Common Mistakes

### ❌ Mistake 1: Wrong Configuration File Location

**Wrong**:
```
~/.config/claude-code/mcp.json  ← Claude Code doesn't read this
```

**Correct**:
```
~/.claude.json                   ← User-scoped servers
.mcp.json (project root)         ← Project-scoped servers
```

### ❌ Mistake 2: Using Relative Paths for Docker --env-file

**Wrong**:
```json
"args": ["--env-file", ".env"]  ← Relative paths may fail
```

**Correct**:
```json
"args": ["--env-file", "/absolute/path/to/project/.env"]
```

### ❌ Mistake 3: Exposing Secrets System-Wide

**Wrong**:
```bash
# In ~/.bashrc
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_token  ← Exposes to all processes
```

**Correct**:
```bash
# In project .env (with chmod 600)
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_token

# Then use Docker --env-file to pass to container only
```

### ❌ Mistake 4: Not Using Scope Flag

**Wrong**:
```bash
# This adds to LOCAL scope (temporary, this session only)
claude mcp add github
```

**Correct**:
```bash
# Use --scope user for persistent, cross-project servers
claude mcp add --scope user github
```

### ❌ Mistake 5: Using apiKeyHelper for MCP Environment Variables

**Wrong**:
```json
{
  "apiKeyHelper": "~/.config/claude-code/token-helper.sh"
}
```

**Why it's wrong**: The `apiKeyHelper` setting is specifically for **Anthropic API keys** used by Claude Code to authenticate with the Anthropic API, not for providing environment variables to MCP servers.

**Correct**: Use Docker's `--env-file` flag or project `.env` file loaded by `preRunCommands`.

### ❌ Mistake 6: Forgetting to Approve Project Servers

**Symptom**: Project-scoped servers don't load

**Solution**: Claude Code prompts for approval on first use. If you dismissed it, run:
```bash
claude mcp reset-project-choices
```

Then restart Claude Code to see the approval prompt again.

## Verification

Verify all servers are connected:

```bash
claude mcp list
```

**Expected Output**:
```
git: ✓ Connected
ollama: ✓ Connected
uv: ✓ Connected
github: ✓ Connected
analyzer: ✓ Connected
python-lft: ✓ Connected
sqlite: ✓ Connected
```

All 7 servers should show "✓ Connected".

## Further Reading

- [MCP Quick Reference](./MCP_QUICK_REFERENCE.md) - Commands cheat sheet
- [MCP Environment Setup](./MCP_ENVIRONMENT_SETUP.md) - Secure credential management
- [MCP Python Packages](./MCP_PYTHON_PACKAGES.md) - Python package installation
- [Official Claude Code MCP Docs](https://docs.claude.com/en/docs/claude-code/mcp)

---

**Configuration Summary**:
- **Active**: 7 servers (4 user + 3 project)
- **All Connected**: ✅ 100% success rate
- **Security**: Docker --env-file for credentials
- **Removed**: rest-api (deferred to Phase 3)

**Last Verified**: 2025-11-07
