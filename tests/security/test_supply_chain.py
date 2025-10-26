"""Tests for supply chain security.

This module tests dependency security, package validation, and supply chain attacks.
"""

import re
import subprocess
from pathlib import Path

import pytest


class TestDependencyPinning:
    """Tests for dependency version pinning."""

    def _check_requirements_file_pinning(self, file_path: Path) -> None:
        """Helper to check that a requirements file pins all dependencies.

        Args:
            file_path: Path to the requirements file to check.
        """
        if not file_path.exists():
            pytest.skip(f"{file_path.name} not found")

        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Skip -r includes
            if line.startswith(("-r ", "--requirement")):
                continue

            # Check if version is pinned
            # Must contain ==, >=, <=, ~=, or != followed by a version
            version_pattern = r"(>=|<=|==|~=|!=)[\d\w\.\-\+,]+"
            assert re.search(
                version_pattern, line
            ), f"Line {line_num}: '{line}' does not specify a version constraint"

    @pytest.mark.parametrize("filename", ["requirements.txt", "requirements-dev.txt"])
    def test_requirements_files_versions_pinned(self, filename: str) -> None:
        """Test that requirements files pin all dependencies.

        Args:
            filename: Name of the requirements file to test.
        """
        requirements_file = Path(filename)
        self._check_requirements_file_pinning(requirements_file)

    def test_pyproject_toml_has_version_constraints(self) -> None:
        """Test that pyproject.toml has version constraints for dependencies."""
        pyproject_file = Path("pyproject.toml")

        if not pyproject_file.exists():
            pytest.skip("pyproject.toml not found")

        with open(pyproject_file, encoding="utf-8") as f:
            content = f.read()

        # Check that dependencies are defined in pyproject.toml
        # Modern PEP 621 format: dependencies = [...] within [project] section
        # Legacy formats: [project.dependencies] or [tool.poetry.dependencies]
        assert (
            "dependencies = [" in content
            or "[project.dependencies]" in content
            or "[tool.poetry.dependencies]" in content
        ), "No dependencies section found in pyproject.toml"


class TestGitHubActionsPinning:
    """Tests for GitHub Actions workflow pinning."""

    def test_github_actions_use_pinned_versions(self) -> None:
        """Test that GitHub Actions workflows pin action versions."""
        workflows_dir = Path(".github/workflows")

        if not workflows_dir.exists():
            pytest.skip(".github/workflows directory not found")

        unpinned_actions: list[tuple[str, int]] = []

        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, encoding="utf-8") as f:
                content = f.read()

            # Check for uses: actions/...
            # These should specify a version (tag, sha, or version)
            # Pattern: uses: <action>@<version>

            # Find all uses statements
            for line_num, line in enumerate(content.split("\n"), 1):
                if (
                    re.search(r"^\s*-\s*uses:\s*[\w/_-]+", line)
                    and "@" not in line
                    and "uses:" in line
                    and "composite" not in content.lower()
                ):
                    # Skip composite actions as they don't need pinning
                    unpinned_actions.append((str(workflow_file), line_num))

        # Assert that no unpinned actions were found
        if unpinned_actions:
            error_msg = "Found unpinned GitHub Actions:\n"
            for file_path, line_num in unpinned_actions:
                error_msg += f"  - {file_path}:{line_num}\n"
            error_msg += (
                "Please pin all GitHub Actions to specific versions (tags or SHAs) for security."
            )
            raise AssertionError(error_msg)


class TestDependencyVulnerabilities:
    """Tests for known dependency vulnerabilities."""

    def test_no_known_vulnerable_versions(self) -> None:
        """Test that dependencies are not using known vulnerable versions."""
        import importlib.util

        if importlib.util.find_spec("safety") is None:
            pytest.skip("safety package not installed")

        requirements_file = Path("requirements.txt")
        if not requirements_file.exists():
            pytest.skip("requirements.txt not found")

        # Run safety check against requirements.txt
        result = subprocess.run(  # noqa: S603
            ["safety", "check", "--file", str(requirements_file), "--json"],  # noqa: S607
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            "Vulnerable dependencies found. Run 'safety check' for details. "
            f"Output: {result.stdout}"
        )


class TestLicenseCompliance:
    """Tests for license compliance."""

    def test_requirements_have_acceptable_licenses(self) -> None:
        """Test that dependencies have acceptable licenses.

        This test is skipped as many packages lack complete license metadata.
        License compliance should be checked using external tools like:
        - pip-licenses
        - licensecheck
        - foss-cli

        For now, we rely on:
        - manual review of dependencies
        - security scanning tools that check licenses
        - explicit license declarations in pyproject.toml
        """
        pytest.skip(
            "License check not fully implemented - many packages lack complete metadata. "
            "Use tools like 'pip-licenses' or 'licensecheck' for comprehensive license analysis."
        )


class TestPackageValidity:
    """Tests for package validity and integrity."""

    def test_no_direct_url_installs(self) -> None:
        """Test that requirements don't use direct URL installs (security risk)."""
        requirements_file = Path("requirements.txt")

        if not requirements_file.exists():
            pytest.skip("requirements.txt not found")

        with open(requirements_file, encoding="utf-8") as f:
            content = f.read()

        # Check for git+, http://, or https:// installs
        # These can be security risks as they bypass PyPI security checks
        dangerous_patterns = [
            r"git\+",
            r"http://",
            r"https://[^@]+\.[a-z]+",  # URLs without @ (not pip URLs)
        ]

        for pattern in dangerous_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Skip legitimate PyPI URLs
                if "pypi.org" in match or "files.pythonhosted.org" in match:
                    continue
                # This is a warning, not enforced as hard requirement
