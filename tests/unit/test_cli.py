"""Unit tests for CLI commands in pr_conflict_resolver.cli.main."""

from unittest.mock import MagicMock, Mock, patch

from click.testing import CliRunner

from pr_conflict_resolver import Change, Conflict, FileType, Resolution, ResolutionResult
from pr_conflict_resolver.cli.main import _create_llm_parser, cli
from pr_conflict_resolver.config.runtime_config import RuntimeConfig


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


@patch("pr_conflict_resolver.cli.main.ConflictResolver")
def test_cli_analyze_no_conflicts(mock_resolver: Mock) -> None:
    """analyze prints 'No conflicts' when none are found."""
    mock_inst = mock_resolver.return_value
    mock_inst.analyze_conflicts.return_value = []

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--pr", "123", "--owner", "o", "--repo", "r"])

    assert result.exit_code == 0
    assert "No conflicts detected" in result.output


@patch("pr_conflict_resolver.cli.main.ConflictResolver")
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


@patch("pr_conflict_resolver.cli.main.ConflictResolver")
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


@patch("pr_conflict_resolver.cli.main.ConflictResolver")
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


@patch("pr_conflict_resolver.cli.main.ConflictResolver")
def test_cli_analyze_handles_error(mock_resolver: Mock) -> None:
    """analyze gracefully handles exceptions and aborts."""
    mock_inst = mock_resolver.return_value
    mock_inst.analyze_conflicts.side_effect = Exception("boom")

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--pr", "10", "--owner", "o", "--repo", "r"])

    assert result.exit_code != 0
    assert "Error analyzing conflicts" in result.output


@patch("pr_conflict_resolver.cli.main.ConflictResolver")
def test_cli_apply_handles_error(mock_resolver: Mock) -> None:
    """apply gracefully handles exceptions and aborts."""
    mock_inst = mock_resolver.return_value
    mock_inst.resolve_pr_conflicts.side_effect = Exception("Application failed")

    runner = CliRunner()
    result = runner.invoke(cli, ["apply", "--pr", "11", "--owner", "o", "--repo", "r"])

    assert result.exit_code != 0
    assert "Error applying suggestions" in result.output


class TestCreateLLMParser:
    """Test _create_llm_parser helper function."""

    def test_create_llm_parser_disabled(self) -> None:
        """Test _create_llm_parser returns None when LLM is disabled."""
        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(llm_enabled=False)

        parser = _create_llm_parser(config)

        assert parser is None

    @patch("pr_conflict_resolver.llm.factory.create_provider")
    @patch("pr_conflict_resolver.cli.main.ParallelLLMParser")
    def test_create_llm_parser_parallel_enabled(
        self, mock_parallel_parser: Mock, mock_create_provider: Mock
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

        parser = _create_llm_parser(config)

        assert parser is not None
        mock_parallel_parser.assert_called_once()
        call_kwargs = mock_parallel_parser.call_args[1]
        assert call_kwargs["max_workers"] == 8
        assert call_kwargs["rate_limit"] == 20.0

    @patch("pr_conflict_resolver.llm.factory.create_provider")
    @patch("pr_conflict_resolver.cli.main.UniversalLLMParser")
    def test_create_llm_parser_parallel_disabled(
        self, mock_universal_parser: Mock, mock_create_provider: Mock
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

        parser = _create_llm_parser(config)

        assert parser is not None
        mock_universal_parser.assert_called_once()

    @patch("pr_conflict_resolver.llm.factory.create_provider")
    def test_create_llm_parser_provider_error(self, mock_create_provider: Mock) -> None:
        """Test _create_llm_parser returns None when provider creation fails."""
        mock_create_provider.side_effect = RuntimeError("Provider initialization failed")

        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(
            llm_enabled=True,
            llm_provider="claude-cli",  # Use valid provider, but creation will fail
        )

        parser = _create_llm_parser(config)

        assert parser is None

    @patch("pr_conflict_resolver.llm.factory.create_provider")
    @patch("pr_conflict_resolver.cli.main.ParallelLLMParser")
    def test_create_llm_parser_parser_error(
        self, mock_parallel_parser: Mock, mock_create_provider: Mock
    ) -> None:
        """Test _create_llm_parser returns None when parser creation fails."""
        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider
        mock_parallel_parser.side_effect = ValueError("Invalid parser configuration")

        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(
            llm_enabled=True,
            llm_parallel_parsing=True,
        )

        parser = _create_llm_parser(config)

        assert parser is None
