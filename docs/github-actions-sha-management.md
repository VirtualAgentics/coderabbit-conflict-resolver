# GitHub Actions SHA Management Guide

## Overview

This document provides comprehensive guidance on how to correctly find, verify, and manage GitHub Actions SHAs in workflow files to prevent "version not found" errors and ensure reliable CI/CD execution.

## The Problem

GitHub Actions SHAs must be exactly 40 characters long. Malformed SHAs (wrong length, incorrect characters, or outdated commits) will cause workflow failures with errors like:
- "version not found"
- "action not found"
- "invalid SHA format"

## How to Find Correct SHAs

### Method 1: Using GitHub CLI (Recommended)

The most reliable way to get the correct SHA for any GitHub Action:

```bash
# Get SHA for a specific tag
gh api repos/actions/checkout/git/refs/tags/v5.0.0 | jq -r '.object.sha'

# Get SHA for a specific branch
gh api repos/actions/checkout/git/refs/heads/main | jq -r '.object.sha'

# Get SHA for a specific commit
gh api repos/actions/checkout/commits/v5.0.0 | jq -r '.sha'
```

### Method 2: Using GitHub API Directly

```bash
# Using curl
curl -s "https://api.github.com/repos/actions/checkout/git/refs/tags/v5.0.0" | jq -r '.object.sha'

# Using wget
wget -qO- "https://api.github.com/repos/actions/checkout/git/refs/tags/v5.0.0" | jq -r '.object.sha'
```

### Method 3: Using GitHub Web Interface

1. Go to the action's repository (e.g., https://github.com/actions/checkout)
2. Navigate to the "Releases" or "Tags" section
3. Find the desired version
4. Click on the tag to see the commit SHA
5. Copy the full 40-character SHA

## Verification Process

### Step 1: Check SHA Length
```bash
# Verify SHA is exactly 40 characters
echo "08c6903cd8c0fde910a37f88322edcfb5dd907a8" | wc -c
# Should output: 41 (40 chars + newline)
```

### Step 2: Validate SHA Format
```bash
# Check if SHA contains only valid hex characters
echo "08c6903cd8c0fde910a37f88322edcfb5dd907a8" | grep -E '^[a-f0-9]{40}$'
# Should return the SHA if valid, empty if invalid
```

### Step 3: Verify SHA Exists
```bash
# Check if the SHA exists in the repository
gh api repos/actions/checkout/commits/08c6903cd8c0fde910a37f88322edcfb5dd907a8
# Should return commit details if valid, error if invalid
```

## Common SHA Issues and Solutions

### Issue 1: Malformed SHAs (Wrong Length)
**Problem**: SHA is not exactly 40 characters
```yaml
# ❌ WRONG - 50 characters
uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfac47a2899e69799

# ✅ CORRECT - 40 characters
uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8
```

**Solution**: Get the correct SHA using GitHub API
```bash
gh api repos/actions/checkout/git/refs/tags/v5.0.0 | jq -r '.object.sha'
```

### Issue 2: Outdated SHAs
**Problem**: SHA points to an old commit that no longer exists
```yaml
# ❌ WRONG - Old SHA
uses: actions/checkout@old-sha-that-does-not-exist

# ✅ CORRECT - Current SHA
uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8
```

**Solution**: Update to the latest SHA for the desired version
```bash
gh api repos/actions/checkout/git/refs/tags/v5.0.0 | jq -r '.object.sha'
```

### Issue 3: Incorrect Repository
**Problem**: SHA from wrong repository
```yaml
# ❌ WRONG - SHA from different action
uses: actions/checkout@sha-from-different-action

# ✅ CORRECT - SHA from correct action
uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8
```

**Solution**: Ensure SHA matches the specific action repository

## Automated SHA Verification

### Script to Check All Workflow SHAs

```bash
#!/bin/bash
# verify-workflow-shas.sh

echo "Verifying all GitHub Actions SHAs in workflow files..."

for file in .github/workflows/*.yml .github/workflows/*.yaml; do
  if [ -f "$file" ]; then
    echo "=== $file ==="
    grep -n "uses: .*@[a-f0-9]" "$file" | while read line; do
      sha=$(echo "$line" | grep -o '@[a-f0-9]*' | tr -d '@')
      length=$(echo "$sha" | wc -c)

      if [ "$length" -ne 41 ]; then  # 40 chars + newline
        echo "❌ MALFORMED: $line (length: $((length-1)))"
      else
        echo "✅ OK: $line"
      fi
    done
    echo
  fi
done
```

### Script to Get Correct SHA for Any Action

```bash
#!/bin/bash
# get-action-sha.sh

if [ $# -ne 2 ]; then
  echo "Usage: $0 <action-repo> <version>"
  echo "Example: $0 actions/checkout v5.0.0"
  exit 1
fi

REPO="$1"
VERSION="$2"

echo "Getting SHA for $REPO@$VERSION..."
SHA=$(gh api repos/$REPO/git/refs/tags/$VERSION | jq -r '.object.sha')

if [ "$SHA" = "null" ] || [ -z "$SHA" ]; then
  echo "❌ Error: Could not find version $VERSION for $REPO"
  exit 1
fi

echo "✅ Correct SHA: $SHA"
echo "Usage: uses: $REPO@$SHA # $VERSION"
```

## Best Practices

### 1. Always Pin to Specific SHAs
```yaml
# ✅ GOOD - Pinned to specific SHA
uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0

# ❌ BAD - Using version tags (can change)
uses: actions/checkout@v5.0.0
```

### 2. Include Version Comments
```yaml
# ✅ GOOD - SHA with version comment
uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0

# ❌ BAD - SHA without version context
uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8
```

### 3. Regular SHA Updates
- Update SHAs when upgrading action versions
- Verify SHAs after major action updates
- Test workflows after SHA changes

### 4. Validation Before Committing
```bash
# Run this before committing workflow changes
./verify-workflow-shas.sh
```

## Troubleshooting

### Error: "version not found"
1. Check SHA length (must be 40 characters)
2. Verify SHA exists in the repository
3. Ensure SHA is from the correct action repository

### Error: "action not found"
1. Verify the action repository name is correct
2. Check if the action is public and accessible
3. Ensure the SHA points to a valid commit

### Error: "invalid SHA format"
1. Check for typos in the SHA
2. Ensure only hexadecimal characters (0-9, a-f)
3. Verify no extra characters or spaces

## Common Actions and Their SHAs

### Frequently Used Actions

```yaml
# Checkout action
- uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0

# Setup Python
- uses: actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c # v6.0.0

# Upload artifact
- uses: actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4 # v5.0.0

# CodeQL init
- uses: github/codeql-action/init@a79638c6e166cca8d437da39b8b88cae58fed1f3 # v4.31.0

# CodeQL analyze
- uses: github/codeql-action/analyze@a79638c6e166cca8d437da39b8b88cae58fed1f3 # v4.31.0
```

**Note**: These SHAs are current as of the last update. Always verify current SHAs using the methods described above.

## Maintenance Schedule

### Monthly
- Check for action updates
- Verify all SHAs are still valid
- Update to latest stable versions

### Before Major Releases
- Audit all workflow SHAs
- Test all workflows
- Update documentation

### When Adding New Actions
- Always get SHA from official source
- Verify SHA before committing
- Test the action in a test workflow first

## Tools and Resources

### GitHub CLI Commands
```bash
# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Authenticate
gh auth login
```

### Useful GitHub API Endpoints
- Repository refs: `GET /repos/{owner}/{repo}/git/refs/tags/{tag}`
- Repository commits: `GET /repos/{owner}/{repo}/commits/{sha}`
- Repository tags: `GET /repos/{owner}/{repo}/tags`

### Validation Tools
- SHA length checker: `echo "$sha" | wc -c`
- SHA format validator: `echo "$sha" | grep -E '^[a-f0-9]{40}$'`
- SHA existence checker: `gh api repos/{owner}/{repo}/commits/{sha}`

## Conclusion

Proper SHA management is crucial for reliable GitHub Actions workflows. Always:
1. Use the GitHub API to get correct SHAs
2. Verify SHA length and format
3. Test workflows after SHA updates
4. Keep documentation current
5. Use automated verification scripts

Following these practices will prevent "version not found" errors and ensure your CI/CD pipelines run reliably.
