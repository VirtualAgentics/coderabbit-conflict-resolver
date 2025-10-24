"""Text utility functions for conflict resolution.

This module provides common text manipulation utilities used across
the conflict resolver.
"""


def normalize_content(text: str) -> str:
    """Normalize whitespace for comparison.

    Args:
        text: The text to normalize.

    Returns:
        Normalized text with stripped lines and removed empty lines.
    """
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())
