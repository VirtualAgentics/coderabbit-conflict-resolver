"""Metrics tracking and aggregation for LLM operations.

This package provides centralized metrics collection for tracking costs, latency,
token usage, and error rates across all LLM providers.
"""

# Legacy metrics (original LLMMetrics class)
from pr_conflict_resolver.llm.metrics.llm_metrics import LLMMetrics

# New metrics aggregation system
from pr_conflict_resolver.llm.metrics.metrics_aggregator import (
    MetricsAggregator,
    MetricsSummary,
    ProviderMetrics,
    RequestTracker,
)

__all__ = [
    # Legacy
    "LLMMetrics",
    # New system
    "MetricsAggregator",
    "MetricsSummary",
    "ProviderMetrics",
    "RequestTracker",
]
