"""Unit tests for CLI input validation."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from click import BadParameter, Context, Option
from click.testing import CliRunner

from review_bot_automator.cli.main import cli, validate_github_repo, validate_pr_number


@pytest.fixture(autouse=True)
def mock_github_api() -> Generator[None, None, None]:
    """Mock GitHub API calls to prevent network access in tests."""
    with patch(
        "review_bot_automator.integrations.github.GitHubCommentExtractor.fetch_pr_comments",
        return_value=[],
    ):
        yield


@pytest.fixture()
def click_ctx() -> Context:
    """Provide a Click Context bound to the CLI group for validator tests."""
    return Context(cli)


@pytest.fixture()
def repo_param() -> Option:
    """Provide a Click Option instance for the '--repo' parameter."""
    return Option(["--repo"])  # acts as a Parameter instance


@pytest.fixture()
def pr_param() -> Option:
    """Provide a Click Option instance for the '--pr' parameter."""
    return Option(["--pr"])  # acts as a Parameter instance


class TestCLIPathValidation:
    """Test CLI path validation logic."""

    @pytest.mark.parametrize("path", ["myrepo", "my-repo", "my_repo"])
    def test_safe_relative_paths_allowed(self, path: str) -> None:
        """Test that safe relative paths are accepted."""
        runner = CliRunner()

        # Should fail for other reasons but not path validation
        result = runner.invoke(cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", path])
        # Command should succeed for safe values
        assert result.exit_code == 0
        output_lower = result.output.lower()
        # Safe paths should not trigger validation error messages
        validation_messages = [
            "invalid value for '--repo'",
            "identifier must be a single segment",
            "repository name must be a single segment",
        ]
        assert not any(
            msg in output_lower for msg in validation_messages
        ), f"Safe path should not trigger validation error: {path}"

    def test_slash_in_repo_name_rejected(self) -> None:
        """Test that repo names with slashes are rejected by new validation."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", "org/repo"]
        )
        assert result.exit_code != 0
        assert "identifier must be a single segment (no slashes or spaces)" in result.output

    def test_traversal_paths_rejected(self, subtests: pytest.Subtests) -> None:
        """Test that path traversal attempts are rejected using subtests."""
        runner = CliRunner()
        unsafe_paths = [
            "../../../etc/passwd",
            "../../sensitive",
            "../parent",
        ]

        for path in unsafe_paths:
            with subtests.test(msg=f"Path traversal: {path}", path=path):
                result = runner.invoke(
                    cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", path]
                )
                assert result.exit_code != 0
                assert "invalid value for '--repo'" in result.output.lower()

    def test_absolute_unix_paths_rejected(self, subtests: pytest.Subtests) -> None:
        """Test that absolute Unix paths are rejected using subtests."""
        runner = CliRunner()
        unsafe_paths = [
            "/etc/passwd",
            "/var/log/secure",
            "/root/.ssh/id_rsa",
            "/usr/local/bin",
            "/home/user/documents",
        ]

        for path in unsafe_paths:
            with subtests.test(msg=f"Absolute Unix path: {path}", path=path):
                result = runner.invoke(
                    cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", path]
                )
                assert result.exit_code != 0
                assert "invalid value for '--repo'" in result.output.lower()

    def test_absolute_windows_paths_rejected(self, subtests: pytest.Subtests) -> None:
        """Test that absolute Windows paths are rejected using subtests."""
        runner = CliRunner()
        unsafe_paths = [
            "C:\\Windows\\System32",
            "D:\\Program Files",
            "C:/Windows/System32",
            "C:\\\\path\\\\to\\\\repo",
            "C:/path/to/repo",
            "\\\\server\\\\share\\\\repo",
            "\\\\server\\share\\repo",
            "D:\\\\data\\\\projects\\\\myrepo",
        ]

        for path in unsafe_paths:
            with subtests.test(msg=f"Absolute Windows path: {path}", path=path):
                result = runner.invoke(
                    cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", path]
                )
                assert result.exit_code != 0
                assert "invalid value for '--repo'" in result.output.lower()

    def test_owner_parameter_also_validated(self) -> None:
        """Test that owner parameter is also validated."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["analyze", "--pr", "1", "--owner", "../../../etc", "--repo", "test"]
        )
        assert result.exit_code != 0
        # Verify error is bound to the --owner parameter specifically
        assert "invalid value for '--owner'" in result.output.lower()
        assert "--owner" in result.output.lower()
        assert "owner" in result.output.lower()


class TestValidateGitHubRepo:
    """Test GitHub repository name validation function."""

    def test_repo_ending_with_git_rejected(self, click_ctx: Context, repo_param: Option) -> None:
        """Test that repo names ending with .git are rejected."""
        with pytest.raises(BadParameter, match=r"cannot end with '\.git'"):
            validate_github_repo(click_ctx, repo_param, "myrepo.git")

    @pytest.mark.parametrize("name", [".", ".."])
    def test_repo_dot_or_dotdot_rejected(
        self, name: str, click_ctx: Context, repo_param: Option
    ) -> None:
        """Repo names '.' or '..' are rejected."""
        with pytest.raises(BadParameter, match=r"repository name cannot be '\.' or '\.\.'"):
            validate_github_repo(click_ctx, repo_param, name)

    def test_valid_repo_accepted(self, click_ctx: Context, repo_param: Option) -> None:
        """Valid repo names should pass validation."""
        assert validate_github_repo(click_ctx, repo_param, "my-repo_1") == "my-repo_1"
        assert validate_github_repo(click_ctx, repo_param, "my.repo") == "my.repo"


class TestValidatePRNumber:
    """Test PR number validation function."""

    def test_zero_pr_rejected(self, click_ctx: Context, pr_param: Option) -> None:
        """Test that PR number 0 is rejected."""
        with pytest.raises(BadParameter, match=r"PR number must be positive"):
            validate_pr_number(click_ctx, pr_param, 0)

    def test_negative_pr_rejected(self, click_ctx: Context, pr_param: Option) -> None:
        """Negative PR numbers should be rejected."""
        with pytest.raises(BadParameter, match=r"PR number must be positive"):
            validate_pr_number(click_ctx, pr_param, -5)

    def test_positive_pr_accepted(self, click_ctx: Context, pr_param: Option) -> None:
        """Positive PR numbers should be accepted."""
        assert validate_pr_number(click_ctx, pr_param, 42) == 42
