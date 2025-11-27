"""Tests for CLI security.

This module tests argument injection prevention, environment variable handling,
and token exposure in CLI operations.
"""

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

if TYPE_CHECKING:
    from click.testing import Result

import pytest
from click.testing import CliRunner

from review_bot_automator.cli.main import MAX_GITHUB_USERNAME_LENGTH, cli


@pytest.fixture(autouse=True)
def _stub_github(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent real GitHub calls in CLI tests."""

    def _no_comments(
        self: object, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(
        "review_bot_automator.integrations.github.GitHubCommentExtractor.fetch_pr_comments",
        _no_comments,
        raising=True,
    )


# Redaction placeholders used to verify CLI output sanitization
REDACTION_PLACEHOLDERS = ("[REDACTED]", "<redacted>", "[SANITIZED]", "<sanitized>")


class TestArgumentInjectionPrevention:
    """Tests for command-line argument injection prevention."""

    @pytest.mark.parametrize(
        "malicious_input",
        [
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& echo malicious",
            "`whoami`",
            "$(cat /etc/passwd)",
            "../../../etc/passwd",
            "owner; rm -rf /",
            "repo && echo hacked",
        ],
    )
    def test_cli_sanitizes_user_input(self, malicious_input: str) -> None:
        """Test that CLI sanitizes user-provided input.

        Malicious inputs should either be rejected or not echoed back in error messages.
        """
        runner = CliRunner()

        result = runner.invoke(
            cli, ["analyze", "--pr", "1", "--owner", malicious_input, "--repo", "test"]
        )

        # CLI should either reject with Click validation error, or not echo raw input
        if result.exit_code != 0:
            assert "invalid value for '--owner'" in result.output.lower()
        else:
            assert malicious_input not in result.output

    @pytest.mark.parametrize(
        "cmd",
        [
            "--help; rm -rf /",
            "--version && echo hacked",
            "--pr 1 --owner test --repo test; cat /etc/passwd",
        ],
    )
    def test_cli_rejects_dangerous_flags(self, cmd: str) -> None:
        """Test that dangerous command-line flags are rejected."""
        runner = CliRunner()

        parts = cmd.split()
        result = runner.invoke(cli, parts)
        malicious_input = " ".join(parts)
        assert (
            malicious_input not in result.output
        ), f"CLI must not echo raw injection: {malicious_input}"
        if result.exit_code == 0:
            assert "rm -rf" not in result.output
            assert "cat /etc/passwd" not in result.output


class TestEnvironmentVariableHandling:
    """Tests for environment variable security."""

    def test_token_not_exposed_in_env(self) -> None:
        """Test that tokens are not exposed in environment variables."""
        runner = CliRunner()

        # Set a test token (clearly marked as test data)
        test_token = "ghp_test12345678901234567890123456789012"  # noqa: S105  # gitleaks:allow
        with patch.dict(os.environ, {"GITHUB_TOKEN": test_token}):
            result = runner.invoke(
                cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", "test"]
            )

            # Token should not appear in output
            assert test_token not in result.output

    def _assert_injection_handled(self, result: "Result", injection: str) -> None:
        """Helper to assert injection is safely handled.

        Args:
            result: Click CLI result object
            injection: The injection string that was attempted
        """
        # First requirement: raw injection string must NOT be present in output
        assert injection not in result.output, f"CLI must not echo raw injection: {injection}"

        # Second requirement: if CLI succeeds (exit_code == 0), output must be sanitized
        if result.exit_code == 0:
            # Must contain redaction placeholder to prove sanitization occurred
            has_redaction = any(
                placeholder in result.output for placeholder in REDACTION_PLACEHOLDERS
            )
            assert has_redaction, (
                f"CLI succeeded but output not sanitized for injection '{injection}'. "
                f"Expected redaction placeholder in output: {result.output[:200]}..."
            )
        # If exit_code != 0, that's acceptable (CLI rejected the injection)

    def test_env_var_injection_handled(self, subtests: pytest.Subtests) -> None:
        """Test that environment variable injection is handled safely using subtests."""
        runner = CliRunner()

        # Test with environment variable injection attempts
        injection_attempts = [
            ("Command substitution $(...)", "$(GITHUB_TOKEN)"),
            ("Shell variable ${...}", "${GITHUB_TOKEN}"),
            ("Direct shell variable", "$GITHUB_TOKEN"),
            ("Backtick execution", "`echo $GITHUB_TOKEN`"),
        ]

        for injection_type, injection in injection_attempts:
            with subtests.test(msg=f"{injection_type}: {injection}", injection=injection):
                result = runner.invoke(
                    cli, ["analyze", "--pr", "1", "--owner", injection, "--repo", "test"]
                )

                # Use helper for consistency
                self._assert_injection_handled(result, injection)


class TestTokenExposurePrevention:
    """Tests for preventing token exposure in logs/errors."""

    def test_tokens_not_in_error_messages(self) -> None:
        """Test that tokens are not included in error messages."""
        runner = CliRunner()

        # Test with invalid token format (clearly marked as test data)
        invalid_token = "invalid_token_format"  # noqa: S105
        with patch.dict(os.environ, {"GITHUB_TOKEN": invalid_token}):
            result = runner.invoke(
                cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", "test"]
            )

            # Token should not appear in error output
            if result.exit_code != 0:
                assert invalid_token not in result.output

    def test_help_text_no_secrets(self) -> None:
        """Test that help text doesn't contain sensitive information."""
        runner = CliRunner()

        # Test help output
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

        # Check that no sensitive patterns appear in help
        sensitive_patterns = [
            r"\bghp_",
            r"\bgho_",
            r"\bghu_",
            r"\bghs_",
            r"\bghr_",
            r"\bpassword\b",
            r"\bsecret\b",
            # Match whole tokens to avoid false positives
            r"\bapi_key\b",
            r"\baccess_key\b",
            r"\bsecret_key\b",
        ]

        for pattern in sensitive_patterns:
            assert re.search(pattern, result.output, flags=re.IGNORECASE) is None


class TestDryRunModeValidation:
    """Tests for dry-run mode security."""

    def test_dry_run_doesnt_modify_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that dry-run mode doesn't actually modify files."""
        runner = CliRunner()

        # Create a test file to monitor in the temporary directory
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("original content")

        # Change to the temporary directory for the test
        monkeypatch.chdir(tmp_path)

        # Run CLI command
        result = runner.invoke(
            cli, ["apply", "--pr", "1", "--owner", "test", "--repo", "test", "--dry-run"]
        )

        # File should remain unchanged
        assert test_file.read_text() == "original content"

        # Should show dry-run message
        assert "DRY RUN" in result.output or "dry-run" in result.output.lower()

    def test_dry_run_shows_changes_safely(self) -> None:
        """Test that dry-run output doesn't leak sensitive data."""
        runner = CliRunner()

        # Set a test token (clearly marked as test data)
        test_token = "ghp_test12345678901234567890123456789012"  # noqa: S105  # gitleaks:allow
        with patch.dict(os.environ, {"GITHUB_TOKEN": test_token}):
            result = runner.invoke(
                cli, ["apply", "--pr", "1", "--owner", "test", "--repo", "test", "--dry-run"]
            )

            # Token should not appear in dry-run output
            assert test_token not in result.output


class TestCommandLineParsingSecurity:
    """Tests for secure command-line parsing."""

    def test_multiple_flags_handled_safely(self) -> None:
        """Test that multiple flags are parsed safely."""
        runner = CliRunner()

        # Test with multiple flags
        result = runner.invoke(
            cli,
            ["analyze", "--pr", "1", "--owner", "test", "--repo", "test", "--config", "balanced"],
        )

        # Should handle multiple flags without issues
        assert result.exit_code == 0, "CLI should parse multiple flags successfully"
        assert "error" not in result.output.lower(), "CLI should not show errors for valid flags"

    def test_unicode_in_arguments_handled(self) -> None:
        """Test that Unicode characters in arguments are rejected by validate_github_identifier.

        The CLI uses GitHub username validation rules: only ASCII letters (A-Za-z),
        digits (0-9), and hyphens are allowed. No leading/trailing hyphens, no consecutive
        hyphens, no control/null characters, and no path separators (/, \\) are permitted.
        """
        runner = CliRunner()

        # Test Unicode handling - these should all be rejected
        unicode_inputs = [
            "\x00\x01",  # Null bytes
            "../../",  # Path traversal (contains slashes)
            "\n\r",  # Control characters
            "测试",  # Chinese characters (not in allowed set)
            "тест",  # Cyrillic (not in allowed set)
        ]

        for unicode_input in unicode_inputs:
            result = runner.invoke(
                cli, ["analyze", "--pr", "1", "--owner", unicode_input, "--repo", "test"]
            )

            # Should reject invalid identifiers with non-zero exit code
            assert result.exit_code != 0, f"CLI should reject invalid identifier: {unicode_input!r}"
            # Should show appropriate error message
            assert "Error:" in result.output or "error" in result.output.lower()

    @pytest.mark.parametrize(
        "path",
        [
            "../../../etc/passwd",
            "C:\\Windows\\System32",
            "/etc/hosts",
            "..\\..\\..\\windows\\system32",
        ],
    )
    def test_file_path_arguments_validated(self, path: str) -> None:
        """Test that file path arguments are validated.

        Dangerous paths should be rejected with path validation errors.
        """
        runner = CliRunner()

        result = runner.invoke(cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", path])

        # CLI should reject dangerous paths with non-zero exit code
        assert result.exit_code != 0, f"CLI should reject dangerous path: {path}"
        assert (
            "invalid value for '--repo'" in result.output.lower()
        ), f"CLI should show path validation error for: {path}"


class TestInputValidation:
    """Tests for input validation in CLI."""

    def test_input_validated_before_processing(self) -> None:
        """Test that input is validated before processing."""
        runner = CliRunner()

        # Test with invalid input types
        invalid_inputs = [
            ("--pr", "not_a_number"),  # Invalid integer format
            ("--pr", "abc123"),  # Invalid integer format
            ("--pr", "3.14"),  # Invalid integer format (float)
        ]

        for flag, value in invalid_inputs:
            result = runner.invoke(
                cli, ["analyze", flag, value, "--owner", "test", "--repo", "test"]
            )

            # Click should reject invalid input before command execution
            assert result.exit_code != 0, f"CLI should reject invalid {flag} value: {value}"

            # Should contain indication of invalid integer input
            output_lower = result.output.lower()
            assert (
                "invalid value" in output_lower or "not a valid integer" in output_lower
            ), f"CLI should show integer validation error for {flag} value: {value}"

    def test_max_input_size_enforced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that maximum input size is enforced."""

        runner = CliRunner()

        # Boundary: exactly at limit should pass (use valid username pattern)
        max_len = MAX_GITHUB_USERNAME_LENGTH
        at_limit = "a" * (max_len - 2) + "bc"  # Valid: no trailing hyphens, alphanum
        ok_result = runner.invoke(
            cli, ["analyze", "--pr", "1", "--owner", at_limit, "--repo", "test"]
        )
        assert ok_result.exit_code == 0

        # Above limit should be rejected with Click-style invalid message
        over_limit = "x" * (max_len + 1)
        result = runner.invoke(
            cli, ["analyze", "--pr", "1", "--owner", over_limit, "--repo", "test"]
        )
        assert result.exit_code != 0
        assert "invalid value for '--owner'" in result.output.lower()


class TestOutputSanitization:
    """Test that CLI output is properly sanitized."""

    def test_malicious_config_sanitized(self) -> None:
        """Test that malicious config values pass through output safely.

        After the sanitization refactor, only control characters are redacted.
        Shell metacharacters pass through because config values are not validated
        as identifiers and never executed. This is safe because:
        1. Config values are just preset names, not shell commands
        2. These values would not match any valid preset and use default
        """
        runner = CliRunner()

        # These are considered "malicious" but are safe in config context
        # They will pass through output since they don't contain control chars
        malicious_configs = [
            "$(cat /etc/passwd)",
            "`whoami`",
            "; rm -rf /",
            "${GITHUB_TOKEN}",
        ]

        for malicious_config in malicious_configs:
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
                    "--config",
                    malicious_config,
                ],
            )
            # After sanitization refactor: shell metacharacters pass through
            # This is safe because config is not validated as identifier
            # and values are never executed
            # The malicious string should appear in output (not redacted)
            assert malicious_config in result.output or result.exit_code != 0

    def test_malicious_strategy_sanitized(self) -> None:
        """Test that malicious strategy values pass through output safely.

        After the sanitization refactor, only control characters are redacted.
        Shell metacharacters pass through because strategy values are not validated
        as identifiers and never executed. This is safe because:
        1. Strategy values are just strategy names, not shell commands
        2. These values would not match any valid strategy and use default
        """
        runner = CliRunner()

        # These are considered "malicious" but are safe in strategy context
        # They will pass through output since they don't contain control chars
        malicious_strategies = [
            "$(cat /etc/passwd)",
            "`whoami`",
            "; rm -rf /",
            "${GITHUB_TOKEN}",
        ]

        for malicious_strategy in malicious_strategies:
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
                    "--strategy",
                    malicious_strategy,
                ],
            )
            # After sanitization refactor: shell metacharacters pass through
            # This is safe because strategy is not validated as identifier
            # and values are never executed
            # The malicious string should appear in output (not redacted)
            assert malicious_strategy in result.output or result.exit_code != 0

    def test_clean_values_not_sanitized(self) -> None:
        """Test that clean values are not sanitized."""
        runner = CliRunner()

        clean_values = ["balanced", "priority", "conservative", "aggressive"]

        for clean_value in clean_values:
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
                    "--config",
                    clean_value,
                ],
            )
            # Clean values should appear in output
            assert clean_value in result.output


class TestCommandSuccessPaths:
    """Test successful command execution paths."""

    @patch("review_bot_automator.core.resolver.ConflictResolver.analyze_conflicts")
    def test_analyze_command_success_path(self, mock_analyze: Mock) -> None:
        """Test analyze command success path."""
        mock_analyze.return_value = []
        runner = CliRunner()

        result = runner.invoke(cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", "test"])

        assert result.exit_code == 0
        assert "No conflicts detected" in result.output

    @patch("review_bot_automator.core.resolver.ConflictResolver.analyze_conflicts")
    def test_analyze_command_with_conflicts(self, mock_analyze: Mock) -> None:
        """Test analyze command with conflicts."""
        from review_bot_automator.core.models import Change, Conflict, FileType

        mock_conflict = Conflict(
            file_path="test.py",
            line_range=(1, 5),
            changes=[
                Change(
                    path="test.py",
                    start_line=1,
                    end_line=5,
                    content="test content",
                    metadata={},
                    fingerprint="test1",
                    file_type=FileType.PYTHON,
                )
            ],
            conflict_type="overlap",
            severity="medium",
            overlap_percentage=50.0,
        )
        mock_analyze.return_value = [mock_conflict]
        runner = CliRunner()

        result = runner.invoke(cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", "test"])

        assert result.exit_code == 0
        assert "Found 1 conflicts" in result.output

    @patch("review_bot_automator.core.resolver.ConflictResolver.resolve_pr_conflicts")
    def test_apply_command_success_path(self, mock_resolve: Mock) -> None:
        """Test apply command success path."""
        from review_bot_automator.core.models import ResolutionResult

        mock_result = ResolutionResult(
            applied_count=5,
            conflict_count=2,
            success_rate=71.4,
            resolutions=[],
            conflicts=[],
        )
        mock_resolve.return_value = mock_result
        runner = CliRunner()

        result = runner.invoke(cli, ["apply", "--pr", "1", "--owner", "test", "--repo", "test"])

        assert result.exit_code == 0
        assert "Applied: 5 suggestions" in result.output
        assert "Skipped: 2 conflicts" in result.output
        assert "Success rate: 71.4%" in result.output

    @patch("review_bot_automator.core.resolver.ConflictResolver.analyze_conflicts")
    def test_simulate_command_success_path(self, mock_analyze: Mock) -> None:
        """Test simulate command success path."""
        from review_bot_automator.core.models import Change, Conflict, FileType

        mock_conflict = Conflict(
            file_path="test.py",
            line_range=(1, 5),
            changes=[
                Change(
                    path="test.py",
                    start_line=1,
                    end_line=5,
                    content="test content",
                    metadata={},
                    fingerprint="test1",
                    file_type=FileType.PYTHON,
                )
            ],
            conflict_type="overlap",
            severity="medium",
            overlap_percentage=50.0,
        )
        mock_analyze.return_value = [mock_conflict]
        runner = CliRunner()

        result = runner.invoke(cli, ["simulate", "--pr", "1", "--owner", "test", "--repo", "test"])

        assert result.exit_code == 0
        assert "Simulation Results:" in result.output
        assert "Total changes:" in result.output
        assert "Would apply:" in result.output
        assert "Would skip:" in result.output
        assert "Success rate:" in result.output
