#!/usr/bin/env python3
"""Clean script for removing build artifacts and temporary files.

This script removes:
- Directories: build, dist, .pytest_cache, .mypy_cache, .ruff_cache, htmlcov
- Files: .coverage, bandit-report.json, safety-report.json
- Recursively removes __pycache__ directories and *.pyc files
- Removes any *.egg-info directories
"""

import logging
import pathlib
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def remove_directories(directories: list[str]) -> None:
    """Remove specified directories if they exist."""
    for directory in directories:
        if pathlib.Path(directory).exists():
            logger.info(f"Removing directory: {directory}")
            shutil.rmtree(directory, ignore_errors=True)


def remove_files(files: list[str]) -> None:
    """Remove specified files if they exist."""
    for file_path in files:
        path = pathlib.Path(file_path)
        if path.exists():
            logger.info(f"Removing file: {file_path}")
            path.unlink(missing_ok=True)


def remove_pycache_directories() -> None:
    """Recursively remove all __pycache__ directories."""
    for pycache_dir in pathlib.Path(".").rglob("__pycache__"):
        if pycache_dir.is_dir():
            logger.info(f"Removing __pycache__ directory: {pycache_dir}")
            shutil.rmtree(pycache_dir, ignore_errors=True)


def remove_pyc_files() -> None:
    """Recursively remove all *.pyc files."""
    for pyc_file in pathlib.Path(".").rglob("*.pyc"):
        if pyc_file.is_file():
            logger.info(f"Removing .pyc file: {pyc_file}")
            pyc_file.unlink()


def remove_egg_info_directories() -> None:
    """Remove any *.egg-info directories."""
    for egg_info_dir in pathlib.Path(".").glob("*.egg-info"):
        if egg_info_dir.is_dir():
            logger.info(f"Removing .egg-info directory: {egg_info_dir}")
            shutil.rmtree(egg_info_dir, ignore_errors=True)


def main() -> None:
    """Main function to clean build artifacts and temporary files."""
    logger.info("Cleaning build artifacts and temporary files...")

    # Directories to remove
    directories_to_remove = [
        "build",
        "dist",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
    ]

    # Files to remove
    files_to_remove = [".coverage", "bandit-report.json", "safety-report.json"]

    # Remove directories
    remove_directories(directories_to_remove)

    # Remove files
    remove_files(files_to_remove)

    # Remove __pycache__ directories recursively
    remove_pycache_directories()

    # Remove *.pyc files recursively
    remove_pyc_files()

    # Remove *.egg-info directories
    remove_egg_info_directories()

    logger.info("Cleanup completed!")


if __name__ == "__main__":
    main()
