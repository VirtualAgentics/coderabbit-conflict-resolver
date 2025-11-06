"""Base data structures for LLM-based parsing.

This module provides foundational data structures for LLM integration.
Phase 0: Foundation only - no actual LLM parsing implemented yet.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedChange:
    r"""Intermediate representation of a change parsed by an LLM.

    This dataclass represents the output from an LLM parser before conversion
    to the standard Change model. It includes additional metadata specific to
    LLM parsing like confidence scores and rationale.

    Args:
        file_path: Path to the file to be modified
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (inclusive)
        new_content: The new content to apply
        change_type: Type of change ("addition", "modification", "deletion")
        confidence: LLM confidence score (0.0-1.0)
        rationale: Explanation of why this change was suggested
        risk_level: Risk assessment ("low", "medium", "high")

    Example:
        >>> change = ParsedChange(
        ...     file_path="src/example.py",
        ...     start_line=10,
        ...     end_line=12,
        ...     new_content="def new_function():\n    pass",
        ...     change_type="modification",
        ...     confidence=0.95,
        ...     rationale="Replace deprecated function with new API",
        ...     risk_level="low"
        ... )
        >>> change.confidence
        0.95
    """

    file_path: str
    start_line: int
    end_line: int
    new_content: str
    change_type: str
    confidence: float
    rationale: str
    risk_level: str = "low"

    def __post_init__(self) -> None:
        """Validate ParsedChange fields after initialization.

        Raises:
            ValueError: If any field has an invalid value
        """
        if self.start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {self.start_line}")
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if self.change_type not in ("addition", "modification", "deletion"):
            raise ValueError(
                f"change_type must be 'addition', 'modification', or 'deletion', "
                f"got '{self.change_type}'"
            )
        if self.risk_level not in ("low", "medium", "high"):
            raise ValueError(
                f"risk_level must be 'low', 'medium', or 'high', got '{self.risk_level}'"
            )
