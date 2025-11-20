"""Tests for resilient provider wrapper.

This module tests the ResilientProvider wrapper that combines circuit breaker,
metrics tracking, and cost budgeting.
"""

import pytest
from conftest import create_mock_provider

from pr_conflict_resolver.llm.metrics.metrics_aggregator import MetricsAggregator
from pr_conflict_resolver.llm.providers.resilient_provider import (
    CostBudgetExceededError,
    ResilientProvider,
)
from pr_conflict_resolver.llm.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
)


class TestResilientProviderInitialization:
    """Test ResilientProvider initialization."""

    def test_init_with_provider_only(self) -> None:
        """Test initialization with provider only."""
        mock_provider = create_mock_provider("ClaudeCLIProvider", "claude-sonnet-4-5")

        resilient = ResilientProvider(mock_provider)

        assert resilient.provider == mock_provider
        assert resilient.circuit_breaker is None
        assert resilient.metrics_aggregator is None
        assert resilient.cost_budget_usd is None

    def test_init_with_circuit_breaker(self) -> None:
        """Test initialization with circuit breaker."""
        mock_provider = create_mock_provider()
        breaker = CircuitBreaker()

        resilient = ResilientProvider(mock_provider, circuit_breaker=breaker)

        assert resilient.circuit_breaker is breaker

    def test_init_with_metrics(self) -> None:
        """Test initialization with metrics aggregator."""
        mock_provider = create_mock_provider()
        metrics = MetricsAggregator()

        resilient = ResilientProvider(mock_provider, metrics_aggregator=metrics)

        assert resilient.metrics_aggregator is metrics

    def test_init_with_cost_budget(self) -> None:
        """Test initialization with cost budget."""
        mock_provider = create_mock_provider()

        resilient = ResilientProvider(mock_provider, cost_budget_usd=10.0)

        assert resilient.cost_budget_usd == 10.0
        assert resilient.remaining_budget == 10.0

    def test_init_auto_detects_provider_name(self) -> None:
        """Test auto-detection of provider name."""
        mock_provider = create_mock_provider("ClaudeCLIProvider")

        resilient = ResilientProvider(mock_provider)

        assert resilient.provider_name == "claude-cli"

    def test_init_auto_detects_model_name(self) -> None:
        """Test auto-detection of model name."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test-model-v2"

        resilient = ResilientProvider(mock_provider)

        assert resilient.model_name == "test-model-v2"


class TestResilientProviderGenerate:
    """Test generate method."""

    def test_generate_without_resilience_features(self) -> None:
        """Test generate without any resilience features."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.generate.return_value = "Response"

        resilient = ResilientProvider(mock_provider)
        result = resilient.generate("Test prompt")

        assert result == "Response"
        mock_provider.generate.assert_called_once_with("Test prompt", max_tokens=2000)

    def test_generate_with_circuit_breaker(self) -> None:
        """Test generate with circuit breaker protection."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.generate.return_value = "Response"

        breaker = CircuitBreaker()
        resilient = ResilientProvider(mock_provider, circuit_breaker=breaker)

        result = resilient.generate("Test prompt")

        assert result == "Response"

    def test_generate_with_open_circuit(self) -> None:
        """Test generate fails when circuit is open."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.generate.side_effect = RuntimeError("Error")

        breaker = CircuitBreaker(failure_threshold=1)
        resilient = ResilientProvider(mock_provider, circuit_breaker=breaker)

        # First call opens circuit
        with pytest.raises(RuntimeError):
            resilient.generate("Test prompt")

        # Second call rejected by circuit breaker
        with pytest.raises(CircuitBreakerError):
            resilient.generate("Test prompt")

    def test_generate_with_metrics_tracking(self) -> None:
        """Test generate tracks metrics."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.generate.return_value = "Response"

        metrics = MetricsAggregator()
        resilient = ResilientProvider(
            mock_provider,
            metrics_aggregator=metrics,
            provider_name="test",
            model_name="test-model",
        )

        resilient.generate("Test prompt")

        # Check metrics were tracked
        summary = metrics.get_summary()
        assert summary.total_requests == 1
        assert summary.total_successful == 1

    def test_generate_with_cost_budget_enforcement(self) -> None:
        """Test generate enforces cost budget."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.generate.return_value = "Response"
        # Configure count_tokens to return reasonable token counts
        mock_provider.count_tokens.side_effect = lambda text: len(text) // 3

        resilient = ResilientProvider(
            mock_provider,
            cost_budget_usd=0.01,
            cost_per_1k_input_tokens=0.003,
            cost_per_1k_output_tokens=0.015,
        )

        # First small request should succeed
        resilient.generate("Short", max_tokens=10)

        # Large request should exceed budget
        with pytest.raises(CostBudgetExceededError):
            resilient.generate("x" * 10000, max_tokens=5000)


class TestResilientProviderCostTracking:
    """Test cost tracking and budgeting."""

    def test_cost_estimation(self) -> None:
        """Test cost estimation for requests."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        # Configure count_tokens to return token count (1 token per 4 chars)
        mock_provider.count_tokens.side_effect = lambda text: len(text) // 4
        mock_provider.generate.return_value = "Test response"

        resilient = ResilientProvider(
            mock_provider,
            cost_per_1k_input_tokens=0.003,
            cost_per_1k_output_tokens=0.015,
        )

        # Generate with 4000 char prompt (≈1000 tokens) and 500 max_tokens
        # Input: 1000 tokens * $0.003/1k = $0.003
        # Output: 500 tokens * $0.015/1k = $0.0075
        # Total: $0.0105
        resilient.generate("x" * 4000, max_tokens=500)

        # Verify cost was tracked correctly via public property
        assert 0.01 <= resilient.total_cost <= 0.012  # Rough estimate

    def test_cost_estimation_without_costs_configured(self) -> None:
        """Test that cost tracking works even without configured costs."""
        mock_provider = create_mock_provider()
        mock_provider.generate.return_value = "Test response"

        resilient = ResilientProvider(mock_provider)
        resilient.generate("Test prompt", max_tokens=100)

        # Without configured costs, total_cost should remain 0
        assert resilient.total_cost == 0.0

    def test_budget_check_with_no_budget(self) -> None:
        """Test budget check when no budget is set."""
        mock_provider = create_mock_provider()
        mock_provider.generate.return_value = "response"
        mock_provider.count_tokens.return_value = 100000  # Large token count

        resilient = ResilientProvider(
            mock_provider,
            cost_per_1k_input_tokens=10.0,  # Expensive: $10 per 1k tokens
            cost_per_1k_output_tokens=0.0,
        )

        # Should not raise (unlimited budget) - call generate multiple times
        resilient.generate("prompt1", max_tokens=1)  # $1000
        resilient.generate("prompt2", max_tokens=1)  # Another $1000
        # No exception should be raised despite high cost

    def test_budget_check_within_budget(self) -> None:
        """Test budget check when within budget."""
        mock_provider = create_mock_provider()
        mock_provider.generate.return_value = "response"
        # First call: 5000 tokens, second call: 2000 tokens
        mock_provider.count_tokens.side_effect = [5000, 2000]

        # Configure to $1 per 1k input tokens: 5000 tokens * $1/1k = $5
        resilient = ResilientProvider(
            mock_provider,
            cost_budget_usd=10.0,
            cost_per_1k_input_tokens=1.0,
            cost_per_1k_output_tokens=0.0,
        )
        resilient.generate("prompt", max_tokens=1)  # Accumulates $5

        # Verify current cost is $5
        assert resilient.total_cost == 5.0

        # Generate with additional $2 (5 + 2 = 7, within 10) - should not raise
        resilient.generate("prompt2", max_tokens=1)  # Accumulates $2, total $7

    def test_budget_check_exceeds_budget(self) -> None:
        """Test budget check when budget would be exceeded."""
        mock_provider = create_mock_provider()
        mock_provider.generate.return_value = "response"
        # First call: 9000 tokens, second call: 2000 tokens
        mock_provider.count_tokens.side_effect = [9000, 2000]

        # Configure to $1 per 1k input tokens: 9000 tokens * $1/1k = $9
        resilient = ResilientProvider(
            mock_provider,
            cost_budget_usd=10.0,
            cost_per_1k_input_tokens=1.0,
            cost_per_1k_output_tokens=0.0,
        )
        resilient.generate("prompt", max_tokens=1)  # Accumulates $9

        assert resilient.total_cost == 9.0

        # Generate with additional $2 (9 + 2 = 11, exceeds 10) - should raise
        with pytest.raises(CostBudgetExceededError):
            resilient.generate("prompt2", max_tokens=1)  # Would accumulate $2, exceeds budget

    def test_remaining_budget_calculation(self) -> None:
        """Test remaining budget calculation."""
        mock_provider = create_mock_provider()
        mock_provider.generate.return_value = "response"
        mock_provider.count_tokens.return_value = 3500  # 3500 tokens

        # Configure to $1 per 1k input tokens: 3500 tokens * $1/1k = $3.5
        resilient = ResilientProvider(
            mock_provider,
            cost_budget_usd=10.0,
            cost_per_1k_input_tokens=1.0,
            cost_per_1k_output_tokens=0.0,
        )
        resilient.generate("prompt", max_tokens=1)  # Accumulates $3.5

        assert resilient.total_cost == 3.5
        assert resilient.remaining_budget == 6.5

    def test_remaining_budget_with_no_budget(self) -> None:
        """Test remaining budget when no budget is set."""
        mock_provider = create_mock_provider()

        resilient = ResilientProvider(mock_provider)

        assert resilient.remaining_budget is None

    def test_total_cost_property(self) -> None:
        """Test total_cost property."""
        mock_provider = create_mock_provider()
        mock_provider.generate.return_value = "response"
        mock_provider.count_tokens.return_value = 5500  # 5500 tokens

        # Configure to $1 per 1k input tokens: 5500 tokens * $1/1k = $5.5
        resilient = ResilientProvider(
            mock_provider,
            cost_per_1k_input_tokens=1.0,
            cost_per_1k_output_tokens=0.0,
        )
        resilient.generate("prompt", max_tokens=1)  # Accumulates $5.5

        assert resilient.total_cost == 5.5

    def test_reset_cost_tracking(self) -> None:
        """Test resetting cost tracking."""
        mock_provider = create_mock_provider()
        mock_provider.generate.return_value = "response"
        mock_provider.count_tokens.return_value = 10000  # 10000 tokens

        # Configure to $1 per 1k input tokens: 10000 tokens * $1/1k = $10
        resilient = ResilientProvider(
            mock_provider,
            cost_per_1k_input_tokens=1.0,
            cost_per_1k_output_tokens=0.0,
        )
        resilient.generate("prompt", max_tokens=1)  # Accumulates $10

        assert resilient.total_cost == 10.0

        resilient.reset_cost_tracking()

        assert resilient.total_cost == 0.0


class TestResilientProviderCountTokens:
    """Test count_tokens pass-through."""

    def test_count_tokens_passes_through(self) -> None:
        """Test that count_tokens passes through to provider."""
        mock_provider = create_mock_provider()
        mock_provider.count_tokens.return_value = 42

        resilient = ResilientProvider(mock_provider)
        result = resilient.count_tokens("Test text")

        assert result == 42
        mock_provider.count_tokens.assert_called_once_with("Test text")


class TestResilientProviderIntegration:
    """Test integration of all resilience features together."""

    def test_full_integration(self) -> None:
        """Test all features working together."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "Response"
        # Configure count_tokens to return reasonable token counts
        mock_provider.count_tokens.side_effect = lambda text: len(text) // 3

        breaker = CircuitBreaker()
        metrics = MetricsAggregator()

        resilient = ResilientProvider(
            mock_provider,
            circuit_breaker=breaker,
            metrics_aggregator=metrics,
            cost_budget_usd=1.0,
            provider_name="test",
            model_name="test-model",
            cost_per_1k_input_tokens=0.001,
            cost_per_1k_output_tokens=0.005,
        )

        # Make a successful request
        result = resilient.generate("Test prompt")

        assert result == "Response"

        # Check metrics were tracked
        summary = metrics.get_summary()
        assert summary.total_requests == 1
        assert summary.total_successful == 1

        # Check cost was tracked
        assert resilient.total_cost > 0
        assert resilient.remaining_budget is not None
        assert resilient.remaining_budget < 1.0

    def test_integration_with_failures(self) -> None:
        """Test integration when provider fails."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.generate.side_effect = RuntimeError("API Error")

        breaker = CircuitBreaker(failure_threshold=2)
        metrics = MetricsAggregator()

        resilient = ResilientProvider(
            mock_provider,
            circuit_breaker=breaker,
            metrics_aggregator=metrics,
            provider_name="test",
            model_name="test",
        )

        # First failure
        with pytest.raises(RuntimeError):
            resilient.generate("Test")

        # Second failure opens circuit
        with pytest.raises(RuntimeError):
            resilient.generate("Test")

        # Third attempt rejected by circuit breaker
        with pytest.raises(CircuitBreakerError):
            resilient.generate("Test")

        # Check metrics (circuit breaker rejections are counted as failures)
        summary = metrics.get_summary()
        assert summary.total_requests == 3  # All three attempts tracked
        assert summary.total_failed == 3  # Including circuit breaker rejection


class TestResilientProviderRepr:
    """Test string representation."""

    def test_repr_with_budget(self) -> None:
        """Test repr with budget set."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"

        resilient = ResilientProvider(
            mock_provider,
            cost_budget_usd=10.0,
            provider_name="test",
            model_name="test-model",
        )

        repr_str = repr(resilient)

        assert "ResilientProvider" in repr_str
        assert "test" in repr_str
        assert "test-model" in repr_str
        assert "$10.00" in repr_str

    def test_repr_without_budget(self) -> None:
        """Test repr without budget."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"

        resilient = ResilientProvider(
            mock_provider,
            provider_name="test",
            model_name="test",
        )

        repr_str = repr(resilient)

        assert "unlimited" in repr_str
