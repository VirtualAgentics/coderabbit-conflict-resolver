# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Base strategy interface for conflict resolution.

This module provides the abstract base class that all resolution strategies must implement.
"""

from abc import ABC, abstractmethod

from review_bot_automator.core.models import Conflict, Resolution


class ResolutionStrategy(ABC):
    """Abstract base class for all conflict resolution strategies.

    All resolution strategies must inherit from this class and implement the resolve method.
    This ensures a consistent interface for different resolution approaches.
    """

    @abstractmethod
    def resolve(self, conflict: Conflict) -> Resolution:
        """Resolve a conflict and return the resolution decision.

        Args:
            conflict: The conflict to resolve, containing all conflicting changes and metadata.

        Returns:
            Resolution: Object containing:
            - applied_changes: List of changes that were applied (often a single item)
            - skipped_changes: List of changes that were not applied
            - message: Explanation for the resolution decision
            - success: Whether the resolution was successful

        Raises:
            NotImplementedError: If the subclass doesn't implement this method.
        """
