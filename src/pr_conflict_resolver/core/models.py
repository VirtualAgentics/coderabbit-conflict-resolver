"""Data models for the conflict resolution system.

This module contains the core data classes used throughout the system
to represent changes, conflicts, resolutions, and results.

Metadata Migration Examples:

With typed ChangeMetadata fields (recommended):
    >>> from pr_conflict_resolver.core.models import Change, FileType, ChangeMetadata
    >>> metadata: ChangeMetadata = {"url": "https://github.com/...", "author": "coderabbit"}
    >>> change = Change(
    ...     path="file.json",
    ...     start_line=1,
    ...     end_line=10,
    ...     content='{"key": "value"}',
    ...     metadata=metadata,
    ...     fingerprint="abc123",
    ...     file_type=FileType.JSON,
    ... )

With arbitrary/custom dict fields (backward compatible):
    >>> from pr_conflict_resolver.core.models import Change, FileType
    >>> custom_metadata = {
    ...     "url": "https://github.com/...",
    ...     "author": "coderabbit",
    ...     "custom_field": "custom_value",
    ...     "nested": {"data": 123},
    ... }
    >>> change = Change(
    ...     path="file.json",
    ...     start_line=1,
    ...     end_line=10,
    ...     content='{"key": "value"}',
    ...     metadata=custom_metadata,
    ...     fingerprint="abc123",
    ...     file_type=FileType.JSON,
    ... )

Both forms are accepted. Use ChangeMetadata for type safety, or use dict for flexibility.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, TypedDict


class FileType(Enum):
    """File type enumeration for routing suggestions to appropriate handlers."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    PLAINTEXT = "plaintext"


class ChangeMetadata(TypedDict, total=False):
    """Metadata fields for Change objects.

    All fields are optional (total=False) to maintain backward compatibility.
    """

    url: str
    author: str
    source: str
    option_label: str


@dataclass
class Change:
    """Represents a single change suggestion."""

    path: str
    start_line: int
    end_line: int
    content: str
    metadata: ChangeMetadata | dict[str, Any]  # Known fields typed, allows unknown fields
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
