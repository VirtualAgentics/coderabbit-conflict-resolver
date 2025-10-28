"""Unit tests for CLI commands in pr_conflict_resolver.cli.main."""

from typing import Any
from unittest.mock import patch

from click.testing import CliRunner

from pr_conflict_resolver import Change, Conflict, FileType, Resolution, ResolutionResult
from pr_conflict_resolver.cli.main import cli


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
def test_cli_analyze_no_conflicts(mock_resolver: Any) -> None:
    """analyze prints 'No conflicts' when none are found."""
    mock_inst = mock_resolver.return_value
    mock_inst.analyze_conflicts.return_value = []

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--pr", "123", "--owner", "o", "--repo", "r"])

    assert result.exit_code == 0
    assert "No conflicts detected" in result.output


@patch("pr_conflict_resolver.cli.main.ConflictResolver")
def test_cli_analyze_with_conflicts(mock_resolver: Any) -> None:
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
    assert "DRY RUN:" in result.output
    assert "Would apply suggestions to PR #7" in result.output


@patch("pr_conflict_resolver.cli.main.ConflictResolver")
def test_cli_apply_success(mock_resolver: Any) -> None:
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
    assert "Applied 3 suggestions" in result.output
    assert "Skipped 2 conflicts" in result.output
    assert "Success rate: 60.0%" in result.output


@patch("pr_conflict_resolver.cli.main.ConflictResolver")
def test_cli_simulate_mixed_conflicts(mock_resolver: Any) -> None:
    """simulate reports how many would be applied vs skipped."""
    from pr_conflict_resolver.core.models import Change, FileType, Resolution

    mock_inst = mock_resolver.return_value
    # One 'low' (would apply) and one 'high' (would skip)
    mock_inst.analyze_conflicts.return_value = [
        _sample_conflict("a.json", "low"),
        _sample_conflict("b.json", "high"),
    ]

    # Mock resolve_conflicts to return Resolution objects with applied/skipped changes
    change1 = Change("a.json", 1, 2, "change 1", {}, "fp1", FileType.JSON)
    change2 = Change("b.json", 1, 2, "change 2", {}, "fp2", FileType.JSON)
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
def test_cli_analyze_handles_error(mock_resolver: Any) -> None:
    """analyze gracefully handles exceptions and aborts."""
    mock_inst = mock_resolver.return_value
    mock_inst.analyze_conflicts.side_effect = Exception("boom")

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze", "--pr", "10", "--owner", "o", "--repo", "r"])

    assert result.exit_code != 0
    assert "Error analyzing conflicts" in result.output
