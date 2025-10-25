#!/usr/bin/env python3
"""Pre-commit hook to block the --no-verify option.

This hook prevents commits and pushes that bypass quality checks,
ensuring all code quality standards are enforced.
"""

import os
import subprocess
import sys


def check_git_command_for_no_verify() -> bool:
    """Check if the current git command contains --no-verify."""
    # Check command line arguments
    if "--no-verify" in sys.argv:
        return True

    # Check environment variables that might contain the command
    for env_var in ["GIT_INDEX_FILE", "GIT_EDITOR", "GIT_SEQUENCE_EDITOR"]:
        if env_var in os.environ and "--no-verify" in os.environ[env_var]:
            return True

    # Check if we're in a git hook context and examine the command history
    if "GIT_INDEX_FILE" in os.environ:
        try:
            # Get the command that triggered this hook - use full path for security
            cmd = subprocess.run(  # noqa: S603
                ["/bin/ps", "-o", "args=", "-p", str(os.getppid())],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            if "--no-verify" in cmd.stdout:
                return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Also check the git log for recent commits with --no-verify
        try:
            # Check if the last commit was made with --no-verify - use full path for security
            result = subprocess.run(
                ["/usr/bin/git", "log", "-1", "--pretty=format:%B"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            # This is a heuristic - if we detect patterns that suggest --no-verify was used
            if "bypass" in result.stdout.lower() or "no-verify" in result.stdout.lower():
                return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Check current working directory for any git commands in progress
    try:
        # Look for any running git processes with --no-verify - use full path for security
        result = subprocess.run(
            ["/bin/pgrep", "-f", "git.*--no-verify"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Additional check: Look for --no-verify in the current process tree
    try:
        # Get the full command line of the current process
        with open("/proc/self/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8").replace("\x00", " ")
            if "--no-verify" in cmdline:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    # Check if we're being called from a git command that might have --no-verify
    try:
        # Check the parent process command line
        with open(f"/proc/{os.getppid()}/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8").replace("\x00", " ")
            if "--no-verify" in cmdline:
                return True
    except (FileNotFoundError, PermissionError):
        pass

    return False


def main() -> int:
    """Main function to block --no-verify usage."""
    if check_git_command_for_no_verify():
        # Use sys.stderr for error messages instead of print
        error_msg = """❌ ERROR: --no-verify option is FORBIDDEN!

Quality checks are MANDATORY and cannot be bypassed.
Please fix the issues instead of bypassing them:

  • Fix linting errors: ruff check --fix
  • Fix formatting: black src/ tests/
  • Fix type errors: mypy src/ --strict
  • Fix security issues: bandit -r src/

All quality checks must pass before committing.
This ensures code quality and prevents technical debt.

If you're facing persistent issues, please:
  1. Fix the root cause of the quality issues
  2. Ask for help in the project's issue tracker
  3. Consider if the quality standards need adjustment"""

        sys.stderr.write(error_msg + "\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
