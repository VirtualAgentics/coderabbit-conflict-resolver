"""Tests for metrics aggregation and tracking.

This module tests centralized metrics collection for LLM operations including
costs, latency, token usage, and error rates.
"""

import time

import pytest

from pr_conflict_resolver.llm.metrics.metrics_aggregator import (
    MetricsAggregator,
    ProviderMetrics,
)


class TestMetricsAggregatorInitialization:
    """Test MetricsAggregator initialization."""

    def test_init(self) -> None:
        """Test basic initialization."""
        metrics = MetricsAggregator()
        summary = metrics.get_summary()

        assert summary.total_requests == 0
        assert summary.total_cost == 0.0


class TestMetricsAggregatorBasicTracking:
    """Test basic metric tracking operations."""

    def test_increment_requests(self) -> None:
        """Test incrementing request count."""
        metrics = MetricsAggregator()

        metrics.increment_requests("anthropic", "claude-sonnet-4-5")
        metrics.increment_requests("anthropic", "claude-sonnet-4-5")

        pm = metrics.get_provider_metrics("anthropic", "claude-sonnet-4-5")
        assert pm is not None
        assert pm.total_requests == 2

    def test_record_success(self) -> None:
        """Test recording successful requests."""
        metrics = MetricsAggregator()

        metrics.increment_requests("openai", "gpt-4")
        metrics.record_success("openai", "gpt-4", latency_ms=250.5)

        pm = metrics.get_provider_metrics("openai", "gpt-4")
        assert pm is not None
        assert pm.successful_requests == 1
        assert pm.total_latency_ms == 250.5
        assert len(pm.latencies_ms) == 1

    def test_record_failure(self) -> None:
        """Test recording failed requests."""
        metrics = MetricsAggregator()

        metrics.increment_requests("anthropic", "claude-3")
        metrics.record_failure("anthropic", "claude-3", "TimeoutError")

        pm = metrics.get_provider_metrics("anthropic", "claude-3")
        assert pm is not None
        assert pm.failed_requests == 1
        assert pm.errors["TimeoutError"] == 1

    def test_record_tokens(self) -> None:
        """Test recording token usage."""
        metrics = MetricsAggregator()

        # Use track_request to set proper context
        with (
            pytest.raises(RuntimeError),
            metrics.track_request("anthropic", "claude-sonnet-4-5") as tracker,
        ):
            tracker.record_tokens(1000, 500)
            # Don't let it succeed naturally, we want to test token recording
            raise RuntimeError("Simulated error")

        # Even though request failed, tokens should be recorded
        pm = metrics.get_provider_metrics("anthropic", "claude-sonnet-4-5")
        assert pm is not None
        assert pm.total_input_tokens == 1000
        assert pm.total_output_tokens == 500
        assert pm.total_tokens == 1500

    def test_record_cost(self) -> None:
        """Test recording cost."""
        metrics = MetricsAggregator()

        # Use track_request to set proper context
        with (
            pytest.raises(RuntimeError),
            metrics.track_request("openai", "gpt-4") as tracker,
        ):
            tracker.record_cost(0.06)
            raise RuntimeError("Simulated error")

        # Even though request failed, cost should be recorded
        pm = metrics.get_provider_metrics("openai", "gpt-4")
        assert pm is not None
        assert pm.total_cost == 0.06


class TestMetricsAggregatorTrackRequest:
    """Test track_request context manager."""

    def test_track_request_success(self) -> None:
        """Test track_request with successful operation."""
        metrics = MetricsAggregator()

        with metrics.track_request("anthropic", "claude-sonnet-4-5") as tracker:
            tracker.record_tokens(1000, 500)
            tracker.record_cost(0.015)
            # Simulate some work
            time.sleep(0.01)

        pm = metrics.get_provider_metrics("anthropic", "claude-sonnet-4-5")
        assert pm is not None
        assert pm.total_requests == 1
        assert pm.successful_requests == 1
        assert pm.failed_requests == 0
        assert pm.total_input_tokens == 1000
        assert pm.total_output_tokens == 500
        assert pm.total_cost == 0.015
        assert pm.avg_latency_ms > 0

    def test_track_request_failure(self) -> None:
        """Test track_request with failed operation."""
        metrics = MetricsAggregator()

        with (
            pytest.raises(RuntimeError),
            metrics.track_request("openai", "gpt-4") as tracker,
        ):
            tracker.record_tokens(500, 0)
            raise RuntimeError("API Error")

        pm = metrics.get_provider_metrics("openai", "gpt-4")
        assert pm is not None
        assert pm.total_requests == 1
        assert pm.successful_requests == 0
        assert pm.failed_requests == 1
        assert pm.errors["RuntimeError"] == 1

    def test_track_request_records_latency(self) -> None:
        """Test that track_request records latency automatically."""
        metrics = MetricsAggregator()

        with metrics.track_request("anthropic", "claude-sonnet-4-5"):
            time.sleep(0.05)  # 50ms

        pm = metrics.get_provider_metrics("anthropic", "claude-sonnet-4-5")
        assert pm is not None
        assert pm.avg_latency_ms >= 40  # At least 40ms (accounting for overhead)
        assert len(pm.latencies_ms) == 1


class TestProviderMetrics:
    """Test ProviderMetrics dataclass and properties."""

    def test_provider_metrics_creation(self) -> None:
        """Test ProviderMetrics creation."""
        pm = ProviderMetrics("anthropic", "claude-sonnet-4-5")

        assert pm.provider == "anthropic"
        assert pm.model == "claude-sonnet-4-5"
        assert pm.total_requests == 0

    def test_total_tokens_property(self) -> None:
        """Test total_tokens property."""
        pm = ProviderMetrics("test", "test")
        pm.total_input_tokens = 1000
        pm.total_output_tokens = 500

        assert pm.total_tokens == 1500

    def test_success_rate_property(self) -> None:
        """Test success_rate property."""
        pm = ProviderMetrics("test", "test")

        # No requests
        assert pm.success_rate == 0.0

        # 7 out of 10 successful
        pm.total_requests = 10
        pm.successful_requests = 7
        assert pm.success_rate == 0.7

    def test_avg_latency_ms_property(self) -> None:
        """Test avg_latency_ms property."""
        pm = ProviderMetrics("test", "test")

        # No successes
        assert pm.avg_latency_ms == 0.0

        # 3 successes with total 300ms
        pm.successful_requests = 3
        pm.total_latency_ms = 300.0
        assert pm.avg_latency_ms == 100.0

    def test_avg_cost_per_request_property(self) -> None:
        """Test avg_cost_per_request property."""
        pm = ProviderMetrics("test", "test")

        # No successes
        assert pm.avg_cost_per_request == 0.0

        # 5 successes with total cost $0.25
        pm.successful_requests = 5
        pm.total_cost = 0.25
        assert pm.avg_cost_per_request == 0.05


class TestMetricsAggregatorSummary:
    """Test get_summary aggregation."""

    def test_summary_aggregates_across_providers(self) -> None:
        """Test that summary aggregates metrics across all providers."""
        metrics = MetricsAggregator()

        # Provider 1
        with metrics.track_request("anthropic", "claude-sonnet-4-5") as t:
            t.record_tokens(1000, 500)
            t.record_cost(0.015)

        # Provider 2
        with metrics.track_request("openai", "gpt-4") as t:
            t.record_tokens(2000, 1000)
            t.record_cost(0.06)

        summary = metrics.get_summary()
        assert summary.total_requests == 2
        assert summary.total_successful == 2
        assert summary.total_tokens == 4500
        assert summary.total_cost == 0.075
        assert summary.success_rate == 1.0

    def test_summary_calculates_percentiles(self) -> None:
        """Test that summary calculates latency percentiles."""
        metrics = MetricsAggregator()

        # Record 10 requests with known latencies: 0, 10, 20, ..., 90
        for i in range(10):
            metrics.increment_requests("test", "model")
            metrics.record_success("test", "model", latency_ms=float(i * 10))

        summary = metrics.get_summary()
        assert summary.p50_latency_ms == 50.0  # 50th percentile (median of 0-90)
        assert summary.p95_latency_ms == 90.0  # 95th percentile
        assert summary.p99_latency_ms == 90.0  # 99th percentile

    def test_summary_cost_by_provider(self) -> None:
        """Test cost breakdown by provider."""
        metrics = MetricsAggregator()

        with metrics.track_request("anthropic", "claude-sonnet-4-5") as t:
            t.record_cost(0.015)

        with metrics.track_request("openai", "gpt-4") as t:
            t.record_cost(0.06)

        summary = metrics.get_summary()
        assert summary.cost_by_provider["anthropic"] == 0.015
        assert summary.cost_by_provider["openai"] == 0.06

    def test_summary_requests_by_provider(self) -> None:
        """Test request count by provider."""
        metrics = MetricsAggregator()

        for _ in range(3):
            metrics.increment_requests("anthropic", "claude-sonnet-4-5")

        for _ in range(2):
            metrics.increment_requests("openai", "gpt-4")

        summary = metrics.get_summary()
        assert summary.requests_by_provider["anthropic"] == 3
        assert summary.requests_by_provider["openai"] == 2


class TestMetricsAggregatorMultipleProviders:
    """Test metrics tracking for multiple providers."""

    def test_separate_tracking_per_provider_model(self) -> None:
        """Test that metrics are tracked separately per provider/model."""
        metrics = MetricsAggregator()

        # Same provider, different models
        with metrics.track_request("anthropic", "claude-sonnet-4-5") as t:
            t.record_cost(0.015)

        with metrics.track_request("anthropic", "claude-3-opus") as t:
            t.record_cost(0.025)

        pm1 = metrics.get_provider_metrics("anthropic", "claude-sonnet-4-5")
        pm2 = metrics.get_provider_metrics("anthropic", "claude-3-opus")

        assert pm1 is not None
        assert pm2 is not None
        assert pm1.total_cost == 0.015
        assert pm2.total_cost == 0.025

    def test_error_tracking_per_provider(self) -> None:
        """Test that errors are tracked separately per provider."""
        metrics = MetricsAggregator()

        # Provider 1: TimeoutError
        metrics.increment_requests("anthropic", "claude-sonnet-4-5")
        metrics.record_failure("anthropic", "claude-sonnet-4-5", "TimeoutError")

        # Provider 2: RateLimitError
        metrics.increment_requests("openai", "gpt-4")
        metrics.record_failure("openai", "gpt-4", "RateLimitError")

        pm1 = metrics.get_provider_metrics("anthropic", "claude-sonnet-4-5")
        pm2 = metrics.get_provider_metrics("openai", "gpt-4")

        assert pm1 is not None
        assert pm2 is not None
        assert pm1.errors["TimeoutError"] == 1
        assert "RateLimitError" not in pm1.errors
        assert pm2.errors["RateLimitError"] == 1
        assert "TimeoutError" not in pm2.errors


class TestMetricsAggregatorReset:
    """Test metrics reset functionality."""

    def test_reset_clears_all_metrics(self) -> None:
        """Test that reset clears all collected metrics."""
        metrics = MetricsAggregator()

        # Collect some metrics
        with metrics.track_request("anthropic", "claude-sonnet-4-5") as t:
            t.record_tokens(1000, 500)
            t.record_cost(0.015)

        # Reset
        metrics.reset()

        # Verify cleared
        summary = metrics.get_summary()
        assert summary.total_requests == 0
        assert summary.total_cost == 0.0
        pm = metrics.get_provider_metrics("anthropic", "claude-sonnet-4-5")
        assert pm is None


class TestMetricsAggregatorExport:
    """Test metrics export to dictionary."""

    def test_to_dict_structure(self) -> None:
        """Test to_dict returns correct structure."""
        metrics = MetricsAggregator()

        with metrics.track_request("anthropic", "claude-sonnet-4-5") as t:
            t.record_tokens(1000, 500)
            t.record_cost(0.015)

        data = metrics.to_dict()

        assert "summary" in data
        assert "by_provider" in data
        assert "total_requests" in data["summary"]
        assert "total_cost" in data["summary"]

    def test_to_dict_includes_provider_details(self) -> None:
        """Test that to_dict includes per-provider details."""
        metrics = MetricsAggregator()

        with metrics.track_request("anthropic", "claude-sonnet-4-5") as t:
            t.record_tokens(1000, 500)
            t.record_cost(0.015)

        data = metrics.to_dict()
        provider_key = "anthropic/claude-sonnet-4-5"

        assert provider_key in data["by_provider"]
        provider_data = data["by_provider"][provider_key]
        assert provider_data["total_cost"] == 0.015
        assert provider_data["total_tokens"] == 1500

    def test_to_dict_percentiles(self) -> None:
        """Test that to_dict includes percentile data."""
        metrics = MetricsAggregator()

        for i in range(10):
            metrics.increment_requests("test", "model")
            metrics.record_success("test", "model", latency_ms=float(i * 10))

        data = metrics.to_dict()
        summary = data["summary"]

        assert "p50_latency_ms" in summary
        assert "p95_latency_ms" in summary
        assert "p99_latency_ms" in summary


class TestMetricsAggregatorEdgeCases:
    """Test edge cases and error conditions."""

    def test_get_nonexistent_provider_metrics(self) -> None:
        """Test getting metrics for non-existent provider."""
        metrics = MetricsAggregator()

        pm = metrics.get_provider_metrics("nonexistent", "model")
        assert pm is None

    def test_record_tokens_without_context(self) -> None:
        """Test record_tokens without setting context raises RuntimeError."""
        metrics = MetricsAggregator()

        # Should raise RuntimeError when called without context
        with pytest.raises(
            RuntimeError,
            match="record_tokens called without provider/model context",
        ):
            metrics.record_tokens(1000, 500)

    def test_record_cost_without_context(self) -> None:
        """Test record_cost without setting context raises RuntimeError."""
        metrics = MetricsAggregator()

        # Should raise RuntimeError when called without context
        with pytest.raises(
            RuntimeError,
            match="record_cost called without provider/model context",
        ):
            metrics.record_cost(0.015)

    def test_summary_with_no_data(self) -> None:
        """Test getting summary with no data."""
        metrics = MetricsAggregator()
        summary = metrics.get_summary()

        assert summary.total_requests == 0
        assert summary.total_successful == 0
        assert summary.total_failed == 0
        assert summary.total_tokens == 0
        assert summary.total_cost == 0.0
        assert summary.avg_latency_ms == 0.0
        assert summary.success_rate == 0.0


class TestMetricsAggregatorThreadSafety:
    """Test thread safety of metrics aggregator."""

    def test_concurrent_tracking(self) -> None:
        """Test that concurrent tracking is thread-safe."""
        import threading

        metrics = MetricsAggregator()
        results = []

        def track_request() -> None:
            try:
                with metrics.track_request("test", "model") as t:
                    t.record_tokens(100, 50)
                    t.record_cost(0.001)
                results.append(True)
            except Exception:
                results.append(False)

        # Launch 20 concurrent tracking operations
        threads = [threading.Thread(target=track_request) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert len(results) == 20
        assert all(results)

        # Verify totals
        summary = metrics.get_summary()
        assert summary.total_requests == 20
        assert summary.total_tokens == 3000  # 20 * 150
        assert abs(summary.total_cost - 0.02) < 0.001  # 20 * 0.001

    def test_concurrent_different_providers(self) -> None:
        """Test concurrent tracking with different provider names to catch attribution races."""
        import threading

        metrics = MetricsAggregator()
        num_providers = 10

        def track_provider_request(provider_id: int) -> None:
            provider_name = f"provider_{provider_id}"
            with metrics.track_request(provider_name, "model") as t:
                t.record_tokens(100, 0)  # 100 input tokens

        # Spawn 10 threads, each with unique provider name
        threads = [
            threading.Thread(target=track_provider_request, args=(i,)) for i in range(num_providers)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify each provider has correct attribution (no cross-contamination)
        for i in range(num_providers):
            provider_name = f"provider_{i}"
            provider_metrics = metrics.get_provider_metrics(provider_name, "model")
            assert provider_metrics is not None, f"Provider {provider_name} metrics missing"
            assert provider_metrics.total_input_tokens == 100, (
                f"Provider {provider_name} has {provider_metrics.total_input_tokens} tokens, "
                f"expected 100"
            )
