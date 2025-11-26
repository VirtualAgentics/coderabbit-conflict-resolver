"""Unit tests for build scripts (generate_build_metadata.py and validate_wheel.py)."""

import importlib.util
import subprocess
import tomllib
import types
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

# Load build scripts dynamically using importlib
_SCRIPTS = Path(__file__).parent.parent.parent / "scripts"


def _load_module(name: str, path: Path) -> types.ModuleType:
    """Load a module from a file path using importlib.

    Args:
        name: Name to assign to the loaded module.
        path: Path to the Python file to load.

    Returns:
        The loaded module object.

    Raises:
        ImportError: If the module cannot be loaded.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generate_build_metadata = _load_module(
    "generate_build_metadata", _SCRIPTS / "generate_build_metadata.py"
)
validate_wheel = _load_module("validate_wheel", _SCRIPTS / "validate_wheel.py")


class TestGenerateBuildMetadata:
    """Tests for generate_build_metadata.py."""

    def test_get_project_root(self) -> None:
        """Test that get_project_root returns the correct path."""
        root = generate_build_metadata.get_project_root()
        assert root.exists()
        assert (root / "pyproject.toml").exists()
        assert (root / "src" / "review_bot_automator").exists()

    def test_extract_version_from_pyproject(self) -> None:
        """Test version extraction from pyproject.toml."""
        version = generate_build_metadata.extract_version_from_pyproject()

        # Read expected version from pyproject.toml
        with (generate_build_metadata.get_project_root() / "pyproject.toml").open("rb") as f:
            expected_version = tomllib.load(f)["project"]["version"]

        assert version == expected_version
        assert isinstance(version, str)

    def test_extract_version_from_init(self) -> None:
        """Test version extraction from __init__.py."""
        version = generate_build_metadata.extract_version_from_init()

        # Read expected version from pyproject.toml
        with (generate_build_metadata.get_project_root() / "pyproject.toml").open("rb") as f:
            expected_version = tomllib.load(f)["project"]["version"]

        assert version == expected_version
        assert isinstance(version, str)

    def test_validate_versions_match(self) -> None:
        """Test that versions match across files."""
        version = generate_build_metadata.validate_versions_match()

        # Read expected version from pyproject.toml
        with (generate_build_metadata.get_project_root() / "pyproject.toml").open("rb") as f:
            expected_version = tomllib.load(f)["project"]["version"]

        assert version == expected_version

    @patch.object(generate_build_metadata, "extract_version_from_pyproject")
    @patch.object(generate_build_metadata, "extract_version_from_init")
    def test_validate_versions_mismatch(
        self, mock_init_version: Mock, mock_pyproject_version: Mock
    ) -> None:
        """Test that version mismatch raises error."""
        mock_pyproject_version.return_value = "0.1.0"
        mock_init_version.return_value = "0.2.0"

        with pytest.raises(ValueError, match="Version mismatch"):
            generate_build_metadata.validate_versions_match()

    @patch("subprocess.run")
    def test_run_git_command(self, mock_run: Mock) -> None:
        """Test running git commands."""
        # Setup mock to return deterministic output
        mock_run.return_value = Mock(stdout="a" * 40 + "\n", returncode=0)

        # Test getting commit SHA
        result = generate_build_metadata.run_git_command(["rev-parse", "HEAD"])
        assert isinstance(result, str)
        assert len(result) == 40  # Full SHA is 40 characters

    @patch("subprocess.run")
    def test_run_git_command_failure(self, mock_run: Mock) -> None:
        """Test that git command failures raise CalledProcessError."""
        # Setup mock to raise CalledProcessError
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        with pytest.raises(subprocess.CalledProcessError):
            generate_build_metadata.run_git_command(["invalid-command"])

    @patch.object(generate_build_metadata, "run_git_command")
    def test_get_git_metadata(self, mock_git_command: Mock) -> None:
        """Test collecting git metadata."""

        # Mock git command outputs
        def git_side_effect(args: list[str]) -> str:
            if args == ["rev-parse", "HEAD"]:
                return "a" * 40
            elif args == ["rev-parse", "--short", "HEAD"]:
                return "a" * 7
            elif args == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return "main"
            elif args == ["describe", "--exact-match", "--tags"]:
                raise subprocess.CalledProcessError(1, "git")
            elif args == ["config", "--get", "remote.origin.url"]:
                return "https://github.com/test/repo.git"
            return ""

        mock_git_command.side_effect = git_side_effect

        metadata = generate_build_metadata.get_git_metadata()

        assert isinstance(metadata, dict)
        assert "commit_sha" in metadata
        assert "commit_sha_short" in metadata
        assert "branch" in metadata

        # Verify commit SHA format
        assert len(metadata["commit_sha"]) == 40
        assert len(metadata["commit_sha_short"]) == 7
        assert metadata["branch"] == "main"

    def test_get_build_metadata(self) -> None:
        """Test collecting build metadata."""
        metadata = generate_build_metadata.get_build_metadata()

        assert isinstance(metadata, dict)
        assert "build_timestamp" in metadata
        assert "python_version" in metadata
        assert "python_implementation" in metadata

        # Verify timestamp format (ISO 8601)
        assert "T" in metadata["build_timestamp"]
        assert "+" in metadata["build_timestamp"] or "Z" in metadata["build_timestamp"]

        # Verify Python version format
        assert metadata["python_version"].count(".") == 2

    @patch.dict("os.environ", {"GITHUB_WORKFLOW": "CI", "GITHUB_RUN_ID": "12345"})
    def test_get_build_metadata_with_github_env(self) -> None:
        """Test that GitHub environment variables are collected."""
        metadata = generate_build_metadata.get_build_metadata()

        assert "github_workflow" in metadata
        assert metadata["github_workflow"] == "CI"
        assert "github_run_id" in metadata
        assert metadata["github_run_id"] == "12345"

    @patch.object(generate_build_metadata, "get_git_metadata")
    def test_generate_metadata(self, mock_git_metadata: Mock) -> None:
        """Test complete metadata generation."""
        # Mock git metadata to return deterministic values
        mock_git_metadata.return_value = {
            "commit_sha": "a" * 40,
            "commit_sha_short": "a" * 7,
            "branch": "main",
            "tag": None,
            "remote_url": "https://github.com/test/repo.git",
        }

        metadata = generate_build_metadata.generate_metadata()

        # Verify structure
        assert isinstance(metadata, dict)
        assert "package" in metadata
        assert "git" in metadata
        assert "build" in metadata

        # Verify package section
        assert metadata["package"]["name"] == "review-bot-automator"

        # Read expected version from pyproject.toml
        with (generate_build_metadata.get_project_root() / "pyproject.toml").open("rb") as f:
            expected_version = tomllib.load(f)["project"]["version"]
        assert metadata["package"]["version"] == expected_version

        # Verify git section exists
        assert isinstance(metadata["git"], dict)

        # Verify build section
        assert isinstance(metadata["build"], dict)
        assert "build_timestamp" in metadata["build"]
        assert "python_version" in metadata["build"]

    @patch.object(generate_build_metadata, "get_git_metadata")
    def test_metadata_json_schema(self, mock_git_metadata: Mock) -> None:
        """Test that generated metadata conforms to expected schema."""
        # Mock git metadata to return deterministic values
        mock_git_metadata.return_value = {
            "commit_sha": "a" * 40,
            "commit_sha_short": "a" * 7,
            "branch": "main",
            "tag": None,
            "remote_url": "https://github.com/test/repo.git",
        }

        metadata = generate_build_metadata.generate_metadata()

        # Required top-level keys
        required_keys = ["package", "git", "build"]
        assert all(key in metadata for key in required_keys)

        # Package keys
        assert "name" in metadata["package"]
        assert "version" in metadata["package"]

        # Git keys (may be empty if not in a git repo)
        assert isinstance(metadata["git"], dict)

        # Build keys
        assert "build_timestamp" in metadata["build"]
        assert "python_version" in metadata["build"]
        assert "python_implementation" in metadata["build"]

    @patch.object(generate_build_metadata, "get_project_root")
    @patch("builtins.open", new_callable=mock_open)
    @patch.object(generate_build_metadata, "generate_metadata")
    def test_main_success(self, mock_generate: Mock, mock_file: Mock, mock_root: Mock) -> None:
        """Test successful main execution."""
        # Setup mocks
        mock_root_path = Mock()
        mock_dist_path = Mock()
        mock_output_path = Mock()

        mock_root.return_value = mock_root_path
        mock_root_path.__truediv__ = Mock(
            side_effect=lambda x: mock_dist_path if x == "dist" else Mock()
        )
        mock_dist_path.parent = mock_dist_path
        mock_dist_path.mkdir = Mock()
        mock_dist_path.__truediv__ = Mock(return_value=mock_output_path)
        mock_output_path.parent = mock_dist_path
        mock_output_path.open = mock_file

        mock_generate.return_value = {
            "package": {"name": "test-package", "version": "1.0.0"},
            "git": {"commit_sha_short": "abc1234", "branch": "main"},
            "build": {"python_version": "3.12.0"},
        }

        result = generate_build_metadata.main()

        assert result == 0
        mock_generate.assert_called_once()

    @patch.object(generate_build_metadata, "generate_metadata")
    def test_main_failure(self, mock_generate: Mock) -> None:
        """Test main execution with error."""
        mock_generate.side_effect = Exception("Test error")

        result = generate_build_metadata.main()

        assert result == 1


class TestValidateWheel:
    """Tests for validate_wheel.py."""

    def test_get_project_root(self) -> None:
        """Test that get_project_root returns the correct path."""
        root = validate_wheel.get_project_root()
        assert root.exists()
        assert (root / "pyproject.toml").exists()

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.glob")
    def test_find_wheel_file_success(self, mock_glob: Mock, mock_exists: Mock) -> None:
        """Test successful wheel file detection."""
        mock_exists.return_value = True
        mock_wheel = Mock()
        mock_wheel.name = "test_package-1.0.0-py3-none-any.whl"
        mock_glob.return_value = [mock_wheel]

        result = validate_wheel.find_wheel_file()

        assert result == mock_wheel

    @patch("pathlib.Path.exists")
    def test_find_wheel_file_no_dist_dir(self, mock_exists: Mock) -> None:
        """Test error when dist/ directory doesn't exist."""
        mock_exists.return_value = False

        with pytest.raises(FileNotFoundError, match="dist/ directory not found"):
            validate_wheel.find_wheel_file()

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.glob")
    def test_find_wheel_file_no_wheel(self, mock_glob: Mock, mock_exists: Mock) -> None:
        """Test error when no wheel file found."""
        mock_exists.return_value = True
        mock_glob.return_value = []

        with pytest.raises(FileNotFoundError, match="No wheel file found"):
            validate_wheel.find_wheel_file()

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.glob")
    def test_find_wheel_file_multiple_wheels(self, mock_glob: Mock, mock_exists: Mock) -> None:
        """Test error when multiple wheel files found."""
        mock_exists.return_value = True
        mock_wheel1 = Mock()
        mock_wheel1.name = "package1.whl"
        mock_wheel2 = Mock()
        mock_wheel2.name = "package2.whl"
        mock_glob.return_value = [mock_wheel1, mock_wheel2]

        with pytest.raises(ValueError, match="Multiple wheel files found"):
            validate_wheel.find_wheel_file()

    @patch.object(validate_wheel, "get_project_root")
    def test_load_metadata_success(self, mock_root: Mock) -> None:
        """Test successful metadata loading."""
        # Setup mock path
        mock_root_path = Mock()
        mock_metadata_path = Mock()

        mock_root.return_value = mock_root_path
        mock_root_path.__truediv__ = Mock(
            side_effect=lambda x: (
                Mock() if x != "dist" else Mock(__truediv__=lambda _, y: mock_metadata_path)
            )
        )
        mock_metadata_path.exists = Mock(return_value=True)
        mock_metadata_path.open = mock_open(read_data='{"package":{"version":"1.0.0"}}')

        metadata = validate_wheel.load_metadata()

        assert isinstance(metadata, dict)
        assert "package" in metadata
        assert metadata["package"]["version"] == "1.0.0"

    @patch("pathlib.Path.exists")
    def test_load_metadata_not_found(self, mock_exists: Mock) -> None:
        """Test error when metadata.json not found."""
        mock_exists.return_value = False

        with pytest.raises(FileNotFoundError, match="metadata.json not found"):
            validate_wheel.load_metadata()

    @patch("subprocess.run")
    def test_install_wheel_isolated_success(self, mock_run: Mock) -> None:
        """Test successful wheel installation."""
        mock_run.return_value = Mock(returncode=0)
        wheel_path = Path("/tmp/test.whl")
        target_dir = Path("/tmp/target")

        # Should not raise
        validate_wheel.install_wheel_isolated(wheel_path, target_dir)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert str(wheel_path) in call_args
        assert str(target_dir) in call_args

    @patch("subprocess.run")
    def test_install_wheel_isolated_failure(self, mock_run: Mock) -> None:
        """Test wheel installation failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "pip")

        with pytest.raises(subprocess.CalledProcessError):
            validate_wheel.install_wheel_isolated(Path("/tmp/test.whl"), Path("/tmp/target"))

    @patch("subprocess.run")
    def test_validate_import_success(self, mock_run: Mock) -> None:
        """Test successful import validation."""
        mock_run.return_value = Mock(
            returncode=0, stdout="VERSION:1.0.0\nIMPORT:SUCCESS\n", stderr=""
        )

        result = validate_wheel.validate_import(Path("/tmp/install"), "1.0.0")

        assert result["import_successful"] is True
        assert result["version_matches"] is True
        assert result["version_found"] == "1.0.0"
        assert result["error"] is None

    @patch("subprocess.run")
    def test_validate_import_version_mismatch(self, mock_run: Mock) -> None:
        """Test import validation with version mismatch."""
        mock_run.return_value = Mock(
            returncode=0, stdout="VERSION:2.0.0\nIMPORT:SUCCESS\n", stderr=""
        )

        result = validate_wheel.validate_import(Path("/tmp/install"), "1.0.0")

        assert result["import_successful"] is True
        assert result["version_matches"] is False
        assert result["version_found"] == "2.0.0"

    @patch("subprocess.run")
    def test_validate_import_failure(self, mock_run: Mock) -> None:
        """Test import validation failure."""
        mock_run.return_value = Mock(
            returncode=1, stdout="", stderr="ImportError: module not found"
        )

        result = validate_wheel.validate_import(Path("/tmp/install"), "1.0.0")

        assert result["import_successful"] is False
        assert result["error"] is not None

    @patch("subprocess.run")
    def test_validate_entry_point_success(self, mock_run: Mock) -> None:
        """Test successful entry point validation."""
        mock_run.return_value = Mock(
            returncode=0, stdout="ENTRY_POINT:EXISTS\nENTRY_POINT:CALLABLE\n", stderr=""
        )

        result = validate_wheel.validate_entry_point(Path("/tmp/install"))

        assert result["entry_point_exists"] is True
        assert result["entry_point_callable"] is True
        assert result["error"] is None

    @patch("subprocess.run")
    def test_validate_entry_point_not_callable(self, mock_run: Mock) -> None:
        """Test entry point validation when not callable."""
        mock_run.return_value = Mock(returncode=0, stdout="ENTRY_POINT:EXISTS\n", stderr="")

        result = validate_wheel.validate_entry_point(Path("/tmp/install"))

        assert result["entry_point_exists"] is True
        assert result["entry_point_callable"] is False

    @patch("subprocess.run")
    def test_validate_entry_point_failure(self, mock_run: Mock) -> None:
        """Test entry point validation failure."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="ERROR:Entry point not found")

        result = validate_wheel.validate_entry_point(Path("/tmp/install"))

        assert result["entry_point_exists"] is False
        assert result["entry_point_callable"] is False
        assert result["error"] is not None
