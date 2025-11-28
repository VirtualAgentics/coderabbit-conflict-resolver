# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Resolution strategies for different conflict types."""

from review_bot_automator.strategies.base import ResolutionStrategy
from review_bot_automator.strategies.priority_strategy import PriorityStrategy

__all__ = ["PriorityStrategy", "ResolutionStrategy"]
