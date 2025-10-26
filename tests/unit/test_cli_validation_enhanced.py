"""Enhanced unit tests for CLI validation functions.

This module provides comprehensive tests for the CLI validation functions
including validate_github_username and sanitize_for_output.
"""

from unittest.mock import Mock

import pytest
from click import BadParameter, Context
from click.testing import CliRunner

from pr_conflict_resolver.cli.main import (
    cli,
    sanitize_for_output,
    validate_github_username,
)


class TestValidateGitHubUsername:
    """Test GitHub username validation function."""

    def test_empty_string_raises_error(self) -> None:
        """Test that empty string raises 'username required' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username required"):
            validate_github_username(ctx, param, "")

    def test_whitespace_only_raises_error(self) -> None:
        """Test that whitespace-only string raises 'username required' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username required"):
            validate_github_username(ctx, param, "   ")

    def test_none_input_raises_error(self) -> None:
        """Test that None input raises 'username required' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        # Test with None input to verify handling of non-string sentinel values
        with pytest.raises(BadParameter, match="username required"):
            validate_github_username(ctx, param, None)  # type: ignore[arg-type]

    def test_too_long_raises_error(self) -> None:
        """Test that username exceeding max length raises error."""
        from pr_conflict_resolver.cli.main import MAX_GITHUB_USERNAME_LENGTH

        ctx = Context(cli)
        param = Mock()
        param.name = "test"
        long_username = "a" * (MAX_GITHUB_USERNAME_LENGTH + 1)

        with pytest.raises(
            BadParameter, match=f"username too long \\(max {MAX_GITHUB_USERNAME_LENGTH}\\)"
        ):
            validate_github_username(ctx, param, long_username)

    def test_slash_raises_error(self) -> None:
        """Test that slash in username raises 'single segment' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username must be a single segment"):
            validate_github_username(ctx, param, "org/repo")

    def test_backslash_raises_error(self) -> None:
        """Test that backslash in username raises 'single segment' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username must be a single segment"):
            validate_github_username(ctx, param, "org\\repo")

    def test_whitespace_raises_error(self) -> None:
        """Test that whitespace in username raises 'single segment' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username must be a single segment"):
            validate_github_username(ctx, param, "org repo")

    def test_tab_raises_error(self) -> None:
        """Test that tab in username raises 'single segment' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username must be a single segment"):
            validate_github_username(ctx, param, "org\trepo")

    def test_invalid_characters_raises_error(self) -> None:
        """Test that invalid characters raise 'invalid characters' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username contains invalid characters"):
            validate_github_username(ctx, param, "org@repo")

    def test_special_chars_raises_error(self) -> None:
        """Test that special characters raise 'invalid characters' error."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username contains invalid characters"):
            validate_github_username(ctx, param, "org#repo")

    def test_valid_username_pass(self) -> None:
        """Test that valid usernames pass validation."""

        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        # GitHub usernames: A-Za-z0-9 and hyphen only, no leading/trailing hyphen
        valid_usernames = [
            "myrepo",
            "my-repo",
            "repo123",
            "a",
            "A",
            "test-repo-123",
        ]

        for username in valid_usernames:
            result = validate_github_username(ctx, param, username)
            assert result == username

    def test_leading_hyphen_rejected(self) -> None:
        """Test that username starting with hyphen is rejected."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username contains invalid characters"):
            validate_github_username(ctx, param, "-invalid")

    def test_trailing_hyphen_rejected(self) -> None:
        """Test that username ending with hyphen is rejected."""
        ctx = Context(cli)
        param = Mock()
        param.name = "test"

        with pytest.raises(BadParameter, match="username contains invalid characters"):
            validate_github_username(ctx, param, "invalid-")

    def test_max_length_boundary(self) -> None:
        """Test that username at max length passes."""
        from pr_conflict_resolver.cli.main import MAX_GITHUB_USERNAME_LENGTH

        ctx = Context(cli)
        param = Mock()
        param.name = "test"
        max_length_username = "a" * MAX_GITHUB_USERNAME_LENGTH

        result = validate_github_username(ctx, param, max_length_username)
        assert result == max_length_username


class TestSanitizeForOutput:
    """Test output sanitization function."""

    def test_shell_metacharacters_pass_through(self) -> None:
        """Test that shell metacharacters pass through after validation."""
        # These would be rejected by validate_github_username, but if they somehow
        # got through, they should pass sanitization since they're not control chars
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
            assert result == dangerous  # Should pass through now

    def test_environment_variables_pass_through(self) -> None:
        """Test that environment variable patterns pass through after validation."""
        # These would be rejected by validate_github_username, but if they somehow
        # got through, they should pass sanitization since they're not control chars
        dangerous_inputs = [
            "$GITHUB_TOKEN",
            "${GITHUB_TOKEN}",
            "$(GITHUB_TOKEN)",
            "token=$SECRET",
            "value=${API_KEY}",
        ]

        for dangerous in dangerous_inputs:
            result = sanitize_for_output(dangerous)
            assert result == dangerous  # Should pass through now

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

    def test_shell_quotes_pass_through(self) -> None:
        """Test that shell quotes pass through after validation."""
        # These would be rejected by validate_github_username, but if they somehow
        # got through, they should pass sanitization since they're not control chars
        dangerous_inputs = [
            'text"with"quotes',
            "text'with'quotes",
            "text\"with'mixed'quotes",
        ]

        for dangerous in dangerous_inputs:
            result = sanitize_for_output(dangerous)
            assert result == dangerous  # Should pass through now

    def test_shell_brackets_pass_through(self) -> None:
        """Test that shell brackets pass through after validation."""
        # These would be rejected by validate_github_username, but if they somehow
        # got through, they should pass sanitization since they're not control chars
        dangerous_inputs = [
            "text[with]brackets",
            "text{with}braces",
            "text(with)parens",
        ]

        for dangerous in dangerous_inputs:
            result = sanitize_for_output(dangerous)
            assert result == dangerous  # Should pass through now

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
            # Should not fail due to validation errors - check for specific identifier errors
            output_lower = result.output.lower()
            # Check for specific identifier validation error messages
            identifier_errors = [
                "identifier required",
                "identifier too long",
                "identifier must be a single segment",
                "identifier contains invalid characters",
            ]
            for error_msg in identifier_errors:
                assert (
                    error_msg not in output_lower
                ), f"Command should not fail with identifier validation error: {error_msg}"
