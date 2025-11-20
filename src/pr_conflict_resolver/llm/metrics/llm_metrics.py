"""LLM metrics tracking for cost and performance monitoring.

This module provides data structures for tracking LLM usage metrics including
token consumption, API call counts, costs, cache performance, and GPU acceleration status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pr_conflict_resolver.llm.providers.gpu_detector import GPUInfo


@dataclass(frozen=True, slots=True)
class LLMMetrics:
    """Metrics for LLM usage tracking and cost optimization.

    Tracks comprehensive metrics for LLM operations including token usage,
    cost, cache performance, parsing success rates, and GPU acceleration status.

    Attributes:
        provider: LLM provider name (e.g., "anthropic", "openai", "ollama").
        model: Specific model used (e.g., "claude-haiku-4", "gpt-4o-mini").
        changes_parsed: Total number of Change objects extracted via LLM parsing.
        avg_confidence: Average confidence score across parsed changes (0.0-1.0).
        cache_hit_rate: Percentage of cache hits (0.0-1.0, where 1.0 = 100%).
        total_cost: Total cost in USD for all API calls.
        api_calls: Total number of API calls made.
        total_tokens: Total tokens consumed (prompt + completion).
        gpu_info: GPU hardware information (Ollama only). None for other providers.

    Example:
        >>> metrics = LLMMetrics(
        ...     provider="anthropic",
        ...     model="claude-haiku-4-20250514",
        ...     changes_parsed=20,
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

        With GPU info (Ollama):
        >>> from pr_conflict_resolver.llm.providers.gpu_detector import GPUInfo
        >>> gpu = GPUInfo(available=True, gpu_type="NVIDIA", model_name="RTX 4090",
        ...               vram_total_mb=24576, vram_available_mb=20480, compute_capability="8.9")
        >>> metrics = LLMMetrics(
        ...     provider="ollama", model="llama3.3:70b",
        ...     changes_parsed=15, avg_confidence=0.88,
        ...     cache_hit_rate=0.0, total_cost=0.0,
        ...     api_calls=5, total_tokens=12000, gpu_info=gpu
        ... )
        >>> metrics.gpu_info.model_name
        'RTX 4090'
    """

    provider: str
    model: str
    changes_parsed: int
    avg_confidence: float
    cache_hit_rate: float
    total_cost: float
    api_calls: int
    total_tokens: int
    gpu_info: GPUInfo | None = None

    def __post_init__(self) -> None:
        """Validate metrics values."""
        # Validate string fields
        if not self.provider or not self.provider.strip():
            raise ValueError("provider must be a non-empty string")
        if not self.model or not self.model.strip():
            raise ValueError("model must be a non-empty string")

        # Validate gpu_info is only for Ollama provider
        if self.gpu_info is not None and self.provider.lower().strip() != "ollama":
            raise ValueError(
                f"gpu_info is only valid for Ollama provider, got provider='{self.provider}'"
            )

        # Validate numeric fields
        if self.changes_parsed < 0:
            raise ValueError(f"changes_parsed must be >= 0, got {self.changes_parsed}")
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
    def cost_per_change(self) -> float | None:
        """Calculate average cost per parsed change.

        Returns:
            Average cost per change in USD, or None if no changes parsed.

        Example:
            >>> metrics = LLMMetrics(
            ...     provider="openai", model="gpt-4o-mini",
            ...     changes_parsed=10, avg_confidence=0.85,
            ...     cache_hit_rate=0.5, total_cost=0.05,
            ...     api_calls=5, total_tokens=5000
            ... )
            >>> f"${metrics.cost_per_change:.4f}"
            '$0.0050'
            >>> metrics_no_changes = LLMMetrics(
            ...     provider="openai", model="gpt-4o-mini",
            ...     changes_parsed=0, avg_confidence=0.0,
            ...     cache_hit_rate=0.0, total_cost=0.0,
            ...     api_calls=0, total_tokens=0
            ... )
            >>> metrics_no_changes.cost_per_change is None
            True
        """
        if self.changes_parsed == 0:
            return None
        return self.total_cost / self.changes_parsed

    @property
    def avg_tokens_per_call(self) -> float | None:
        """Calculate average tokens per API call.

        Returns:
            Average tokens per API call, or None if no API calls made.

        Example:
            >>> metrics = LLMMetrics(
            ...     provider="anthropic", model="claude-haiku-4",
            ...     changes_parsed=20, avg_confidence=0.92,
            ...     cache_hit_rate=0.65, total_cost=0.02,
            ...     api_calls=7, total_tokens=15420
            ... )
            >>> int(metrics.avg_tokens_per_call)
            2202
            >>> metrics_no_calls = LLMMetrics(
            ...     provider="anthropic", model="claude-haiku-4",
            ...     changes_parsed=0, avg_confidence=0.0,
            ...     cache_hit_rate=0.0, total_cost=0.0,
            ...     api_calls=0, total_tokens=0
            ... )
            >>> metrics_no_calls.avg_tokens_per_call is None
            True
        """
        if self.api_calls == 0:
            return None
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
            ...     changes_parsed=20, avg_confidence=0.92,
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
            computed_savings = cache_miss_cost - self.total_cost
            raise ValueError(
                f"cache_miss_cost ({cache_miss_cost:.4f}) < total_cost ({self.total_cost:.4f}), "
                f"which would result in negative savings ({computed_savings:.4f}). "
                f"Likely cause: Incorrect cache miss cost estimation. "
                f"Fix: Ensure cache_miss_cost >= total cost of all API calls."
            )
        return cache_miss_cost - self.total_cost
