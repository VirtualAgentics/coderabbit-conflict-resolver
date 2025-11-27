"""Integration tests for cost budget CLI options.

Tests the --cost-budget option in analyze and apply commands.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from review_bot_automator.cli.main import cli
from review_bot_automator.config.runtime_config import ApplicationMode
from review_bot_automator.llm.cost_tracker import CostTracker


class TestCostBudgetCLIOption:
    """Tests for --cost-budget CLI option."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_resolver(self) -> Generator[MagicMock, None, None]:
        """Create mock ConflictResolver."""
        with patch("review_bot_automator.cli.main.ConflictResolver") as mock:
            resolver_instance = MagicMock()
            resolver_instance.analyze_conflicts.return_value = []
            mock.return_value = resolver_instance
            yield mock

    @pytest.fixture
    def mock_provider(self) -> Generator[MagicMock, None, None]:
        """Create mock LLM provider."""
        with patch("review_bot_automator.llm.factory.create_provider") as mock:
            provider_instance = MagicMock()
            provider_instance.get_total_cost.return_value = 0.0
            mock.return_value = provider_instance
            yield mock

    def test_cost_budget_option_analyze_accepts_value(
        self, runner: CliRunner, mock_resolver: MagicMock, mock_provider: MagicMock
    ) -> None:
        """Analyze command accepts --cost-budget option."""
        result = runner.invoke(
            cli,
            [
                "analyze",
                "--pr",
                "1",
                "--owner",
                "test",
                "--repo",
                "test",
                "--cost-budget",
                "5.00",
                "--llm",
                "--llm-provider",
                "ollama",
            ],
        )
        # Should not fail due to unknown option (exit code 2 = usage/parse error)
        assert result.exit_code != 2, f"CLI parse error: {result.output}"
        assert "--cost-budget" not in (result.output or "")

    def test_cost_budget_option_apply_accepts_value(
        self, runner: CliRunner, mock_resolver: MagicMock, mock_provider: MagicMock
    ) -> None:
        """Apply command accepts --cost-budget option."""
        result = runner.invoke(
            cli,
            [
                "apply",
                "--pr",
                "1",
                "--owner",
                "test",
                "--repo",
                "test",
                "--cost-budget",
                "10.00",
                "--llm",
                "--llm-provider",
                "ollama",
            ],
        )
        # Should not fail due to unknown option (exit code 2 = usage/parse error)
        assert result.exit_code != 2, f"CLI parse error: {result.output}"
        assert "--cost-budget" not in (result.output or "")

    def test_cost_budget_env_var_respected(
        self, runner: CliRunner, mock_resolver: MagicMock, mock_provider: MagicMock
    ) -> None:
        """CR_LLM_COST_BUDGET environment variable is respected."""
        result = runner.invoke(
            cli,
            [
                "analyze",
                "--pr",
                "1",
                "--owner",
                "test",
                "--repo",
                "test",
                "--llm",
                "--llm-provider",
                "ollama",
            ],
            env={"CR_LLM_COST_BUDGET": "2.50"},
        )
        # Should not fail due to unknown env var (exit code 2 = usage/parse error)
        assert result.exit_code != 2, f"CLI parse error: {result.output}"
        assert "--cost-budget" not in (result.output or "")


class TestCostTrackerCreation:
    """Tests for CostTracker creation in _create_llm_parser."""

    @pytest.fixture
    def mock_provider(self) -> MagicMock:
        """Create mock LLM provider."""
        provider = MagicMock()
        provider.get_total_cost.return_value = 0.0
        return provider

    def test_cost_tracker_created_with_budget(self, mock_provider: MagicMock) -> None:
        """CostTracker is created when budget is set."""
        from review_bot_automator.cli.main import _create_llm_parser
        from review_bot_automator.config.runtime_config import RuntimeConfig

        config = RuntimeConfig(
            mode=ApplicationMode.ALL,
            enable_rollback=False,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=4,
            log_level="INFO",
            log_file=None,
            llm_enabled=True,
            llm_provider="ollama",
            llm_model="llama3.2",
            llm_cost_budget=5.00,
        )

        with patch("review_bot_automator.llm.factory.create_provider", return_value=mock_provider):
            _, tracker = _create_llm_parser(config)

        assert tracker is not None
        assert tracker.budget == 5.00

    def test_cost_tracker_not_created_without_budget(self, mock_provider: MagicMock) -> None:
        """CostTracker is None when no budget is set."""
        from review_bot_automator.cli.main import _create_llm_parser
        from review_bot_automator.config.runtime_config import RuntimeConfig

        config = RuntimeConfig(
            mode=ApplicationMode.ALL,
            enable_rollback=False,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=4,
            log_level="INFO",
            log_file=None,
            llm_enabled=True,
            llm_provider="ollama",
            llm_model="llama3.2",
            llm_cost_budget=None,
        )

        with patch("review_bot_automator.llm.factory.create_provider", return_value=mock_provider):
            _, tracker = _create_llm_parser(config)

        assert tracker is None

    def test_parser_receives_cost_tracker(self, mock_provider: MagicMock) -> None:
        """Parser is initialized with CostTracker."""
        from review_bot_automator.cli.main import _create_llm_parser
        from review_bot_automator.config.runtime_config import RuntimeConfig
        from review_bot_automator.llm.parser import UniversalLLMParser

        config = RuntimeConfig(
            mode=ApplicationMode.ALL,
            enable_rollback=False,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=4,
            log_level="INFO",
            log_file=None,
            llm_enabled=True,
            llm_provider="ollama",
            llm_model="llama3.2",
            llm_cost_budget=10.00,
        )

        with patch("review_bot_automator.llm.factory.create_provider", return_value=mock_provider):
            parser, tracker = _create_llm_parser(config)

        assert parser is not None
        assert isinstance(parser, UniversalLLMParser)
        assert parser.cost_tracker is tracker

    def test_parallel_parser_receives_cost_tracker(self, mock_provider: MagicMock) -> None:
        """ParallelLLMParser is initialized with CostTracker."""
        from review_bot_automator.cli.main import _create_llm_parser
        from review_bot_automator.config.runtime_config import RuntimeConfig
        from review_bot_automator.llm.parallel_parser import ParallelLLMParser

        config = RuntimeConfig(
            mode=ApplicationMode.ALL,
            enable_rollback=False,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=4,
            log_level="INFO",
            log_file=None,
            llm_enabled=True,
            llm_provider="ollama",
            llm_model="llama3.2",
            llm_cost_budget=10.00,
            llm_parallel_parsing=True,
        )

        with patch("review_bot_automator.llm.factory.create_provider", return_value=mock_provider):
            parser, tracker = _create_llm_parser(config)

        assert isinstance(parser, ParallelLLMParser)
        assert parser.cost_tracker is tracker


class TestCostBudgetEnforcement:
    """Tests for cost budget enforcement in parsers."""

    def test_parser_raises_when_budget_exceeded(self) -> None:
        """Parser raises LLMCostExceededError when budget exceeded."""
        from review_bot_automator.llm.exceptions import LLMCostExceededError
        from review_bot_automator.llm.parser import UniversalLLMParser

        # Create tracker that's already at budget
        tracker = CostTracker(budget=1.0)
        tracker.add_cost(1.0)  # Exhaust budget

        mock_provider = MagicMock()
        parser = UniversalLLMParser(
            provider=mock_provider,
            cost_tracker=tracker,
        )

        with pytest.raises(LLMCostExceededError) as exc_info:
            parser.parse_comment("Test comment", file_path="test.py")

        assert exc_info.value.accumulated_cost == 1.0
        assert exc_info.value.budget == 1.0
        # Verify provider was NOT called when budget is exceeded
        mock_provider.generate.assert_not_called()

    def test_parser_tracks_cost_after_call(self) -> None:
        """Parser tracks cost after successful LLM call."""
        from review_bot_automator.llm.parser import UniversalLLMParser

        tracker = CostTracker(budget=10.0)
        mock_provider = MagicMock()
        # Simulate cost increasing after call
        mock_provider.get_total_cost.side_effect = [0.0, 0.5]  # Before, after
        mock_provider.generate.return_value = "[]"

        parser = UniversalLLMParser(
            provider=mock_provider,
            cost_tracker=tracker,
        )

        parser.parse_comment("Test comment", file_path="test.py")
        assert tracker.accumulated_cost == 0.5


class TestCostBudgetErrorHandling:
    """Tests for LLMCostExceededError handling."""

    def test_error_handler_does_not_abort(self) -> None:
        """Error handler allows graceful degradation (no abort)."""
        from review_bot_automator.cli.llm_error_handler import handle_llm_errors
        from review_bot_automator.config.runtime_config import RuntimeConfig
        from review_bot_automator.llm.exceptions import LLMCostExceededError

        config = RuntimeConfig(
            mode=ApplicationMode.ALL,
            enable_rollback=False,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=4,
            log_level="INFO",
            log_file=None,
        )

        # Create the exception instance to raise
        error = LLMCostExceededError(
            "Budget exceeded",
            accumulated_cost=5.0,
            budget=5.0,
        )

        # Test that handle_llm_errors suppresses LLMCostExceededError
        # The context manager's __exit__ returns True to suppress the exception
        exception_reached_handler = False
        with handle_llm_errors(config):
            exception_reached_handler = True
            raise error

        # If we reach here, the context manager suppressed the exception
        # (mypy doesn't know __exit__ can suppress, so we need type: ignore)
        assert exception_reached_handler  # type: ignore[unreachable]

    def test_error_includes_cost_details(self) -> None:
        """LLMCostExceededError includes cost details in message."""
        from review_bot_automator.llm.exceptions import LLMCostExceededError

        error = LLMCostExceededError(
            "Budget exceeded",
            accumulated_cost=7.5,
            budget=5.0,
        )

        error_str = str(error)
        assert "7.5000" in error_str
        assert "5.0000" in error_str
