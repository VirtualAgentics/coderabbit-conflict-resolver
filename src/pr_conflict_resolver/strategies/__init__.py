"""Resolution strategies for different conflict types."""

from pr_conflict_resolver.strategies.base import ResolutionStrategy
from pr_conflict_resolver.strategies.priority_strategy import PriorityStrategy

__all__ = ["PriorityStrategy", "ResolutionStrategy"]
