#!/usr/bin/env python3
"""Bump patch version in pyproject.toml and __init__.py.

This script increments the patch version (X.Y.Z -> X.Y.(Z+1)) in both
pyproject.toml and src/review_bot_automator/__init__.py to keep them in sync.

Usage:
    python scripts/bump_version.py

Output:
    Prints the version change (e.g., "2.0.0 -> 2.0.1")
    Sets GitHub Actions output variable 'new_version' for use in workflows
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def get_current_version() -> str:
    """Read version from pyproject.toml.

    Returns:
        The current version string (e.g., "2.0.0")

    Raises:
        ValueError: If version cannot be found in pyproject.toml
    """
    pyproject = Path("pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', pyproject, re.MULTILINE)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def bump_patch(version: str) -> str:
    """Increment patch version: X.Y.Z -> X.Y.(Z+1).

    Args:
        version: Current version string (e.g., "2.0.0")

    Returns:
        New version string with incremented patch (e.g., "2.0.1")
    """
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def update_pyproject(old_version: str, new_version: str) -> None:
    """Update version in pyproject.toml.

    Args:
        old_version: Current version to replace
        new_version: New version to set
    """
    path = Path("pyproject.toml")
    content = path.read_text()
    updated = content.replace(f'version = "{old_version}"', f'version = "{new_version}"')
    path.write_text(updated)


def update_init(old_version: str, new_version: str) -> None:
    """Update __version__ in __init__.py.

    Args:
        old_version: Current version to replace
        new_version: New version to set
    """
    path = Path("src/review_bot_automator/__init__.py")
    content = path.read_text()
    updated = content.replace(f'__version__ = "{old_version}"', f'__version__ = "{new_version}"')
    path.write_text(updated)


def main() -> int:
    """Main entry point for version bumping.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        current = get_current_version()
        new = bump_patch(current)

        update_pyproject(current, new)
        update_init(current, new)

        # Print version change for human readers
        print(f"{current} -> {new}")

        # Output new version for GitHub Actions (using new GITHUB_OUTPUT format)
        # Note: ::set-output is deprecated, but kept for backward compatibility
        print(f"::set-output name=new_version::{new}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
