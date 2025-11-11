"""Tests for CLI LLM integration (metrics display and error handling).

This module tests the CLI's integration with LLM metrics display and
error handling functionality, ensuring proper formatting and user experience.
"""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from pr_conflict_resolver.cli.main import _display_llm_metrics, cli
from pr_conflict_resolver.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from pr_conflict_resolver.llm.metrics import LLMMetrics


class TestMetricsDisplay:
    """Tests for _display_llm_metrics() function."""

    def test_display_metrics_basic(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test basic metrics display output."""
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

        _display_llm_metrics(metrics)
        captured = capsys.readouterr()

        # Check panel title includes provider and model
        assert "Anthropic" in captured.out
        assert "claude-haiku-4-20250514" in captured.out

        # Check all key metrics are displayed
        assert "Changes parsed: 20" in captured.out
        assert "92.0%" in captured.out  # Confidence as percentage
        assert "API calls: 7" in captured.out
        assert "15,420" in captured.out  # Tokens with comma separator
        assert "65.0%" in captured.out  # Cache hit rate
        assert "$0.0234" in captured.out  # Total cost

    def test_display_metrics_openai_capitalization(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test OpenAI provider name is capitalized correctly."""
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

        _display_llm_metrics(metrics)
        captured = capsys.readouterr()

        # OpenAI should be capitalized as "OpenAI", not "Openai"
        assert "OpenAI" in captured.out
        assert "gpt-4o-mini" in captured.out

    def test_display_metrics_free_local_model(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test metrics display for free local model (Ollama)."""
        metrics = LLMMetrics(
            provider="ollama",
            model="llama3.3:70b",
            changes_parsed=50,
            avg_confidence=0.88,
            cache_hit_rate=0.0,
            total_cost=0.0,  # Free
            api_calls=50,
            total_tokens=100000,
        )

        _display_llm_metrics(metrics)
        captured = capsys.readouterr()

        # Cost should show "Free" instead of $0.0000
        assert "Free" in captured.out
        assert "Ollama" in captured.out
        assert "llama3.3:70b" in captured.out

    def test_display_metrics_high_token_count(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test metrics display formats large token counts with commas."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-opus-4",
            changes_parsed=100,
            avg_confidence=0.95,
            cache_hit_rate=0.8,
            total_cost=1.2345,
            api_calls=100,
            total_tokens=1234567,  # > 1M tokens
        )

        _display_llm_metrics(metrics)
        captured = capsys.readouterr()

        # Check comma formatting for large numbers
        assert "1,234,567" in captured.out  # Total tokens
        assert "12,346" in captured.out  # Avg tokens per call (1234567/100)

    def test_display_metrics_computed_properties(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test display includes computed metrics (cost per change, avg tokens)."""
        metrics = LLMMetrics(
            provider="openai",
            model="gpt-4o",
            changes_parsed=25,
            avg_confidence=0.90,
            cache_hit_rate=0.7,
            total_cost=0.125,  # $0.125 total
            api_calls=10,
            total_tokens=20000,
        )

        _display_llm_metrics(metrics)
        captured = capsys.readouterr()

        # Cost per change: $0.125 / 25 = $0.0050
        assert "$0.0050" in captured.out
        # Avg tokens per call: 20000 / 10 = 2000
        assert "2,000" in captured.out


class TestApplyCommandLLMIntegration:
    """Tests for apply command with LLM error handling."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create Click test runner."""
        return CliRunner()

    def test_apply_displays_metrics_on_success(self, runner: CliRunner) -> None:
        """Test apply command displays LLM metrics when available."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            # Mock resolver to return result with metrics
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=5,
                conflict_count=2,
                success_rate=71.4,
                llm_metrics=LLMMetrics(
                    provider="anthropic",
                    model="claude-haiku-4",
                    changes_parsed=7,
                    avg_confidence=0.90,
                    cache_hit_rate=0.5,
                    total_cost=0.01,
                    api_calls=4,
                    total_tokens=5000,
                ),
            )
            mock_resolver.resolve_pr_conflicts.return_value = mock_result

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "123",
                    "--owner",
                    "testowner",
                    "--repo",
                    "testrepo",
                ],
            )

            # Check metrics are displayed
            assert "LLM Metrics" in result.output
            assert "Anthropic" in result.output
            assert "claude-haiku-4" in result.output

    def test_apply_handles_auth_error(self, runner: CliRunner) -> None:
        """Test apply command handles LLM authentication errors."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.resolve_pr_conflicts.side_effect = LLMAuthenticationError(
                "Invalid API key"
            )

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "123",
                    "--owner",
                    "testowner",
                    "--repo",
                    "testrepo",
                ],
            )

            # Should display authentication error guidance
            assert result.exit_code != 0
            assert "Authentication Error" in result.output or "API key" in result.output

    def test_apply_handles_rate_limit_error(self, runner: CliRunner) -> None:
        """Test apply command handles LLM rate limit errors."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.resolve_pr_conflicts.side_effect = LLMRateLimitError(
                "Rate limit exceeded"
            )

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "123",
                    "--owner",
                    "testowner",
                    "--repo",
                    "testrepo",
                ],
            )

            # Should display rate limit guidance
            assert result.exit_code != 0
            assert "Rate Limit" in result.output or "rate limit" in result.output.lower()

    def test_apply_handles_timeout_error(self, runner: CliRunner) -> None:
        """Test apply command handles LLM timeout errors."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.resolve_pr_conflicts.side_effect = LLMTimeoutError("Request timed out")

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "123",
                    "--owner",
                    "testowner",
                    "--repo",
                    "testrepo",
                ],
            )

            # Should display timeout guidance
            assert result.exit_code != 0
            assert "Timeout" in result.output or "timeout" in result.output.lower()

    def test_apply_handles_config_error(self, runner: CliRunner) -> None:
        """Test apply command handles LLM configuration errors."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.resolve_pr_conflicts.side_effect = LLMConfigurationError(
                "Invalid model name"
            )

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "123",
                    "--owner",
                    "testowner",
                    "--repo",
                    "testrepo",
                ],
            )

            # Should display configuration error guidance
            assert result.exit_code != 0
            assert (
                "Configuration Error" in result.output or "configuration" in result.output.lower()
            )

    def test_apply_handles_api_error(self, runner: CliRunner) -> None:
        """Test apply command handles generic LLM API errors."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.resolve_pr_conflicts.side_effect = LLMAPIError("Service unavailable")

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "123",
                    "--owner",
                    "testowner",
                    "--repo",
                    "testrepo",
                ],
            )

            # Should display API error guidance
            assert result.exit_code != 0
            assert "API Error" in result.output or "error" in result.output.lower()


class TestMetricsDisplayEdgeCases:
    """Tests for edge cases in metrics display."""

    def test_display_metrics_zero_values(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test metrics display with all zero values."""
        metrics = LLMMetrics(
            provider="ollama",
            model="test-model",
            changes_parsed=0,
            avg_confidence=0.0,
            cache_hit_rate=0.0,
            total_cost=0.0,
            api_calls=0,
            total_tokens=0,
        )

        _display_llm_metrics(metrics)
        captured = capsys.readouterr()

        # Should display zeros without errors
        assert "Changes parsed: 0" in captured.out
        assert "0.0%" in captured.out  # Cache hit rate
        assert "Free" in captured.out  # Zero cost shows as Free

    def test_display_metrics_perfect_scores(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test metrics display with perfect confidence and cache hit rate."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-opus-4",
            changes_parsed=10,
            avg_confidence=1.0,  # Perfect confidence
            cache_hit_rate=1.0,  # Perfect cache hits
            total_cost=0.001,
            api_calls=1,
            total_tokens=1000,
        )

        _display_llm_metrics(metrics)
        captured = capsys.readouterr()

        # Check perfect percentages display correctly
        assert "100.0%" in captured.out

    def test_display_metrics_very_small_cost(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test metrics display with very small cost values."""
        metrics = LLMMetrics(
            provider="openai",
            model="gpt-4o-mini",
            changes_parsed=1000,
            avg_confidence=0.85,
            cache_hit_rate=0.9,
            total_cost=0.000123,  # Very small cost
            api_calls=100,
            total_tokens=50000,
        )

        _display_llm_metrics(metrics)
        captured = capsys.readouterr()

        # Should display with 4 decimal places
        assert "$0.0001" in captured.out
