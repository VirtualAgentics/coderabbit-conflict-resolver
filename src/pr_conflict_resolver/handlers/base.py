"""
Base handler for file-type specific conflict resolution.

This module provides the abstract base class that all file handlers must implement.
"""

from abc import ABC, abstractmethod
from typing import Any, Tuple


class BaseHandler(ABC):
    """Abstract base class for file-type specific handlers."""
    
    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """Check if this handler can process the given file."""
        pass
    
    @abstractmethod
    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply a change to the file."""
        pass
    
    @abstractmethod
    def validate_change(self, path: str, content: str, start_line: int, end_line: int) -> Tuple[bool, str]:
        """Validate a change without applying it."""
        pass
    
    @abstractmethod
    def detect_conflicts(self, path: str, changes: list) -> list:
        """Detect conflicts between changes in the same file."""
        pass
    
    def backup_file(self, path: str) -> str:
        """Create a backup of the file."""
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
