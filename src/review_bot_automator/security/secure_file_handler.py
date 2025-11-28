# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Secure file handling utilities for atomic operations and rollback."""

import logging
import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from review_bot_automator.security.config import SecurityConfig

logger: Final[logging.Logger] = logging.getLogger(__name__)


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
    def secure_temp_file(suffix: str = "", content: str | None = None) -> Iterator[Path]:
        """Create a secure temporary file with automatic cleanup.

        Args:
            suffix: Optional suffix for the temporary file.
            content: Optional content to write to the temporary file.

        Yields:
            Path: Path to the temporary file.

        Example:
            >>> with SecureFileHandler.secure_temp_file() as temp_path:
            ...     # Use temp_path
            ...     pass
            # File is automatically deleted
        """
        fd, path = tempfile.mkstemp(suffix=suffix)
        path_obj = Path(path)

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                if content is not None:
                    f.write(content)

            yield path_obj

        finally:
            # Secure deletion
            try:
                path_obj.unlink(missing_ok=True)
            except OSError:
                logger.exception("Failed to remove temporary file %s", path_obj)

    @staticmethod
    def atomic_write(
        file_path: Path, content: str, backup: bool = True, config: "SecurityConfig | None" = None
    ) -> None:
        """Perform an atomic file write with backup and rollback.

        This method ensures that file writes are atomic and provides
        automatic rollback on failure. The original file is backed up
        if it exists.

        Args:
            file_path: Path to the file to write.
            content: Content to write to the file.
            backup: Whether to create a backup (default: True).
            config: Optional SecurityConfig to use for backup and atomic behavior.
                    If None, uses backup parameter. If provided, overrides backup with
                    config.enable_backups and respects config.enable_atomic_writes.

        Raises:
            OSError: If the file operation fails.

        Example:
            >>> SecureFileHandler.atomic_write(
            ...     Path("config.json"),
            ...     '{"key": "value"}'
            ... )
        """
        # Use config settings if provided, otherwise use function parameter
        should_backup = config.enable_backups if config else backup
        use_atomic = config.enable_atomic_writes if config else True

        backup_path: Path | None = None
        temp_file: Path | None = None

        try:
            # Create backup if file exists and backup is enabled
            if should_backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                shutil.copy2(file_path, backup_path)

            # Write to temporary file first
            temp_file = file_path.with_suffix(file_path.suffix + ".tmp")

            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()  # Ensure data is written to OS buffer
                if use_atomic:
                    os.fsync(f.fileno())  # Ensure data is written to disk

            # Atomic move (atomic on most filesystems)
            if use_atomic:
                temp_file.replace(file_path)
            else:
                # Non-atomic write (for when atomic writes are disabled)
                temp_file.rename(file_path)

            # Ensure directory entry durability (only if atomic)
            if use_atomic:
                dir_fd: int | None = None
                try:
                    # Open directory descriptor with proper flags
                    dir_fd = os.open(
                        str(file_path.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                    )
                    os.fsync(dir_fd)
                except OSError:
                    # Directory fsync may not be supported on all systems
                    # This is not critical for the atomic operation
                    pass
                finally:
                    if dir_fd is not None:
                        os.close(dir_fd)

            # Clean up backup on success
            if backup_path and backup_path.exists():
                backup_path.unlink()

        except OSError as e:
            # Clean up temporary file if it exists
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError as cleanup_error:
                    logger.warning(
                        "Failed to remove temporary file %s: %s", temp_file, cleanup_error
                    )

            # Restore backup on failure
            if backup_path and backup_path.exists() and should_backup:
                try:
                    backup_path.replace(file_path)
                    logger.info("Restored backup from %s", backup_path)
                except OSError as restore_error:
                    logger.error("Failed to restore backup: %s", restore_error)

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
            if path.is_symlink() or path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path)
            else:
                # Unknown type (e.g., device), attempt unlink
                path.unlink(missing_ok=True)

            return True

        except OSError as e:
            logger.error("Failed to delete %s: %s", path, e)
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
        # Ensure both parameters are Path instances
        source = Path(source)
        destination = Path(destination)

        if not source.is_file():
            # Provide rich diagnostic information
            resolved_path = source.resolve() if source.exists() else "N/A"
            logger.error(
                f"Source is not a regular file: {source} "
                f"(is_dir={source.is_dir()}, is_symlink={source.is_symlink()}, "
                f"resolved={resolved_path})"
            )
            return False

        try:
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            shutil.copy2(source, destination)
            return True

        except OSError:
            logger.exception("Failed to copy %s to %s", source, destination)
            return False
