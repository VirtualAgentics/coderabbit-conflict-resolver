#!/usr/bin/env python3
r"""Bump patch version and update CHANGELOG.

This script increments the patch version (X.Y.Z -> X.Y.(Z+1)) in both
pyproject.toml and src/review_bot_automator/__init__.py to keep them in sync.
It can also update CHANGELOG.md with a new version entry.

Usage:
    python scripts/bump_version.py                    # Bump version only
    python scripts/bump_version.py --changelog \
        --version 2.0.1 --date 2025-01-01 \
        --entry "* Fix bug (#123)"                    # Update changelog

Output:
    Prints the version change (e.g., "2.0.0 -> 2.0.1")
    Sets GitHub Actions output variable 'new_version' for use in workflows
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

PYPROJECT_PATH = Path("pyproject.toml")
INIT_PATH = Path("src/review_bot_automator/__init__.py")
CHANGELOG_PATH = Path("CHANGELOG.md")


def get_current_version() -> str:
    """Read version from pyproject.toml.

    Returns:
        The current version string (e.g., "2.0.0")

    Raises:
        ValueError: If version cannot be found in pyproject.toml
    """
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
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

    Raises:
        ValueError: If version format is invalid
    """
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid version format: {version} (expected X.Y.Z)")
    major, minor, patch = parts
    return f"{major}.{minor}.{int(patch) + 1}"


def update_pyproject(old_version: str, new_version: str) -> None:
    """Update version in pyproject.toml.

    Args:
        old_version: Current version to replace
        new_version: New version to set

    Raises:
        ValueError: If version string not found (prevents silent desync)
    """
    path = Path("pyproject.toml")
    content = path.read_text(encoding="utf-8")
    updated = content.replace(f'version = "{old_version}"', f'version = "{new_version}"')
    if updated == content:
        raise ValueError(
            f'Version {old_version} not found in {path} as `version = "{old_version}"`'
        )
    path.write_text(updated, encoding="utf-8")


def update_init(old_version: str, new_version: str) -> None:
    """Update __version__ in __init__.py.

    Args:
        old_version: Current version to replace
        new_version: New version to set

    Raises:
        ValueError: If version string not found (prevents silent desync)
    """
    content = INIT_PATH.read_text(encoding="utf-8")
    updated = content.replace(f'__version__ = "{old_version}"', f'__version__ = "{new_version}"')
    if updated == content:
        raise ValueError(f'__version__ = "{old_version}" not found in {INIT_PATH}')
    INIT_PATH.write_text(updated, encoding="utf-8")


def update_changelog(version: str, date: str, entry: str) -> None:
    """Insert new version section after [Unreleased].

    Args:
        version: New version string (e.g., "2.0.1")
        date: Release date in YYYY-MM-DD format
        entry: Changelog entry text (e.g., "* Fix bug (#123)")

    Raises:
        FileNotFoundError: If CHANGELOG.md doesn't exist
        ValueError: If [Unreleased] section not found
    """
    if not CHANGELOG_PATH.exists():
        raise FileNotFoundError("CHANGELOG.md not found")

    lines = CHANGELOG_PATH.read_text(encoding="utf-8").splitlines(keepends=True)

    for i, line in enumerate(lines):
        if line.strip() == "## [Unreleased]":
            new_section = [
                "\n",
                f"## [{version}] - {date}\n",
                "\n",
                "### Changed\n",
                "\n",
                f"{entry}\n",
            ]
            lines[i + 1 : i + 1] = new_section
            break
    else:
        raise ValueError("Could not find [Unreleased] section in CHANGELOG.md")

    CHANGELOG_PATH.write_text("".join(lines), encoding="utf-8")


def bump_version() -> tuple[str, str]:
    """Bump patch version with atomic updates and rollback.

    Returns:
        Tuple of (old_version, new_version)

    Raises:
        FileNotFoundError: If required files don't exist
        RuntimeError: If update fails (after rollback attempt)
    """
    # Validate files exist before modifying
    if not PYPROJECT_PATH.exists():
        raise FileNotFoundError("pyproject.toml not found")
    if not INIT_PATH.exists():
        raise FileNotFoundError("__init__.py not found")

    current = get_current_version()
    new = bump_patch(current)

    # Update with rollback on failure
    update_pyproject(current, new)
    try:
        update_init(current, new)
    except Exception as e:
        # Rollback pyproject.toml on failure
        update_pyproject(new, current)
        raise RuntimeError("Failed to update __init__.py, rolled back pyproject.toml") from e

    return current, new


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Bump patch version and optionally update CHANGELOG"
    )
    parser.add_argument(
        "--changelog",
        action="store_true",
        help="Update CHANGELOG.md instead of bumping version",
    )
    parser.add_argument(
        "--version",
        help="Version for changelog entry (required with --changelog)",
    )
    parser.add_argument(
        "--date",
        help="Date for changelog entry in YYYY-MM-DD (required with --changelog)",
    )
    parser.add_argument(
        "--entry",
        help="Changelog entry text (required with --changelog)",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point for version bumping.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        args = parse_args()

        if args.changelog:
            # Update changelog mode
            if not all([args.version, args.date, args.entry]):
                print(
                    "Error: --version, --date, and --entry are required " "with --changelog",
                    file=sys.stderr,
                )
                return 1
            update_changelog(args.version, args.date, args.entry)
            print(f"Updated CHANGELOG.md with version {args.version}")
            return 0

        # Bump version mode (default)
        current, new = bump_version()

        # Print version change for human readers
        print(f"{current} -> {new}")

        # Output new version for GitHub Actions
        github_output = os.getenv("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a", encoding="utf-8") as f:
                f.write(f"new_version={new}\n")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
