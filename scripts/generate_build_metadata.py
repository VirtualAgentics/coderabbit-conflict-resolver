#!/usr/bin/env python3
"""Generate build metadata for package artifacts.

This script extracts version information, git metadata, and build details
to create a comprehensive metadata.json file for package artifacts.
"""

import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def get_project_root() -> Path:
    """Get the project root directory.

    Returns:
        Path: Project root directory.
    """
    return Path(__file__).parent.parent


def extract_version_from_pyproject() -> str:
    """Extract version from pyproject.toml.

    Returns:
        str: Version string from pyproject.toml.

    Raises:
        ValueError: If version not found in pyproject.toml.
    """
    pyproject_path = get_project_root() / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

    content = pyproject_path.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise ValueError("Version not found in pyproject.toml")

    return match.group(1)


def extract_version_from_init() -> str:
    """Extract version from __init__.py.

    Returns:
        str: Version string from __init__.py.

    Raises:
        ValueError: If version not found in __init__.py.
    """
    init_path = get_project_root() / "src" / "review_bot_automator" / "__init__.py"
    if not init_path.exists():
        raise FileNotFoundError(f"__init__.py not found at {init_path}")

    content = init_path.read_text()
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise ValueError("__version__ not found in __init__.py")

    return match.group(1)


def validate_versions_match() -> str:
    """Validate that versions match across pyproject.toml and __init__.py.

    Returns:
        str: The validated version string.

    Raises:
        ValueError: If versions don't match.
    """
    pyproject_version = extract_version_from_pyproject()
    init_version = extract_version_from_init()

    if pyproject_version != init_version:
        raise ValueError(
            f"Version mismatch: pyproject.toml has '{pyproject_version}' "
            f"but __init__.py has '{init_version}'"
        )

    return pyproject_version


def run_git_command(args: list[str]) -> str:
    """Run a git command and return the output.

    Args:
        args: Git command arguments.

    Returns:
        str: Command output, stripped of whitespace.

    Raises:
        subprocess.CalledProcessError: If git command fails.
    """
    result = subprocess.run(
        ["git"] + args,  # noqa: RUF005 - avoid S607 security warning
        cwd=get_project_root(),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_git_metadata() -> dict[str, str]:
    """Collect git metadata.

    Returns:
        dict: Git metadata including commit, branch, and tag info.
    """
    metadata = {}

    try:
        metadata["commit_sha"] = run_git_command(["rev-parse", "HEAD"])
        metadata["commit_sha_short"] = run_git_command(["rev-parse", "--short", "HEAD"])
        metadata["branch"] = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])

        # Try to get the tag if we're on a tagged commit
        try:
            metadata["tag"] = run_git_command(["describe", "--exact-match", "--tags"])
        except subprocess.CalledProcessError:
            metadata["tag"] = None

        # Get the remote URL (if available)
        try:
            metadata["remote_url"] = run_git_command(["config", "--get", "remote.origin.url"])
        except subprocess.CalledProcessError:
            metadata["remote_url"] = None

    except subprocess.CalledProcessError as e:
        print(f"Warning: Git command failed: {e}", file=sys.stderr)
        # Return partial metadata if some git commands fail

    return metadata


def get_build_metadata() -> dict[str, Any]:
    """Collect build environment metadata.

    Returns:
        dict: Build metadata including timestamp, Python version, etc.
    """
    ver = sys.version_info
    metadata = {
        "build_timestamp": datetime.now(UTC).isoformat(),
        "python_version": f"{ver.major}.{ver.minor}.{ver.micro}",
        "python_implementation": sys.implementation.name,
    }

    # Collect GitHub Actions environment variables
    github_env_vars = [
        "GITHUB_WORKFLOW",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_JOB",
        "GITHUB_ACTION",
        "GITHUB_ACTOR",
        "GITHUB_REPOSITORY",
        "GITHUB_REF",
        "GITHUB_SHA",
        "GITHUB_SERVER_URL",
    ]

    for var in github_env_vars:
        value = os.environ.get(var)
        if value:
            metadata[var.lower()] = value

    return metadata


def generate_metadata() -> dict[str, Any]:
    """Generate complete build metadata.

    Returns:
        dict: Complete metadata dictionary.

    Raises:
        ValueError: If version validation fails.
    """
    print("Validating package versions...")
    version = validate_versions_match()
    print(f"✓ Version validated: {version}")

    print("Collecting git metadata...")
    git_metadata = get_git_metadata()
    print(f"✓ Git metadata collected (commit: {git_metadata.get('commit_sha_short', 'N/A')})")

    print("Collecting build metadata...")
    build_metadata = get_build_metadata()
    print(f"✓ Build metadata collected (Python {build_metadata['python_version']})")

    metadata = {
        "package": {
            "name": "review-bot-automator",
            "version": version,
        },
        "git": git_metadata,
        "build": build_metadata,
    }

    return metadata


def main() -> int:
    """Main entry point for metadata generation.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    try:
        print("=" * 70)
        print("Generating Build Metadata")
        print("=" * 70)

        metadata = generate_metadata()

        # Write metadata to file
        output_path = get_project_root() / "dist" / "metadata.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(metadata, f, indent=2)

        print(f"\n✓ Metadata written to: {output_path}")
        print("\nMetadata Summary:")
        print(f"  Package: {metadata['package']['name']} v{metadata['package']['version']}")
        print(f"  Commit:  {metadata['git'].get('commit_sha_short', 'N/A')}")
        print(f"  Branch:  {metadata['git'].get('branch', 'N/A')}")
        if metadata["git"].get("tag"):
            print(f"  Tag:     {metadata['git']['tag']}")
        print(f"  Python:  {metadata['build']['python_version']}")
        print("=" * 70)

        return 0

    except Exception as e:
        print(f"\n✗ Error generating metadata: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
