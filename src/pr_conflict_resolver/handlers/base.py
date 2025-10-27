"""Base handler for file-type specific conflict resolution.

This module provides the abstract base class that all file handlers must implement.
"""

import contextlib
import os
import shutil
import time
import uuid
from abc import ABC, abstractmethod
from os import PathLike
from pathlib import Path

from ..core.models import Change, Conflict
from ..security.input_validator import InputValidator
from ..utils.path_utils import resolve_file_path


class BaseHandler(ABC):
    """Abstract base class for file-type specific handlers."""

    workspace_root: Path

    def __init__(self, workspace_root: str | PathLike[str] | None = None) -> None:
        """Initialize the base handler with workspace root for path validation.

        Args:
            workspace_root: Root directory for validating absolute paths.
                Can be str, PathLike, or None. If None, defaults to current
                working directory.
        """
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """Determine whether this handler can process the given file.

        Returns:
            True if the handler can process the file, False otherwise.
        """

    @abstractmethod
    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply a replacement to a file's line range.

        Parameters:
            path (str): Path to the target file.
            content (str): New content to insert in place of the specified lines.
            start_line (int): 1-indexed starting line number (inclusive).
            end_line (int): 1-indexed ending line number (inclusive).

        Returns:
            bool: `True` if the change was applied successfully, `False` otherwise.

        Raises:
            IOError: If the file cannot be read or written.
            ValueError: If the provided line numbers are invalid.
        """

    @abstractmethod
    def validate_change(
        self, path: str, content: str, start_line: int, end_line: int
    ) -> tuple[bool, str]:
        """Validate a proposed edit to a file's specified line range without applying it.

        Parameters:
            path (str): File path whose contents are validated against the change.
            content (str): New content to substitute into the file for the given range.
            start_line (int): 1-indexed starting line of the replacement range (inclusive).
            end_line (int): 1-indexed ending line of the replacement range (inclusive).

        Returns:
            tuple[bool, str]: (is_valid, message) where is_valid is True if the change is valid
                and False otherwise; message contains success details or an error description.

        Raises:
            IOError: If the file cannot be read.
            ValueError: If the provided line numbers are invalid.
        """

    @abstractmethod
    def detect_conflicts(self, path: str, changes: list[Change]) -> list[Conflict]:
        """Identify conflicts among proposed changes targeting the same file.

        Args:
            path: File path to analyze for conflicting changes.
            changes: List of Change objects representing proposed modifications to the file.

        Returns:
            A list of Conflict objects representing detected conflicts between the provided changes.

        Raises:
            IOError: If the file cannot be read.
            ValueError: If any change contains invalid data (e.g., invalid line ranges).
        """

    def backup_file(self, path: str) -> str:
        """Create a filesystem backup of the given file and return the backup file path.

        This method performs comprehensive security validation including path traversal
        protection, file existence verification, and collision handling for backup files.
        The backup file is created with secure permissions (0o600) to prevent unauthorized access.

        Security Features:
            - Path traversal protection using InputValidator
            - Absolute path containment checking
            - Secure file permissions (0o600) on backup files
            - Collision handling with timestamp-based naming
            - Automatic cleanup on failure

        Args:
            path (str): Path to the file to back up. Must be a valid, accessible file path.

        Returns:
            str: Path to the created backup file with .backup suffix.

        Raises:
            ValueError: If the path is invalid, contains path traversal, or file doesn't exist.
            OSError: If the file cannot be copied or permissions cannot be set.
            FileNotFoundError: If the source file doesn't exist or isn't a regular file.

        Example:
            >>> handler = JsonHandler(workspace_root="/path/to/workspace")
            >>> backup_path = handler.backup_file("config.json")
            >>> print(backup_path)
            config.json.backup
            >>> # Backup file has secure permissions (0o600)
            >>> import os
            >>> oct(os.stat(backup_path).st_mode & 0o777)
            '0o600'

        Note:
            This method uses InputValidator.validate_file_path() with allow_absolute=True
            and base_dir set to the workspace_root, ensuring absolute paths are validated
            for containment within the workspace root directory.
        """
        # Validate file path for security (path traversal protection)
        # Use workspace root for absolute path containment check
        if not InputValidator.validate_file_path(
            path, base_dir=str(self.workspace_root), allow_absolute=True
        ):
            raise ValueError(f"Invalid file path: {path}")

        # Resolve path relative to workspace_root (not CWD)
        file_path = resolve_file_path(path, self.workspace_root)

        # Verify source file exists and is a regular file
        if not file_path.exists():
            raise FileNotFoundError(f"Source file does not exist: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"Source path is not a regular file: {file_path}")

        # Use atomic file creation with race-free operations
        # Generate deterministic unique suffixes per attempt (timestamp + pid + optional uuid)
        timestamp = int(time.time())
        pid = os.getpid()
        base_suffix = f"{timestamp}.{pid}"

        # Try to create backup file atomically with limited retries
        max_attempts = 5
        attempt = 0

        while attempt < max_attempts:
            # Generate backup path with unique identifier
            if attempt == 0:
                # First attempt: try original backup path
                backup_path = file_path.with_suffix(file_path.suffix + ".backup")
            elif attempt == 1:
                # Second attempt: use timestamp only for deterministic test results
                backup_path = file_path.with_suffix(f"{file_path.suffix}.backup.{timestamp}")
            else:
                # Subsequent attempts: add UUID for uniqueness
                backup_path = file_path.with_suffix(
                    f"{file_path.suffix}.backup.{base_suffix}.{uuid.uuid4().hex[:8]}"
                )

            # Attempt atomic file creation with open fd for copy operation
            backup_fd = None
            try:
                # Open backup atomically with O_CREAT|O_EXCL|O_WRONLY
                backup_fd = os.open(
                    backup_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,  # Secure permissions from start
                )

                # Wrap fd with file-like object for copying
                with os.fdopen(backup_fd, "wb") as backup_file:
                    # Copy source to backup via open fd
                    with open(file_path, "rb") as source_file:
                        shutil.copyfileobj(source_file, backup_file)

                    # Ensure data is written to disk before closing
                    os.fsync(backup_fd)

                # Successfully created backup with secure permissions
                return str(backup_path)

            except FileExistsError:
                # File exists, try next attempt
                attempt += 1
                continue
            except OSError as e:
                # Close fd if open and clean up partial backup
                if backup_fd is not None:
                    with contextlib.suppress(OSError):
                        os.close(backup_fd)

                if backup_path and backup_path.exists():
                    with contextlib.suppress(OSError):
                        backup_path.unlink()

                attempt += 1
                if attempt >= max_attempts:
                    raise OSError(
                        f"Unable to create unique backup filename after {max_attempts} attempts "
                        f"for: {file_path}"
                    ) from e

        # This should never be reached, but included for completeness
        raise OSError(
            f"Unable to create unique backup filename after {max_attempts} attempts "
            f"for: {file_path}"
        )

    def restore_file(self, backup_path: str, original_path: str) -> bool:
        """Restore an original file by copying it from a backup and removing the backup file.

        Args:
            backup_path: Path to the backup file to restore from.
            original_path: Path where the original file should be restored.

        Returns:
            `True` if the file was restored and the backup removed, `False` if an error
                occurred.
        """
        try:
            shutil.copy2(backup_path, original_path)
            Path(backup_path).unlink()  # Remove backup
            return True
        except OSError:
            return False
