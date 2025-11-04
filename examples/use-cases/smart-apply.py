#!/usr/bin/env python3
"""Smart apply script - automatically adjusts worker count based on PR size."""
# ruff: noqa: T201, S603, S607
# T201: print is intentional for user-facing script
# S603/S607: subprocess with gh/pr-resolve is expected for this script

import subprocess
import sys


def get_pr_file_count(owner: str, repo: str, pr_number: str) -> int:
    """Get number of files changed in PR using gh CLI."""
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                pr_number,
                "--repo",
                f"{owner}/{repo}",
                "--json",
                "files",
                "--jq",
                ".files | length",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"Error getting PR file count: {e}", file=sys.stderr)
        return 0


def determine_workers(file_count: int) -> int:
    """Determine optimal worker count based on file count."""
    if file_count < 10:
        return 1  # Sequential for small PRs
    elif file_count < 30:
        return 4  # Low parallelism
    elif file_count < 100:
        return 8  # Moderate parallelism
    elif file_count < 300:
        return 16  # High parallelism
    else:
        return 32  # Maximum parallelism


def main() -> int:
    """Main entry point."""
    if len(sys.argv) != 4:
        print("Usage: smart-apply.py OWNER REPO PR_NUMBER")
        print("Example: smart-apply.py myorg myrepo 123")
        return 1

    owner, repo, pr = sys.argv[1:4]

    # Get PR size
    file_count = get_pr_file_count(owner, repo, pr)
    if file_count == 0:
        print("Warning: Could not determine PR size, using default settings")
        file_count = 10

    print(f"PR #{pr} has {file_count} files")

    # Determine optimal workers
    workers = determine_workers(file_count)
    print(f"Using {workers} workers")

    # Build command
    cmd = [
        "pr-resolve",
        "apply",
        "--pr",
        pr,
        "--owner",
        owner,
        "--repo",
        repo,
        "--rollback",
    ]

    if workers > 1:
        cmd.extend(["--parallel", "--max-workers", str(workers)])
        print("Parallel processing enabled")
    else:
        print("Sequential processing (small PR)")

    # Execute
    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error: Command failed with exit code {e.returncode}", file=sys.stderr)
        return e.returncode


if __name__ == "__main__":
    sys.exit(main())
