# MCP Environment Variables Setup Guide

This guide explains how to set up environment variables required by MCP servers in this project.

## Overview

As of **2025-11-07**, all sensitive credentials (API tokens, keys) have been removed from MCP configuration files and must be set as environment variables for security.

## Required Environment Variables

### Critical (Required for GitHub MCP Server)

| Variable | Purpose | Required By | How to Get |
|----------|---------|-------------|------------|
| `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub API authentication | github MCP server | [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) |

### Optional (Provider-specific)

| Variable | Purpose | Required By | How to Get |
|----------|---------|-------------|------------|
| `OPENAI_API_KEY` | OpenAI API authentication | OpenAI provider | [OpenAI API Keys](https://platform.openai.com/api-keys) |
| `ANTHROPIC_API_KEY` | Anthropic API authentication | Anthropic provider | [Anthropic Console](https://console.anthropic.com/) |
| `OLLAMA_BASE_URL` | Ollama server URL | ollama MCP server | Default: `http://localhost:11434` |

## Setup Methods

### Method 1: Project .env File (Recommended for This Project) ✅

This project is configured to automatically load environment variables from the project `.env` file using `preRunCommands` in `.claude/settings.json`.

#### Setup Instructions

1. **Ensure .env file exists** in project root:
   ```bash
   cd /home/bofh/projects/review-bot-automator
   ls -la .env  # Should exist and be gitignored
   ```

2. **Add your tokens to .env**:
   ```bash
   # Edit the .env file
   nano .env

   # Add or verify these lines:
   GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
   ANTHROPIC_API_KEY=sk-ant-your_key_here
   OPENAI_API_KEY=sk-your_key_here
   OLLAMA_BASE_URL=http://localhost:11434
   ```

3. **Verify preRunCommands configuration**:
   The `.claude/settings.json` should have:
   ```json
   {
     "preRunCommands": [
       "test -f .env && set -a && source .env && set +a || true",
       "test -d .venv && source .venv/bin/activate || true"
     ]
   }
   ```

4. **Restart Claude Code**:
   Environment variables will be loaded automatically on startup.

**Benefits**:
- ✓ Project-specific configuration
- ✓ Automatically loaded by Claude Code
- ✓ Already gitignored (.env in .gitignore)
- ✓ Easy for team members (each creates their own .env)
- ✓ Works with MCP servers via Docker (`-e` flag passes from environment)

**How It Works**:
- `set -a` exports all variables when sourcing
- `source .env` loads variables from file
- `set +a` stops auto-exporting
- MCP servers inherit these environment variables

### Method 2: Shell Profile (Alternative for System-Wide Setup)

Add environment variables to your shell profile file for persistent availability across all projects.

#### For Bash Users (~/.bashrc or ~/.bash_profile)

```bash
# Edit your bash profile
nano ~/.bashrc

# Add the following lines at the end:
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
export ANTHROPIC_API_KEY="sk-ant-your_key_here"
export OPENAI_API_KEY="sk-your_key_here"
export OLLAMA_BASE_URL="http://localhost:11434"

# Save and reload
source ~/.bashrc
```

#### For Zsh Users (~/.zshrc)

```bash
# Edit your zsh profile
nano ~/.zshrc

# Add the following lines at the end:
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
export ANTHROPIC_API_KEY="sk-ant-your_key_here"
export OPENAI_API_KEY="sk-your_key_here"
export OLLAMA_BASE_URL="http://localhost:11434"

# Save and reload
source ~/.zshrc
```

#### For Fish Users (~/.config/fish/config.fish)

```fish
# Edit your fish config
nano ~/.config/fish/config.fish

# Add the following lines:
set -gx GITHUB_PERSONAL_ACCESS_TOKEN "ghp_your_token_here"
set -gx ANTHROPIC_API_KEY "sk-ant-your_key_here"
set -gx OPENAI_API_KEY "sk-your_key_here"
set -gx OLLAMA_BASE_URL "http://localhost:11434"

# Save and reload
source ~/.config/fish/config.fish
```

### Method 2: Session-Only (Temporary)

For temporary setup in the current shell session only:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
export ANTHROPIC_API_KEY="sk-ant-your_key_here"
export OPENAI_API_KEY="sk-your_key_here"
export OLLAMA_BASE_URL="http://localhost:11434"
```

**Note**: These will be lost when you close the terminal.

### Method 3: direnv (Alternative Project-Specific Method)

[direnv](https://direnv.net/) automatically loads environment variables when entering a project directory.

#### Installation

```bash
# Ubuntu/Debian
sudo apt install direnv

# macOS
brew install direnv

# Add direnv hook to your shell (example for bash)
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
source ~/.bashrc
```

#### Usage

```bash
# Create .envrc in project root
cd /home/bofh/projects/review-bot-automator
nano .envrc

# Add environment variables:
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token_here"
export ANTHROPIC_API_KEY="sk-ant-your_key_here"
export OPENAI_API_KEY="sk-your_key_here"
export OLLAMA_BASE_URL="http://localhost:11434"

# Allow direnv to load this file
direnv allow .

# Add .envrc to .gitignore (if not already there)
echo ".envrc" >> .gitignore
```

**Benefits**:
- ✓ Automatically loads when entering project directory
- ✓ Automatically unloads when leaving project directory
- ✓ Can be version-controlled (but keep tokens out!)
- ✓ Team members can create their own `.envrc.local` (gitignored)

**Note**: This project already uses `.env` with `preRunCommands`, so direnv is optional. Use direnv if you want shell-level automatic loading.

### Method 4: systemd Environment (Linux System-Wide)

For system-wide availability across all users and services:

```bash
# Edit systemd user environment
systemctl --user edit-environment

# Or add to ~/.config/environment.d/envvars.conf
mkdir -p ~/.config/environment.d
nano ~/.config/environment.d/mcp.conf

# Add variables:
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
ANTHROPIC_API_KEY=sk-ant-your_key_here
OPENAI_API_KEY=sk-your_key_here
OLLAMA_BASE_URL=http://localhost:11434
```

## Verification

After setting up environment variables, verify they're accessible:

```bash
# Check if variables are set
echo $GITHUB_PERSONAL_ACCESS_TOKEN
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY
echo $OLLAMA_BASE_URL

# Test GitHub token (should return your user info)
curl -H "Authorization: token $GITHUB_PERSONAL_ACCESS_TOKEN" https://api.github.com/user

# Check all environment variables at once
env | grep -E "(GITHUB|ANTHROPIC|OPENAI|OLLAMA)"
```

## Obtaining API Tokens

### GitHub Personal Access Token

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Give it a descriptive name (e.g., "MCP Server Access")
4. Set expiration (recommended: 90 days)
5. Select scopes:
   - ✓ `repo` (Full control of private repositories)
   - ✓ `read:org` (Read org and team membership)
   - ✓ `read:user` (Read user profile data)
   - ✓ `workflow` (Update GitHub Actions workflows) - optional
6. Click "Generate token"
7. **Copy the token immediately** (you won't be able to see it again)

### Anthropic API Key

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign in with your account
3. Navigate to "API Keys" section
4. Click "Create Key"
5. Give it a name and create
6. Copy the API key (starts with `sk-ant-`)

### OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign in with your account
3. Navigate to "API Keys" section
4. Click "Create new secret key"
5. Give it a name and create
6. Copy the API key (starts with `sk-`)

## Security Best Practices

### DO ✅

- ✅ Store tokens in environment variables, not in files
- ✅ Add `.envrc`, `.env`, and similar files to `.gitignore`
- ✅ Use shell profiles for personal workstations
- ✅ Use secret management tools for production/team environments
- ✅ Rotate tokens regularly (90-day policy recommended)
- ✅ Use minimal token scopes (principle of least privilege)
- ✅ Revoke tokens immediately if compromised
- ✅ Keep tokens in password managers as backup

### DON'T ❌

- ❌ NEVER commit tokens to version control
- ❌ NEVER hardcode tokens in configuration files
- ❌ NEVER share tokens via email or chat
- ❌ NEVER use production tokens for development
- ❌ NEVER commit `.env` or `.envrc` files
- ❌ NEVER expose tokens in logs or error messages
- ❌ NEVER use tokens with more permissions than needed

## Troubleshooting

### Environment Variable Not Found

**Problem**: MCP server can't find environment variable

**Solutions**:
1. Verify variable is set: `echo $VARIABLE_NAME`
2. Check for typos in variable name (case-sensitive!)
3. Ensure shell profile has been reloaded: `source ~/.bashrc`
4. Restart Claude Code after setting variables
5. If using direnv, ensure `direnv allow` was run

### Token Authentication Fails

**Problem**: API returns authentication error

**Solutions**:
1. Verify token is not expired (check provider dashboard)
2. Ensure token has required scopes/permissions
3. Test token with curl command (see Verification section)
4. Regenerate token if compromised or invalid
5. Check for extra spaces or quotes in token value

### Variable Not Available to Claude Code

**Problem**: Variable works in terminal but not in Claude Code

**Solutions**:
1. **Restart Claude Code completely** (not just reload window)
2. Start Claude Code from a terminal where variables are set:
   ```bash
   # Set variables in terminal
   export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_..."

   # Launch Claude Code from same terminal
   claude
   ```
3. Use system-wide environment (systemd method)
4. Check Claude Code logs for errors

### Shell Profile Not Loading

**Problem**: Variables set in `.bashrc` but not available

**Solutions**:
1. Check which shell you're using: `echo $SHELL`
2. Ensure you're editing the correct profile file:
   - Login shells: `~/.bash_profile` or `~/.profile`
   - Interactive shells: `~/.bashrc`
3. Source the file manually: `source ~/.bashrc`
4. Start a new terminal session
5. Check for syntax errors in profile file

## For Team Members

When onboarding to this project:

1. **Read this guide** to understand environment variable setup
2. **Obtain your own API tokens** (never share tokens between team members)
3. **Create your `.env` file** in the project root:
   ```bash
   cd /home/bofh/projects/review-bot-automator
   cp .env.example .env  # If example exists, or create from scratch
   nano .env  # Add your tokens
   ```
4. **Set required variables** in `.env` (at minimum: `GITHUB_PERSONAL_ACCESS_TOKEN`)
5. **Verify setup** using the verification commands above
6. **Restart Claude Code** - it will automatically load `.env` via `preRunCommands`
7. **Test MCP servers** by running `/mcp` in Claude Code

**IMPORTANT**: The `.env` file is gitignored. Each team member creates their own with their personal API tokens.

## Additional Resources

- [GitHub Personal Access Tokens Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- [direnv Official Documentation](https://direnv.net/)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [MCP Servers Setup Guide](./MCP_SERVERS_SETUP.md)
- [Python Package Installation Guide](./MCP_PYTHON_PACKAGES.md)

## Support

If you encounter issues:

1. Check troubleshooting section above
2. Review [MCP_SERVERS_SETUP.md](./MCP_SERVERS_SETUP.md) troubleshooting
3. Search project issues for similar problems
4. Create a new issue with the `mcp-servers` label

---

**Last Updated**: 2025-11-07
**Maintained By**: Project team
