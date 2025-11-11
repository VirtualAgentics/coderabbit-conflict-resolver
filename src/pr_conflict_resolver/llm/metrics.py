"""LLM metrics tracking for cost and performance monitoring.

This module provides data structures for tracking LLM usage metrics including
token consumption, API call counts, costs, and cache performance.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LLMMetrics:
    """Metrics for LLM usage tracking and cost optimization.

    Tracks comprehensive metrics for LLM operations including token usage,
    cost, cache performance, and parsing success rates.

    Attributes:
        provider: LLM provider name (e.g., "anthropic", "openai", "ollama").
        model: Specific model used (e.g., "claude-haiku-4", "gpt-4o-mini").
        comments_parsed: Total number of comments successfully parsed.
        avg_confidence: Average confidence score across parsed comments (0.0-1.0).
        cache_hit_rate: Percentage of cache hits (0.0-1.0, where 1.0 = 100%).
        total_cost: Total cost in USD for all API calls.
        api_calls: Total number of API calls made.
        total_tokens: Total tokens consumed (prompt + completion).

    Example:
        >>> metrics = LLMMetrics(
        ...     provider="anthropic",
        ...     model="claude-haiku-4-20250514",
        ...     comments_parsed=20,
        ...     avg_confidence=0.92,
        ...     cache_hit_rate=0.65,
        ...     total_cost=0.0234,
        ...     api_calls=7,
        ...     total_tokens=15420
        ... )
        >>> metrics.cache_hit_rate
        0.65
        >>> f"${metrics.total_cost:.4f}"
        '$0.0234'
    """

    provider: str
    model: str
    comments_parsed: int
    avg_confidence: float
    cache_hit_rate: float
    total_cost: float
    api_calls: int
    total_tokens: int

    def __post_init__(self) -> None:
        """Validate metrics values."""
        if self.comments_parsed < 0:
            raise ValueError(f"comments_parsed must be >= 0, got {self.comments_parsed}")
        if not 0.0 <= self.avg_confidence <= 1.0:
            raise ValueError(
                f"avg_confidence must be between 0.0 and 1.0, got {self.avg_confidence}"
            )
        if not 0.0 <= self.cache_hit_rate <= 1.0:
            raise ValueError(
                f"cache_hit_rate must be between 0.0 and 1.0, got {self.cache_hit_rate}"
            )
        if self.total_cost < 0:
            raise ValueError(f"total_cost must be >= 0, got {self.total_cost}")
        if self.api_calls < 0:
            raise ValueError(f"api_calls must be >= 0, got {self.api_calls}")
        if self.total_tokens < 0:
            raise ValueError(f"total_tokens must be >= 0, got {self.total_tokens}")

    @property
    def cost_per_comment(self) -> float:
        """Calculate average cost per parsed comment.

        Returns:
            Average cost per comment in USD. Returns 0.0 if no comments parsed.

        Example:
            >>> metrics = LLMMetrics(
            ...     provider="openai", model="gpt-4o-mini",
            ...     comments_parsed=10, avg_confidence=0.85,
            ...     cache_hit_rate=0.5, total_cost=0.05,
            ...     api_calls=5, total_tokens=5000
            ... )
            >>> f"${metrics.cost_per_comment:.4f}"
            '$0.0050'
        """
        if self.comments_parsed == 0:
            return 0.0
        return self.total_cost / self.comments_parsed

    @property
    def avg_tokens_per_call(self) -> float:
        """Calculate average tokens per API call.

        Returns:
            Average tokens per API call. Returns 0.0 if no API calls made.

        Example:
            >>> metrics = LLMMetrics(
            ...     provider="anthropic", model="claude-haiku-4",
            ...     comments_parsed=20, avg_confidence=0.92,
            ...     cache_hit_rate=0.65, total_cost=0.02,
            ...     api_calls=7, total_tokens=15420
            ... )
            >>> int(metrics.avg_tokens_per_call)
            2202
        """
        if self.api_calls == 0:
            return 0.0
        return self.total_tokens / self.api_calls

    def calculate_savings(self, cache_miss_cost: float) -> float:
        """Calculate cost savings from cache hits.

        Args:
            cache_miss_cost: Estimated total cost if cache hit rate was 0%.

        Returns:
            Cost savings in USD from cache hits.

        Raises:
            ValueError: If cache_miss_cost is negative.

        Example:
            >>> metrics = LLMMetrics(
            ...     provider="anthropic", model="claude-haiku-4",
            ...     comments_parsed=20, avg_confidence=0.92,
            ...     cache_hit_rate=0.65, total_cost=0.0234,
            ...     api_calls=7, total_tokens=15420
            ... )
            >>> savings = metrics.calculate_savings(0.0646)
            >>> f"${savings:.4f}"
            '$0.0412'
        """
        if cache_miss_cost < 0:
            raise ValueError(f"cache_miss_cost must be >= 0, got {cache_miss_cost}")
        if cache_miss_cost < self.total_cost:
            raise ValueError(
                f"cache_miss_cost ({cache_miss_cost}) must be >= total_cost ({self.total_cost})"
            )
        return cache_miss_cost - self.total_cost
