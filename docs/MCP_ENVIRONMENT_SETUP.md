# MCP Environment Setup Guide

This guide explains how to securely configure GitHub Personal Access Token for the GitHub MCP server.

**Last Updated**: 2025-11-11

## Overview

The GitHub MCP server requires a GitHub Personal Access Token for API authentication. This token must be stored securely as an environment variable.

## Required Environment Variable

| Variable | Purpose | How to Get |
| ---------- | --------- | ------------ |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub API authentication | [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) |

## Setup Method: Project .env File (Recommended)

This project is configured to automatically load environment variables from `.env` using `preRunCommands` in `.claude/settings.json`.

### Step 1: Create .env File

```bash
# Navigate to project root
cd /home/bofh/projects/coderabbit-conflict-resolver

# Create .env file (if it doesn't exist)
touch .env

# Secure the file permissions
chmod 600 .env

```

### Step 2: Add Your GitHub Token

Edit `.env` and add:

```bash
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here

```

**Important**: Replace `ghp_your_token_here` with your actual GitHub token.

### Step 3: Verify Configuration

The `.claude/settings.json` file should contain:

```json
{
  "preRunCommands": [
    "test -f .env && set -a && source .env && set +a || true",
    "test -d .venv && source .venv/bin/activate || true"
  ]
}

```

This automatically loads `.env` when Claude Code starts.

### Step 4: Restart Claude Code

Environment variables will be loaded automatically on startup.

### Benefits of This Method

* ✓ Project-specific configuration
* ✓ Automatically loaded by Claude Code
* ✓ Already gitignored (`.env` in `.gitignore`)
* ✓ Easy for team members (each creates their own `.env`)
* ✓ Docker containers inherit environment variables via `-e` flag

## Obtaining a GitHub Personal Access Token

### Step-by-Step Instructions

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click **"Generate new token (classic)"**
3. Give it a descriptive name (e.g., "MCP Server Access")
4. Set expiration (recommended: 90 days)
5. Select scopes:
   * ✓ `repo` - Full control of private repositories (required)
   * ✓ `read:org` - Read org and team membership (optional, for organization repos)
6. Click **"Generate token"**
7. **Copy the token immediately** (you won't be able to see it again)

### Token Format

GitHub Personal Access Tokens start with `ghp_` and are followed by alphanumeric characters.

**Example**: `ghp_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8`

## Verification

After setting up your token, verify it works:

```bash
# Check if variable is set
echo $GITHUB_PERSONAL_ACCESS_TOKEN

# Test GitHub token (should return your user info)
curl -H "Authorization: token $GITHUB_PERSONAL_ACCESS_TOKEN" https://api.github.com/user

# Verify token is loaded in environment
env | grep GITHUB_PERSONAL_ACCESS_TOKEN

```

## Security Best Practices

### ✅ DO

* ✅ Store token in `.env` file (gitignored)
* ✅ Use `chmod 600 .env` to secure file permissions
* ✅ Rotate tokens regularly (90-day policy recommended)
* ✅ Use minimal token scopes (`repo` at minimum)
* ✅ Revoke tokens immediately if compromised
* ✅ Keep tokens in password manager as backup
* ✅ Each team member uses their own token

### ❌ DON'T

* ❌ NEVER commit tokens to version control
* ❌ NEVER hardcode tokens in configuration files
* ❌ NEVER share tokens via email or chat
* ❌ NEVER commit `.env` file to git
* ❌ NEVER expose tokens in logs or error messages
* ❌ NEVER use tokens with more permissions than needed
* ❌ NEVER share tokens between team members

## Troubleshooting

### Token Not Found

**Problem**: MCP server can't find `GITHUB_PERSONAL_ACCESS_TOKEN`

**Solutions**:

1. Verify variable is set: `echo $GITHUB_PERSONAL_ACCESS_TOKEN`
2. Check `.env` file exists: `ls -la .env`
3. Ensure `.env` contains token (no extra spaces or quotes)
4. Restart Claude Code completely
5. Verify `preRunCommands` in `.claude/settings.json`

### Authentication Fails

**Problem**: GitHub API returns 401 Unauthorized

**Solutions**:

1. Verify token has not expired (check [GitHub tokens page](https://github.com/settings/tokens))
2. Ensure token has `repo` scope minimum
3. Test token manually with curl (see Verification section)
4. Regenerate token if compromised
5. Check for extra spaces or quotes in token value

### Token Works in Terminal but Not in Claude Code

**Problem**: Variable works in terminal but MCP server fails

**Solutions**:

1. **Restart Claude Code completely** (not just reload)
2. Check Docker can access environment:

   ```bash
   docker run --rm -e GITHUB_PERSONAL_ACCESS_TOKEN alpine env | grep GITHUB

   ```

3. Verify `.env` file is in project root
4. Check Claude Code logs for errors

### Permission Denied Errors

**Problem**: GitHub API returns 403 Forbidden

**Cause**: Insufficient token scopes

**Fix**:

1. Go to [GitHub tokens page](https://github.com/settings/tokens)
2. Delete old token
3. Generate new token with correct scopes (`repo` at minimum)
4. Update `.env` file with new token
5. Restart Claude Code

## For Team Members

When joining this project:

1. **Create your `.env` file** in project root:

   ```bash
   cd /home/bofh/projects/coderabbit-conflict-resolver
   touch .env
   chmod 600 .env

   ```

2. **Obtain your own GitHub Personal Access Token** (see instructions above)

3. **Add token to `.env`**:

   ```bash
   echo "GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token" >> .env

   ```

4. **Verify setup**:

   ```bash
   curl -H "Authorization: token $(cat .env | grep GITHUB | cut -d'=' -f2)" https://api.github.com/user

   ```

5. **Restart Claude Code** - it will automatically load `.env`

6. **Verify GitHub MCP is connected**:

   ```bash
   claude mcp list
   # Should show: github - ✓ Connected

   ```

**IMPORTANT**: The `.env` file is gitignored. Each team member creates their own with their personal token.

## Additional Resources

* [GitHub Personal Access Tokens Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
* [GitHub API Documentation](https://docs.github.com/rest)
* [MCP Servers Setup Guide](./MCP_SERVERS_SETUP.md)
* [MCP Quick Reference](./MCP_QUICK_REFERENCE.md)

## Support

If you encounter issues:

1. Check troubleshooting section above
2. Review [MCP_SERVERS_SETUP.md](./MCP_SERVERS_SETUP.md) troubleshooting
3. Search project issues for similar problems
4. Create a new issue with the `mcp-servers` label
