"""Centralized metrics tracking and aggregation for LLM operations.

This module provides comprehensive metrics collection, aggregation, and reporting
for LLM usage including costs, latency, token usage, and error rates.

Metrics Tracked:
    - Request counts (total, success, failure)
    - Token usage (input, output, total)
    - Cost tracking (per-provider, per-model)
    - Latency (p50, p95, p99)
    - Error rates and types
    - Cache hit rates

Usage Examples:
    Track LLM operation:
        >>> metrics = MetricsAggregator()
        >>> with metrics.track_request("anthropic", "claude-sonnet-4-5"):
        ...     response = provider.generate("prompt")
        >>> metrics.record_tokens(1000, 500)
        >>> metrics.record_cost(0.015)

    Get metrics summary:
        >>> summary = metrics.get_summary()
        >>> print(f"Total cost: ${summary.total_cost:.2f}")
        >>> print(f"Average latency: {summary.avg_latency_ms:.0f}ms")

    Export metrics for monitoring:
        >>> metrics_dict = metrics.to_dict()
        >>> send_to_monitoring(metrics_dict)
"""

import logging
import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProviderMetrics:
    """Metrics for a specific provider/model combination.

    Attributes:
        provider: Provider name (e.g., "anthropic", "openai")
        model: Model name (e.g., "claude-sonnet-4-5", "gpt-4")
        total_requests: Total requests made
        successful_requests: Successfully completed requests
        failed_requests: Failed requests
        total_input_tokens: Total input tokens consumed
        total_output_tokens: Total output tokens generated
        total_cost: Total cost in USD
        total_latency_ms: Cumulative latency in milliseconds
        latencies_ms: List of individual latencies for percentile calculation
        errors: Count of errors by type

    Examples:
        >>> metrics = ProviderMetrics("anthropic", "claude-sonnet-4-5")
        >>> metrics.total_requests += 1
        >>> metrics.total_cost += 0.015
    """

    provider: str
    model: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=10000))
    errors: dict[str, int] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def success_rate(self) -> float:
        """Success rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    @property
    def avg_cost_per_request(self) -> float:
        """Average cost per request in USD."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_cost / self.successful_requests


@dataclass(frozen=True)
class MetricsSummary:
    """Aggregated metrics summary across all providers.

    Attributes:
        total_requests: Total requests across all providers
        total_successful: Total successful requests
        total_failed: Total failed requests
        total_tokens: Total tokens used
        total_cost: Total cost in USD
        avg_latency_ms: Average latency across all requests
        p50_latency_ms: 50th percentile latency
        p95_latency_ms: 95th percentile latency
        p99_latency_ms: 99th percentile latency
        success_rate: Overall success rate (0.0 to 1.0)
        cost_by_provider: Cost breakdown by provider
        requests_by_provider: Request count by provider

    Examples:
        >>> summary = metrics.get_summary()
        >>> print(f"Total cost: ${summary.total_cost:.2f}")
        >>> print(f"Success rate: {summary.success_rate * 100:.1f}%")
        >>> print(f"P95 latency: {summary.p95_latency_ms:.0f}ms")
    """

    total_requests: int
    total_successful: int
    total_failed: int
    total_tokens: int
    total_cost: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    success_rate: float
    cost_by_provider: dict[str, float]
    requests_by_provider: dict[str, int]


class MetricsAggregator:
    """Centralized metrics collection and aggregation for LLM operations.

    Thread-safe metrics tracking for multiple providers and models. Collects
    request counts, token usage, costs, latency, and errors. Provides aggregation
    and reporting capabilities.

    Attributes:
        None (internal state is private)

    Examples:
        Basic tracking:
            >>> metrics = MetricsAggregator()
            >>> with metrics.track_request("anthropic", "claude-sonnet-4-5") as tracker:
            ...     response = provider.generate("prompt")
            ...     tracker.record_tokens(1000, 500)
            ...     tracker.record_cost(0.015)

        Manual tracking:
            >>> metrics.increment_requests("openai", "gpt-4")
            >>> metrics.record_success("openai", "gpt-4", latency_ms=250)
            >>> metrics.record_tokens(2000, 1000)
            >>> metrics.record_cost(0.06)

        Get summary:
            >>> summary = metrics.get_summary()
            >>> print(f"Total: ${summary.total_cost:.2f}, "
            ...       f"{summary.total_requests} requests")
    """

    def __init__(self) -> None:
        """Initialize metrics aggregator.

        Examples:
            >>> metrics = MetricsAggregator()
        """
        # Metrics storage: {(provider, model): ProviderMetrics}
        self._metrics: dict[tuple[str, str], ProviderMetrics] = {}
        self._lock = threading.RLock()
        # Use thread-local storage for provider/model context to avoid cross-thread attribution
        self._thread_locals = threading.local()

        logger.debug("Initialized MetricsAggregator")

    def _get_or_create_metrics(self, provider: str, model: str) -> ProviderMetrics:
        """Get or create ProviderMetrics for provider/model (caller must hold lock).

        Args:
            provider: Provider name
            model: Model name

        Returns:
            ProviderMetrics instance

        Note:
            This method must be called while holding self._lock. This is enforced
            by callers using 'with self._lock:' context manager. We cannot add a
            runtime assertion here because RLock does not provide a .locked()
            method like Lock does.
        """
        key = (provider, model)
        if key not in self._metrics:
            self._metrics[key] = ProviderMetrics(provider=provider, model=model)
        return self._metrics[key]

    def increment_requests(self, provider: str, model: str) -> None:
        """Increment request count for provider/model.

        Args:
            provider: Provider name
            model: Model name

        Examples:
            >>> metrics.increment_requests("anthropic", "claude-sonnet-4-5")
        """
        with self._lock:
            pm = self._get_or_create_metrics(provider, model)
            pm.total_requests += 1

    def record_success(self, provider: str, model: str, latency_ms: float) -> None:
        """Record successful request with latency.

        Args:
            provider: Provider name
            model: Model name
            latency_ms: Request latency in milliseconds

        Examples:
            >>> metrics.record_success("anthropic", "claude-sonnet-4-5", 245.5)
        """
        with self._lock:
            pm = self._get_or_create_metrics(provider, model)
            pm.successful_requests += 1
            pm.total_latency_ms += latency_ms
            pm.latencies_ms.append(latency_ms)

    def record_failure(self, provider: str, model: str, error_type: str) -> None:
        """Record failed request with error type.

        Args:
            provider: Provider name
            model: Model name
            error_type: Type of error (exception class name)

        Examples:
            >>> metrics.record_failure("openai", "gpt-4", "TimeoutError")
        """
        with self._lock:
            pm = self._get_or_create_metrics(provider, model)
            pm.failed_requests += 1
            pm.errors[error_type] = pm.errors.get(error_type, 0) + 1

    def record_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        """Record token usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            provider: Provider name (uses current if None)
            model: Model name (uses current if None)

        Raises:
            RuntimeError: If provider and model context is missing

        Examples:
            >>> with metrics.track_request("anthropic", "claude-sonnet-4-5") as tracker:
            ...     tracker.record_tokens(1000, 500)
        """
        # Validate inputs before lock acquisition (fail fast)
        if not isinstance(input_tokens, int) or input_tokens < 0:
            raise ValueError(f"input_tokens must be non-negative integer, got: {input_tokens}")
        if not isinstance(output_tokens, int) or output_tokens < 0:
            raise ValueError(f"output_tokens must be non-negative integer, got: {output_tokens}")

        provider = provider or getattr(self._thread_locals, "provider", None)
        model = model or getattr(self._thread_locals, "model", None)

        if not provider or not model:
            raise RuntimeError(
                "record_tokens called without provider/model context - "
                "use track_request() context manager or provide provider/model explicitly"
            )

        with self._lock:
            pm = self._get_or_create_metrics(provider, model)
            pm.total_input_tokens += input_tokens
            pm.total_output_tokens += output_tokens

    def record_cost(
        self, cost: float, provider: str | None = None, model: str | None = None
    ) -> None:
        """Record cost for request.

        Args:
            cost: Cost in USD
            provider: Provider name (uses current if None)
            model: Model name (uses current if None)

        Raises:
            RuntimeError: If provider and model context is missing

        Examples:
            >>> with metrics.track_request("anthropic", "claude-sonnet-4-5") as tracker:
            ...     tracker.record_cost(0.015)
        """
        # Validate cost parameter before acquiring lock (fail fast)
        if not isinstance(cost, (int, float)):
            raise ValueError(f"cost must be a number (int or float), got: {type(cost).__name__}")
        if cost < 0:
            raise ValueError(f"cost must be a non-negative number, got: {cost}")

        provider = provider or getattr(self._thread_locals, "provider", None)
        model = model or getattr(self._thread_locals, "model", None)

        if not provider or not model:
            raise RuntimeError(
                "record_cost called without provider/model context - "
                "use track_request() context manager or provide provider/model explicitly"
            )

        with self._lock:
            pm = self._get_or_create_metrics(provider, model)
            pm.total_cost += cost

    @contextmanager
    def track_request(self, provider: str, model: str) -> Iterator["RequestTracker"]:
        """Context manager for tracking a request with automatic timing.

        Args:
            provider: Provider name
            model: Model name

        Yields:
            RequestTracker for recording tokens and cost

        Examples:
            >>> with metrics.track_request("anthropic", "claude-sonnet-4-5") as tracker:
            ...     response = provider.generate("prompt")
            ...     tracker.record_tokens(1000, 500)
            ...     tracker.record_cost(0.015)
        """
        self.increment_requests(provider, model)
        start_time = time.monotonic()

        # Set thread-local context (thread-safe, won't affect other threads)
        old_provider = getattr(self._thread_locals, "provider", None)
        old_model = getattr(self._thread_locals, "model", None)
        self._thread_locals.provider = provider
        self._thread_locals.model = model

        tracker = RequestTracker(self, provider, model)

        try:
            yield tracker
            # If we get here, request succeeded
            latency_ms = (time.monotonic() - start_time) * 1000
            self.record_success(provider, model, latency_ms)

        except Exception as e:
            # Request failed
            error_type = type(e).__name__
            self.record_failure(provider, model, error_type)
            raise

        finally:
            # Restore thread-local context
            self._thread_locals.provider = old_provider
            self._thread_locals.model = old_model

    def get_summary(self) -> MetricsSummary:
        """Get aggregated metrics summary.

        Returns:
            MetricsSummary with overall statistics

        Examples:
            >>> summary = metrics.get_summary()
            >>> print(f"Cost: ${summary.total_cost:.2f}")
            >>> print(f"Success rate: {summary.success_rate * 100:.1f}%")
            >>> print(f"P95 latency: {summary.p95_latency_ms:.0f}ms")
        """
        with self._lock:
            total_requests = 0
            total_successful = 0
            total_failed = 0
            total_tokens = 0
            total_cost = 0.0
            total_latency_ms = 0.0
            all_latencies: list[float] = []
            cost_by_provider: dict[str, float] = defaultdict(float)
            requests_by_provider: dict[str, int] = defaultdict(int)

            for pm in self._metrics.values():
                total_requests += pm.total_requests
                total_successful += pm.successful_requests
                total_failed += pm.failed_requests
                total_tokens += pm.total_tokens
                total_cost += pm.total_cost
                total_latency_ms += pm.total_latency_ms
                all_latencies.extend(pm.latencies_ms)
                cost_by_provider[pm.provider] += pm.total_cost
                requests_by_provider[pm.provider] += pm.total_requests

            # Calculate averages
            avg_latency = total_latency_ms / total_successful if total_successful > 0 else 0.0
            success_rate = total_successful / total_requests if total_requests > 0 else 0.0

            # Calculate percentiles
            p50, p95, p99 = self._calculate_percentiles(all_latencies)

            return MetricsSummary(
                total_requests=total_requests,
                total_successful=total_successful,
                total_failed=total_failed,
                total_tokens=total_tokens,
                total_cost=total_cost,
                avg_latency_ms=avg_latency,
                p50_latency_ms=p50,
                p95_latency_ms=p95,
                p99_latency_ms=p99,
                success_rate=success_rate,
                cost_by_provider=dict(cost_by_provider),
                requests_by_provider=dict(requests_by_provider),
            )

    def _calculate_percentiles(self, latencies: list[float]) -> tuple[float, float, float]:
        """Calculate p50, p95, p99 percentiles.

        Args:
            latencies: List of latency values

        Returns:
            Tuple of (p50, p95, p99)
        """
        if not latencies:
            return (0.0, 0.0, 0.0)

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        # Use a modified nearest-rank method for percentiles
        # This implementation is optimized for latency metrics and SLA reporting,
        # prioritizing consistency over strict statistical conformity:
        #
        # - When n*p is an exact integer (e.g., 10*0.5=5.0), we use that index directly,
        #   returning the value at position 5 (6th element) instead of averaging indices 4 and 5.
        #   This biases toward higher values but avoids interpolation complexity.
        #
        # - When n*p is not exact, we round up using ceil(n*p) - 1 to get the next rank.
        #
        # Example: For 10 values [0,10,20,30,40,50,60,70,80,90]:
        #   - p50: n*p = 10*0.5 = 5.0 (exact) → index 5 → value 50
        #   - p95: n*p = 10*0.95 = 9.5 → ceil(9.5)-1 = 9 → value 90
        #
        # This method is consistent with the percentile reporting used throughout the metrics
        # system and ensures latency SLAs are conservatively estimated.
        def percentile_index(p: float) -> int:
            """Calculate 0-based index for percentile p (0-1 range)."""
            idx = n * p
            if idx == int(idx):  # Exact integer, use it directly (0-indexed)
                return min(n - 1, int(idx))
            else:  # Not exact, round up
                return min(n - 1, math.ceil(idx) - 1)

        p50_idx = percentile_index(0.50)
        p95_idx = percentile_index(0.95)
        p99_idx = percentile_index(0.99)

        p50 = sorted_latencies[p50_idx]
        p95 = sorted_latencies[p95_idx]
        p99 = sorted_latencies[p99_idx]

        return (p50, p95, p99)

    def get_provider_metrics(self, provider: str, model: str) -> ProviderMetrics | None:
        """Get metrics for specific provider/model.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            ProviderMetrics if found, None otherwise

        Examples:
            >>> pm = metrics.get_provider_metrics("anthropic", "claude-sonnet-4-5")
            >>> if pm:
            ...     print(f"Requests: {pm.total_requests}")
        """
        with self._lock:
            return self._metrics.get((provider, model))

    def reset(self) -> None:
        """Reset all metrics.

        Examples:
            >>> metrics.reset()  # Clear all collected metrics
        """
        with self._lock:
            self._metrics.clear()
            logger.info("Metrics reset")

    def to_dict(self) -> dict[str, Any]:
        """Export metrics as dictionary for serialization.

        Returns:
            Dictionary with all metrics data

        Examples:
            >>> metrics_dict = metrics.to_dict()
            >>> import json
            >>> json.dump(metrics_dict, open("metrics.json", "w"))
        """
        with self._lock:
            summary = self.get_summary()
            return {
                "summary": {
                    "total_requests": summary.total_requests,
                    "total_successful": summary.total_successful,
                    "total_failed": summary.total_failed,
                    "total_tokens": summary.total_tokens,
                    "total_cost": summary.total_cost,
                    "avg_latency_ms": summary.avg_latency_ms,
                    "p50_latency_ms": summary.p50_latency_ms,
                    "p95_latency_ms": summary.p95_latency_ms,
                    "p99_latency_ms": summary.p99_latency_ms,
                    "success_rate": summary.success_rate,
                    "cost_by_provider": summary.cost_by_provider,
                    "requests_by_provider": summary.requests_by_provider,
                },
                "by_provider": {
                    f"{pm.provider}/{pm.model}": {
                        "total_requests": pm.total_requests,
                        "successful_requests": pm.successful_requests,
                        "failed_requests": pm.failed_requests,
                        "total_tokens": pm.total_tokens,
                        "total_cost": pm.total_cost,
                        "avg_latency_ms": pm.avg_latency_ms,
                        "success_rate": pm.success_rate,
                        "errors": dict(pm.errors),
                    }
                    for pm in self._metrics.values()
                },
            }


class RequestTracker:
    """Helper for tracking metrics within a request context.

    Used by track_request() context manager. Should not be instantiated directly.

    Examples:
        >>> with metrics.track_request("anthropic", "claude-sonnet-4-5") as tracker:
        ...     tracker.record_tokens(1000, 500)
        ...     tracker.record_cost(0.015)
    """

    def __init__(self, aggregator: MetricsAggregator, provider: str, model: str) -> None:
        """Initialize request tracker.

        Args:
            aggregator: Parent MetricsAggregator
            provider: Provider name
            model: Model name
        """
        self._aggregator = aggregator
        self._provider = provider
        self._model = model

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage for this request.

        Args:
            input_tokens: Input token count
            output_tokens: Output token count
        """
        self._aggregator.record_tokens(input_tokens, output_tokens, self._provider, self._model)

    def record_cost(self, cost: float) -> None:
        """Record cost for this request.

        Args:
            cost: Cost in USD
        """
        self._aggregator.record_cost(cost, self._provider, self._model)
