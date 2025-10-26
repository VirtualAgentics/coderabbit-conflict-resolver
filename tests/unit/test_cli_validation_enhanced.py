"""Enhanced unit tests for CLI validation functions.

This module provides comprehensive tests for the CLI validation functions
including validate_github_identifier, sanitize_for_output, and validate_path_option.
"""

from unittest.mock import Mock

import pytest
from click import BadParameter, Context
from click.testing import CliRunner

from pr_conflict_resolver.cli.main import (
    MAX_CLI_NAME_LENGTH,
    cli,
    sanitize_for_output,
    validate_github_identifier,
    validate_path_option,
)


class TestValidateGitHubIdentifier:
    """Test GitHub identifier validation function."""

    def test_empty_string_raises_error(self) -> None:
        """Test that empty string raises 'identifier required' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="identifier required"):
            validate_github_identifier(ctx, param, "")

    def test_whitespace_only_raises_error(self) -> None:
        """Test that whitespace-only string raises 'identifier required' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="identifier required"):
            validate_github_identifier(ctx, param, "   ")

    def test_none_input_raises_error(self) -> None:
        """Test that None input raises 'identifier required' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        # Test with None input to verify handling of non-string sentinel values
        with pytest.raises(BadParameter, match="identifier required"):
            validate_github_identifier(ctx, param, None)  # type: ignore[arg-type]

    def test_too_long_raises_error(self) -> None:
        """Test that identifier exceeding max length raises error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"
        long_identifier = "a" * (MAX_CLI_NAME_LENGTH + 1)

        with pytest.raises(
            BadParameter, match=f"identifier too long \\(max {MAX_CLI_NAME_LENGTH}\\)"
        ):
            validate_github_identifier(ctx, param, long_identifier)

    def test_slash_raises_error(self) -> None:
        """Test that slash in identifier raises 'single segment' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="identifier must be a single segment"):
            validate_github_identifier(ctx, param, "org/repo")

    def test_backslash_raises_error(self) -> None:
        """Test that backslash in identifier raises 'single segment' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="identifier must be a single segment"):
            validate_github_identifier(ctx, param, "org\\repo")

    def test_whitespace_raises_error(self) -> None:
        """Test that whitespace in identifier raises 'single segment' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="identifier must be a single segment"):
            validate_github_identifier(ctx, param, "org repo")

    def test_tab_raises_error(self) -> None:
        """Test that tab in identifier raises 'single segment' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="identifier must be a single segment"):
            validate_github_identifier(ctx, param, "org\trepo")

    def test_invalid_characters_raises_error(self) -> None:
        """Test that invalid characters raise 'invalid characters' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="identifier contains invalid characters"):
            validate_github_identifier(ctx, param, "org@repo")

    def test_special_chars_raises_error(self) -> None:
        """Test that special characters raise 'invalid characters' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="identifier contains invalid characters"):
            validate_github_identifier(ctx, param, "org#repo")

    def test_valid_identifiers_pass(self) -> None:
        """Test that valid identifiers pass validation."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        valid_identifiers = [
            "myrepo",
            "my-repo",
            "my_repo",
            "my.repo",
            "repo123",
            "123repo",
            "a",
            "A",
            "test-repo_123",
        ]

        for identifier in valid_identifiers:
            result = validate_github_identifier(ctx, param, identifier)
            assert result == identifier

    def test_max_length_boundary(self) -> None:
        """Test that identifier at max length passes."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"
        max_length_identifier = "a" * MAX_CLI_NAME_LENGTH

        result = validate_github_identifier(ctx, param, max_length_identifier)
        assert result == max_length_identifier


class TestSanitizeForOutput:
    """Test output sanitization function."""

    def test_shell_metacharacters_redacted(self) -> None:
        """Test that shell metacharacters trigger redaction."""
        dangerous_inputs = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& echo malicious",
            "`whoami`",
            "$(cat /etc/passwd)",
            "command; rm -rf /",
        ]

        for dangerous in dangerous_inputs:
            result = sanitize_for_output(dangerous)
            assert result == "[REDACTED]"

    def test_environment_variables_redacted(self) -> None:
        """Test that environment variable patterns trigger redaction."""
        dangerous_inputs = [
            "$GITHUB_TOKEN",
            "${GITHUB_TOKEN}",
            "$(GITHUB_TOKEN)",
            "token=$SECRET",
            "value=${API_KEY}",
        ]

        for dangerous in dangerous_inputs:
            result = sanitize_for_output(dangerous)
            assert result == "[REDACTED]"

    def test_control_characters_redacted(self) -> None:
        """Test that control characters trigger redaction."""
        dangerous_inputs = [
            "text\nwith\nnewlines",
            "text\rwith\rreturns",
            "text\x00with\x00nulls",
        ]

        for dangerous in dangerous_inputs:
            result = sanitize_for_output(dangerous)
            assert result == "[REDACTED]"

    def test_shell_quotes_redacted(self) -> None:
        """Test that shell quotes trigger redaction."""
        dangerous_inputs = [
            'text"with"quotes',
            "text'with'quotes",
            "text\"with'mixed'quotes",
        ]

        for dangerous in dangerous_inputs:
            result = sanitize_for_output(dangerous)
            assert result == "[REDACTED]"

    def test_shell_brackets_redacted(self) -> None:
        """Test that shell brackets trigger redaction."""
        dangerous_inputs = [
            "text[with]brackets",
            "text{with}braces",
            "text(with)parens",
        ]

        for dangerous in dangerous_inputs:
            result = sanitize_for_output(dangerous)
            assert result == "[REDACTED]"

    def test_clean_strings_pass_through(self) -> None:
        """Test that clean strings pass through unchanged."""
        clean_inputs = [
            "myrepo",
            "my-repo",
            "my_repo",
            "my.repo",
            "repo123",
            "balanced",
            "priority",
            "conservative",
            "aggressive",
        ]

        for clean in clean_inputs:
            result = sanitize_for_output(clean)
            assert result == clean

    def test_empty_string_passes_through(self) -> None:
        """Test that empty string passes through."""
        result = sanitize_for_output("")
        assert result == ""

    def test_whitespace_only_passes_through(self) -> None:
        """Test that whitespace-only string passes through."""
        result = sanitize_for_output("   ")
        assert result == "   "


class TestValidatePathOption:
    """Test path option validation function."""

    def test_path_too_long_raises_error(self) -> None:
        """Test that path exceeding max length raises error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"
        long_path = "a" * (MAX_CLI_NAME_LENGTH + 1)

        with pytest.raises(
            BadParameter, match=f"test: value too long \\(max {MAX_CLI_NAME_LENGTH}\\)"
        ):
            validate_path_option(ctx, param, long_path)

    def test_invalid_path_raises_error(self) -> None:
        """Test that invalid path raises error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="test: invalid path"):
            validate_path_option(ctx, param, "../../../etc/passwd")


class TestCLIIntegration:
    """Test CLI integration with validation functions."""

    def test_analyze_command_with_invalid_owner(self) -> None:
        """Test analyze command with invalid owner identifier."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["analyze", "--pr", "1", "--owner", "org/repo", "--repo", "test"]
        )
        assert result.exit_code != 0
        assert "identifier must be a single segment" in result.output

    def test_analyze_command_with_invalid_repo(self) -> None:
        """Test analyze command with invalid repo identifier."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", "org repo"]
        )
        assert result.exit_code != 0
        assert "identifier must be a single segment" in result.output

    def test_apply_command_with_invalid_owner(self) -> None:
        """Test apply command with invalid owner identifier."""
        runner = CliRunner()

        result = runner.invoke(cli, ["apply", "--pr", "1", "--owner", "org@repo", "--repo", "test"])
        assert result.exit_code != 0
        assert "identifier contains invalid characters" in result.output

    def test_simulate_command_with_invalid_repo(self) -> None:
        """Test simulate command with invalid repo identifier."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["simulate", "--pr", "1", "--owner", "test", "--repo", "org\\repo"]
        )
        assert result.exit_code != 0
        assert "identifier must be a single segment" in result.output

    def test_commands_with_valid_identifiers(self) -> None:
        """Test that commands accept valid identifiers."""
        runner = CliRunner()

        # These should fail for other reasons (no actual PR) but not validation
        commands = [
            ["analyze", "--pr", "1", "--owner", "myrepo", "--repo", "test"],
            ["apply", "--pr", "1", "--owner", "my-repo", "--repo", "test"],
            ["simulate", "--pr", "1", "--owner", "my_repo", "--repo", "test"],
        ]

        for cmd in commands:
            result = runner.invoke(cli, cmd)
            # Should not fail due to validation errors - ensure both terms are absent
            output_lower = result.output.lower()
            assert "identifier" not in output_lower and "invalid" not in output_lower
