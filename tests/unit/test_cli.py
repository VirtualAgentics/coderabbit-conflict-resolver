"""Unit tests for CLI commands in review_bot_automator.cli.main."""

from contextlib import nullcontext
from unittest.mock import MagicMock, Mock, patch

import click
import pytest
from click.testing import CliRunner

from review_bot_automator import Change, Conflict, FileType, Resolution, ResolutionResult
from review_bot_automator.cli.main import (
    _create_llm_parser,
    _display_cost_status,
    _display_llm_metrics,
    _export_metrics,
    _record_and_display_metrics,
    cli,
    sanitize_for_output,
    validate_cost_budget,
    validate_github_repo,
    validate_github_username,
    validate_pr_number,
)
from review_bot_automator.config.exceptions import ConfigError
from review_bot_automator.config.runtime_config import RuntimeConfig
from review_bot_automator.llm.cost_tracker import CostTracker
from review_bot_automator.llm.metrics import LLMMetrics
from review_bot_automator.llm.metrics_aggregator import MetricsAggregator
from review_bot_automator.llm.providers.gpu_detector import GPUInfo


def _sample_conflict(file_path: str = "test.json", severity: str = "low") -> Conflict:
    ch = Change(
        path=file_path,
        start_line=1,
        end_line=3,
        content='{"k": "v"}',
        metadata={},
        fingerprint="fp1",
        file_type=FileType.JSON,
    )
    return Conflict(
        file_path=file_path,
        line_range=(1, 3),
        changes=[ch],
        conflict_type="partial",
        severity=severity,
        overlap_percentage=50.0,
    )


def test_validate_pr_number_rejects_non_positive() -> None:
    """validate_pr_number should reject values less than 1."""
    with pytest.raises(click.BadParameter, match="PR number must be positive"):
        validate_pr_number(Mock(), Mock(), 0)


def test_sanitize_for_output_redacts_control_chars() -> None:
    """sanitize_for_output should redact control characters."""
    assert sanitize_for_output("safe-value") == "safe-value"
    assert sanitize_for_output("\x00unsafe\n") == "[REDACTED]"


def test_validate_github_username_rules() -> None:
    """validate_github_username enforces GitHub naming rules."""
    ctx = Mock()
    param = Mock()

    with pytest.raises(click.BadParameter):
        validate_github_username(ctx, param, "bad/user")

    with pytest.raises(click.BadParameter):
        validate_github_username(ctx, param, " " * 3)

    assert validate_github_username(ctx, param, "valid-user") == "valid-user"


def test_validate_github_repo_rules() -> None:
    """validate_github_repo enforces repository naming rules."""
    ctx = Mock()
    param = Mock()

    with pytest.raises(click.BadParameter):
        validate_github_repo(ctx, param, "repo/with/slash")

    with pytest.raises(click.BadParameter):
        validate_github_repo(ctx, param, "")

    assert validate_github_repo(ctx, param, "valid_repo") == "valid_repo"


@patch("review_bot_automator.cli.main.ConflictResolver")
def test_cli_analyze_no_conflicts(mock_resolver: Mock) -> None:
    """analyze prints 'No conflicts' when none are found."""
    mock_inst = mock_resolver.return_value
    mock_inst.analyze_conflicts.return_value = []

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--pr", "123", "--owner", "o", "--repo", "r"])

    assert result.exit_code == 0
    assert "No conflicts detected" in result.output


@patch("review_bot_automator.cli.main.ConflictResolver")
def test_cli_analyze_with_conflicts(mock_resolver: Mock) -> None:
    """analyze prints a table and summary when conflicts exist."""
    mock_inst = mock_resolver.return_value
    mock_inst.analyze_conflicts.return_value = [_sample_conflict("test.json", "medium")]

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--pr", "5", "--owner", "o", "--repo", "r"])

    assert result.exit_code == 0
    # Robust assertions that don't depend on table formatting/emoji
    assert "Analyzing conflicts in PR #5" in result.output
    assert "Found 1 conflicts" in result.output
    assert "test.json" in result.output


def test_cli_apply_dry_run() -> None:
    """apply --dry-run prints an informational message and exits cleanly."""
    runner = CliRunner()
    result = runner.invoke(cli, ["apply", "--pr", "7", "--owner", "o", "--repo", "r", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN MODE:" in result.output
    assert "Analyzing conflicts without applying changes" in result.output


@patch("review_bot_automator.cli.main.ConflictResolver")
def test_cli_apply_success(mock_resolver: Mock) -> None:
    """apply prints resolution summary when successful."""
    mock_inst = mock_resolver.return_value
    res = Resolution(
        strategy="priority", applied_changes=[], skipped_changes=[], success=True, message="ok"
    )
    rr = ResolutionResult(
        applied_count=3, conflict_count=2, success_rate=60.0, resolutions=[res], conflicts=[]
    )
    mock_inst.resolve_pr_conflicts.return_value = rr

    runner = CliRunner()
    result = runner.invoke(cli, ["apply", "--pr", "8", "--owner", "o", "--repo", "r"])

    assert result.exit_code == 0
    assert "Applied: 3 suggestions" in result.output
    assert "Skipped: 2 conflicts" in result.output
    assert "Success rate: 60.0%" in result.output


@patch("review_bot_automator.cli.main.ConflictResolver")
def test_cli_simulate_mixed_conflicts(mock_resolver: Mock) -> None:
    """simulate reports how many would be applied vs skipped."""
    mock_inst = mock_resolver.return_value
    # One 'low' (would apply) and one 'high' (would skip)
    mock_inst.analyze_conflicts.return_value = [
        _sample_conflict("a.json", "low"),
        _sample_conflict("b.json", "high"),
    ]

    # Mock resolve_conflicts to return Resolution objects with applied/skipped changes
    change1 = Change(
        path="a.json",
        start_line=1,
        end_line=2,
        content="change 1",
        metadata={},
        fingerprint="fp1",
        file_type=FileType.JSON,
    )
    change2 = Change(
        path="b.json",
        start_line=1,
        end_line=2,
        content="change 2",
        metadata={},
        fingerprint="fp2",
        file_type=FileType.JSON,
    )
    mock_inst.resolve_conflicts.return_value = [
        Resolution(
            strategy="priority",
            applied_changes=[change1],
            skipped_changes=[],
            success=True,
            message="",
        ),
        Resolution(
            strategy="priority",
            applied_changes=[],
            skipped_changes=[change2],
            success=True,
            message="",
        ),
    ]

    runner = CliRunner()
    result = runner.invoke(cli, ["simulate", "--pr", "9", "--owner", "o", "--repo", "r"])

    assert result.exit_code == 0
    assert "Simulation Results" in result.output
    assert "Would apply: 1" in result.output
    assert "Would skip: 1" in result.output


@patch("review_bot_automator.cli.main.ConflictResolver")
def test_cli_analyze_handles_error(mock_resolver: Mock) -> None:
    """analyze gracefully handles exceptions and aborts."""
    mock_inst = mock_resolver.return_value
    mock_inst.analyze_conflicts.side_effect = Exception("boom")

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--pr", "10", "--owner", "o", "--repo", "r"])

    assert result.exit_code != 0
    assert "Error analyzing conflicts" in result.output


@patch("review_bot_automator.cli.main.ConflictResolver")
def test_cli_apply_handles_error(mock_resolver: Mock) -> None:
    """apply gracefully handles exceptions and aborts."""
    mock_inst = mock_resolver.return_value
    mock_inst.resolve_pr_conflicts.side_effect = Exception("Application failed")

    runner = CliRunner()
    result = runner.invoke(cli, ["apply", "--pr", "11", "--owner", "o", "--repo", "r"])

    assert result.exit_code != 0
    assert "Error applying suggestions" in result.output


@patch("review_bot_automator.cli.main.load_runtime_config")
@patch("review_bot_automator.cli.main.ConflictResolver")
def test_cli_analyze_confidence_threshold_override(
    mock_resolver: Mock, mock_load_config: Mock
) -> None:
    """analyze forwards --llm-confidence-threshold into cli_overrides."""
    config = RuntimeConfig.from_defaults()
    mock_load_config.return_value = (config, None)
    mock_resolver.return_value.analyze_conflicts.return_value = []

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            "--pr",
            "12",
            "--owner",
            "o",
            "--repo",
            "r",
            "--llm-confidence-threshold",
            "0.7",
        ],
    )

    assert result.exit_code == 0
    overrides = mock_load_config.call_args.kwargs["cli_overrides"]
    assert overrides["llm_confidence_threshold"] == 0.7


@patch("review_bot_automator.cli.main._display_llm_metrics")
@patch("review_bot_automator.cli.main.handle_llm_errors")
@patch("review_bot_automator.cli.main._create_llm_parser")
@patch("review_bot_automator.cli.main.load_runtime_config")
@patch("review_bot_automator.cli.main.ConflictResolver")
def test_cli_analyze_shows_llm_metrics(
    mock_resolver: Mock,
    mock_load_config: Mock,
    mock_create_parser: Mock,
    mock_handle_llm_errors: Mock,
    mock_display_metrics: Mock,
) -> None:
    """analyze displays LLM metrics when enabled."""
    runtime_config = RuntimeConfig.from_defaults().merge_with_cli(
        llm_enabled=True,
        llm_provider="anthropic",
        llm_model="claude-3-haiku",
        llm_parallel_parsing=False,
        llm_api_key="test-key-123",
    )
    mock_load_config.return_value = (runtime_config, "balanced")
    mock_handle_llm_errors.return_value = nullcontext()
    mock_create_parser.return_value = (object(), None)  # (parser, tracker) tuple

    conflict = _sample_conflict("test.json", "low")
    mock_inst = mock_resolver.return_value
    mock_inst.analyze_conflicts.return_value = [conflict]
    mock_inst._fetch_comments_with_error_context.return_value = []
    mock_inst.extract_changes_from_comments.return_value = []
    mock_inst._aggregate_llm_metrics.return_value = LLMMetrics(
        provider="anthropic",
        model="claude-3-haiku",
        changes_parsed=1,
        avg_confidence=0.9,
        cache_hit_rate=0.0,
        total_cost=0.01,
        api_calls=1,
        total_tokens=100,
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "analyze",
            "--pr",
            "12",
            "--owner",
            "o",
            "--repo",
            "r",
            "--llm",
        ],
    )

    assert result.exit_code == 0
    mock_display_metrics.assert_called_once()


@patch("review_bot_automator.cli.main.load_runtime_config")
@patch("review_bot_automator.cli.main.ConflictResolver")
def test_cli_apply_confidence_threshold_override(
    mock_resolver: Mock, mock_load_config: Mock
) -> None:
    """apply forwards --llm-confidence-threshold into cli_overrides."""
    config = RuntimeConfig.from_defaults()
    mock_load_config.return_value = (config, None)

    mock_inst = mock_resolver.return_value
    res = Resolution(
        strategy="priority", applied_changes=[], skipped_changes=[], success=True, message="ok"
    )
    rr = ResolutionResult(
        applied_count=1, conflict_count=0, success_rate=100.0, resolutions=[res], conflicts=[]
    )
    mock_inst.resolve_pr_conflicts.return_value = rr

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "apply",
            "--pr",
            "13",
            "--owner",
            "o",
            "--repo",
            "r",
            "--llm-confidence-threshold",
            "0.6",
        ],
    )

    assert result.exit_code == 0
    overrides = mock_load_config.call_args.kwargs["cli_overrides"]
    assert overrides["llm_confidence_threshold"] == 0.6


@patch("review_bot_automator.cli.main.load_runtime_config")
def test_cli_apply_invalid_confidence_threshold(mock_load_config: Mock) -> None:
    """apply surfaces configuration errors for invalid confidence thresholds."""
    mock_load_config.side_effect = ConfigError("llm_confidence_threshold must be between 0 and 1")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "apply",
            "--pr",
            "14",
            "--owner",
            "o",
            "--repo",
            "r",
            "--llm-confidence-threshold",
            "1.5",
        ],
    )

    assert result.exit_code != 0
    assert "Configuration error" in result.output


def test_create_llm_parser_disabled() -> None:
    """Test _create_llm_parser returns (None, None) when LLM is disabled."""
    config = RuntimeConfig.from_defaults()
    config = config.merge_with_cli(llm_enabled=False)

    parser, tracker = _create_llm_parser(config)

    assert parser is None
    assert tracker is None


@patch("review_bot_automator.cli.main.console")
def test_display_llm_metrics_gpu_branch(mock_console: Mock) -> None:
    """_display_llm_metrics renders GPU details when available."""
    metrics = LLMMetrics(
        provider="ollama",
        model="llama3",
        changes_parsed=5,
        avg_confidence=0.9,
        cache_hit_rate=0.5,
        total_cost=0.0,
        api_calls=2,
        total_tokens=2000,
        gpu_info=GPUInfo(
            available=True,
            gpu_type="NVIDIA",
            model_name="RTX 4090",
            vram_total_mb=24576,
            vram_available_mb=20480,
            compute_capability="8.9",
        ),
    )

    _display_llm_metrics(metrics)

    # console.print called twice (blank line + panel)
    assert mock_console.print.call_count == 2


@patch("review_bot_automator.cli.main.console")
def test_display_llm_metrics_cpu_branch(mock_console: Mock) -> None:
    """_display_llm_metrics prints CPU info when GPU unavailable."""
    metrics = LLMMetrics(
        provider="anthropic",
        model="claude",
        changes_parsed=0,
        avg_confidence=0.0,
        cache_hit_rate=0.0,
        total_cost=0.0,
        api_calls=0,
        total_tokens=0,
        gpu_info=GPUInfo(
            available=False,
            gpu_type=None,
            model_name=None,
            vram_total_mb=None,
            vram_available_mb=None,
            compute_capability=None,
        ),
    )

    _display_llm_metrics(metrics)

    assert mock_console.print.call_count == 2


@patch("review_bot_automator.llm.factory.create_provider")
@patch("review_bot_automator.cli.main.ParallelLLMParser")
def test_create_llm_parser_parallel_enabled(
    mock_parallel_parser: Mock, mock_create_provider: Mock
) -> None:
    """Test _create_llm_parser creates ParallelLLMParser when parallel parsing enabled."""
    mock_provider = MagicMock()
    mock_create_provider.return_value = mock_provider
    mock_parser_instance = MagicMock()
    mock_parallel_parser.return_value = mock_parser_instance

    config = RuntimeConfig.from_defaults()
    config = config.merge_with_cli(
        llm_enabled=True,
        llm_provider="claude-cli",
        llm_model="claude-sonnet-4-5",
        llm_parallel_parsing=True,
        llm_parallel_max_workers=8,
        llm_rate_limit=20.0,
    )

    parser, _tracker = _create_llm_parser(config)

    assert parser is not None
    mock_parallel_parser.assert_called_once()
    call_kwargs = mock_parallel_parser.call_args[1]
    assert call_kwargs["max_workers"] == 8
    assert call_kwargs["rate_limit"] == 20.0


@patch("review_bot_automator.llm.factory.create_provider")
@patch("review_bot_automator.cli.main.UniversalLLMParser")
def test_create_llm_parser_parallel_disabled(
    mock_universal_parser: Mock, mock_create_provider: Mock
) -> None:
    """Test _create_llm_parser creates UniversalLLMParser when parallel parsing disabled."""
    mock_provider = MagicMock()
    mock_create_provider.return_value = mock_provider
    mock_parser_instance = MagicMock()
    mock_universal_parser.return_value = mock_parser_instance

    config = RuntimeConfig.from_defaults()
    config = config.merge_with_cli(
        llm_enabled=True,
        llm_provider="claude-cli",
        llm_model="claude-sonnet-4-5",
        llm_parallel_parsing=False,
    )

    parser, _tracker = _create_llm_parser(config)

    assert parser is not None
    mock_universal_parser.assert_called_once()


@patch("review_bot_automator.llm.factory.create_provider")
def test_create_llm_parser_provider_error(mock_create_provider: Mock) -> None:
    """Test _create_llm_parser returns (None, None) when provider creation fails."""
    mock_create_provider.side_effect = RuntimeError("Provider initialization failed")

    config = RuntimeConfig.from_defaults()
    config = config.merge_with_cli(
        llm_enabled=True,
        llm_provider="claude-cli",  # Use valid provider, but creation will fail
    )

    parser, tracker = _create_llm_parser(config)

    assert parser is None
    assert tracker is None


@patch("review_bot_automator.llm.factory.create_provider")
@patch("review_bot_automator.cli.main.ParallelLLMParser")
def test_create_llm_parser_parser_error(
    mock_parallel_parser: Mock, mock_create_provider: Mock
) -> None:
    """Test _create_llm_parser returns (None, None) when parser creation fails."""
    mock_provider = MagicMock()
    mock_create_provider.return_value = mock_provider
    mock_parallel_parser.side_effect = ValueError("Invalid parser configuration")

    config = RuntimeConfig.from_defaults()
    config = config.merge_with_cli(
        llm_enabled=True,
        llm_parallel_parsing=True,
    )

    parser, tracker = _create_llm_parser(config)

    assert parser is None
    assert tracker is None


# ============================================================
# Cost Budget Coverage Tests (Issue #225)
# ============================================================


class TestValidateCostBudget:
    """Tests for validate_cost_budget CLI callback."""

    def test_validate_cost_budget_valid_values(self) -> None:
        """validate_cost_budget accepts valid non-negative values."""
        assert validate_cost_budget(Mock(), Mock(), 0.0) == 0.0
        assert validate_cost_budget(Mock(), Mock(), 1.5) == 1.5
        assert validate_cost_budget(Mock(), Mock(), None) is None

    def test_validate_cost_budget_rejects_negative(self) -> None:
        """validate_cost_budget rejects negative values."""
        with pytest.raises(click.BadParameter, match="cost budget must be non-negative"):
            validate_cost_budget(Mock(), Mock(), -0.01)


class TestDisplayCostStatus:
    """Tests for _display_cost_status function."""

    @patch("review_bot_automator.cli.main.console")
    def test_display_cost_status_no_tracker(self, mock_console: Mock) -> None:
        """_display_cost_status returns early when tracker is None."""
        _display_cost_status(None)
        mock_console.print.assert_not_called()

    @patch("review_bot_automator.cli.main.console")
    def test_display_cost_status_no_budget_set(self, mock_console: Mock) -> None:
        """_display_cost_status returns early when budget is None."""
        tracker = CostTracker(budget=None)
        _display_cost_status(tracker)
        mock_console.print.assert_not_called()

    @patch("review_bot_automator.cli.main.console")
    def test_display_cost_status_ok(self, mock_console: Mock) -> None:
        """_display_cost_status shows OK status when under warning threshold."""
        tracker = CostTracker(budget=1.0, warning_threshold=0.8)
        tracker.add_cost(0.5)  # 50%
        _display_cost_status(tracker)
        call_text = mock_console.print.call_args[0][0]
        assert "green" in call_text and "OK" in call_text

    @patch("review_bot_automator.cli.main.console")
    def test_display_cost_status_warning(self, mock_console: Mock) -> None:
        """_display_cost_status shows WARNING status above threshold."""
        tracker = CostTracker(budget=1.0, warning_threshold=0.8)
        tracker.add_cost(0.85)  # 85%
        _display_cost_status(tracker)
        call_text = mock_console.print.call_args[0][0]
        assert "yellow" in call_text and "WARNING" in call_text

    @patch("review_bot_automator.cli.main.console")
    def test_display_cost_status_exceeded(self, mock_console: Mock) -> None:
        """_display_cost_status shows EXCEEDED status over 100%."""
        tracker = CostTracker(budget=1.0, warning_threshold=0.8)
        tracker.add_cost(1.05)  # 105%
        _display_cost_status(tracker)
        call_text = mock_console.print.call_args[0][0]
        assert "red" in call_text and "EXCEEDED" in call_text


class TestRecordAndDisplayMetrics:
    """Tests for _record_and_display_metrics function."""

    @patch("review_bot_automator.cli.main._display_aggregated_metrics")
    @patch("review_bot_automator.cli.main._export_metrics")
    def test_record_and_display_metrics_no_export(
        self, mock_export: Mock, mock_display: Mock
    ) -> None:
        """_record_and_display_metrics displays without export."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            changes_parsed=5,
            avg_confidence=0.9,
            cache_hit_rate=0.0,
            total_cost=0.05,
            api_calls=2,
            total_tokens=1000,
        )
        _record_and_display_metrics(metrics, "owner", "repo", 123, None, "summary")
        mock_display.assert_called_once()
        mock_export.assert_not_called()

    @patch("review_bot_automator.cli.main._display_aggregated_metrics")
    @patch("review_bot_automator.cli.main._export_metrics")
    def test_record_and_display_metrics_with_export(
        self, mock_export: Mock, mock_display: Mock
    ) -> None:
        """_record_and_display_metrics exports when path provided."""
        metrics = LLMMetrics(
            provider="anthropic",
            model="claude-haiku-4",
            changes_parsed=5,
            avg_confidence=0.9,
            cache_hit_rate=0.0,
            total_cost=0.05,
            api_calls=2,
            total_tokens=1000,
        )
        _record_and_display_metrics(metrics, "owner", "repo", 123, "/path/metrics.json", "full")
        mock_display.assert_called_once()
        mock_export.assert_called_once()


class TestExportMetrics:
    """Tests for _export_metrics function."""

    @patch("review_bot_automator.cli.main.console")
    @patch.object(MetricsAggregator, "export_json")
    def test_export_metrics_oserror(self, mock_export_json: Mock, mock_console: Mock) -> None:
        """_export_metrics handles OSError gracefully."""
        mock_export_json.side_effect = OSError("Permission denied")
        aggregator = MetricsAggregator()
        _export_metrics(aggregator, "/invalid/path/metrics.json", "summary")
        # Check that error message was printed
        error_calls = [c for c in mock_console.print.call_args_list if "Failed" in str(c)]
        assert len(error_calls) > 0


class TestCostBudgetCLI:
    """Tests for --cost-budget CLI integration."""

    @patch("review_bot_automator.cli.main.load_runtime_config")
    @patch("review_bot_automator.cli.main.ConflictResolver")
    def test_cli_analyze_with_cost_budget(
        self, mock_resolver: Mock, mock_load_config: Mock
    ) -> None:
        """analyze forwards --cost-budget to config overrides."""
        config = RuntimeConfig.from_defaults()
        mock_load_config.return_value = (config, None)
        mock_resolver.return_value.analyze_conflicts.return_value = []

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "analyze",
                "--pr",
                "15",
                "--owner",
                "o",
                "--repo",
                "r",
                "--cost-budget",
                "2.50",
            ],
        )

        assert result.exit_code == 0
        overrides = mock_load_config.call_args.kwargs["cli_overrides"]
        assert overrides["llm_cost_budget"] == 2.50

    @patch("review_bot_automator.llm.factory.create_provider")
    @patch("review_bot_automator.cli.main.UniversalLLMParser")
    def test_create_llm_parser_with_cost_budget(
        self, mock_parser: Mock, mock_provider: Mock
    ) -> None:
        """_create_llm_parser creates CostTracker when budget configured."""
        mock_provider.return_value = MagicMock()
        mock_parser.return_value = MagicMock()

        config = RuntimeConfig.from_defaults().merge_with_cli(
            llm_enabled=True,
            llm_provider="anthropic",
            llm_api_key="test-key-123",
            llm_cost_budget=2.50,
        )
        parser, tracker = _create_llm_parser(config)

        assert parser is not None
        assert tracker is not None
        assert tracker.budget == 2.50

    @patch("review_bot_automator.llm.factory.create_provider")
    @patch("review_bot_automator.cli.main.UniversalLLMParser")
    def test_create_llm_parser_without_cost_budget(
        self, mock_parser: Mock, mock_provider: Mock
    ) -> None:
        """_create_llm_parser returns None tracker when no budget."""
        mock_provider.return_value = MagicMock()
        mock_parser.return_value = MagicMock()

        config = RuntimeConfig.from_defaults().merge_with_cli(
            llm_enabled=True,
            llm_provider="anthropic",
            llm_api_key="test-key-123",
            llm_cost_budget=None,
        )
        parser, tracker = _create_llm_parser(config)

        assert parser is not None
        assert tracker is None
