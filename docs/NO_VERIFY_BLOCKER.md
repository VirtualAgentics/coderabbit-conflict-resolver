# --no-verify Blocker Documentation

This project includes comprehensive protection against the `--no-verify` option to ensure all quality checks are enforced.

## Overview

The `--no-verify` option bypasses git hooks and pre-commit checks, which violates our quality standards. This project includes multiple layers of protection to prevent this.

## Protection Layers

### 1. Pre-commit Hook
- **File**: `.pre-commit-config.yaml` includes a custom `block-no-verify` hook
- **Function**: Detects `--no-verify` in git commands and blocks them
- **Scope**: Runs on every commit attempt

### 2. Git Hooks
- **Pre-commit**: Blocks commits with `--no-verify`
- **Pre-push**: Blocks pushes with `--no-verify`
- **Commit-msg**: Blocks commit messages containing bypass language

### 3. Git Aliases
- **commit**: Wrapper that blocks `--no-verify` on commit
- **push**: Wrapper that blocks `--no-verify` on push

### 4. Wrapper Script
- **File**: `scripts/git-wrapper.sh`
- **Function**: Can be used to replace the git command entirely
- **Usage**: Add to PATH or use as git replacement

## Installation

The blocker is automatically installed when you run:

```bash
./scripts/install-no-verify-blocker.sh
```

This installs all protection layers.

## Manual Installation

### 1. Install Pre-commit Hooks
```bash
pre-commit install
```

### 2. Install Git Hooks
```bash
cp scripts/pre-push-hook.sh .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

### 3. Install Git Aliases
```bash
git config alias.commit '!f() { if [[ "$*" == *"--no-verify"* ]]; then echo "❌ ERROR: --no-verify option is FORBIDDEN!"; exit 1; fi; git commit "$@"; }; f'
git config alias.push '!f() { if [[ "$*" == *"--no-verify"* ]]; then echo "❌ ERROR: --no-verify option is FORBIDDEN!"; exit 1; fi; git push "$@"; }; f'
```

## How It Works

### Detection Methods

1. **Command Line Arguments**: Checks if `--no-verify` is in the command line
2. **Process Tree**: Examines parent processes for `--no-verify`
3. **Environment Variables**: Checks git environment variables
4. **Commit Messages**: Scans for bypass language in commit messages
5. **Process Monitoring**: Monitors running git processes

### Blocking Behavior

When `--no-verify` is detected:

```
❌ ERROR: --no-verify option is FORBIDDEN!

Quality checks are MANDATORY and cannot be bypassed.
Please fix the issues instead of bypassing them:

  • Fix linting errors: ruff check --fix
  • Fix formatting: black src/ tests/
  • Fix type errors: mypy src/ --strict
  • Fix security issues: bandit -r src/

All quality checks must pass before committing.
This ensures code quality and prevents technical debt.
```

## Bypassing the Blocker

**WARNING**: The blocker is designed to be difficult to bypass. Attempting to bypass it may result in:

1. **Commit Rejection**: Commits with `--no-verify` will be blocked
2. **Push Rejection**: Pushes with `--no-verify` will be blocked
3. **Message Rejection**: Commit messages with bypass language will be blocked

## Troubleshooting

### If the Blocker is Too Restrictive

1. **Fix the Root Cause**: Address the quality issues that are causing problems
2. **Adjust Standards**: If the quality standards are too strict, discuss with the team
3. **Temporary Override**: In extreme emergencies, contact the project maintainers

### If the Blocker Isn't Working

1. **Check Installation**: Ensure all hooks are properly installed
2. **Check Permissions**: Ensure hook files are executable
3. **Check Configuration**: Verify pre-commit and git configurations

## Files

- `scripts/block-no-verify.py` - Main detection script
- `scripts/pre-push-hook.sh` - Pre-push hook
- `scripts/install-no-verify-blocker.sh` - Installation script
- `scripts/git-wrapper.sh` - Git command wrapper
- `.pre-commit-config.yaml` - Pre-commit configuration
- `.git/hooks/pre-commit` - Git pre-commit hook
- `.git/hooks/pre-push` - Git pre-push hook
- `.git/hooks/commit-msg` - Git commit message hook

## Maintenance

### Updating the Blocker

1. **Update Scripts**: Modify the detection logic as needed
2. **Reinstall**: Run the installation script again
3. **Test**: Verify the blocker still works correctly

### Removing the Blocker

```bash
# Remove pre-commit hooks
pre-commit uninstall

# Remove git hooks
rm .git/hooks/pre-commit
rm .git/hooks/pre-push
rm .git/hooks/commit-msg

# Remove git aliases
git config --unset alias.commit
git config --unset alias.push
```

## Best Practices

1. **Never Use --no-verify**: Always fix quality issues instead
2. **Regular Testing**: Test the blocker periodically
3. **Team Education**: Ensure all team members understand the importance
4. **Documentation**: Keep this documentation up to date

## Emergency Procedures

In extreme emergencies where the blocker must be bypassed:

1. **Contact Maintainers**: Get approval from project maintainers
2. **Document Reason**: Clearly document why the bypass was necessary
3. **Fix Immediately**: Address the quality issues in the next commit
4. **Review Process**: Review the blocker to prevent future emergencies

## Conclusion

The `--no-verify` blocker is a critical component of our quality assurance process. It ensures that all code meets our standards and prevents technical debt from accumulating. By following the guidelines in this document, you can work effectively within the quality framework while maintaining high code standards.
