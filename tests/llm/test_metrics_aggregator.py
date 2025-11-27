"""Tests for MetricsAggregator and related dataclasses.

This module tests the metrics aggregation functionality including:
- RequestMetrics, ProviderStats, AggregatedMetrics dataclasses
- MetricsAggregator class with start/end request tracking
- Percentile calculations (p50, p95, p99)
- JSON/CSV export formats
- Thread safety
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from review_bot_automator.llm.metrics import (
    AggregatedMetrics,
    ProviderStats,
    RequestMetrics,
)
from review_bot_automator.llm.metrics_aggregator import MetricsAggregator


class TestRequestMetrics:
    """Tests for RequestMetrics dataclass."""

    def test_creation_valid(self) -> None:
        """Test creating RequestMetrics with valid values."""
        metrics = RequestMetrics(
            request_id="req-abc123",
            provider="anthropic",
            model="claude-haiku-4",
            latency_seconds=0.234,
            success=True,
            tokens_input=500,
            tokens_output=120,
            cost=0.00093,
            cache_hit=False,
        )
        assert metrics.request_id == "req-abc123"
        assert metrics.provider == "anthropic"
        assert metrics.latency_seconds == 0.234
        assert metrics.success is True
        assert metrics.total_tokens == 620

    def test_total_tokens_property(self) -> None:
        """Test total_tokens computed property."""
        metrics = RequestMetrics(
            request_id="req-1",
            provider="openai",
            model="gpt-4o-mini",
            latency_seconds=0.1,
            success=True,
            tokens_input=100,
            tokens_output=50,
            cost=0.001,
            cache_hit=False,
        )
        assert metrics.total_tokens == 150

    def test_failed_request_with_error_type(self) -> None:
        """Test creating failed RequestMetrics with error type."""
        metrics = RequestMetrics(
            request_id="req-fail",
            provider="anthropic",
            model="claude-haiku-4",
            latency_seconds=5.0,
            success=False,
            tokens_input=0,
            tokens_output=0,
            cost=0.0,
            cache_hit=False,
            error_type="APITimeoutError",
        )
        assert metrics.success is False
        assert metrics.error_type == "APITimeoutError"

    def test_validation_negative_latency(self) -> None:
        """Test validation rejects negative latency."""
        with pytest.raises(ValueError, match="latency_seconds must be >= 0"):
            RequestMetrics(
                request_id="req-1",
                provider="openai",
                model="gpt-4o-mini",
                latency_seconds=-0.1,
                success=True,
                tokens_input=100,
                tokens_output=50,
                cost=0.001,
                cache_hit=False,
            )

    def test_validation_negative_tokens(self) -> None:
        """Test validation rejects negative token counts."""
        with pytest.raises(ValueError, match="tokens_input must be >= 0"):
            RequestMetrics(
                request_id="req-1",
                provider="openai",
                model="gpt-4o-mini",
                latency_seconds=0.1,
                success=True,
                tokens_input=-100,
                tokens_output=50,
                cost=0.001,
                cache_hit=False,
            )

    def test_validation_negative_tokens_output(self) -> None:
        """Test validation rejects negative output token counts."""
        with pytest.raises(ValueError, match="tokens_output must be >= 0"):
            RequestMetrics(
                request_id="req-1",
                provider="openai",
                model="gpt-4o-mini",
                latency_seconds=0.1,
                success=True,
                tokens_input=100,
                tokens_output=-50,
                cost=0.001,
                cache_hit=False,
            )

    def test_validation_negative_cost(self) -> None:
        """Test validation rejects negative cost."""
        with pytest.raises(ValueError, match="cost must be >= 0"):
            RequestMetrics(
                request_id="req-1",
                provider="openai",
                model="gpt-4o-mini",
                latency_seconds=0.1,
                success=True,
                tokens_input=100,
                tokens_output=50,
                cost=-0.001,
                cache_hit=False,
            )


class TestProviderStats:
    """Tests for ProviderStats dataclass."""

    def test_creation_valid(self) -> None:
        """Test creating ProviderStats with valid values."""
        stats = ProviderStats(
            provider="anthropic",
            model="claude-haiku-4",
            total_requests=25,
            successful_requests=24,
            failed_requests=1,
            success_rate=0.96,
            total_cost=0.0234,
            total_tokens=15420,
            avg_latency=0.287,
            latency_p50=0.234,
            latency_p95=0.512,
            latency_p99=0.789,
            cache_hit_rate=0.65,
            error_counts={"APITimeoutError": 1},
        )
        assert stats.provider == "anthropic"
        assert stats.total_requests == 25
        assert stats.success_rate == 0.96

    def test_validation_success_rate_bounds(self) -> None:
        """Test validation rejects success_rate outside 0.0-1.0."""
        with pytest.raises(ValueError, match="success_rate must be between 0.0 and 1.0"):
            ProviderStats(
                provider="anthropic",
                model="claude-haiku-4",
                total_requests=25,
                successful_requests=24,
                failed_requests=1,
                success_rate=1.5,  # Invalid
                total_cost=0.0234,
                total_tokens=15420,
                avg_latency=0.287,
                latency_p50=0.234,
                latency_p95=0.512,
                latency_p99=0.789,
                cache_hit_rate=0.65,
            )

    def test_validation_cache_hit_rate_bounds(self) -> None:
        """Test validation rejects cache_hit_rate outside 0.0-1.0."""
        with pytest.raises(ValueError, match="cache_hit_rate must be between 0.0 and 1.0"):
            ProviderStats(
                provider="anthropic",
                model="claude-haiku-4",
                total_requests=25,
                successful_requests=24,
                failed_requests=1,
                success_rate=0.96,
                total_cost=0.0234,
                total_tokens=15420,
                avg_latency=0.287,
                latency_p50=0.234,
                latency_p95=0.512,
                latency_p99=0.789,
                cache_hit_rate=-0.1,  # Invalid
            )


class TestAggregatedMetrics:
    """Tests for AggregatedMetrics dataclass."""

    def test_creation_empty(self) -> None:
        """Test creating empty AggregatedMetrics."""
        metrics = AggregatedMetrics()
        assert metrics.total_requests == 0
        assert metrics.success_rate == 0.0
        assert metrics.provider_stats == {}

    def test_creation_with_provider_stats(self) -> None:
        """Test creating AggregatedMetrics with provider stats."""
        stats = ProviderStats(
            provider="anthropic",
            model="claude-haiku-4",
            total_requests=25,
            successful_requests=24,
            failed_requests=1,
            success_rate=0.96,
            total_cost=0.0234,
            total_tokens=15420,
            avg_latency=0.287,
            latency_p50=0.234,
            latency_p95=0.512,
            latency_p99=0.789,
            cache_hit_rate=0.65,
        )
        metrics = AggregatedMetrics(
            provider_stats={"anthropic": stats},
            latency_p50=0.234,
            latency_p95=0.512,
            latency_p99=0.789,
            latency_avg=0.287,
            total_requests=25,
            successful_requests=24,
            failed_requests=1,
            success_rate=0.96,
            total_cost=0.0234,
            cost_per_comment=0.00094,
            cache_hit_rate=0.65,
            cache_savings=0.0412,
        )
        assert metrics.total_requests == 25
        assert "anthropic" in metrics.provider_stats


class TestMetricsAggregator:
    """Tests for MetricsAggregator class."""

    def test_start_end_request(self) -> None:
        """Test basic request tracking."""
        aggregator = MetricsAggregator()
        request_id = aggregator.start_request("anthropic", "claude-haiku-4")

        assert request_id.startswith("req-")

        # Minimal sleep - latency will be > 0 due to function call overhead
        time.sleep(0.001)

        aggregator.end_request(
            request_id,
            success=True,
            tokens_input=100,
            tokens_output=50,
            cost=0.001,
        )

        metrics = aggregator.get_aggregated_metrics()
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.latency_avg > 0
        # Latency should be reasonable (under 1 second for this simple test)
        assert metrics.latency_avg < 1.0

    def test_multiple_requests(self) -> None:
        """Test tracking multiple requests."""
        aggregator = MetricsAggregator()

        for _ in range(5):
            request_id = aggregator.start_request("openai", "gpt-4o-mini")
            time.sleep(0.001)
            aggregator.end_request(
                request_id,
                success=True,
                tokens_input=100,
                tokens_output=50,
                cost=0.001,
            )

        metrics = aggregator.get_aggregated_metrics()
        assert metrics.total_requests == 5
        assert metrics.successful_requests == 5
        assert metrics.success_rate == 1.0

    def test_multiple_providers(self) -> None:
        """Test aggregation across multiple providers."""
        aggregator = MetricsAggregator()

        # Add Anthropic requests
        for _ in range(3):
            req_id = aggregator.start_request("anthropic", "claude-haiku-4")
            aggregator.end_request(req_id, success=True, tokens_input=100)

        # Add OpenAI requests
        for _ in range(2):
            req_id = aggregator.start_request("openai", "gpt-4o-mini")
            aggregator.end_request(req_id, success=True, tokens_input=50)

        metrics = aggregator.get_aggregated_metrics()
        assert metrics.total_requests == 5
        assert "anthropic" in metrics.provider_stats
        assert "openai" in metrics.provider_stats
        assert metrics.provider_stats["anthropic"].total_requests == 3
        assert metrics.provider_stats["openai"].total_requests == 2

    def test_failed_requests(self) -> None:
        """Test tracking of failed requests with error types."""
        aggregator = MetricsAggregator()

        # Successful request
        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(req_id, success=True, tokens_input=100)

        # Failed request
        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(req_id, success=False, error_type="APITimeoutError")

        metrics = aggregator.get_aggregated_metrics()
        assert metrics.total_requests == 2
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 1
        assert metrics.success_rate == 0.5

        # Check error counts in provider stats
        assert metrics.provider_stats["anthropic"].error_counts == {"APITimeoutError": 1}

    def test_cache_hit_tracking(self) -> None:
        """Test cache hit rate calculation."""
        aggregator = MetricsAggregator()

        # 2 cache hits
        for _ in range(2):
            req_id = aggregator.start_request("anthropic", "claude-haiku-4", cache_hit=True)
            aggregator.end_request(req_id, success=True)

        # 2 cache misses
        for _ in range(2):
            req_id = aggregator.start_request("anthropic", "claude-haiku-4", cache_hit=False)
            aggregator.end_request(req_id, success=True)

        metrics = aggregator.get_aggregated_metrics()
        assert metrics.cache_hit_rate == 0.5

    def test_pr_info(self) -> None:
        """Test setting and getting PR info."""
        aggregator = MetricsAggregator()
        aggregator.set_pr_info("myorg", "myrepo", 123)

        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(req_id, success=True)

        # Use public accessor to get PR info
        pr_info = aggregator.get_pr_info()
        assert pr_info == {
            "owner": "myorg",
            "repo": "myrepo",
            "pr_number": 123,
        }

    def test_pr_info_not_set(self) -> None:
        """Test get_pr_info returns None when not set."""
        aggregator = MetricsAggregator()
        assert aggregator.get_pr_info() is None

    def test_unknown_request_id(self) -> None:
        """Test error on unknown request ID."""
        aggregator = MetricsAggregator()

        with pytest.raises(ValueError, match="Unknown request_id"):
            aggregator.end_request("unknown-id", success=True)

    def test_reset(self) -> None:
        """Test resetting aggregator."""
        aggregator = MetricsAggregator()

        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(req_id, success=True)

        aggregator.reset()

        metrics = aggregator.get_aggregated_metrics()
        assert metrics.total_requests == 0

    def test_record_request_directly(self) -> None:
        """Test recording a RequestMetrics object directly."""
        aggregator = MetricsAggregator()

        metrics = RequestMetrics(
            request_id="external-req",
            provider="ollama",
            model="llama3.3:70b",
            latency_seconds=1.5,
            success=True,
            tokens_input=500,
            tokens_output=200,
            cost=0.0,
            cache_hit=False,
        )
        aggregator.record_request(metrics)

        aggregated = aggregator.get_aggregated_metrics()
        assert aggregated.total_requests == 1
        assert "ollama" in aggregated.provider_stats


class TestPercentileCalculations:
    """Tests for percentile calculations."""

    def test_p50_calculation(self) -> None:
        """Test p50 (median) calculation."""
        aggregator = MetricsAggregator()

        # Add requests with known latencies via record_request
        latencies = [0.1, 0.2, 0.3, 0.4, 0.5]
        for i, latency in enumerate(latencies):
            metrics = RequestMetrics(
                request_id=f"req-{i}",
                provider="anthropic",
                model="claude-haiku-4",
                latency_seconds=latency,
                success=True,
                tokens_input=100,
                tokens_output=50,
                cost=0.001,
                cache_hit=False,
            )
            aggregator.record_request(metrics)

        aggregated = aggregator.get_aggregated_metrics()
        assert aggregated.latency_p50 == pytest.approx(0.3, rel=0.1)

    def test_p95_p99_calculation(self) -> None:
        """Test p95 and p99 calculations."""
        aggregator = MetricsAggregator()

        # Add 100 requests with latencies 0.01 to 1.0
        for i in range(100):
            latency = (i + 1) / 100.0
            metrics = RequestMetrics(
                request_id=f"req-{i}",
                provider="openai",
                model="gpt-4o-mini",
                latency_seconds=latency,
                success=True,
                tokens_input=100,
                tokens_output=50,
                cost=0.001,
                cache_hit=False,
            )
            aggregator.record_request(metrics)

        aggregated = aggregator.get_aggregated_metrics()
        assert aggregated.latency_p95 == pytest.approx(0.95, rel=0.05)
        assert aggregated.latency_p99 == pytest.approx(0.99, rel=0.05)

    def test_single_request_percentiles(self) -> None:
        """Test percentiles with single request (edge case)."""
        aggregator = MetricsAggregator()

        metrics = RequestMetrics(
            request_id="single",
            provider="anthropic",
            model="claude-haiku-4",
            latency_seconds=0.5,
            success=True,
            tokens_input=100,
            tokens_output=50,
            cost=0.001,
            cache_hit=False,
        )
        aggregator.record_request(metrics)

        aggregated = aggregator.get_aggregated_metrics()
        # All percentiles should equal the single value
        assert aggregated.latency_p50 == 0.5
        assert aggregated.latency_p95 == 0.5
        assert aggregated.latency_p99 == 0.5

    def test_empty_metrics_percentiles(self) -> None:
        """Test percentiles return 0 for empty aggregator."""
        aggregator = MetricsAggregator()
        aggregated = aggregator.get_aggregated_metrics()

        assert aggregated.latency_p50 == 0.0
        assert aggregated.latency_p95 == 0.0
        assert aggregated.latency_p99 == 0.0


class TestExportFormats:
    """Tests for export functionality."""

    def test_export_json(self, tmp_path: Path) -> None:
        """Test JSON export format."""
        aggregator = MetricsAggregator()
        aggregator.set_pr_info("myorg", "myrepo", 123)

        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        time.sleep(0.01)
        aggregator.end_request(req_id, success=True, tokens_input=100, cost=0.001)

        output_path = tmp_path / "metrics.json"
        aggregator.export_json(output_path)

        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "summary" in data
        assert "provider_stats" in data
        assert "pr_info" in data
        assert data["summary"]["total_requests"] == 1
        assert data["pr_info"]["owner"] == "myorg"
        # Requests not included by default
        assert "requests" not in data

    def test_export_json_with_requests(self, tmp_path: Path) -> None:
        """Test JSON export with per-request data."""
        aggregator = MetricsAggregator()

        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(req_id, success=True, tokens_input=100)

        output_path = tmp_path / "metrics_detailed.json"
        aggregator.export_json(output_path, include_requests=True)

        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "requests" in data
        assert len(data["requests"]) == 1
        assert data["requests"][0]["provider"] == "anthropic"

    def test_export_csv(self, tmp_path: Path) -> None:
        """Test CSV export format."""
        aggregator = MetricsAggregator()

        # Add 3 requests: 2 successful (i=0,1) followed by 1 failure (i=2)
        for i in range(3):
            req_id = aggregator.start_request("anthropic", "claude-haiku-4")
            aggregator.end_request(req_id, success=(i < 2), tokens_input=100)

        output_path = tmp_path / "metrics.csv"
        aggregator.export_csv(output_path)

        with open(output_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Header + 3 data rows
        assert len(lines) == 4
        assert "request_id,provider,model" in lines[0]

    def test_export_empty_metrics(self, tmp_path: Path) -> None:
        """Test export with no requests recorded."""
        aggregator = MetricsAggregator()

        json_path = tmp_path / "empty.json"
        aggregator.export_json(json_path)

        with open(json_path) as f:
            data = json.load(f)

        assert data["summary"]["total_requests"] == 0

    def test_get_summary_report(self) -> None:
        """Test human-readable summary report."""
        aggregator = MetricsAggregator()

        for _ in range(5):
            req_id = aggregator.start_request("anthropic", "claude-haiku-4")
            aggregator.end_request(req_id, success=True, cost=0.001)

        report = aggregator.get_summary_report()

        assert "LLM Metrics Summary" in report
        assert "Total requests: 5" in report
        assert "Success rate: 100.0%" in report


class TestThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_requests(self) -> None:
        """Test concurrent request tracking from multiple threads."""
        aggregator = MetricsAggregator()
        num_threads = 10
        requests_per_thread = 5

        def worker() -> None:
            for _ in range(requests_per_thread):
                req_id = aggregator.start_request("anthropic", "claude-haiku-4")
                time.sleep(0.001)  # Small delay
                aggregator.end_request(req_id, success=True, tokens_input=100)

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = aggregator.get_aggregated_metrics()
        expected_total = num_threads * requests_per_thread
        assert metrics.total_requests == expected_total


class TestGetProviderStats:
    """Tests for get_provider_stats method."""

    def test_get_provider_stats_returns_none_for_unknown(self) -> None:
        """Returns None when querying an unknown provider."""
        aggregator = MetricsAggregator()

        # Add request for one provider
        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(req_id, success=True, tokens_input=100)

        # Query for a different provider
        stats = aggregator.get_provider_stats("openai")
        assert stats is None

    def test_get_provider_stats_returns_none_for_empty_aggregator(self) -> None:
        """Returns None when aggregator has no requests."""
        aggregator = MetricsAggregator()
        stats = aggregator.get_provider_stats("anthropic")
        assert stats is None

    def test_get_provider_stats_returns_stats_for_known(self) -> None:
        """Returns ProviderStats for a provider with requests."""
        aggregator = MetricsAggregator()

        # Add multiple requests for the provider
        for i in range(3):
            req_id = aggregator.start_request("anthropic", "claude-haiku-4")
            aggregator.end_request(
                req_id,
                success=(i < 2),  # 2 success, 1 failure
                tokens_input=100,
                cost=0.001,
                error_type="timeout" if i == 2 else None,
            )

        stats = aggregator.get_provider_stats("anthropic")
        assert stats is not None
        assert stats.provider == "anthropic"
        assert stats.model == "claude-haiku-4"
        assert stats.total_requests == 3
        assert stats.successful_requests == 2
        assert stats.failed_requests == 1
        assert stats.error_counts == {"timeout": 1}


class TestExportErrorHandling:
    """Tests for export error handling."""

    def test_export_json_error_handling(self, tmp_path: Path) -> None:
        """Export JSON raises OSError for invalid path."""
        aggregator = MetricsAggregator()
        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(req_id, success=True)

        # Try to write to a non-existent directory
        invalid_path = tmp_path / "nonexistent" / "subdir" / "metrics.json"

        with pytest.raises(OSError):
            aggregator.export_json(invalid_path)

    def test_export_csv_error_handling(self, tmp_path: Path) -> None:
        """Export CSV raises OSError for invalid path."""
        aggregator = MetricsAggregator()
        req_id = aggregator.start_request("openai", "gpt-4o-mini")
        aggregator.end_request(req_id, success=True, tokens_input=50)

        # Try to write to a non-existent directory
        invalid_path = tmp_path / "nonexistent" / "subdir" / "metrics.csv"

        with pytest.raises(OSError):
            aggregator.export_csv(invalid_path)

    def test_export_json_with_no_pr_info(self, tmp_path: Path) -> None:
        """Export JSON without PR info omits pr_info field."""
        aggregator = MetricsAggregator()
        # Don't set PR info
        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(req_id, success=True)

        output_path = tmp_path / "no_pr_info.json"
        aggregator.export_json(output_path)

        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert "pr_info" not in data
        assert "summary" in data


class TestMixedModels:
    """Tests for mixed model scenarios."""

    def test_provider_stats_with_mixed_models(self) -> None:
        """Provider stats reports 'mixed' when multiple models used."""
        aggregator = MetricsAggregator()

        # Add requests with different models for same provider
        req_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(req_id, success=True, tokens_input=100)

        req_id = aggregator.start_request("anthropic", "claude-sonnet-4")
        aggregator.end_request(req_id, success=True, tokens_input=200)

        stats = aggregator.get_provider_stats("anthropic")
        assert stats is not None
        assert stats.model == "mixed"
        assert stats.total_requests == 2
