"""Secure file handling utilities for atomic operations and rollback."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

logger = __import__("logging").getLogger(__name__)


class SecureFileHandler:
    """Secure file operations with atomic writes and validation.

    This class provides secure file operations including:
    - Atomic file writes with automatic rollback
    - Secure temporary file creation with automatic cleanup
    - Backup and restore functionality
    - Safe file deletion
    """

    @staticmethod
    @contextmanager
    def secure_temp_file(suffix: str = "", content: str | None = None) -> Iterator[str]:
        """Create a secure temporary file with automatic cleanup.

        Args:
            suffix: Optional suffix for the temporary file.
            content: Optional content to write to the temporary file.

        Yields:
            str: Path to the temporary file.

        Example:
            >>> with SecureFileHandler.secure_temp_file() as temp_path:
            ...     # Use temp_path
            ...     pass
            # File is automatically deleted
        """
        fd, path = tempfile.mkstemp(suffix=suffix)

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                if content:
                    f.write(content)

            yield path

        finally:
            # Secure deletion
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as e:
                    logger.warning(f"Failed to remove temporary file {path}: {e}")

    @staticmethod
    def atomic_write(file_path: Path, content: str, backup: bool = True) -> None:
        """Perform an atomic file write with backup and rollback.

        This method ensures that file writes are atomic and provides
        automatic rollback on failure. The original file is backed up
        if it exists.

        Args:
            file_path: Path to the file to write.
            content: Content to write to the file.
            backup: Whether to create a backup (default: True).

        Raises:
            OSError: If the file operation fails.

        Example:
            >>> SecureFileHandler.atomic_write(
            ...     Path("config.json"),
            ...     '{"key": "value"}'
            ... )
        """
        backup_path: Path | None = None

        try:
            # Create backup if file exists and backup is enabled
            if backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                shutil.copy2(file_path, backup_path)

            # Write to temporary file first
            temp_file = file_path.with_suffix(file_path.suffix + ".tmp")

            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)

            # Atomic move (atomic on most filesystems)
            temp_file.replace(file_path)

            # Clean up backup on success
            if backup_path and backup_path.exists():
                backup_path.unlink()

        except Exception as e:
            # Restore backup on failure
            if backup_path and backup_path.exists() and backup:
                try:
                    backup_path.replace(file_path)
                    logger.info(f"Restored backup from {backup_path}")
                except OSError as restore_error:
                    logger.error(f"Failed to restore backup: {restore_error}")

            raise OSError(f"Atomic write failed for {file_path}: {e}") from e

    @staticmethod
    def safe_delete(path: Path) -> bool:
        """Safely delete a file or directory.

        Args:
            path: Path to the file or directory to delete.

        Returns:
            bool: True if the deletion was successful, False otherwise.
        """
        if not path.exists():
            return True

        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                os.remove(path)

            return True

        except OSError as e:
            logger.error(f"Failed to delete {path}: {e}")
            return False

    @staticmethod
    def safe_copy(source: Path, destination: Path) -> bool:
        """Safely copy a file with error handling.

        Args:
            source: Source file path.
            destination: Destination file path.

        Returns:
            bool: True if the copy was successful, False otherwise.
        """
        if not source.exists():
            logger.error(f"Source file does not exist: {source}")
            return False

        try:
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(source, destination)
            return True

        except OSError as e:
            logger.error(f"Failed to copy {source} to {destination}: {e}")
            return False
