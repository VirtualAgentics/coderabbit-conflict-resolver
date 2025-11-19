# MCP Quick Reference

Quick reference for GitHub MCP server commands and operations.

**Last Updated**: 2025-11-11
**Active Server**: GitHub MCP (✓ Connected)

## MCP Management Commands

```bash
# List all MCP servers and their status
claude mcp list

# Add GitHub server (user scope)
claude mcp add github \
  --transport docker \
  --image ghcr.io/github/github-mcp-server:latest \
  --env-file .env \
  --env GITHUB_TOOLSETS=repos,issues,pull_requests,actions,code_security \
  --scope user

# Remove a server
claude mcp remove <server-name> --scope user

# Verify connection
claude mcp list  # Expected: github - ✓ Connected

```

## GitHub MCP Operations

Available through Claude Code (requires `GITHUB_PERSONAL_ACCESS_TOKEN` in `.env`):

### Pull Requests

* Fetch PR details, reviews, and comments
* List, create, update, and merge PRs
* Get PR diffs and file changes
* Manage PR review comments

### Issues

* List, create, update, and close issues
* Add comments to issues
* Manage labels and milestones

### Repository Operations

* List branches and commits
* Get file contents
* Create and update files
* Manage releases and tags

### GitHub Actions

* List workflows and runs
* Get job logs (including failed jobs)
* Re-run failed jobs
* Cancel workflow runs

### Code Security

* List code scanning alerts
* Get alert details
* Monitor security status

## Security Best Practices

### ✅ DO

* Store `GITHUB_PERSONAL_ACCESS_TOKEN` in project `.env` file
* Use `chmod 600 .env` to secure the file
* Add `.env` to `.gitignore`
* Use minimal required token scopes (`repo` at minimum)
* Regenerate tokens periodically

### ❌ DON'T

* Commit tokens to version control
* Share tokens in documentation
* Use overly broad token scopes
* Hardcode tokens in configuration files

## Quick Troubleshooting

### Server Not Connected

```bash
# Check Docker is running
docker ps

# Verify token in .env
cat .env | grep GITHUB_PERSONAL_ACCESS_TOKEN

# Test token manually
curl -H "Authorization: token YOUR_TOKEN" <https://api.github.com/user>

# Restart Claude Code if needed

```

### Permission Errors

**Cause**: Insufficient GitHub token permissions

**Fix**: Regenerate token with correct scopes at <https://github.com/settings/tokens>

* Minimum: `repo` scope
* Recommended: `repo` + `read:org` (for organization repos)

## Configuration Location

**User-scoped server**: `~/.claude.json` (in mcpServers section)

* Available in all projects
* Persistent across sessions

## See Also

* [MCP Servers Setup Guide](./MCP_SERVERS_SETUP.md) - Complete GitHub MCP setup
* [MCP Environment Setup](./MCP_ENVIRONMENT_SETUP.md) - GitHub token configuration
* [Official Claude Code Docs](https://docs.claude.com/en/docs/claude-code/mcp)
