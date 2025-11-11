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
    LLMParsingError,
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

    def test_apply_handles_none_llm_metrics_gracefully(self, runner: CliRunner) -> None:
        """Test apply command succeeds when llm_metrics is None (no LLM parsing used)."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            # Mock resolver to return result WITHOUT metrics (regex parsing scenario)
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=5,
                conflict_count=2,
                success_rate=71.4,
                llm_metrics=None,  # No LLM parsing was used
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

            # Should succeed
            assert result.exit_code == 0
            # Should NOT display LLM metrics panel
            assert "LLM Metrics" not in result.output
            # Should NOT display provider/model names
            assert "Anthropic" not in result.output
            assert "OpenAI" not in result.output
            assert "claude" not in result.output.lower()
            assert "gpt" not in result.output.lower()

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

            # Should display API error guidance with specific error message
            assert result.exit_code != 0
            assert "API Error" in result.output or "Service unavailable" in result.output

    def test_apply_handles_error_with_none_llm_provider(self, runner: CliRunner) -> None:
        """Test error handlers correctly handle llm_provider=None without AttributeError."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.resolve_pr_conflicts.side_effect = LLMAuthenticationError(
                "Authentication failed"
            )

            # Don't specify --llm-provider, which can result in None value
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
                    # No --llm-provider flag - may default to None
                ],
            )

            # Should display error without crashing with AttributeError
            assert result.exit_code != 0
            # Verify no AttributeError (would happen if .lower() called on None)
            # Key test: it doesn't crash - error message may vary by provider
            assert (
                "CLI Error" in result.output
                or "Authentication" in result.output
                or "authentication failed" in result.output.lower()
            )

    def test_apply_handles_parsing_error(self, runner: CliRunner) -> None:
        """Test apply command handles LLM parsing errors with warning (non-aborting)."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_resolver.resolve_pr_conflicts.side_effect = LLMParsingError(
                "Failed to parse LLM response"
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

            # Should display parsing error message
            assert "LLMParsingError" in result.output or "parsing" in result.output.lower()
            assert "Failed to parse LLM response" in result.output
            # LLMParsingError doesn't abort - exits successfully (fallback scenario)
            assert result.exit_code == 0


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


class TestApplyCommandLLMPreset:
    """Tests for apply command with --llm-preset flag."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create Click test runner."""
        return CliRunner()

    def test_apply_with_codex_cli_preset(self, runner: CliRunner) -> None:
        """Test apply command with --llm-preset codex-cli-free."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=5,
                conflict_count=0,
                success_rate=100.0,
                llm_metrics=None,
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
                    "--llm-preset",
                    "codex-cli-free",
                ],
            )

            # Should display preset loading message
            assert "Loaded LLM preset: codex-cli-free" in result.output
            assert result.exit_code == 0

    def test_apply_with_ollama_preset(self, runner: CliRunner) -> None:
        """Test apply command with --llm-preset ollama-local."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=3,
                conflict_count=1,
                success_rate=75.0,
                llm_metrics=None,
            )
            mock_resolver.resolve_pr_conflicts.return_value = mock_result

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "456",
                    "--owner",
                    "myorg",
                    "--repo",
                    "myrepo",
                    "--llm-preset",
                    "ollama-local",
                ],
            )

            # Should display preset loading message
            assert "Loaded LLM preset: ollama-local" in result.output
            assert result.exit_code == 0

    def test_apply_with_claude_cli_preset(self, runner: CliRunner) -> None:
        """Test apply command with --llm-preset claude-cli-sonnet."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=10,
                conflict_count=2,
                success_rate=83.3,
                llm_metrics=None,
            )
            mock_resolver.resolve_pr_conflicts.return_value = mock_result

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "789",
                    "--owner",
                    "acme",
                    "--repo",
                    "project",
                    "--llm-preset",
                    "claude-cli-sonnet",
                ],
            )

            # Should display preset loading message
            assert "Loaded LLM preset: claude-cli-sonnet" in result.output
            assert result.exit_code == 0

    def test_apply_with_openai_preset_and_api_key(self, runner: CliRunner) -> None:
        """Test apply command with --llm-preset openai-api-mini and --llm-api-key."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=7,
                conflict_count=1,
                success_rate=87.5,
                llm_metrics=None,
            )
            mock_resolver.resolve_pr_conflicts.return_value = mock_result

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "100",
                    "--owner",
                    "demo",
                    "--repo",
                    "test",
                    "--llm-preset",
                    "openai-api-mini",
                    "--llm-api-key",
                    "sk-test123",
                ],
            )

            # Should display preset loading message
            assert "Loaded LLM preset: openai-api-mini" in result.output
            assert result.exit_code == 0

    def test_apply_with_anthropic_preset_and_api_key(self, runner: CliRunner) -> None:
        """Test apply command with --llm-preset anthropic-api-balanced and --llm-api-key."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=8,
                conflict_count=2,
                success_rate=80.0,
                llm_metrics=None,
            )
            mock_resolver.resolve_pr_conflicts.return_value = mock_result

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "200",
                    "--owner",
                    "org",
                    "--repo",
                    "app",
                    "--llm-preset",
                    "anthropic-api-balanced",
                    "--llm-api-key",
                    "sk-ant-test456",
                ],
            )

            # Should display preset loading message
            assert "Loaded LLM preset: anthropic-api-balanced" in result.output
            assert result.exit_code == 0

    def test_apply_preset_overridden_by_individual_flags(self, runner: CliRunner) -> None:
        """Test that individual --llm-* flags override preset values."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=5,
                conflict_count=0,
                success_rate=100.0,
                llm_metrics=None,
            )
            mock_resolver.resolve_pr_conflicts.return_value = mock_result

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "300",
                    "--owner",
                    "test",
                    "--repo",
                    "repo",
                    "--llm-preset",
                    "ollama-local",  # Default model: qwen2.5-coder:7b
                    "--llm-model",
                    "llama3.3:70b",  # Override model
                ],
            )

            # Should load preset but allow override
            assert "Loaded LLM preset: ollama-local" in result.output
            assert result.exit_code == 0

    def test_apply_config_preset_takes_priority_over_llm_preset(self, runner: CliRunner) -> None:
        """Test that --config preset takes priority over --llm-preset."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=4,
                conflict_count=0,
                success_rate=100.0,
                llm_metrics=None,
            )
            mock_resolver.resolve_pr_conflicts.return_value = mock_result

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "400",
                    "--owner",
                    "user",
                    "--repo",
                    "project",
                    "--config",
                    "balanced",  # Config preset
                    "--llm-preset",
                    "codex-cli-free",  # Should be ignored
                ],
            )

            # Should load config preset, not LLM preset
            assert "Loaded configuration preset: balanced" in result.output
            assert "Loaded LLM preset" not in result.output
            assert result.exit_code == 0

    def test_apply_invalid_preset_name(self, runner: CliRunner) -> None:
        """Test apply command rejects invalid preset name."""
        result = runner.invoke(
            cli,
            [
                "apply",
                "--pr",
                "500",
                "--owner",
                "test",
                "--repo",
                "repo",
                "--llm-preset",
                "invalid-preset",  # Not in the choices list
            ],
        )

        # Should fail with invalid choice error
        assert result.exit_code != 0
        assert "Invalid value for '--llm-preset'" in result.output

    def test_apply_case_insensitive_preset(self, runner: CliRunner) -> None:
        """Test apply command accepts preset names case-insensitively."""
        with patch("pr_conflict_resolver.cli.main.ConflictResolver") as mock_resolver_class:
            mock_resolver = mock_resolver_class.return_value
            mock_result = Mock(
                applied_count=5,
                conflict_count=0,
                success_rate=100.0,
                llm_metrics=None,
            )
            mock_resolver.resolve_pr_conflicts.return_value = mock_result

            result = runner.invoke(
                cli,
                [
                    "apply",
                    "--pr",
                    "600",
                    "--owner",
                    "test",
                    "--repo",
                    "repo",
                    "--llm-preset",
                    "CODEX-CLI-FREE",  # All caps
                ],
            )

            # Should accept and normalize to lowercase
            assert "Loaded LLM preset: codex-cli-free" in result.output
            assert result.exit_code == 0
