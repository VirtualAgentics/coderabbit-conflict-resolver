"""Tests for supply chain security.

This module tests dependency security, package validation, and supply chain attacks.
"""

import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from review_bot_automator.utils.version_utils import validate_version_constraint

# Type alias for JSON dictionaries
JSONDict = dict[str, object]


def _extract_json_boundaries(content: str, start_char: str, end_char: str) -> str:
    """Extract JSON content between start and end characters.

    Args:
        content: The content to extract from
        start_char: Opening character (e.g., '{' or '[')
        end_char: Closing character (e.g., '}' or ']')

    Returns:
        Extracted JSON substring, or an empty string if the start character is not
        present, the end character occurs before the start, or no valid JSON
        boundaries are found.
    """
    start_idx = content.find(start_char)
    if start_idx < 0:
        return ""

    end_idx = content.rfind(end_char)
    if end_idx < start_idx:
        return ""

    return content[start_idx : end_idx + 1]


def _parse_safety_json(stdout: str) -> JSONDict | None:
    """Parse JSON from safety command output using multiple strategies.

    Args:
        stdout: Raw stdout from safety command.

    Returns:
        Parsed JSON dict, or None if parsing failed.
    """
    stdout_content = stdout.strip()
    safety_data = None

    # Try multiple JSON extraction strategies
    strategies = [
        stdout_content,  # Full stripped stdout
        _extract_json_boundaries(stdout_content, "{", "}"),  # First '{' to last '}'
        _extract_json_boundaries(stdout_content, "[", "]"),  # First '[' to last ']'
    ]

    for strategy_content in strategies:
        if not strategy_content:
            continue
        try:
            safety_data = json.loads(strategy_content)
            break  # Success, exit the loop
        except json.JSONDecodeError:
            continue  # Try next strategy

    return safety_data


def _extract_vulnerabilities(
    data: JSONDict | list[object],
) -> tuple[list[JSONDict], list[JSONDict]]:
    """Extract vulnerability and ignored_vulnerability lists from JSON.

    Args:
        data: Parsed safety JSON output.

    Returns:
        Tuple of (vulnerabilities, ignored_vulnerabilities).
    """
    vulnerabilities: list[JSONDict] = []
    ignored_vulnerabilities: list[JSONDict] = []

    if isinstance(data, list):
        vulnerabilities = [v for v in data if isinstance(v, dict)]
    elif isinstance(data, dict):
        # Check common keys for vulnerability data
        for key in ["vulnerabilities", "vulnerability", "issues", "findings"]:
            if key in data:
                value = data[key]
                if isinstance(value, list):
                    vulnerabilities = [v for v in value if isinstance(v, dict)]
                    break

        # Also check for ignored_vulnerabilities
        if "ignored_vulnerabilities" in data:
            ignored_value = data["ignored_vulnerabilities"]
            if isinstance(ignored_value, list):
                ignored_vulnerabilities = [v for v in ignored_value if isinstance(v, dict)]

    return vulnerabilities, ignored_vulnerabilities


def _parse_vulnerability_report(
    result: subprocess.CompletedProcess[str],
) -> tuple[list[JSONDict], list[JSONDict], str | None]:
    """Parse vulnerability report from safety command output.

    Args:
        result: Completed process result from safety command.

    Returns:
        Tuple of (vulnerabilities, ignored_vulnerabilities, optional_error_message).
        If error_message is set, it indicates parsing failed and fallback should be used.
    """
    if not result or not result.stdout:
        return [], [], None

    try:
        safety_data = _parse_safety_json(result.stdout)
        if safety_data is None:
            logging.warning(
                "Failed to parse safety JSON output, using fallback: %s",
                result.stdout[:200] if result.stdout else "empty",
            )
            return [], [], "Failed to parse safety JSON output"

        vulnerabilities, ignored_vulnerabilities = _extract_vulnerabilities(safety_data)
        return vulnerabilities, ignored_vulnerabilities, None

    except (json.JSONDecodeError, KeyError, TypeError):
        return [], [], "JSON parsing failed"


def _validate_no_vulnerabilities(vulnerabilities: list[JSONDict], ignored: list[JSONDict]) -> None:
    """Validate that no real vulnerabilities exist and log ignored ones.

    Args:
        vulnerabilities: List of actual vulnerability dictionaries.
        ignored: List of ignored vulnerability dictionaries.

    Raises:
        AssertionError: If real vulnerabilities are found.
    """
    vulnerability_details = _format_vulnerability_details(vulnerabilities, is_ignored=False)
    ignored_vulnerability_details = _format_vulnerability_details(ignored, is_ignored=True)

    # Fail if there are actual vulnerabilities
    if vulnerability_details:
        error_msg = f"Found {len(vulnerability_details)} vulnerable dependencies:\n"
        error_msg += "\n".join(vulnerability_details)
        error_msg += (
            "\n\nRun 'safety scan --output json --target "
            f"{Path('requirements.txt').parent}' for more details."
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


def _format_vulnerability_details(
    vulnerabilities: list[JSONDict], is_ignored: bool = False
) -> list[str]:
    """Format vulnerability dictionaries into human-readable strings.

    Args:
        vulnerabilities: List of vulnerability dictionaries.
        is_ignored: Whether these are ignored vulnerabilities (adds IGNORED prefix).

    Returns:
        List of formatted vulnerability strings.
    """
    vulnerability_details = []

    for vuln in vulnerabilities:
        if isinstance(vuln, dict):
            package = vuln.get("package", vuln.get("name", vuln.get("package_name", "unknown")))
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

            if is_ignored:
                ignored_reason = vuln.get("ignored_reason", "Ignored")
                vulnerability_details.append(
                    f"  • {package}=={version} - {vulnerability_id}: "
                    f"{advisory} (IGNORED: {ignored_reason})"
                )
            else:
                vulnerability_details.append(
                    f"  • {package}=={version} - {vulnerability_id}: {advisory}"
                )

    return vulnerability_details


def _extract_string_dependencies(
    deps_data: dict[str, object] | list[object] | str,
) -> list[str]:
    """Safely extract string dependencies from various data structures.

    Args:
        deps_data: Dependency data from TOML file (dict, list, or str).

    Returns:
        List of dependency strings extracted from the data structure.
    """
    result: list[str] = []

    if isinstance(deps_data, dict):
        for value in deps_data.values():
            if isinstance(value, str):
                result.append(value)
            elif (
                isinstance(value, dict) and "version" in value and isinstance(value["version"], str)
            ):
                result.append(value["version"])
    elif isinstance(deps_data, list):
        for item in deps_data:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict) and "version" in item and isinstance(item["version"], str):
                result.append(item["version"])
    elif isinstance(deps_data, str):
        result.append(deps_data)

    return result


def _run_safety_scan(
    safety_cmd: str, requirements_file: Path, timeout: int = 60
) -> subprocess.CompletedProcess[str] | None:
    """Run safety CLI scan with fallback to legacy command.

    Args:
        safety_cmd: Path to safety executable.
        requirements_file: Path to requirements.txt file.
        timeout: Timeout in seconds for subprocess.

    Returns:
        CompletedProcess object on success, None on timeout.
    """
    # Try new "scan --output json --target <parent>" and fall back once.
    try:
        return subprocess.run(  # noqa: S603
            [safety_cmd, "scan", "--output", "json", "--target", str(requirements_file.parent)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        try:
            return subprocess.run(  # noqa: S603
                [safety_cmd, "check", "--file", str(requirements_file), "--json"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None


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
            # Check if version constraint is valid using utility
            require_exact_pin = file_path.name == "requirements.txt"
            result = validate_version_constraint(line, require_exact_pin)

            if not result.is_valid:
                pytest.fail(f"Line {line_num}: {result.message}")

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
        with open(pyproject_file, "rb") as f:
            data = tomllib.load(f)

        # Check for dependencies in various locations
        dependencies: list[str] = []

        # Project dependencies: [project].dependencies
        if "project" in data and "dependencies" in data["project"]:
            deps = data["project"]["dependencies"]
            dependencies.extend(_extract_string_dependencies(deps))

        # Poetry format: [tool.poetry.dependencies]
        if "tool" in data and "poetry" in data["tool"] and "dependencies" in data["tool"]["poetry"]:
            poetry_deps = data["tool"]["poetry"]["dependencies"]
            dependencies.extend(_extract_string_dependencies(poetry_deps))

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
                # Check line is not a comment
                if line.strip().startswith("#"):
                    continue

                # Match uses: with proper action format
                match = re.search(r"^\s*-?\s*uses:\s+([^\s#]+)", line)
                if match:
                    uses_value = match.group(1).strip()

                    # Skip local action paths and already pinned actions
                    is_not_local = not uses_value.startswith(("./", "../"))
                    is_not_pinned = "@" not in uses_value
                    if is_not_local and is_not_pinned and "/" in uses_value:
                        # Verify it looks like a GitHub action (owner/repo format)
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
        if importlib.util.find_spec("safety") is None:
            pytest.skip("safety package not installed")

        requirements_file = Path("requirements.txt")
        if not requirements_file.exists():
            pytest.skip("requirements.txt not found")

        # Find safety command path
        safety_cmd = shutil.which("safety")
        if not safety_cmd:
            pytest.skip("safety command not found in PATH")

        # Run safety scan with fallback
        result = _run_safety_scan(safety_cmd, requirements_file)

        # Skip if command timed out
        if result is None:
            pytest.skip("Safety check timed out")

        # Check if safety command failed due to EOF error
        if result.returncode != 0 and result.stderr and "EOF" in result.stderr:
            pytest.skip("Safety command failed with EOF error (likely interactive mode issue)")

        # Parse vulnerability report using helper function
        vulnerabilities, ignored_vulnerabilities, error_message = _parse_vulnerability_report(
            result
        )

        # Handle parsing errors with fallback assertion
        if error_message:
            if result.returncode != 0:
                error_msg = (
                    "Vulnerable dependencies found. Run 'safety scan' for details. "
                    f"Output: {result.stdout[:500] if result.stdout else 'no output'}..."
                )
                raise AssertionError(error_msg)
            # If returncode is 0 but parsing failed, skip (no vulnerabilities detected)
            pytest.skip("Failed to parse safety output but command succeeded")
        else:
            # Validate no real vulnerabilities exist
            _validate_no_vulnerabilities(vulnerabilities, ignored_vulnerabilities)


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
            r"https://(?!(?:files\.pythonhosted\.org|pypi\.org)(?:[:/]|$))",
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
