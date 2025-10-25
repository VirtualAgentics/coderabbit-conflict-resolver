"""Data models for the conflict resolution system.

This module contains the core data classes used throughout the system
to represent changes, conflicts, resolutions, and results.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FileType(Enum):
    """File type enumeration for routing suggestions to appropriate handlers."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    PLAINTEXT = "plaintext"


@dataclass
@dataclass
class Change:
    """Represents a single change suggestion."""

    path: str
    start_line: int
    end_line: int
    content: str
    metadata: dict[str, Any]
    fingerprint: str
    file_type: FileType


@dataclass
class Conflict:
    """Represents a conflict between two or more changes."""

    file_path: str
    line_range: tuple[int, int]
    changes: list[Change]
    conflict_type: str
    severity: str
    overlap_percentage: float


@dataclass
class Resolution:
    """Represents a resolution for a conflict."""

    strategy: str
    applied_changes: list[Change]
    skipped_changes: list[Change]
    success: bool
    message: str


@dataclass
class ResolutionResult:
    """Result of conflict resolution."""

    applied_count: int
    conflict_count: int
    success_rate: float
    resolutions: list[Resolution]
    conflicts: list[Conflict]
