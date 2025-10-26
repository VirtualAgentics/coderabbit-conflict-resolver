"""Tests for supply chain security.

This module tests dependency security, package validation, and supply chain attacks.
"""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

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

            # Check if version is pinned or has reasonable constraints
            # Allow ==, ~=, or range constraints like >=x.y.z,<a.b.c
            version_pattern = r"(==|~=|>=)(?=\d)[\d\w\.\-\+]+"
            has_version_constraint = re.search(version_pattern, line)

            # For production requirements.txt, require exact pinning (== or ~=)
            if file_path.name == "requirements.txt":
                exact_pin_pattern = r"(==|~=)(?=\d)[\d\w\.\-\+]+"
                assert re.search(exact_pin_pattern, line), (
                    f"Line {line_num}: '{line}' does not specify exact version pinning. "
                    f"Production dependencies must use '==1.2.3' or '~=1.2.3' for security"
                )
            else:
                # For dev requirements, allow range constraints but require some constraint
                assert has_version_constraint, (
                    f"Line {line_num}: '{line}' does not specify a version constraint. "
                    f"Use '==1.2.3', '~=1.2.3', or '>=1.2.3,<2.0.0' for security"
                )

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

        # Parse the TOML file
        import tomllib

        with open(pyproject_file, "rb") as f:
            data = tomllib.load(f)

        def extract_string_dependencies(deps_data: Any) -> list[str]:
            """Safely extract string dependencies from various data structures."""
            result: list[str] = []

            if isinstance(deps_data, dict):
                for value in deps_data.values():
                    if isinstance(value, str):
                        result.append(value)
                    elif (
                        isinstance(value, dict)
                        and "version" in value
                        and isinstance(value["version"], str)
                    ):
                        # Extract version if present, otherwise skip
                        result.append(value["version"])
                        # Skip non-string dict values for safety
            elif isinstance(deps_data, list):
                for item in deps_data:
                    if isinstance(item, str):
                        result.append(item)
                    elif (
                        isinstance(item, dict)
                        and "version" in item
                        and isinstance(item["version"], str)
                    ):
                        # Extract version if present, otherwise skip
                        result.append(item["version"])
                        # Skip non-string dict items for safety
            elif isinstance(deps_data, str):
                result.append(deps_data)

            return result

        # Check for dependencies in various locations
        dependencies: list[str] = []

        # Project dependencies: [project].dependencies
        if "project" in data and "dependencies" in data["project"]:
            deps = data["project"]["dependencies"]
            dependencies.extend(extract_string_dependencies(deps))

        # Poetry format: [tool.poetry.dependencies]
        if "tool" in data and "poetry" in data["tool"] and "dependencies" in data["tool"]["poetry"]:
            poetry_deps = data["tool"]["poetry"]["dependencies"]
            dependencies.extend(extract_string_dependencies(poetry_deps))

        # Ensure we found dependencies
        assert dependencies, "No dependencies found in pyproject.toml"

        # Validate each dependency has a version constraint
        for dep in dependencies:
            dep_str = str(dep).strip()

            # Skip empty dependencies
            if not dep_str:
                continue

            # Check if dependency has a version constraint
            # Must contain an operator (==, >=, <=, ~=, ^, etc.) or be a URL/git reference
            has_version_constraint = (
                any(op in dep_str for op in ["==", ">=", "<=", "~=", "!=", "^", "~"])
                or dep_str.startswith(("git+", "hg+", "svn+", "bzr+", "http://", "https://"))
                or "@" in dep_str  # For pip installable URLs
            )

            assert has_version_constraint, (
                f"Dependency '{dep_str}' does not specify a version constraint. "
                f"Use format like 'package>=1.0.0' or 'package==1.2.3'"
            )


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
                # Match lines with "uses:" that don't have "@" for version pinning
                # Handle both single-line (- uses: action) and multi-line (uses: action) formats
                if re.search(r"^\s*-?\s*uses:\s+[\w/_-]+", line) and "@" not in line:
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

        # Find safety command path
        safety_cmd = shutil.which("safety")
        if not safety_cmd:
            pytest.skip("safety command not found in PATH")

        # Run safety scan against requirements.txt (new command)
        # Fallback to deprecated check command if scan fails
        result = None
        try:
            # Primary call uses full path from shutil.which() (no S607 needed)
            result = subprocess.run(  # noqa: S603
                [
                    safety_cmd,
                    "scan",
                    "--output",
                    "json",
                    "--target",
                    str(requirements_file.parent),
                ],
                capture_output=True,
                text=True,
                timeout=60,  # Add timeout to prevent hanging
            )
        except subprocess.TimeoutExpired:
            # Fallback uses partial path "safety" - needs both S603 and S607
            result = subprocess.run(  # noqa: S603
                ["safety", "check", "--file", str(requirements_file), "--json"],  # noqa: S607
                capture_output=True,
                text=True,
            )

        # Always parse JSON output to provide detailed vulnerability information
        # even when returncode is 0 (ignored vulnerabilities)
        if result and result.stdout:
            try:
                import json

                # Extract JSON from output using robust strategy
                stdout_content = result.stdout.strip()
                safety_data = None

                # Try multiple JSON extraction strategies
                # Store start indices to avoid redundant find() calls
                start_brace = stdout_content.find("{")
                start_bracket = stdout_content.find("[")

                strategies = [
                    stdout_content,  # Full stripped stdout
                    (
                        stdout_content[start_brace : stdout_content.rfind("}") + 1]
                        if start_brace >= 0
                        else ""
                    ),  # First '{' to last '}'
                    (
                        stdout_content[start_bracket : stdout_content.rfind("]") + 1]
                        if start_bracket >= 0
                        else ""
                    ),  # First '[' to last ']'
                ]

                for strategy_content in strategies:
                    if not strategy_content:
                        continue
                    try:
                        safety_data = json.loads(strategy_content)
                        break  # Success, exit the loop
                    except json.JSONDecodeError:
                        continue  # Try next strategy

                if safety_data is None:
                    raise json.JSONDecodeError("No valid JSON found in output", stdout_content, 0)

                # Format vulnerability details based on different JSON structures
                vulnerability_details = []
                ignored_vulnerability_details = []

                # Handle different JSON structures
                vulnerabilities = []
                ignored_vulnerabilities = []

                if isinstance(safety_data, list):
                    vulnerabilities = safety_data
                elif isinstance(safety_data, dict):
                    # Check common keys for vulnerability data
                    for key in ["vulnerabilities", "vulnerability", "issues", "findings"]:
                        if key in safety_data and isinstance(safety_data[key], list):
                            vulnerabilities = safety_data[key]
                            break

                    # Also check for ignored_vulnerabilities
                    if "ignored_vulnerabilities" in safety_data and isinstance(
                        safety_data["ignored_vulnerabilities"], list
                    ):
                        ignored_vulnerabilities = safety_data["ignored_vulnerabilities"]

                # Process actual vulnerabilities
                for vuln in vulnerabilities:
                    if isinstance(vuln, dict):
                        package = vuln.get(
                            "package", vuln.get("name", vuln.get("package_name", "unknown"))
                        )
                        version = vuln.get(
                            "installed_version",
                            vuln.get("version", vuln.get("current_version", "unknown")),
                        )
                        vulnerability_id = vuln.get(
                            "vulnerability_id", vuln.get("cve", vuln.get("id", "unknown"))
                        )
                        advisory = vuln.get(
                            "advisory",
                            vuln.get("description", vuln.get("summary", "No advisory available")),
                        )

                        vulnerability_details.append(
                            f"  • {package}=={version} - {vulnerability_id}: {advisory}"
                        )

                # Process ignored vulnerabilities
                for vuln in ignored_vulnerabilities:
                    if isinstance(vuln, dict):
                        package = vuln.get(
                            "package", vuln.get("name", vuln.get("package_name", "unknown"))
                        )
                        version = vuln.get(
                            "installed_version",
                            vuln.get("version", vuln.get("current_version", "unknown")),
                        )
                        vulnerability_id = vuln.get(
                            "vulnerability_id", vuln.get("cve", vuln.get("id", "unknown"))
                        )
                        advisory = vuln.get(
                            "advisory",
                            vuln.get("description", vuln.get("summary", "No advisory available")),
                        )
                        ignored_reason = vuln.get("ignored_reason", "Ignored")

                        ignored_vulnerability_details.append(
                            f"  • {package}=={version} - {vulnerability_id}: {advisory} "
                            f"(IGNORED: {ignored_reason})"
                        )

                # Fail if there are actual vulnerabilities
                if vulnerability_details:
                    error_msg = f"Found {len(vulnerability_details)} vulnerable dependencies:\n"
                    error_msg += "\n".join(vulnerability_details)
                    error_msg += (
                        f"\n\nRun 'safety scan --output json --target "
                        f"{requirements_file.parent}' for more details."
                    )
                    raise AssertionError(error_msg)

                # Warn about ignored vulnerabilities but don't fail
                if ignored_vulnerability_details:
                    logging.warning(
                        "Found %d ignored vulnerabilities: %s",
                        len(ignored_vulnerability_details),
                        "; ".join(ignored_vulnerability_details),
                    )
                    logging.warning(
                        "These vulnerabilities are ignored due to unpinned dependencies. "
                        "Consider pinning dependencies for better security."
                    )

            except (json.JSONDecodeError, KeyError, TypeError):
                # Fallback to plain text if JSON parsing fails
                if result.returncode != 0:
                    error_msg = (
                        "Vulnerable dependencies found. Run 'safety scan' for details. "
                        f"Output: {result.stdout[:500]}..."
                    )
                    raise AssertionError(error_msg) from None


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
        """Test that requirements don't use direct URL installs (security risk).

        This test can be configured to either fail strictly or warn only:
        - Set SUPPLY_CHAIN_WARN_ONLY=1 to log warnings instead of failing
        - Default behavior is to fail the test when dangerous URLs are found
        """
        requirements_file = Path("requirements.txt")

        if not requirements_file.exists():
            pytest.skip("requirements.txt not found")

        with open(requirements_file, encoding="utf-8") as f:
            lines = f.readlines()

        dangerous_patterns = [
            r"git\+",
            r"http://",
            r"https://(?!files\.pythonhosted\.org|pypi\.org)",
        ]

        dangerous_urls = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            for pattern in dangerous_patterns:
                if re.search(pattern, line):
                    dangerous_urls.append((line_num, line))
                    break

        if dangerous_urls:
            error_msg = "Found potentially dangerous direct URL installs:\n"
            for line_num, line in dangerous_urls:
                error_msg += f"  Line {line_num}: {line}\n"

            # Check if warning-only mode is enabled via environment variable
            warn_only = os.getenv("SUPPLY_CHAIN_WARN_ONLY", "0") == "1"

            if warn_only:
                logging.warning(error_msg)
            else:
                # Strict enforcement: fail the test
                pytest.fail(error_msg)
