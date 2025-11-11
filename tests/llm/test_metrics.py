"""Tests for LLM metrics tracking.

This module tests the LLM metrics infrastructure for tracking token usage,
costs, cache performance, and parsing statistics.
"""

import pytest

from pr_conflict_resolver.llm.metrics import LLMMetrics


class TestLLMMetrics:
    """Tests for LLMMetrics dataclass."""

    def test_metrics_creation(self) -> None:
        """Test creating LLMMetrics with valid values."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4-20250514",
            comments_parsed=20,
            avg_confidence=0.92,
            cache_hit_rate=0.65,
            total_cost=0.0234,
            api_calls=7,
            total_tokens=15420,
        )

        assert metrics.provider == "anthropic"
        assert metrics.model == "claude-haiku-4-20250514"
        assert metrics.comments_parsed == 20
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
            comments_parsed=10,
            avg_confidence=0.85,
            cache_hit_rate=0.5,
            total_cost=0.05,
            api_calls=5,
            total_tokens=5000,
        )

        with pytest.raises((AttributeError, TypeError)):
            metrics.provider = "anthropic"  # type: ignore[misc]

    def test_metrics_validation_negative_comments(self) -> None:
        """Test that negative comments_parsed raises ValueError."""
        with pytest.raises(ValueError, match="comments_parsed must be >= 0"):
            LLMMetrics(
                provider="anthropic",
                model="claude-haiku-4",
                comments_parsed=-1,
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
                comments_parsed=10,
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
                comments_parsed=10,
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
                comments_parsed=10,
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
                comments_parsed=10,
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
                comments_parsed=10,
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
                comments_parsed=10,
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
                comments_parsed=10,
                avg_confidence=0.9,
                cache_hit_rate=0.5,
                total_cost=0.01,
                api_calls=5,
                total_tokens=-1000,
            )


class TestLLMMetricsProperties:
    """Tests for LLMMetrics computed properties."""

    def test_cost_per_comment_with_comments(self) -> None:
        """Test cost_per_comment calculation with parsed comments."""
        metrics = LLMMetrics(
            provider="openai",
            model="gpt-4o-mini",
            comments_parsed=10,
            avg_confidence=0.85,
            cache_hit_rate=0.5,
            total_cost=0.05,
            api_calls=5,
            total_tokens=5000,
        )

        assert metrics.cost_per_comment == 0.005

    def test_cost_per_comment_with_zero_comments(self) -> None:
        """Test cost_per_comment returns 0.0 when no comments parsed."""
        metrics = LLMMetrics(
            provider="openai",
            model="gpt-4o-mini",
            comments_parsed=0,
            avg_confidence=0.0,
            cache_hit_rate=0.0,
            total_cost=0.0,
            api_calls=0,
            total_tokens=0,
        )

        assert metrics.cost_per_comment == 0.0

    def test_avg_tokens_per_call_with_calls(self) -> None:
        """Test avg_tokens_per_call calculation with API calls."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            comments_parsed=20,
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
            comments_parsed=0,
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
            comments_parsed=20,
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
            comments_parsed=20,
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
            comments_parsed=20,
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
            comments_parsed=20,
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
            comments_parsed=5,
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
            comments_parsed=10,
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
            comments_parsed=30,
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
            comments_parsed=50,
            avg_confidence=0.88,
            cache_hit_rate=0.0,  # No caching for local
            total_cost=0.0,  # Free
            api_calls=50,
            total_tokens=100000,
        )

        assert metrics.total_cost == 0.0
        assert metrics.cost_per_comment == 0.0
