"""Enhanced unit tests for CLI validation functions.

This module provides comprehensive tests for CLI validation:
validate_github_username, validate_github_repo, validate_pr_number, and sanitize_for_output.
"""

import hashlib
import logging
from unittest.mock import Mock

import pytest
from click import BadParameter, Context
from click.testing import CliRunner

from review_bot_automator.cli.main import (
    MAX_GITHUB_REPO_LENGTH,
    MAX_GITHUB_USERNAME_LENGTH,
    cli,
    sanitize_for_output,
    validate_github_repo,
    validate_github_username,
    validate_pr_number,
)


class TestValidateGitHubUsername:
    """Test GitHub username validation function."""

    def test_empty_string_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that empty string raises 'username required' error."""
        with pytest.raises(BadParameter, match="username required"):
            validate_github_username(mock_ctx, mock_param, "")

    def test_whitespace_only_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that whitespace-only string raises 'username required' error."""
        with pytest.raises(BadParameter, match="username required"):
            validate_github_username(mock_ctx, mock_param, "   ")

    def test_none_input_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that None input raises 'username required' error."""
        # Test with None input to verify handling of non-string sentinel values
        with pytest.raises(BadParameter, match="username required"):
            validate_github_username(mock_ctx, mock_param, None)  # type: ignore[arg-type]

    def test_too_long_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that username exceeding max length raises error."""
        long_username = "a" * (MAX_GITHUB_USERNAME_LENGTH + 1)

        with pytest.raises(
            BadParameter, match=f"username too long \\(max {MAX_GITHUB_USERNAME_LENGTH}\\)"
        ):
            validate_github_username(mock_ctx, mock_param, long_username)

    def test_slash_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that slash in username raises 'single segment' error."""
        with pytest.raises(BadParameter, match="username must be a single segment"):
            validate_github_username(mock_ctx, mock_param, "org/repo")

    def test_backslash_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that backslash in username raises 'single segment' error."""
        with pytest.raises(BadParameter, match="username must be a single segment"):
            validate_github_username(mock_ctx, mock_param, "org\\repo")

    def test_whitespace_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that whitespace in username raises 'single segment' error."""
        with pytest.raises(BadParameter, match="username must be a single segment"):
            validate_github_username(mock_ctx, mock_param, "org repo")

    def test_tab_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that tab in username raises 'single segment' error."""
        with pytest.raises(BadParameter, match="username must be a single segment"):
            validate_github_username(mock_ctx, mock_param, "org\trepo")

    def test_invalid_characters_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that invalid characters raise 'invalid characters' error."""
        with pytest.raises(BadParameter, match="username contains invalid characters"):
            validate_github_username(mock_ctx, mock_param, "org@repo")

    def test_special_chars_raises_error(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that special characters raise 'invalid characters' error."""
        with pytest.raises(BadParameter, match="username contains invalid characters"):
            validate_github_username(mock_ctx, mock_param, "org#repo")

    @pytest.mark.parametrize(
        "username",
        [
            "myrepo",
            "my-repo",
            "repo123",
            "a",
            "A",
            "test-repo-123",
        ],
    )
    def test_valid_username_pass(self, mock_ctx: Context, mock_param: Mock, username: str) -> None:
        """Test that valid usernames pass validation."""
        result = validate_github_username(mock_ctx, mock_param, username)
        assert result == username

    def test_leading_hyphen_rejected(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that username starting with hyphen is rejected."""
        with pytest.raises(BadParameter, match="username contains invalid characters"):
            validate_github_username(mock_ctx, mock_param, "-invalid")

    def test_trailing_hyphen_rejected(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that username ending with hyphen is rejected."""
        with pytest.raises(BadParameter, match="username contains invalid characters"):
            validate_github_username(mock_ctx, mock_param, "invalid-")

    def test_consecutive_hyphens_rejected(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that username with consecutive hyphens is rejected."""
        with pytest.raises(BadParameter, match="username contains invalid characters"):
            validate_github_username(mock_ctx, mock_param, "my--repo")

    def test_max_length_boundary(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Test that username at max length passes."""
        max_length_username = "a" * MAX_GITHUB_USERNAME_LENGTH

        result = validate_github_username(mock_ctx, mock_param, max_length_username)
        assert result == max_length_username


class TestValidateGitHubRepo:
    """Unit tests for validate_github_repo with explicit cases and messages."""

    def test_repo_empty_string_raises(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Empty value should raise 'repository name required'."""
        with pytest.raises(BadParameter, match="repository name required"):
            validate_github_repo(mock_ctx, mock_param, "")

    def test_repo_none_raises(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Non-string (None) should raise 'repository name required'."""
        with pytest.raises(BadParameter, match="repository name required"):
            validate_github_repo(mock_ctx, mock_param, None)  # type: ignore[arg-type]

    def test_repo_too_long_raises(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Names exceeding max length should raise error."""
        with pytest.raises(BadParameter, match="repository name too long"):
            validate_github_repo(mock_ctx, mock_param, "a" * (MAX_GITHUB_REPO_LENGTH + 1))

    def test_repo_multi_segment_raises(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Names with slashes should raise single-segment error."""
        with pytest.raises(BadParameter, match="identifier must be a single segment"):
            validate_github_repo(mock_ctx, mock_param, "a/b")

    def test_repo_backslash_raises(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Backslash should raise single-segment error."""
        with pytest.raises(BadParameter, match="identifier must be a single segment"):
            validate_github_repo(mock_ctx, mock_param, "a\\b")

    def test_repo_whitespace_raises(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Whitespace should raise single-segment error."""
        with pytest.raises(BadParameter, match="identifier must be a single segment"):
            validate_github_repo(mock_ctx, mock_param, "a b")

    def test_repo_invalid_characters_raises(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Names with invalid characters should be rejected."""
        with pytest.raises(BadParameter, match="repository name contains invalid characters"):
            validate_github_repo(mock_ctx, mock_param, "bad@name")

    def test_repo_reserved_dot_names_raises(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Reserved names '.' and '..' should be rejected with explicit message."""
        with pytest.raises(BadParameter, match=r"repository name cannot be '\.' or '\.\.'"):
            validate_github_repo(mock_ctx, mock_param, ".")

    def test_repo_git_suffix_raises(self, mock_ctx: Context, mock_param: Mock) -> None:
        """Names ending with .git should be rejected with explicit message."""
        with pytest.raises(BadParameter, match=r"repository name cannot end with '\.git'"):
            validate_github_repo(mock_ctx, mock_param, "name.git")

    @pytest.mark.parametrize("name", ["repo", "my-repo", "repo_1", "repo.1", "Repo", "REPO-1"])
    def test_valid_repo_names_pass(self, mock_ctx: Context, mock_param: Mock, name: str) -> None:
        """Known-valid repository names should pass validation."""
        assert validate_github_repo(mock_ctx, mock_param, name) == name


class TestValidatePrNumber:
    """Unit tests for validate_pr_number, including negative cases."""

    @pytest.mark.parametrize("n", [0, -1, -5])
    def test_pr_rejects_non_positive(self, mock_ctx: Context, mock_param: Mock, n: int) -> None:
        """Zero or negative numbers should raise a positive-number error."""
        with pytest.raises(BadParameter, match="PR number must be positive"):
            validate_pr_number(mock_ctx, mock_param, n)

    @pytest.mark.parametrize("n", [1, 2, 10])
    def test_pr_accepts_positive(self, mock_ctx: Context, mock_param: Mock, n: int) -> None:
        """Positive numbers should pass validation and be returned unchanged."""
        assert validate_pr_number(mock_ctx, mock_param, n) == n


class TestSanitizeForOutput:
    """Test output sanitization function."""

    @pytest.mark.parametrize(
        "dangerous",
        [
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& echo malicious",
            "`whoami`",
            "$(cat /etc/passwd)",
            "command; rm -rf /",
        ],
    )
    def test_shell_metacharacters_pass_through(self, dangerous: str) -> None:
        """Test that shell metacharacters pass through after validation."""
        result = sanitize_for_output(dangerous)
        assert result == dangerous

    @pytest.mark.parametrize(
        "dangerous",
        [
            "$GITHUB_TOKEN",
            "${GITHUB_TOKEN}",
            "$(GITHUB_TOKEN)",
            "token=$SECRET",
            "value=${API_KEY}",
        ],
    )
    def test_environment_variables_pass_through(self, dangerous: str) -> None:
        """Test that environment variable patterns pass through after validation."""
        result = sanitize_for_output(dangerous)
        assert result == dangerous

    @pytest.mark.parametrize(
        "dangerous",
        [
            "text\nwith\nnewlines",
            "text\rwith\rreturns",
            "text\x00with\x00nulls",
        ],
    )
    def test_control_characters_redacted(self, dangerous: str) -> None:
        """Test that control characters trigger redaction."""
        result = sanitize_for_output(dangerous)
        assert result == "[REDACTED]"

    @pytest.mark.parametrize(
        "dangerous",
        [
            'text"with"quotes',
            "text'with'quotes",
            "text\"with'mixed'quotes",
        ],
    )
    def test_shell_quotes_pass_through(self, dangerous: str) -> None:
        """Test that shell quotes pass through after validation."""
        result = sanitize_for_output(dangerous)
        assert result == dangerous

    @pytest.mark.parametrize(
        "dangerous",
        [
            "text[with]brackets",
            "text{with}braces",
            "text(with)parens",
        ],
    )
    def test_shell_brackets_pass_through(self, dangerous: str) -> None:
        """Test that shell brackets pass through after validation."""
        result = sanitize_for_output(dangerous)
        assert result == dangerous

    @pytest.mark.parametrize(
        "value",
        [
            "myrepo",
            "my-repo",
            "my_repo",
            "my.repo",
            "repo123",
            "balanced",
            "priority",
            "conservative",
            "aggressive",
        ],
    )
    def test_clean_strings_pass_through(self, value: str) -> None:
        """Test that clean strings pass through unchanged."""
        result = sanitize_for_output(value)
        assert result == value

    def test_empty_string_passes_through(self) -> None:
        """Test that empty string passes through."""
        result = sanitize_for_output("")
        assert result == ""

    def test_whitespace_only_passes_through(self) -> None:
        """Test that whitespace-only string passes through."""
        result = sanitize_for_output("   ")
        assert result == "   "

    def test_logs_safe_metadata_for_control_characters(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that logging uses length and hash instead of raw value."""
        test_value = "sensitive\ndata\x00here"

        # Capture logs at DEBUG level
        with caplog.at_level(logging.DEBUG, logger="review_bot_automator.cli.main"):
            result = sanitize_for_output(test_value)

        # Function should return redacted value
        assert result == "[REDACTED]"

        # Verify length and hash are computed correctly
        value_bytes = test_value.encode("utf-8")
        expected_hash = hashlib.sha256(value_bytes).hexdigest()
        expected_length = len(test_value)

        # Get captured log messages
        log_messages = caplog.text

        # Check that logs contain length and hash but not the raw value
        assert f"length={expected_length}" in log_messages
        assert f"hash={expected_hash}" in log_messages
        # Ensure the sensitive data itself is NOT in any log message
        assert "sensitive" not in log_messages
        assert "data" not in log_messages


class TestCLIIntegration:
    """Test CLI integration with validation functions."""

    def test_analyze_command_with_invalid_owner(self) -> None:
        """Test analyze command with invalid owner identifier."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["analyze", "--pr", "1", "--owner", "org/repo", "--repo", "test"]
        )
        assert result.exit_code != 0
        assert "username must be a single segment" in result.output

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
        assert "username contains invalid characters" in result.output

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
            ["simulate", "--pr", "1", "--owner", "myrepo", "--repo", "test"],
        ]

        for cmd in commands:
            result = runner.invoke(cli, cmd)
            # Not a Click usage/option parsing error
            assert result.exit_code != 2, f"Unexpected Click usage error: {result.output}"
            # Should not fail due to validation errors - check for specific identifier errors
            output_lower = result.output.lower()
            # Check for specific identifier validation error messages
            identifier_errors = [
                "username required",
                "username too long",
                "username must be a single segment",
                "username contains invalid characters",
                "repository name required",
                "repository name too long",
                "identifier must be a single segment",
                "repository name contains invalid characters",
                "repository name cannot be '.' or '..'",
                "repository name cannot end with '.git'",
            ]
            for error_msg in (s.lower() for s in identifier_errors):
                assert (
                    error_msg not in output_lower
                ), f"Command should not fail with identifier validation error: {error_msg}"
