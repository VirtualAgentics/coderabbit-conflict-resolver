"""Unit tests for CLI input validation."""

from click.testing import CliRunner

from pr_conflict_resolver.cli.main import cli


class TestCLIPathValidation:
    """Test CLI path validation logic."""

    def test_safe_relative_paths_allowed(self) -> None:
        """Test that safe relative paths are accepted."""
        runner = CliRunner()
        safe_paths = [
            "myrepo",
            "my-repo",
            "my_repo",
        ]

        for path in safe_paths:
            # Should fail for other reasons but not path validation
            result = runner.invoke(cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", path])
            # If it mentions path validation, that's wrong
            assert (
                "invalid value for '--repo'" not in result.output.lower()
            ), f"Safe path should not trigger validation error: {path}"

    def test_slash_in_repo_name_rejected(self) -> None:
        """Test that repo names with slashes are rejected by new validation."""
        runner = CliRunner()

        result = runner.invoke(
            cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", "org/repo"]
        )
        assert result.exit_code != 0
        assert "identifier must be a single segment (no slashes or spaces)" in result.output

    def test_traversal_paths_rejected(self) -> None:
        """Test that path traversal attempts are rejected."""
        runner = CliRunner()
        unsafe_paths = [
            "../../../etc/passwd",
            "../../sensitive",
            "../parent",
        ]

        for path in unsafe_paths:
            result = runner.invoke(cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", path])
            assert result.exit_code != 0, f"Should reject traversal path: {path}"
            assert (
                "invalid value for '--repo'" in result.output.lower()
            ), f"Should show validation error for: {path}"

    def test_absolute_unix_paths_rejected(self) -> None:
        """Test that absolute Unix paths are rejected."""
        runner = CliRunner()
        unsafe_paths = [
            "/etc/passwd",
            "/var/log/secure",
            "/root/.ssh/id_rsa",
            "/usr/local/bin",
            "/home/user/documents",
        ]

        for path in unsafe_paths:
            result = runner.invoke(cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", path])
            assert result.exit_code != 0, f"Should reject absolute path: {path}"
            assert (
                "invalid value for '--repo'" in result.output.lower()
            ), f"Should show validation error for: {path}"

    def test_absolute_windows_paths_rejected(self) -> None:
        """Test that absolute Windows paths are rejected."""
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
            result = runner.invoke(cli, ["analyze", "--pr", "1", "--owner", "test", "--repo", path])
            assert result.exit_code != 0, f"Should reject Windows path: {path}"
            assert (
                "invalid value for '--repo'" in result.output.lower()
            ), f"Should show validation error for: {path}"

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
