# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Text utility functions for conflict resolution.

This module provides common text manipulation utilities used across
the conflict resolver.
"""


def normalize_content(text: str) -> str:
    """Normalize text by stripping whitespace and removing empty lines.

    Args:
        text: Input text to normalize.

    Returns:
        Normalized string with trimmed, non-empty lines joined by a single newline.
    """
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())
