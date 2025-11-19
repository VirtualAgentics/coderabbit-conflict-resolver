# MCP Server Setup Guide

Complete guide to the Model Context Protocol (MCP) server configured in this project.

**Last Updated**: 2025-11-11
**Active Server**: GitHub MCP (connected ✓)

## Table of Contents

1. [Overview](#overview)
2. [Why GitHub MCP Only?](#why-github-mcp-only)
3. [Setup Instructions](#setup-instructions)
4. [Security Considerations](#security-considerations)
5. [Usage Examples](#usage-examples)
6. [Troubleshooting](#troubleshooting)

## Overview

This project uses **GitHub MCP server** for GitHub API integration with Claude Code.

### What is MCP?

The Model Context Protocol (MCP) allows Claude Code to communicate with external tools and services. In this project, we use MCP specifically for GitHub integration, providing capabilities like:

* Creating and managing pull requests
* Listing and searching issues
* Managing code scanning alerts
* Working with branches and commits
* Accessing repository information

### Why MCP for GitHub?

**Benefits of GitHub MCP**:

* **Structured API**: Better than raw `gh` CLI commands for complex operations
* **Rich PR Creation**: Easy to create PRs with detailed, formatted descriptions
* **Type Safety**: Validated parameters ensure correct API usage
* **Comprehensive**: Access to full GitHub API (repos, issues, PRs, actions, security)

**For other tools (git, linting, etc.)**: Standard bash commands work better and are more flexible.

## Why GitHub MCP Only?

After evaluating multiple MCP servers, we found:

### ✅ GitHub MCP - HIGH VALUE

* **Genuinely useful** for PR and issue management
* Better than `gh` CLI for complex operations
* Structured parameters prevent mistakes
* Used frequently in practice

### ❌ Other MCPs - LOW VALUE

Removed due to redundancy with bash commands:

* **git MCP**: Bash git commands are simpler and more flexible
* **ollama MCP**: Direct API calls work fine
* **uv/pip MCPs**: Bash commands are more straightforward
* **analyzer/linting MCPs**: Bash tool invocation is clearer
* **sqlite MCP**: Not needed for this project

**Result**: 87.5% reduction in complexity (8 servers → 1 server)

## Setup Instructions

### Prerequisites

* **Docker**: Required for GitHub MCP server
* **GitHub Personal Access Token**: For API authentication

### Step 1: Install Docker

If not already installed:

```bash
# macOS (via Homebrew)
brew install docker

# Ubuntu/Debian
sudo apt-get update && sudo apt-get install docker.io

# Verify installation
docker --version

```

### Step 2: Create GitHub Personal Access Token

1. Go to: <https://github.com/settings/tokens>
2. Click "Generate new token" → "Generate new token (classic)"
3. Set scopes:
   * `repo` (Full control of private repositories)
   * `read:org` (Read org and team membership, if working with organization repos)
4. Generate token and **save it securely**

### Step 3: Configure Environment Variables

Create or update `.env` file in project root:

```bash
# GitHub Personal Access Token for API access
GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here

```

**Security**: The `.env` file is already in `.gitignore` - never commit tokens!

### Step 4: Add GitHub MCP Server

If not already configured:

```bash
# This configures GitHub MCP globally (available in all projects)
claude mcp add github \
  --transport docker \
  --image ghcr.io/github/github-mcp-server:latest \
  --env-file .env \
  --env GITHUB_TOOLSETS=repos,issues,pull_requests,actions,code_security \
  --scope user

```

**Note**: This command is for reference only. The server should already be configured.

### Step 5: Verify Setup

```bash
# List all MCP servers
claude mcp list

# Expected output
# github: docker run -i --rm --env-file .env ... - ✓ Connected

```

## Security Considerations

### GitHub Token Security

**DO**:

* ✅ Store token in `.env` file (gitignored)
* ✅ Use environment variables only
* ✅ Regenerate tokens periodically
* ✅ Use minimal required scopes

**DON'T**:

* ❌ Commit tokens to version control
* ❌ Hardcode tokens in config files
* ❌ Share tokens in documentation
* ❌ Grant unnecessary scopes

### Token Scopes

**Minimum required**:

* `repo` - Access private repositories

**Optional but recommended**:

* `read:org` - Read organization membership (for org repos)

**Avoid unless needed**:

* `admin:org` - Full admin access (rarely needed)
* `delete_repo` - Delete repositories (dangerous)

### Revoking Compromised Tokens

If a token is compromised:

1. Go to <https://github.com/settings/tokens>
2. Find the compromised token
3. Click "Delete" or "Regenerate"
4. Update `.env` file with new token
5. Restart Claude Code if running

## Usage Examples

### Creating a Pull Request

```python
# Via Claude Code - GitHub MCP tools are available automatically
# Example: "Create a PR for the current branch"

```

The MCP tool provides structured parameters:

* `owner`: Repository owner
* `repo`: Repository name
* `title`: PR title
* `body`: PR description (supports markdown)
* `head`: Source branch
* `base`: Target branch
* `draft`: Boolean for draft PR

### Listing Issues

```python
# Example: "List open issues in this repository"
# GitHub MCP will use list_issues tool with proper pagination

```

### Managing Code Scanning Alerts

```python
# Example: "Show me open CodeQL alerts"
# GitHub MCP will use list_code_scanning_alerts tool

```

### Working with Branches

```python
# Example: "List all branches in this repo"
# GitHub MCP will use list_branches tool

```

## Troubleshooting

### "GitHub MCP not connected"

**Check 1**: Verify Docker is running

```bash
docker ps

```

**Check 2**: Verify `.env` file exists and contains token

```bash
cat .env | grep GITHUB_PERSONAL_ACCESS_TOKEN

```

**Check 3**: Test GitHub token manually

```bash
curl -H "Authorization: token YOUR_TOKEN" <https://api.github.com/user>

```

**Check 4**: Restart Claude Code

```bash
# Exit and restart Claude Code CLI

```

### "Permission denied" or "404 Not Found"

**Cause**: Insufficient GitHub token permissions

**Fix**: Regenerate token with correct scopes (`repo` at minimum)

### Docker Connection Issues

**Symptom**: MCP server fails to start

**Check Docker daemon**:

```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker

```

**Verify Docker permissions**:

```bash
# Linux - add user to docker group
sudo usermod -aG docker $USER
# Then log out and back in

```

### Rate Limiting

**Symptom**: `403` responses or "rate limit exceeded"

**Cause**: Too many API calls in short time

**Fix**:

* Wait 1 hour for rate limit to reset
* Use authenticated requests (token should handle this automatically)
* Check: <https://api.github.com/rate_limit>

### MCP Server Crashes

**Symptom**: Server shows as disconnected after working previously

**Check 1**: View MCP logs

```bash
# Logs are in Claude Code output panel
# Or check ~/.claude/logs/

```

**Check 2**: Restart MCP server

```bash
claude mcp restart github

```

**Check 3**: Remove and re-add server

```bash
claude mcp remove github --scope user
# Then add again with configuration from Step 4

```

## Configuration Reference

### Current GitHub MCP Configuration

**Scope**: User (global - available in all projects)

**Configuration** (in `~/.claude.json`):

```json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--env-file", "/path/to/project/.env",
        "-e", "GITHUB_TOOLSETS=repos,issues,pull_requests,actions,code_security",
        "ghcr.io/github/github-mcp-server:latest"
      ]
    }
  }
}

```

### Environment Variables

**Required**:

* `GITHUB_PERSONAL_ACCESS_TOKEN`: Your GitHub PAT

**Optional**:

* `GITHUB_TOOLSETS`: Comma-separated list of enabled toolsets (default: all)

## Additional Resources

* **GitHub MCP Documentation**: <https://github.com/github/github-mcp-server>
* **GitHub API Documentation**: <https://docs.github.com/rest>
* **GitHub Token Management**: <https://github.com/settings/tokens>
* **Model Context Protocol Spec**: <https://modelcontextprotocol.io>

## See Also

* [MCP Quick Reference](MCP_QUICK_REFERENCE.md) - GitHub MCP command examples
* [MCP Environment Setup](MCP_ENVIRONMENT_SETUP.md) - GitHub token configuration
* [Getting Started](getting-started.md) - Project setup guide
