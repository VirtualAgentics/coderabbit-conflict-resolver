"""Tests for LLM metrics tracking.

This module tests the LLM metrics infrastructure for tracking token usage,
costs, cache performance, and parsing statistics.
"""

import pytest

from review_bot_automator.llm.metrics import (
    AggregatedMetrics,
    LLMMetrics,
    ProviderStats,
)


class TestLLMMetrics:
    """Tests for LLMMetrics dataclass."""

    def test_metrics_creation(self) -> None:
        """Test creating LLMMetrics with valid values."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4-20250514",
            changes_parsed=20,
            avg_confidence=0.92,
            cache_hit_rate=0.65,
            total_cost=0.0234,
            api_calls=7,
            total_tokens=15420,
        )

        assert metrics.provider == "anthropic"
        assert metrics.model == "claude-haiku-4-20250514"
        assert metrics.changes_parsed == 20
        assert metrics.avg_confidence == 0.92
        assert metrics.cache_hit_rate == 0.65
        assert metrics.total_cost == 0.0234
        assert metrics.api_calls == 7
        assert metrics.total_tokens == 15420

    def test_metrics_immutability(self) -> None:
        """Test that LLMMetrics is immutable."""
        metrics = LLMMetrics(
            provider="openai",
            model="gpt-4o-mini",
            changes_parsed=10,
            avg_confidence=0.85,
            cache_hit_rate=0.5,
            total_cost=0.05,
            api_calls=5,
            total_tokens=5000,
        )

        with pytest.raises((AttributeError, TypeError)):
            metrics.provider = "anthropic"  # type: ignore[misc]

    def test_metrics_validation_negative_changes(self) -> None:
        """Test that negative changes_parsed raises ValueError."""
        with pytest.raises(ValueError, match="changes_parsed must be >= 0"):
            LLMMetrics(
                provider="anthropic",
                model="claude-haiku-4",
                changes_parsed=-1,
                avg_confidence=0.9,
                cache_hit_rate=0.5,
                total_cost=0.01,
                api_calls=5,
                total_tokens=1000,
            )

    def test_metrics_validation_confidence_too_low(self) -> None:
        """Test that avg_confidence < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="avg_confidence must be between"):
            LLMMetrics(
                provider="anthropic",
                model="claude-haiku-4",
                changes_parsed=10,
                avg_confidence=-0.1,
                cache_hit_rate=0.5,
                total_cost=0.01,
                api_calls=5,
                total_tokens=1000,
            )

    def test_metrics_validation_confidence_too_high(self) -> None:
        """Test that avg_confidence > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="avg_confidence must be between"):
            LLMMetrics(
                provider="anthropic",
                model="claude-haiku-4",
                changes_parsed=10,
                avg_confidence=1.1,
                cache_hit_rate=0.5,
                total_cost=0.01,
                api_calls=5,
                total_tokens=1000,
            )

    def test_metrics_validation_cache_hit_rate_too_low(self) -> None:
        """Test that cache_hit_rate < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="cache_hit_rate must be between"):
            LLMMetrics(
                provider="anthropic",
                model="claude-haiku-4",
                changes_parsed=10,
                avg_confidence=0.9,
                cache_hit_rate=-0.1,
                total_cost=0.01,
                api_calls=5,
                total_tokens=1000,
            )

    def test_metrics_validation_cache_hit_rate_too_high(self) -> None:
        """Test that cache_hit_rate > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="cache_hit_rate must be between"):
            LLMMetrics(
                provider="anthropic",
                model="claude-haiku-4",
                changes_parsed=10,
                avg_confidence=0.9,
                cache_hit_rate=1.1,
                total_cost=0.01,
                api_calls=5,
                total_tokens=1000,
            )

    def test_metrics_validation_negative_cost(self) -> None:
        """Test that negative total_cost raises ValueError."""
        with pytest.raises(ValueError, match="total_cost must be >= 0"):
            LLMMetrics(
                provider="anthropic",
                model="claude-haiku-4",
                changes_parsed=10,
                avg_confidence=0.9,
                cache_hit_rate=0.5,
                total_cost=-0.01,
                api_calls=5,
                total_tokens=1000,
            )

    def test_metrics_validation_negative_api_calls(self) -> None:
        """Test that negative api_calls raises ValueError."""
        with pytest.raises(ValueError, match="api_calls must be >= 0"):
            LLMMetrics(
                provider="anthropic",
                model="claude-haiku-4",
                changes_parsed=10,
                avg_confidence=0.9,
                cache_hit_rate=0.5,
                total_cost=0.01,
                api_calls=-1,
                total_tokens=1000,
            )

    def test_metrics_validation_negative_tokens(self) -> None:
        """Test that negative total_tokens raises ValueError."""
        with pytest.raises(ValueError, match="total_tokens must be >= 0"):
            LLMMetrics(
                provider="anthropic",
                model="claude-haiku-4",
                changes_parsed=10,
                avg_confidence=0.9,
                cache_hit_rate=0.5,
                total_cost=0.01,
                api_calls=5,
                total_tokens=-1000,
            )


class TestLLMMetricsProperties:
    """Tests for LLMMetrics computed properties."""

    def test_cost_per_change_with_changes(self) -> None:
        """Test cost_per_change calculation with parsed changes."""
        metrics = LLMMetrics(
            provider="openai",
            model="gpt-4o-mini",
            changes_parsed=10,
            avg_confidence=0.85,
            cache_hit_rate=0.5,
            total_cost=0.05,
            api_calls=5,
            total_tokens=5000,
        )

        assert metrics.cost_per_change == 0.005

    def test_cost_per_change_with_zero_changes(self) -> None:
        """Test cost_per_change returns 0.0 when no changes parsed."""
        metrics = LLMMetrics(
            provider="openai",
            model="gpt-4o-mini",
            changes_parsed=0,
            avg_confidence=0.0,
            cache_hit_rate=0.0,
            total_cost=0.0,
            api_calls=0,
            total_tokens=0,
        )

        assert metrics.cost_per_change == 0.0

    def test_avg_tokens_per_call_with_calls(self) -> None:
        """Test avg_tokens_per_call calculation with API calls."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            changes_parsed=20,
            avg_confidence=0.92,
            cache_hit_rate=0.65,
            total_cost=0.02,
            api_calls=7,
            total_tokens=15420,
        )

        expected = 15420 / 7
        assert metrics.avg_tokens_per_call == pytest.approx(expected)

    def test_avg_tokens_per_call_with_zero_calls(self) -> None:
        """Test avg_tokens_per_call returns 0.0 when no API calls made."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            changes_parsed=0,
            avg_confidence=0.0,
            cache_hit_rate=0.0,
            total_cost=0.0,
            api_calls=0,
            total_tokens=0,
        )

        assert metrics.avg_tokens_per_call == 0.0

    def test_calculate_savings_positive(self) -> None:
        """Test calculate_savings with cache hits reducing cost."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            changes_parsed=20,
            avg_confidence=0.92,
            cache_hit_rate=0.65,
            total_cost=0.0234,
            api_calls=7,
            total_tokens=15420,
        )

        # If cache hit rate was 0%, cost would have been higher
        cache_miss_cost = 0.0646
        savings = metrics.calculate_savings(cache_miss_cost)

        assert savings == pytest.approx(0.0412)

    def test_calculate_savings_zero_cache_hits(self) -> None:
        """Test calculate_savings with no cache hits (0% hit rate)."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            changes_parsed=20,
            avg_confidence=0.92,
            cache_hit_rate=0.0,  # No cache hits
            total_cost=0.0646,
            api_calls=7,
            total_tokens=15420,
        )

        # With 0% cache hit rate, actual cost equals cache_miss_cost
        savings = metrics.calculate_savings(0.0646)

        assert savings == pytest.approx(0.0)

    def test_calculate_savings_negative_cache_miss_cost(self) -> None:
        """Test calculate_savings raises ValueError for negative cache_miss_cost."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            changes_parsed=20,
            avg_confidence=0.92,
            cache_hit_rate=0.65,
            total_cost=0.0234,
            api_calls=7,
            total_tokens=15420,
        )

        with pytest.raises(ValueError, match="cache_miss_cost must be >= 0"):
            metrics.calculate_savings(-0.01)

    def test_calculate_savings_cache_miss_less_than_total(self) -> None:
        """Test calculate_savings raises ValueError when cache_miss_cost < total_cost."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            changes_parsed=20,
            avg_confidence=0.92,
            cache_hit_rate=0.65,
            total_cost=0.0234,
            api_calls=7,
            total_tokens=15420,
        )

        # cache_miss_cost should be >= total_cost
        with pytest.raises(ValueError, match="cache_miss_cost.*must be >= total_cost"):
            metrics.calculate_savings(0.01)


class TestLLMMetricsEdgeCases:
    """Tests for LLMMetrics edge cases and boundary conditions."""

    def test_metrics_with_perfect_confidence(self) -> None:
        """Test metrics with perfect 1.0 confidence score."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-opus-4",
            changes_parsed=5,
            avg_confidence=1.0,
            cache_hit_rate=0.0,
            total_cost=0.10,
            api_calls=5,
            total_tokens=10000,
        )

        assert metrics.avg_confidence == 1.0

    def test_metrics_with_zero_confidence(self) -> None:
        """Test metrics with 0.0 confidence score."""
        metrics = LLMMetrics(
            provider="ollama",
            model="llama3.3:70b",
            changes_parsed=10,
            avg_confidence=0.0,
            cache_hit_rate=0.0,
            total_cost=0.0,  # Free for local models
            api_calls=10,
            total_tokens=50000,
        )

        assert metrics.avg_confidence == 0.0

    def test_metrics_with_perfect_cache_hit_rate(self) -> None:
        """Test metrics with 100% cache hit rate."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            changes_parsed=30,
            avg_confidence=0.95,
            cache_hit_rate=1.0,  # All cached
            total_cost=0.001,  # Minimal cost due to full caching
            api_calls=0,  # No actual API calls needed
            total_tokens=0,
        )

        assert metrics.cache_hit_rate == 1.0

    def test_metrics_with_zero_cost_local_model(self) -> None:
        """Test metrics for free local model (Ollama)."""
        metrics = LLMMetrics(
            provider="ollama",
            model="llama3.3:70b",
            changes_parsed=50,
            avg_confidence=0.88,
            cache_hit_rate=0.0,  # No caching for local
            total_cost=0.0,  # Free
            api_calls=50,
            total_tokens=100000,
        )

        assert metrics.total_cost == 0.0
        assert metrics.cost_per_change == 0.0


class TestProviderStatsValidation:
    """Tests for ProviderStats __post_init__ validation."""

    def _valid_provider_stats(
        self,
        provider: str = "anthropic",
        model: str = "claude-haiku-4",
        total_requests: int = 10,
        successful_requests: int = 9,
        failed_requests: int = 1,
        success_rate: float = 0.9,
        total_cost: float = 0.05,
        total_tokens: int = 5000,
        avg_latency: float = 0.5,
        latency_p50: float = 0.4,
        latency_p95: float = 0.8,
        latency_p99: float = 1.0,
        cache_hit_rate: float = 0.5,
    ) -> ProviderStats:
        """Create valid ProviderStats with optional overrides."""
        return ProviderStats(
            provider=provider,
            model=model,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            success_rate=success_rate,
            total_cost=total_cost,
            total_tokens=total_tokens,
            avg_latency=avg_latency,
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            cache_hit_rate=cache_hit_rate,
            error_counts={},
        )

    def test_negative_total_requests_raises(self) -> None:
        """total_requests < 0 raises ValueError."""
        with pytest.raises(ValueError, match="total_requests must be >= 0"):
            self._valid_provider_stats(total_requests=-1)

    def test_negative_successful_requests_raises(self) -> None:
        """successful_requests < 0 raises ValueError."""
        with pytest.raises(ValueError, match="successful_requests must be >= 0"):
            self._valid_provider_stats(successful_requests=-1)

    def test_negative_failed_requests_raises(self) -> None:
        """failed_requests < 0 raises ValueError."""
        with pytest.raises(ValueError, match="failed_requests must be >= 0"):
            self._valid_provider_stats(failed_requests=-1)

    def test_negative_total_cost_raises(self) -> None:
        """total_cost < 0 raises ValueError."""
        with pytest.raises(ValueError, match="total_cost must be >= 0"):
            self._valid_provider_stats(total_cost=-0.01)

    def test_negative_total_tokens_raises(self) -> None:
        """total_tokens < 0 raises ValueError."""
        with pytest.raises(ValueError, match="total_tokens must be >= 0"):
            self._valid_provider_stats(total_tokens=-1)

    def test_negative_avg_latency_raises(self) -> None:
        """avg_latency < 0 raises ValueError."""
        with pytest.raises(ValueError, match="avg_latency must be >= 0"):
            self._valid_provider_stats(avg_latency=-0.1)

    def test_negative_latency_p50_raises(self) -> None:
        """latency_p50 < 0 raises ValueError."""
        with pytest.raises(ValueError, match="latency_p50 must be >= 0"):
            self._valid_provider_stats(latency_p50=-0.1)

    def test_negative_latency_p95_raises(self) -> None:
        """latency_p95 < 0 raises ValueError."""
        with pytest.raises(ValueError, match="latency_p95 must be >= 0"):
            self._valid_provider_stats(latency_p95=-0.1)

    def test_negative_latency_p99_raises(self) -> None:
        """latency_p99 < 0 raises ValueError."""
        with pytest.raises(ValueError, match="latency_p99 must be >= 0"):
            self._valid_provider_stats(latency_p99=-0.1)


class TestAggregatedMetricsValidation:
    """Tests for AggregatedMetrics __post_init__ validation."""

    def _valid_aggregated_metrics(
        self,
        latency_p50: float = 0.4,
        latency_p95: float = 0.8,
        latency_p99: float = 1.0,
        latency_avg: float = 0.5,
        total_requests: int = 10,
        successful_requests: int = 9,
        failed_requests: int = 1,
        success_rate: float = 0.9,
        total_cost: float = 0.05,
        cost_per_comment: float = 0.005,
        cache_hit_rate: float = 0.5,
        cache_savings: float = 0.02,
        fallback_count: int = 0,
        fallback_rate: float = 0.0,
    ) -> AggregatedMetrics:
        """Create valid AggregatedMetrics with optional overrides."""
        return AggregatedMetrics(
            provider_stats={},
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            latency_avg=latency_avg,
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

    def test_negative_latency_p50_raises(self) -> None:
        """latency_p50 < 0 raises ValueError."""
        with pytest.raises(ValueError, match="latency_p50 must be >= 0"):
            self._valid_aggregated_metrics(latency_p50=-0.1)

    def test_negative_latency_p95_raises(self) -> None:
        """latency_p95 < 0 raises ValueError."""
        with pytest.raises(ValueError, match="latency_p95 must be >= 0"):
            self._valid_aggregated_metrics(latency_p95=-0.1)

    def test_negative_latency_p99_raises(self) -> None:
        """latency_p99 < 0 raises ValueError."""
        with pytest.raises(ValueError, match="latency_p99 must be >= 0"):
            self._valid_aggregated_metrics(latency_p99=-0.1)

    def test_negative_latency_avg_raises(self) -> None:
        """latency_avg < 0 raises ValueError."""
        with pytest.raises(ValueError, match="latency_avg must be >= 0"):
            self._valid_aggregated_metrics(latency_avg=-0.1)

    def test_negative_total_requests_raises(self) -> None:
        """total_requests < 0 raises ValueError."""
        with pytest.raises(ValueError, match="total_requests must be >= 0"):
            self._valid_aggregated_metrics(total_requests=-1)

    def test_negative_successful_requests_raises(self) -> None:
        """successful_requests < 0 raises ValueError."""
        with pytest.raises(ValueError, match="successful_requests must be >= 0"):
            self._valid_aggregated_metrics(successful_requests=-1)

    def test_negative_failed_requests_raises(self) -> None:
        """failed_requests < 0 raises ValueError."""
        with pytest.raises(ValueError, match="failed_requests must be >= 0"):
            self._valid_aggregated_metrics(failed_requests=-1)

    def test_success_rate_below_zero_raises(self) -> None:
        """success_rate < 0 raises ValueError."""
        with pytest.raises(ValueError, match="success_rate must be between 0.0 and 1.0"):
            self._valid_aggregated_metrics(success_rate=-0.1)

    def test_success_rate_above_one_raises(self) -> None:
        """success_rate > 1 raises ValueError."""
        with pytest.raises(ValueError, match="success_rate must be between 0.0 and 1.0"):
            self._valid_aggregated_metrics(success_rate=1.1)

    def test_negative_total_cost_raises(self) -> None:
        """total_cost < 0 raises ValueError."""
        with pytest.raises(ValueError, match="total_cost must be >= 0"):
            self._valid_aggregated_metrics(total_cost=-0.01)

    def test_negative_cost_per_comment_raises(self) -> None:
        """cost_per_comment < 0 raises ValueError."""
        with pytest.raises(ValueError, match="cost_per_comment must be >= 0"):
            self._valid_aggregated_metrics(cost_per_comment=-0.001)

    def test_cache_hit_rate_below_zero_raises(self) -> None:
        """cache_hit_rate < 0 raises ValueError."""
        with pytest.raises(ValueError, match="cache_hit_rate must be between 0.0 and 1.0"):
            self._valid_aggregated_metrics(cache_hit_rate=-0.1)

    def test_cache_hit_rate_above_one_raises(self) -> None:
        """cache_hit_rate > 1 raises ValueError."""
        with pytest.raises(ValueError, match="cache_hit_rate must be between 0.0 and 1.0"):
            self._valid_aggregated_metrics(cache_hit_rate=1.1)

    def test_negative_cache_savings_raises(self) -> None:
        """cache_savings < 0 raises ValueError."""
        with pytest.raises(ValueError, match="cache_savings must be >= 0"):
            self._valid_aggregated_metrics(cache_savings=-0.01)

    def test_negative_fallback_count_raises(self) -> None:
        """fallback_count < 0 raises ValueError."""
        with pytest.raises(ValueError, match="fallback_count must be >= 0"):
            self._valid_aggregated_metrics(fallback_count=-1)

    def test_fallback_count_zero_valid(self) -> None:
        """fallback_count=0 is valid."""
        metrics = self._valid_aggregated_metrics(fallback_count=0)
        assert metrics.fallback_count == 0

    def test_fallback_count_positive_valid(self) -> None:
        """fallback_count > 0 is valid."""
        metrics = self._valid_aggregated_metrics(fallback_count=10)
        assert metrics.fallback_count == 10

    def test_fallback_rate_below_zero_raises(self) -> None:
        """fallback_rate < 0 raises ValueError."""
        with pytest.raises(ValueError, match="fallback_rate must be between 0.0 and 1.0"):
            self._valid_aggregated_metrics(fallback_rate=-0.1)

    def test_fallback_rate_above_one_raises(self) -> None:
        """fallback_rate > 1 raises ValueError."""
        with pytest.raises(ValueError, match="fallback_rate must be between 0.0 and 1.0"):
            self._valid_aggregated_metrics(fallback_rate=1.1)

    def test_fallback_rate_boundary_zero_valid(self) -> None:
        """fallback_rate=0.0 is valid."""
        metrics = self._valid_aggregated_metrics(fallback_rate=0.0)
        assert metrics.fallback_rate == 0.0

    def test_fallback_rate_boundary_one_valid(self) -> None:
        """fallback_rate=1.0 is valid."""
        metrics = self._valid_aggregated_metrics(fallback_rate=1.0)
        assert metrics.fallback_rate == 1.0

    def test_aggregated_metrics_with_fallback_fields(self) -> None:
        """Test AggregatedMetrics with fallback tracking fields."""
        metrics = self._valid_aggregated_metrics(fallback_count=5, fallback_rate=0.25)
        assert metrics.fallback_count == 5
        assert metrics.fallback_rate == 0.25
