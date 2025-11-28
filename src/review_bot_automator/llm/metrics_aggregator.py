# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Metrics aggregation for LLM provider performance tracking.

This module provides the MetricsAggregator class for collecting, aggregating,
and exporting metrics across multiple LLM requests and providers.

Example:
    >>> aggregator = MetricsAggregator()
    >>> aggregator.set_pr_info("owner", "repo", 123)
    >>> request_id = aggregator.start_request("anthropic", "claude-haiku-4")
    >>> # ... make LLM call ...
    >>> aggregator.end_request(request_id, success=True, tokens_input=100, tokens_output=50)
    >>> metrics = aggregator.get_aggregated_metrics(comments_processed=10)
    >>> aggregator.export_json(Path("metrics.json"))
"""

from __future__ import annotations

import contextlib
import csv
import json
import logging
import os
import statistics
import tempfile
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from review_bot_automator.benchmarks.utils import calculate_percentile
from review_bot_automator.llm.metrics import (
    AggregatedMetrics,
    ProviderStats,
    RequestMetrics,
)

logger = logging.getLogger(__name__)


def _provider_stats_to_dict(stats: ProviderStats) -> dict[str, Any]:
    """Convert ProviderStats to JSON-serializable dict.

    Handles MappingProxyType fields that can't be deepcopied by asdict().
    """
    return {
        "provider": stats.provider,
        "model": stats.model,
        "total_requests": stats.total_requests,
        "successful_requests": stats.successful_requests,
        "failed_requests": stats.failed_requests,
        "success_rate": stats.success_rate,
        "total_cost": stats.total_cost,
        "total_tokens": stats.total_tokens,
        "avg_latency": stats.avg_latency,
        "latency_p50": stats.latency_p50,
        "latency_p95": stats.latency_p95,
        "latency_p99": stats.latency_p99,
        "cache_hit_rate": stats.cache_hit_rate,
        "error_counts": dict(stats.error_counts),
    }


class MetricsAggregator:
    """Thread-safe metrics collection and aggregation for LLM requests.

    Collects per-request metrics and provides aggregated statistics including
    latency percentiles, success rates, and cost analysis.

    Attributes:
        pr_info: Optional PR metadata (owner, repo, pr_number).

    Example:
        >>> aggregator = MetricsAggregator()
        >>> aggregator.start_request("anthropic", "claude-haiku-4")
        'req-abc123'
        >>> aggregator.end_request("req-abc123", success=True, tokens_input=100)
        >>> metrics = aggregator.get_aggregated_metrics()
        >>> print(f"Total requests: {metrics.total_requests}")
        Total requests: 1
    """

    def __init__(self) -> None:
        """Initialize metrics aggregator."""
        self._requests: list[RequestMetrics] = []
        self._pending: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._pr_info: dict[str, Any] | None = None
        self._fallback_count: int = 0
        self._fallback_total: int = 0

    def set_pr_info(self, owner: str, repo: str, pr_number: int) -> None:
        """Set PR metadata for metrics context.

        Args:
            owner: Repository owner/organization.
            repo: Repository name.
            pr_number: Pull request number.
        """
        with self._lock:
            self._pr_info = {
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
            }

    def get_pr_info(self) -> dict[str, Any] | None:
        """Get PR metadata for metrics context.

        Returns:
            Dict with owner, repo, pr_number keys, or None if not set.
        """
        with self._lock:
            return self._pr_info.copy() if self._pr_info else None

    def set_fallback_stats(self, fallback_count: int, total_count: int) -> None:
        """Set fallback statistics from parser.

        Args:
            fallback_count: Number of times regex fallback was triggered.
            total_count: Total number of parse attempts.
        """
        with self._lock:
            self._fallback_count = fallback_count
            self._fallback_total = total_count

    def get_fallback_stats(self) -> tuple[int, int, float]:
        """Get fallback statistics.

        Returns:
            Tuple of (fallback_count, total_count, fallback_rate).
        """
        with self._lock:
            rate = self._fallback_count / self._fallback_total if self._fallback_total > 0 else 0.0
            return (self._fallback_count, self._fallback_total, rate)

    def start_request(
        self,
        provider: str,
        model: str,
        cache_hit: bool = False,
    ) -> str:
        """Start tracking a new LLM request.

        Args:
            provider: Provider name (e.g., "anthropic", "openai", "ollama").
            model: Model identifier.
            cache_hit: Whether this request will be served from cache.

        Returns:
            Unique request ID for use with end_request().
        """
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._pending[request_id] = {
                "provider": provider,
                "model": model,
                "cache_hit": cache_hit,
                "start_time": time.perf_counter(),
            }
        logger.debug(
            "Started LLM request",
            extra={
                "request_id": request_id,
                "provider": provider,
                "model": model,
                "cache_hit": cache_hit,
            },
        )
        return request_id

    def end_request(
        self,
        request_id: str,
        success: bool,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost: float = 0.0,
        error_type: str | None = None,
    ) -> None:
        """Complete tracking for a request.

        Args:
            request_id: ID returned from start_request().
            success: Whether the request completed successfully.
            tokens_input: Number of input tokens consumed.
            tokens_output: Number of output tokens generated.
            cost: Request cost in USD.
            error_type: Error class name if request failed.

        Raises:
            ValueError: If request_id is not found in pending requests.
        """
        end_time = time.perf_counter()

        with self._lock:
            if request_id not in self._pending:
                raise ValueError(f"Unknown request_id: {request_id}")

            pending = self._pending.pop(request_id)
            latency = end_time - pending["start_time"]

            metrics = RequestMetrics(
                request_id=request_id,
                provider=pending["provider"],
                model=pending["model"],
                latency_seconds=latency,
                success=success,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost=cost,
                cache_hit=pending["cache_hit"],
                error_type=error_type,
            )
            self._requests.append(metrics)

        logger.debug(
            "Completed LLM request",
            extra={
                "request_id": request_id,
                "provider": pending["provider"],
                "model": pending["model"],
                "success": success,
                "latency_seconds": latency,
                "error_type": error_type,
            },
        )

    def record_request(self, metrics: RequestMetrics) -> None:
        """Directly record a completed RequestMetrics object.

        Useful when metrics are constructed externally (e.g., from provider).

        Args:
            metrics: Completed request metrics to record.
        """
        with self._lock:
            self._requests.append(metrics)

    def get_provider_stats(self, provider: str) -> ProviderStats | None:
        """Get aggregated stats for a specific provider.

        Args:
            provider: Provider name to get stats for.

        Returns:
            ProviderStats for the provider, or None if no requests found.
        """
        with self._lock:
            provider_requests = [r for r in self._requests if r.provider == provider]

        if not provider_requests:
            return None

        return self._calculate_provider_stats(provider_requests)

    def get_aggregated_metrics(self, comments_processed: int = 0) -> AggregatedMetrics:
        """Get fully aggregated metrics across all providers.

        Args:
            comments_processed: Number of comments processed (for cost_per_comment).

        Returns:
            AggregatedMetrics with overall statistics and per-provider breakdown.
        """
        with self._lock:
            requests = list(self._requests)

        if not requests:
            return AggregatedMetrics()

        # Group requests by provider
        by_provider: dict[str, list[RequestMetrics]] = defaultdict(list)
        for req in requests:
            by_provider[req.provider].append(req)

        # Calculate per-provider stats
        provider_stats: dict[str, ProviderStats] = {}
        for provider, provider_requests in by_provider.items():
            provider_stats[provider] = self._calculate_provider_stats(provider_requests)

        # Calculate overall metrics
        all_latencies = [r.latency_seconds for r in requests]
        successful = [r for r in requests if r.success]
        cache_hits = [r for r in requests if r.cache_hit]
        non_cache_requests = [r for r in requests if not r.cache_hit]

        total_requests = len(requests)
        successful_requests = len(successful)
        failed_requests = total_requests - successful_requests
        success_rate = successful_requests / total_requests if total_requests > 0 else 0.0

        total_cost = sum(r.cost for r in requests)
        cost_per_comment = total_cost / comments_processed if comments_processed > 0 else 0.0

        cache_hit_rate = len(cache_hits) / total_requests if total_requests > 0 else 0.0

        # Estimate cache savings (assume cached requests would have cost same as average).
        # If all requests are cache hits, we can't compute a baseline cost, so savings = 0.
        avg_non_cache_cost = (
            sum(r.cost for r in non_cache_requests) / len(non_cache_requests)
            if non_cache_requests
            else 0.0
        )
        cache_savings = len(cache_hits) * avg_non_cache_cost

        # Get fallback stats (thread-safe via lock inside method)
        fallback_count, _fallback_total, fallback_rate = self.get_fallback_stats()

        return AggregatedMetrics(
            provider_stats=provider_stats,
            latency_p50=self._safe_percentile(all_latencies, 50),
            latency_p95=self._safe_percentile(all_latencies, 95),
            latency_p99=self._safe_percentile(all_latencies, 99),
            latency_avg=statistics.mean(all_latencies) if all_latencies else 0.0,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            success_rate=success_rate,
            total_cost=total_cost,
            cost_per_comment=cost_per_comment,
            cache_hit_rate=cache_hit_rate,
            cache_savings=cache_savings,
            fallback_count=fallback_count,
            fallback_rate=fallback_rate,
        )

    def export_json(self, path: Path, include_requests: bool = False) -> None:
        """Export metrics to JSON file.

        Args:
            path: Output file path.
            include_requests: If True, include per-request data (verbose).

        Raises:
            OSError: If file cannot be written.
        """
        try:
            metrics = self.get_aggregated_metrics()

            # Thread-safe access to _pr_info and _requests
            with self._lock:
                pr_info_copy = self._pr_info.copy() if self._pr_info else None
                requests_copy = [asdict(r) for r in self._requests] if include_requests else None

            data: dict[str, Any] = {
                "summary": {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "success_rate": metrics.success_rate,
                    "latency_p50": metrics.latency_p50,
                    "latency_p95": metrics.latency_p95,
                    "latency_p99": metrics.latency_p99,
                    "latency_avg": metrics.latency_avg,
                    "total_cost": metrics.total_cost,
                    "cost_per_comment": metrics.cost_per_comment,
                    "cache_hit_rate": metrics.cache_hit_rate,
                    "cache_savings": metrics.cache_savings,
                    "fallback_count": metrics.fallback_count,
                    "fallback_rate": metrics.fallback_rate,
                },
                "provider_stats": {
                    name: _provider_stats_to_dict(stats)
                    for name, stats in metrics.provider_stats.items()
                },
            }

            if pr_info_copy:
                data["pr_info"] = pr_info_copy

            if requests_copy is not None:
                data["requests"] = requests_copy

            # Atomic write: write to temp file, then replace
            temp_fd, temp_path = tempfile.mkstemp(
                dir=path.parent, prefix=".metrics_", suffix=".json"
            )
            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                # Security: Restrict file permissions to owner only before replacing
                os.chmod(temp_path, 0o600)
                os.replace(temp_path, path)
                logger.info("Exported metrics to %s (permissions: 0600)", path)
            except Exception:
                # Clean up temp file on error
                with contextlib.suppress(OSError):
                    os.unlink(temp_path)
                raise
        except OSError as e:
            logger.error("Failed to export metrics to %s: %s", path, e)
            raise

    def export_csv(self, path: Path) -> None:
        """Export per-request metrics to CSV file.

        Args:
            path: Output file path.

        Raises:
            OSError: If file cannot be written.
        """
        fieldnames = [
            "request_id",
            "provider",
            "model",
            "latency_seconds",
            "success",
            "tokens_input",
            "tokens_output",
            "cost",
            "cache_hit",
            "error_type",
        ]

        with self._lock:
            requests = list(self._requests)

        try:
            # Atomic write: write to temp file, then replace
            temp_fd, temp_path = tempfile.mkstemp(
                dir=path.parent, prefix=".metrics_", suffix=".csv"
            )
            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for req in requests:
                        writer.writerow(asdict(req))
                # Security: Restrict file permissions to owner only before replacing
                os.chmod(temp_path, 0o600)
                os.replace(temp_path, path)
                logger.info("Exported metrics to %s (permissions: 0600)", path)
            except Exception:
                # Clean up temp file on error
                with contextlib.suppress(OSError):
                    os.unlink(temp_path)
                raise
        except OSError as e:
            logger.error("Failed to export metrics to %s: %s", path, e)
            raise

    def get_summary_report(self) -> str:
        """Generate human-readable summary report.

        Returns:
            Formatted multi-line summary string.
        """
        metrics = self.get_aggregated_metrics()

        lines = [
            "=== LLM Metrics Summary ===",
            f"Total requests: {metrics.total_requests}",
            f"Success rate: {metrics.success_rate * 100:.1f}%",
            f"Latency: p50={metrics.latency_p50:.3f}s, "
            f"p95={metrics.latency_p95:.3f}s, "
            f"p99={metrics.latency_p99:.3f}s",
            f"Total cost: ${metrics.total_cost:.4f}",
            f"Cache hit rate: {metrics.cache_hit_rate * 100:.1f}%",
            f"Fallback rate: {metrics.fallback_rate * 100:.1f}% "
            f"({metrics.fallback_count} fallbacks)",
        ]

        if metrics.provider_stats:
            lines.append("\nPer-provider breakdown:")
            for name, stats in metrics.provider_stats.items():
                lines.append(
                    f"  {name}: {stats.total_requests} requests, "
                    f"p95={stats.latency_p95:.3f}s, ${stats.total_cost:.4f}"
                )

        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all collected metrics."""
        with self._lock:
            self._requests.clear()
            self._pending.clear()
            self._fallback_count = 0
            self._fallback_total = 0

    def _calculate_provider_stats(self, requests: list[RequestMetrics]) -> ProviderStats:
        """Calculate aggregated stats for a list of requests.

        Args:
            requests: List of requests (assumed to be from same provider).

        Returns:
            ProviderStats with aggregated statistics.
        """
        if not requests:
            raise ValueError("Cannot calculate stats for empty request list")

        provider = requests[0].provider
        models = {r.model for r in requests}
        model = requests[0].model if len(models) == 1 else "mixed"

        latencies = [r.latency_seconds for r in requests]
        successful = [r for r in requests if r.success]
        cache_hits = [r for r in requests if r.cache_hit]
        failed = [r for r in requests if not r.success]

        # Count errors by type
        error_counts: dict[str, int] = defaultdict(int)
        for req in failed:
            if req.error_type:
                error_counts[req.error_type] += 1

        total_requests = len(requests)
        successful_requests = len(successful)
        failed_requests = len(failed)

        return ProviderStats(
            provider=provider,
            model=model,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            success_rate=successful_requests / total_requests if total_requests > 0 else 0.0,
            total_cost=sum(r.cost for r in requests),
            total_tokens=sum(r.total_tokens for r in requests),
            avg_latency=statistics.mean(latencies) if latencies else 0.0,
            latency_p50=self._safe_percentile(latencies, 50),
            latency_p95=self._safe_percentile(latencies, 95),
            latency_p99=self._safe_percentile(latencies, 99),
            cache_hit_rate=len(cache_hits) / total_requests if total_requests > 0 else 0.0,
            error_counts=dict(error_counts),
        )

    @staticmethod
    def _safe_percentile(data: list[float], percentile: int) -> float:
        """Calculate percentile safely, returning 0.0 for empty data.

        Args:
            data: List of values.
            percentile: Percentile to calculate (0-100).

        Returns:
            Percentile value, or 0.0 if data is empty.
        """
        if not data:
            return 0.0
        return calculate_percentile(data, percentile)
