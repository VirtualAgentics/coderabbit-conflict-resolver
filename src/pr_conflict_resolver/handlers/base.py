"""Base handler for file-type specific conflict resolution.

This module provides the abstract base class that all file handlers must implement.
"""

from abc import ABC, abstractmethod

from ..core.models import Change, Conflict


class BaseHandler(ABC):
    """Abstract base class for file-type specific handlers."""

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """Check if this handler can process the given file.

        Args:
            file_path: The path to the file to check.

        Returns:
            True if this handler can process the file, False otherwise.
        """

    @abstractmethod
    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply a change to the file.

        Args:
            path: The file path to apply the change to.
            content: The new content to apply.
            start_line: The starting line number (1-indexed).
            end_line: The ending line number (1-indexed).

        Returns:
            True if the change was applied successfully, False otherwise.

        Raises:
            IOError: If the file cannot be read or written.
            ValueError: If the line numbers are invalid.
        """

    @abstractmethod
    def validate_change(
        self, path: str, content: str, start_line: int, end_line: int
    ) -> tuple[bool, str]:
        """Validate a change without applying it.

        Args:
            path: The file path to validate the change against.
            content: The new content to validate.
            start_line: The starting line number (1-indexed).
            end_line: The ending line number (1-indexed).

        Returns:
            A tuple of (is_valid, message) where is_valid indicates
            whether the change is valid, and message provides details
            about validation (error message if invalid, success if valid).

        Raises:
            IOError: If the file cannot be read.
            ValueError: If the line numbers are invalid.
        """

    @abstractmethod
    def detect_conflicts(self, path: str, changes: list[Change]) -> list[Conflict]:
        """Detect conflicts between changes in the same file.

        Args:
            path: The file path to analyze for conflicts.
            changes: List of changes to check for conflicts.

        Returns:
            List of detected conflicts between the changes.

        Raises:
            IOError: If the file cannot be read.
            ValueError: If the changes contain invalid data.
        """

    def backup_file(self, path: str) -> str:
        """Create a backup of the file before modifications.

        Args:
            path: The path to the file to backup.

        Returns:
            The path to the created backup file with .backup extension.

        Raises:
            OSError: If filesystem access fails during backup creation (e.g.,
                insufficient permissions, disk full, or path resolution errors).
            IOError: If I/O operations fail during file copying (e.g., source
                file cannot be read or backup file cannot be written).
        """
        import shutil
        from pathlib import Path

        file_path = Path(path)
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        shutil.copy2(file_path, backup_path)
        return str(backup_path)

    def restore_file(self, backup_path: str, original_path: str) -> bool:
        """Restore file from backup."""
        import shutil
        from pathlib import Path

        try:
            shutil.copy2(backup_path, original_path)
            Path(backup_path).unlink()  # Remove backup
            return True
        except Exception:
            return False
