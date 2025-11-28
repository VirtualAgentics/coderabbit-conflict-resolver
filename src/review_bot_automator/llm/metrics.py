# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""LLM metrics tracking for cost and performance monitoring.

This module provides data structures for tracking LLM usage metrics including
token consumption, API call counts, costs, cache performance, latency percentiles,
and GPU acceleration status.

Includes:
- LLMMetrics: Per-session metrics for backward compatibility
- RequestMetrics: Per-request metrics for detailed tracking
- ProviderStats: Per-provider aggregated statistics
- AggregatedMetrics: Cross-provider aggregated metrics with percentiles
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from review_bot_automator.llm.providers.gpu_detector import GPUInfo


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
        >>> from review_bot_automator.llm.providers.gpu_detector import GPUInfo
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
    def cost_per_change(self) -> float:
        """Calculate average cost per parsed change.

        Returns:
            Average cost per change in USD. Returns 0.0 if no changes parsed.

        Example:
            >>> metrics = LLMMetrics(
            ...     provider="openai", model="gpt-4o-mini",
            ...     changes_parsed=10, avg_confidence=0.85,
            ...     cache_hit_rate=0.5, total_cost=0.05,
            ...     api_calls=5, total_tokens=5000
            ... )
            >>> f"${metrics.cost_per_change:.4f}"
            '$0.0050'
        """
        if self.changes_parsed == 0:
            return 0.0
        return self.total_cost / self.changes_parsed

    @property
    def avg_tokens_per_call(self) -> float:
        """Calculate average tokens per API call.

        Returns:
            Average tokens per API call. Returns 0.0 if no API calls made.

        Example:
            >>> metrics = LLMMetrics(
            ...     provider="anthropic", model="claude-haiku-4",
            ...     changes_parsed=20, avg_confidence=0.92,
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
            raise ValueError(
                f"cache_miss_cost ({cache_miss_cost}) must be >= total_cost ({self.total_cost})"
            )
        return cache_miss_cost - self.total_cost


@dataclass(frozen=True, slots=True)
class RequestMetrics:
    """Metrics for a single LLM request.

    Captures detailed timing and resource usage for individual API calls,
    enabling latency analysis and debugging.

    Attributes:
        request_id: Unique identifier for this request.
        provider: LLM provider name (e.g., "anthropic", "openai", "ollama").
        model: Specific model used.
        latency_seconds: Request latency in seconds.
        success: Whether the request completed successfully.
        tokens_input: Number of input/prompt tokens.
        tokens_output: Number of output/completion tokens.
        cost: Request cost in USD.
        cache_hit: Whether response came from cache.
        error_type: Error class name if request failed, None otherwise.

    Example:
        >>> metrics = RequestMetrics(
        ...     request_id="req-abc123",
        ...     provider="anthropic",
        ...     model="claude-haiku-4",
        ...     latency_seconds=0.234,
        ...     success=True,
        ...     tokens_input=500,
        ...     tokens_output=120,
        ...     cost=0.00093,
        ...     cache_hit=False
        ... )
        >>> f"{metrics.latency_seconds:.3f}s"
        '0.234s'
    """

    request_id: str
    provider: str
    model: str
    latency_seconds: float
    success: bool
    tokens_input: int
    tokens_output: int
    cost: float
    cache_hit: bool
    error_type: str | None = None

    def __post_init__(self) -> None:
        """Validate request metrics values."""
        if self.latency_seconds < 0:
            raise ValueError(f"latency_seconds must be >= 0, got {self.latency_seconds}")
        if self.tokens_input < 0:
            raise ValueError(f"tokens_input must be >= 0, got {self.tokens_input}")
        if self.tokens_output < 0:
            raise ValueError(f"tokens_output must be >= 0, got {self.tokens_output}")
        if self.cost < 0:
            raise ValueError(f"cost must be >= 0, got {self.cost}")

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens (input + output)."""
        return self.tokens_input + self.tokens_output


@dataclass(frozen=True, slots=True)
class ProviderStats:
    """Aggregated statistics for a single LLM provider.

    Provides summary statistics across multiple requests to the same provider,
    including latency percentiles and success rates.

    Attributes:
        provider: LLM provider name.
        model: Model identifier (or "mixed" if multiple models used).
        total_requests: Total number of requests made.
        successful_requests: Number of successful requests.
        failed_requests: Number of failed requests.
        success_rate: Success rate (0.0-1.0).
        total_cost: Total cost in USD.
        total_tokens: Total tokens consumed.
        avg_latency: Average latency in seconds.
        latency_p50: 50th percentile (median) latency in seconds.
        latency_p95: 95th percentile latency in seconds.
        latency_p99: 99th percentile latency in seconds.
        cache_hit_rate: Cache hit rate (0.0-1.0).
        error_counts: Mapping of error type to occurrence count.

    Example:
        >>> stats = ProviderStats(
        ...     provider="anthropic",
        ...     model="claude-haiku-4",
        ...     total_requests=25,
        ...     successful_requests=24,
        ...     failed_requests=1,
        ...     success_rate=0.96,
        ...     total_cost=0.0234,
        ...     total_tokens=15420,
        ...     avg_latency=0.287,
        ...     latency_p50=0.234,
        ...     latency_p95=0.512,
        ...     latency_p99=0.789,
        ...     cache_hit_rate=0.65,
        ...     error_counts={"APITimeoutError": 1}
        ... )
        >>> f"p95={stats.latency_p95:.3f}s"
        'p95=0.512s'
    """

    provider: str
    model: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    total_cost: float
    total_tokens: int
    avg_latency: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    cache_hit_rate: float
    error_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate provider stats values and ensure immutability."""
        # Validate all fields first, before wrapping in immutable proxy
        if self.total_requests < 0:
            raise ValueError(f"total_requests must be >= 0, got {self.total_requests}")
        if self.successful_requests < 0:
            raise ValueError(f"successful_requests must be >= 0, got {self.successful_requests}")
        if self.failed_requests < 0:
            raise ValueError(f"failed_requests must be >= 0, got {self.failed_requests}")
        if not 0.0 <= self.success_rate <= 1.0:
            raise ValueError(f"success_rate must be between 0.0 and 1.0, got {self.success_rate}")
        if self.total_cost < 0:
            raise ValueError(f"total_cost must be >= 0, got {self.total_cost}")
        if self.total_tokens < 0:
            raise ValueError(f"total_tokens must be >= 0, got {self.total_tokens}")
        if self.avg_latency < 0:
            raise ValueError(f"avg_latency must be >= 0, got {self.avg_latency}")
        if self.latency_p50 < 0:
            raise ValueError(f"latency_p50 must be >= 0, got {self.latency_p50}")
        if self.latency_p95 < 0:
            raise ValueError(f"latency_p95 must be >= 0, got {self.latency_p95}")
        if self.latency_p99 < 0:
            raise ValueError(f"latency_p99 must be >= 0, got {self.latency_p99}")
        if not 0.0 <= self.cache_hit_rate <= 1.0:
            raise ValueError(
                f"cache_hit_rate must be between 0.0 and 1.0, got {self.cache_hit_rate}"
            )
        # All validations passed - wrap error_counts in MappingProxyType to enforce immutability
        object.__setattr__(self, "error_counts", MappingProxyType(dict(self.error_counts)))


@dataclass(frozen=True, slots=True)
class AggregatedMetrics:
    """Cross-provider aggregated metrics with latency percentiles.

    Provides a comprehensive summary across all providers used during
    PR processing, suitable for export to JSON/CSV.

    Attributes:
        provider_stats: Mapping of provider name to ProviderStats.
        latency_p50: Overall 50th percentile latency in seconds.
        latency_p95: Overall 95th percentile latency in seconds.
        latency_p99: Overall 99th percentile latency in seconds.
        latency_avg: Overall average latency in seconds.
        total_requests: Total requests across all providers.
        successful_requests: Total successful requests.
        failed_requests: Total failed requests.
        success_rate: Overall success rate (0.0-1.0).
        total_cost: Total cost across all providers in USD.
        cost_per_comment: Average cost per processed comment in USD.
        cache_hit_rate: Overall cache hit rate (0.0-1.0).
        cache_savings: Estimated savings from cache hits in USD.

    Example:
        >>> from review_bot_automator.llm.metrics import AggregatedMetrics, ProviderStats
        >>> stats = ProviderStats(
        ...     provider="anthropic", model="claude-haiku-4",
        ...     total_requests=25, successful_requests=24, failed_requests=1,
        ...     success_rate=0.96, total_cost=0.0234, total_tokens=15420,
        ...     avg_latency=0.287, latency_p50=0.234, latency_p95=0.512,
        ...     latency_p99=0.789, cache_hit_rate=0.65
        ... )
        >>> metrics = AggregatedMetrics(
        ...     provider_stats={"anthropic": stats},
        ...     latency_p50=0.234, latency_p95=0.512, latency_p99=0.789,
        ...     latency_avg=0.287, total_requests=25, successful_requests=24,
        ...     failed_requests=1, success_rate=0.96, total_cost=0.0234,
        ...     cost_per_comment=0.00094, cache_hit_rate=0.65, cache_savings=0.0412
        ... )
        >>> f"${metrics.total_cost:.4f}"
        '$0.0234'
    """

    provider_stats: Mapping[str, ProviderStats] = field(default_factory=dict)
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    latency_avg: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0
    total_cost: float = 0.0
    cost_per_comment: float = 0.0
    cache_hit_rate: float = 0.0
    cache_savings: float = 0.0
    fallback_count: int = 0
    fallback_rate: float = 0.0

    def __post_init__(self) -> None:
        """Validate aggregated metrics values and ensure immutability."""
        # Validate all fields first, before wrapping in immutable proxy
        if self.latency_p50 < 0:
            raise ValueError(f"latency_p50 must be >= 0, got {self.latency_p50}")
        if self.latency_p95 < 0:
            raise ValueError(f"latency_p95 must be >= 0, got {self.latency_p95}")
        if self.latency_p99 < 0:
            raise ValueError(f"latency_p99 must be >= 0, got {self.latency_p99}")
        if self.latency_avg < 0:
            raise ValueError(f"latency_avg must be >= 0, got {self.latency_avg}")
        if self.total_requests < 0:
            raise ValueError(f"total_requests must be >= 0, got {self.total_requests}")
        if self.successful_requests < 0:
            raise ValueError(f"successful_requests must be >= 0, got {self.successful_requests}")
        if self.failed_requests < 0:
            raise ValueError(f"failed_requests must be >= 0, got {self.failed_requests}")
        if not 0.0 <= self.success_rate <= 1.0:
            raise ValueError(f"success_rate must be between 0.0 and 1.0, got {self.success_rate}")
        if self.total_cost < 0:
            raise ValueError(f"total_cost must be >= 0, got {self.total_cost}")
        if self.cost_per_comment < 0:
            raise ValueError(f"cost_per_comment must be >= 0, got {self.cost_per_comment}")
        if not 0.0 <= self.cache_hit_rate <= 1.0:
            raise ValueError(
                f"cache_hit_rate must be between 0.0 and 1.0, got {self.cache_hit_rate}"
            )
        if self.cache_savings < 0:
            raise ValueError(f"cache_savings must be >= 0, got {self.cache_savings}")
        if self.fallback_count < 0:
            raise ValueError(f"fallback_count must be >= 0, got {self.fallback_count}")
        if not 0.0 <= self.fallback_rate <= 1.0:
            raise ValueError(f"fallback_rate must be between 0.0 and 1.0, got {self.fallback_rate}")
        # All validations passed - wrap provider_stats in MappingProxyType
        object.__setattr__(self, "provider_stats", MappingProxyType(dict(self.provider_stats)))
