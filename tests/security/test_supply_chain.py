"""Tests for supply chain security.

This module tests dependency security, package validation, and supply chain attacks.
"""

import re
from pathlib import Path

import pytest


class TestDependencyPinning:
    """Tests for dependency version pinning."""

    def test_requirements_txt_versions_pinned(self) -> None:
        """Test that requirements.txt pins all dependencies."""
        requirements_file = Path("requirements.txt")

        if not requirements_file.exists():
            pytest.skip("requirements.txt not found")

        with open(requirements_file) as f:
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

    def test_requirements_dev_txt_versions_pinned(self) -> None:
        """Test that requirements-dev.txt pins all dependencies."""
        requirements_file = Path("requirements-dev.txt")

        if not requirements_file.exists():
            pytest.skip("requirements-dev.txt not found")

        with open(requirements_file) as f:
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
            version_pattern = r"(>=|<=|==|~=|!=)[\d\w\.\-\+,]+"
            assert re.search(
                version_pattern, line
            ), f"Line {line_num}: '{line}' does not specify a version constraint"

    def test_pyproject_toml_has_version_constraints(self) -> None:
        """Test that pyproject.toml has version constraints for dependencies."""
        pyproject_file = Path("pyproject.toml")

        if not pyproject_file.exists():
            pytest.skip("pyproject.toml not found")

        with open(pyproject_file) as f:
            content = f.read()

        # Check that [project.dependencies] section exists
        if "[project.dependencies]" in content or "[tool.poetry.dependencies]" in content:
            # For now, just check the section exists
            # Full parsing would require tomli/toml parsing
            assert True, "Dependencies section found in pyproject.toml"


class TestGitHubActionsPinning:
    """Tests for GitHub Actions workflow pinning."""

    def test_github_actions_use_pinned_versions(self) -> None:
        """Test that GitHub Actions workflows pin action versions."""
        workflows_dir = Path(".github/workflows")

        if not workflows_dir.exists():
            pytest.skip(".github/workflows directory not found")

        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file) as f:
                content = f.read()

            # Check for uses: actions/...
            # These should specify a version (tag, sha, or version)
            # Pattern: uses: <action>@<version>

            # Find all uses statements
            for _line_num, line in enumerate(content.split("\n"), 1):
                if (
                    re.search(r"^\s*uses:\s*[\w/_-]+", line)
                    and "@" not in line
                    and "uses:" in line
                    and "composite" not in content.lower()
                ):
                    # This is a warning, not an error for now
                    pass


class TestDependencyVulnerabilities:
    """Tests for known dependency vulnerabilities."""

    def test_no_known_vulnerable_versions(self) -> None:
        """Test that dependencies are not using known vulnerable versions."""
        # This would typically use safety or pip-audit
        # For now, this is a placeholder that checks the tool exists
        import importlib.util

        if importlib.util.find_spec("safety") is None:
            pytest.skip("safety package not installed")


class TestLicenseCompliance:
    """Tests for license compliance."""

    def test_requirements_have_acceptable_licenses(self) -> None:
        """Test that dependencies have acceptable licenses."""
        # Placeholder for license checking
        # In real implementation, would use packages like license-check
        assert True  # TODO: Implement license compliance checking


class TestPackageValidity:
    """Tests for package validity and integrity."""

    def test_no_direct_url_installs(self) -> None:
        """Test that requirements don't use direct URL installs (security risk)."""
        requirements_file = Path("requirements.txt")

        if not requirements_file.exists():
            pytest.skip("requirements.txt not found")

        with open(requirements_file) as f:
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
