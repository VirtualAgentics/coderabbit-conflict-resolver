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

Safe metadata access and narrowing:
    >>> # Prefer safe .get() access with runtime narrowing on a Mapping
    >>> from typing import Mapping
    >>> meta: Mapping[str, object] = change.metadata
    >>> token = meta.get("token")
    >>> if isinstance(token, str) and token:
    ...     # token is safely narrowed to non-empty str here
    ...     pass

Validation points:
    - Required fields (if any) should be validated at parse time.
    - Use TypedDict keys (url/author/source/option_label) when present.
    - Consider adding a helper like `is_change_metadata(value) -> TypeGuard[ChangeMetadata]`
      to narrow arbitrary dicts at runtime.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, TypeAlias, TypedDict

if TYPE_CHECKING:
    from pr_conflict_resolver.llm.metrics import LLMMetrics


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
    llm_confidence: float
    llm_provider: str
    parsing_method: str
    change_rationale: str
    risk_level: str


# Type aliases for clarity and strict typing
LineRange: TypeAlias = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Change:
    """Represents a single change suggestion.

    New in Phase 0 (LLM Foundation):
        - llm_confidence: Confidence score from LLM parser (0.0-1.0)
        - llm_provider: Provider used for parsing ("claude-cli", "gpt-4", etc.)
        - parsing_method: How the change was parsed ("regex" or "llm")
        - change_rationale: Explanation of why this change was suggested
        - risk_level: Risk assessment ("low", "medium", "high")

    All new fields have default values for backward compatibility.
    """

    path: str
    start_line: int
    end_line: int
    content: str
    metadata: ChangeMetadata | Mapping[str, object]  # Known fields typed; allow arbitrary mapping
    fingerprint: str
    file_type: FileType
    llm_confidence: float | None = None
    llm_provider: str | None = None
    parsing_method: str = "regex"
    change_rationale: str | None = None
    risk_level: str | None = None


@dataclass(frozen=True, slots=True)
class Conflict:
    """Represents a conflict between two or more changes."""

    file_path: str
    line_range: LineRange
    changes: list[Change]
    conflict_type: str
    severity: str
    overlap_percentage: float


@dataclass(frozen=True, slots=True)
class Resolution:
    """Represents a resolution for a conflict."""

    strategy: str
    applied_changes: list[Change]
    skipped_changes: list[Change]
    success: bool
    message: str


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """Result of conflict resolution and change application.

    Attributes:
        applied_count: Total number of changes successfully applied (from both
            conflict resolutions and non-conflicting changes).
        conflict_count: Number of conflicts that could not be resolved.
        success_rate: Percentage of successful applications (0-100).
        resolutions: List of successfully applied conflict resolutions.
        conflicts: List of detected conflicts.
        non_conflicting_applied: Number of non-conflicting changes applied directly
            (without going through conflict resolution). Default: 0 for backward compatibility.
        non_conflicting_skipped: Number of non-conflicting changes skipped due to
            validation failures. Default: 0 for backward compatibility.
        non_conflicting_failed: Number of non-conflicting changes that failed to apply.
            Default: 0 for backward compatibility.
        llm_metrics: Optional LLM usage metrics (tokens, cost, cache performance).
            None if LLM parsing was not used. Default: None for backward compatibility.
            Added in Phase 3 (Issue #152).
    """

    applied_count: int
    conflict_count: int
    success_rate: float
    resolutions: list[Resolution]
    conflicts: list[Conflict]
    non_conflicting_applied: int = 0
    non_conflicting_skipped: int = 0
    non_conflicting_failed: int = 0
    llm_metrics: "LLMMetrics | None" = None
