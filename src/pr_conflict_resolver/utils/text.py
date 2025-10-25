"""Text utility functions for conflict resolution.

This module provides common text manipulation utilities used across
the conflict resolver.
"""


def normalize_content(text: str) -> str:
    """Normalize text by stripping whitespace and removing empty lines.

    Returns:
        A string where each non-empty original line has been trimmed and the remaining
        lines are joined with a single newline character.
    """
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())
