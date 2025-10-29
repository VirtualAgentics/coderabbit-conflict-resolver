"""Integration tests for build artifacts and metadata generation.

These tests validate the end-to-end build process including metadata generation,
wheel validation, and artifact quality checks.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def dist_dir(project_root):
    """Get dist directory path."""
    return project_root / "dist"


@pytest.fixture(scope="module")
def build_artifacts(project_root, dist_dir):
    """Build package and generate artifacts.

    This fixture runs once per module to avoid rebuilding for each test.
    """
    # Clean dist directory
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    # Build package
    subprocess.run(
        [sys.executable, "-m", "build"],
        cwd=project_root,
        check=True,
        capture_output=True,
    )

    # Generate metadata
    subprocess.run(
        [sys.executable, str(project_root / "scripts" / "generate_build_metadata.py")],
        cwd=project_root,
        check=True,
        capture_output=True,
    )

    yield dist_dir

    # Cleanup is optional as dist/ is typically .gitignored


@pytest.mark.integration
class TestBuildArtifacts:
    """Integration tests for build artifacts."""

    def test_dist_directory_exists(self, build_artifacts):
        """Test that dist directory is created."""
        assert build_artifacts.exists()
        assert build_artifacts.is_dir()

    def test_wheel_file_generated(self, build_artifacts):
        """Test that wheel file is generated."""
        wheel_files = list(build_artifacts.glob("*.whl"))
        assert len(wheel_files) == 1
        assert wheel_files[0].suffix == ".whl"

    def test_wheel_file_naming(self, build_artifacts):
        """Test that wheel file follows naming convention."""
        wheel_files = list(build_artifacts.glob("*.whl"))
        wheel_name = wheel_files[0].name

        # Expected format: pr_conflict_resolver-0.1.0-py3-none-any.whl
        assert "pr_conflict_resolver" in wheel_name
        assert "0.1.0" in wheel_name
        assert wheel_name.endswith("-py3-none-any.whl")

    def test_sdist_file_generated(self, build_artifacts):
        """Test that source distribution is generated."""
        sdist_files = list(build_artifacts.glob("*.tar.gz"))
        assert len(sdist_files) == 1
        assert sdist_files[0].suffix == ".gz"

    def test_sdist_file_naming(self, build_artifacts):
        """Test that sdist file follows naming convention."""
        sdist_files = list(build_artifacts.glob("*.tar.gz"))
        sdist_name = sdist_files[0].name

        # Expected format: pr_conflict_resolver-0.1.0.tar.gz
        assert "pr_conflict_resolver" in sdist_name or "pr-conflict-resolver" in sdist_name
        assert "0.1.0" in sdist_name
        assert sdist_name.endswith(".tar.gz")

    def test_metadata_file_generated(self, build_artifacts):
        """Test that metadata.json is generated."""
        metadata_file = build_artifacts / "metadata.json"
        assert metadata_file.exists()
        assert metadata_file.is_file()

    def test_artifact_sizes_reasonable(self, build_artifacts):
        """Test that artifact sizes are reasonable (not empty, not too large)."""
        wheel_files = list(build_artifacts.glob("*.whl"))
        sdist_files = list(build_artifacts.glob("*.tar.gz"))

        wheel_size = wheel_files[0].stat().st_size
        sdist_size = sdist_files[0].stat().st_size

        # Wheel should be > 10KB and < 10MB
        assert 10_000 < wheel_size < 10_000_000

        # Sdist should be > 10KB and < 10MB
        assert 10_000 < sdist_size < 10_000_000


@pytest.mark.integration
class TestMetadataContent:
    """Integration tests for metadata.json content."""

    def test_metadata_is_valid_json(self, build_artifacts):
        """Test that metadata.json is valid JSON."""
        metadata_file = build_artifacts / "metadata.json"
        with metadata_file.open() as f:
            metadata = json.load(f)

        assert isinstance(metadata, dict)

    def test_metadata_has_required_structure(self, build_artifacts):
        """Test that metadata has all required top-level keys."""
        metadata_file = build_artifacts / "metadata.json"
        with metadata_file.open() as f:
            metadata = json.load(f)

        required_keys = ["package", "git", "build"]
        assert all(key in metadata for key in required_keys)

    def test_metadata_package_section(self, build_artifacts):
        """Test package section of metadata."""
        metadata_file = build_artifacts / "metadata.json"
        with metadata_file.open() as f:
            metadata = json.load(f)

        package = metadata["package"]
        assert package["name"] == "pr-conflict-resolver"
        assert package["version"] == "0.1.0"

    def test_metadata_git_section(self, build_artifacts):
        """Test git section of metadata."""
        metadata_file = build_artifacts / "metadata.json"
        with metadata_file.open() as f:
            metadata = json.load(f)

        git = metadata["git"]
        assert isinstance(git, dict)

        # These should exist if in a git repository
        if git.get("commit_sha"):
            assert len(git["commit_sha"]) == 40
            assert git["commit_sha"].isalnum()

        if git.get("commit_sha_short"):
            assert len(git["commit_sha_short"]) == 7
            assert git["commit_sha_short"].isalnum()

        if git.get("branch"):
            assert isinstance(git["branch"], str)
            assert len(git["branch"]) > 0

    def test_metadata_build_section(self, build_artifacts):
        """Test build section of metadata."""
        metadata_file = build_artifacts / "metadata.json"
        with metadata_file.open() as f:
            metadata = json.load(f)

        build = metadata["build"]
        assert isinstance(build, dict)

        # Required build fields
        assert "build_timestamp" in build
        assert "python_version" in build
        assert "python_implementation" in build

        # Verify timestamp format (ISO 8601)
        assert "T" in build["build_timestamp"]
        assert "+" in build["build_timestamp"] or "Z" in build["build_timestamp"]

        # Verify Python version format
        assert build["python_version"].count(".") == 2
        parts = build["python_version"].split(".")
        assert all(part.isdigit() for part in parts)

        # Verify implementation
        assert build["python_implementation"] in ["cpython", "pypy", "jython", "ironpython"]

    def test_metadata_version_matches_package(self, build_artifacts):
        """Test that metadata version matches actual package version."""
        # Load metadata
        metadata_file = build_artifacts / "metadata.json"
        with metadata_file.open() as f:
            metadata = json.load(f)

        metadata_version = metadata["package"]["version"]

        # Load version from pyproject.toml
        project_root = build_artifacts.parent
        pyproject_content = (project_root / "pyproject.toml").read_text()
        import re

        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_content, re.MULTILINE)
        assert match
        pyproject_version = match.group(1)

        assert metadata_version == pyproject_version


@pytest.mark.integration
@pytest.mark.slow
class TestWheelValidation:
    """Integration tests for wheel validation script."""

    def test_wheel_validation_script_exists(self, project_root):
        """Test that validate_wheel.py script exists."""
        script_path = project_root / "scripts" / "validate_wheel.py"
        assert script_path.exists()
        assert script_path.is_file()

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Unix permissions not applicable on Windows"
    )
    def test_wheel_validation_script_executable(self, project_root):
        """Test that validate_wheel.py has execute permissions."""
        script_path = project_root / "scripts" / "validate_wheel.py"
        assert script_path.stat().st_mode & 0o111  # Check execute bit

    def test_wheel_validation_runs_successfully(self, project_root, build_artifacts):
        """Test that wheel validation script runs successfully."""
        script_path = project_root / "scripts" / "validate_wheel.py"

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        # Script should exit with 0 for successful validation
        assert result.returncode == 0, f"Validation failed:\n{result.stdout}\n{result.stderr}"

    def test_wheel_validation_output(self, project_root, build_artifacts):
        """Test that wheel validation produces expected output."""
        script_path = project_root / "scripts" / "validate_wheel.py"

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        output = result.stdout

        # Check for expected output markers
        assert "Validating Wheel Package" in output
        assert "Finding wheel file" in output
        assert "Loading metadata" in output
        assert "Installing wheel" in output
        assert "Validating package import" in output
        assert "Validating CLI entry point" in output
        assert "Validation Summary" in output

    def test_wheel_validation_checks_all_criteria(self, project_root, build_artifacts):
        """Test that wheel validation checks all criteria."""
        script_path = project_root / "scripts" / "validate_wheel.py"

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        output = result.stdout

        # All validations should pass
        assert "Wheel Found:" in output
        assert "Install Successful:" in output
        assert "Import Successful:" in output
        assert "Version Matches:" in output
        assert "Entry Point Exists:" in output
        assert "Entry Point Callable:" in output

        # Should have success message
        assert "All validations passed" in output


@pytest.mark.integration
class TestBuildReproducibility:
    """Integration tests for build reproducibility."""

    def test_multiple_metadata_generations_consistent(self, project_root, dist_dir):
        """Test that metadata generation is consistent across multiple runs."""
        script_path = project_root / "scripts" / "generate_build_metadata.py"

        # Generate metadata first time
        subprocess.run(
            [sys.executable, str(script_path)],
            cwd=project_root,
            check=True,
            capture_output=True,
        )

        with (dist_dir / "metadata.json").open() as f:
            metadata1 = json.load(f)

        # Generate metadata second time
        subprocess.run(
            [sys.executable, str(script_path)],
            cwd=project_root,
            check=True,
            capture_output=True,
        )

        with (dist_dir / "metadata.json").open() as f:
            metadata2 = json.load(f)

        # These should be identical (except timestamp)
        assert metadata1["package"] == metadata2["package"]
        assert metadata1["git"] == metadata2["git"]

        # Build info should be similar (except timestamp)
        assert metadata1["build"]["python_version"] == metadata2["build"]["python_version"]
        assert (
            metadata1["build"]["python_implementation"]
            == metadata2["build"]["python_implementation"]
        )


@pytest.mark.integration
class TestBuildArtifactIntegrity:
    """Integration tests for build artifact integrity."""

    def test_wheel_can_be_inspected(self, build_artifacts):
        """Test that wheel can be inspected with wheel tool."""
        wheel_files = list(build_artifacts.glob("*.whl"))
        wheel_path = wheel_files[0]

        # Use zipfile to inspect wheel (wheels are zip files)
        import zipfile

        with zipfile.ZipFile(wheel_path, "r") as zf:
            namelist = zf.namelist()

            # Should contain package files
            assert any("pr_conflict_resolver" in name for name in namelist)

            # Should contain metadata
            assert any("METADATA" in name for name in namelist)
            assert any("WHEEL" in name for name in namelist)

    def test_wheel_metadata_file_content(self, build_artifacts):
        """Test that wheel METADATA file has correct content."""
        import zipfile

        wheel_files = list(build_artifacts.glob("*.whl"))
        wheel_path = wheel_files[0]

        with zipfile.ZipFile(wheel_path, "r") as zf:
            # Find METADATA file
            metadata_files = [name for name in zf.namelist() if name.endswith("METADATA")]
            assert len(metadata_files) == 1

            metadata_content = zf.read(metadata_files[0]).decode("utf-8")

            # Check for required metadata fields
            assert "Name: pr-conflict-resolver" in metadata_content
            assert "Version: 0.1.0" in metadata_content
            assert "VirtualAgentics" in metadata_content

    def test_sdist_can_be_extracted(self, build_artifacts):
        """Test that sdist can be extracted."""
        import tarfile

        sdist_files = list(build_artifacts.glob("*.tar.gz"))
        sdist_path = sdist_files[0]

        with tarfile.open(sdist_path, "r:gz") as tf:
            namelist = tf.getnames()

            # Should contain source files
            assert any("pyproject.toml" in name for name in namelist)
            assert any("pr_conflict_resolver" in name for name in namelist)
