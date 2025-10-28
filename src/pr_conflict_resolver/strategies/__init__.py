"""Resolution strategies for different conflict types."""

from .base import ResolutionStrategy
from .priority_strategy import PriorityStrategy

__all__ = ["PriorityStrategy", "ResolutionStrategy"]
