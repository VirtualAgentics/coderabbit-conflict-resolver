"""Base handler for file-type specific conflict resolution.

This module provides the abstract base class that all file handlers must implement.
"""

from abc import ABC, abstractmethod

from ..core.models import Change, Conflict


class BaseHandler(ABC):
    """Abstract base class for file-type specific handlers."""

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

        Parameters:
            path (str): Path to the file to back up.

        Returns:
            backup_path (str): Path to the created backup file.

        """
        import shutil
        from pathlib import Path

        file_path = Path(path)
        backup_path = file_path.with_suffix(file_path.suffix + ".backup")
        shutil.copy2(file_path, backup_path)
        return str(backup_path)

    def restore_file(self, backup_path: str, original_path: str) -> bool:
        """Restore an original file by copying it from a backup and removing the backup file.

        Args:
            backup_path: Path to the backup file to restore from.
            original_path: Path where the original file should be restored.

        Returns:
            `True` if the file was restored and the backup removed, `False` if an error
                occurred.
        """
        import shutil
        from pathlib import Path

        try:
            shutil.copy2(backup_path, original_path)
            Path(backup_path).unlink()  # Remove backup
            return True
        except Exception:
            return False
