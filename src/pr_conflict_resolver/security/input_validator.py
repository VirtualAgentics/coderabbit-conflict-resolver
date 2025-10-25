"""Input validation and sanitization for security."""

import json
import os
import re
from pathlib import Path
from typing import ClassVar

import tomli
import tomli_w
import yaml


class InputValidator:
    """Comprehensive input validation and sanitization.

    This class provides static methods for validating and sanitizing inputs
    to prevent security vulnerabilities including:
    - Path traversal attacks
    - Code injection
    - File size attacks
    - Malicious content
    """

    # Safe path pattern - alphanumeric, dots, underscores, hyphens, forward slashes
    SAFE_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_./-]+$")

    # Maximum file size: 10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # Allowed file extensions
    ALLOWED_FILE_EXTENSIONS: ClassVar[set[str]] = {
        ".py",
        ".ts",
        ".js",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
    }

    @staticmethod
    def validate_file_path(path: str, base_dir: str | None = None) -> bool:
        """Validate file path is safe (no directory traversal).

        Args:
            path: File path to validate.
            base_dir: Optional base directory to restrict access to.

        Returns:
            bool: True if the path is safe, False otherwise.

        Example:
            >>> InputValidator.validate_file_path("src/file.py")
            True
            >>> InputValidator.validate_file_path("../../etc/passwd")
            False
        """
        if not path or not isinstance(path, str):
            return False

        # Normalize path
        normalized = os.path.normpath(path)

        # Check for directory traversal attempts
        if ".." in normalized:
            return False

        # Check for absolute paths (disallowed unless base_dir is specified)
        if (
            normalized.startswith("/")
            or (os.name == "nt" and len(normalized) > 1 and normalized[1] == ":")
        ) and not base_dir:
            return False

        # Check for safe characters
        if not InputValidator.SAFE_PATH_PATTERN.match(normalized):
            return False

        # If base_dir is specified, ensure path is within it
        if base_dir:
            try:
                # Resolve to absolute paths
                abs_path = Path(normalized).resolve()
                abs_base = Path(base_dir).resolve()

                # Check if path is within base directory
                try:
                    abs_path.relative_to(abs_base)
                except ValueError:
                    # Path is not relative to base_dir
                    return False
            except (OSError, RuntimeError):
                # Path resolution failed
                return False

        return True

    @staticmethod
    def validate_file_size(file_path: Path) -> bool:
        """Validate file size is within limits.

        Args:
            file_path: Path to the file to validate.

        Returns:
            bool: True if file size is within limits, False otherwise.

        Raises:
            FileNotFoundError: If file does not exist.
            OSError: If file cannot be accessed.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            return False

        file_size = file_path.stat().st_size
        return file_size <= InputValidator.MAX_FILE_SIZE

    @staticmethod
    def validate_file_extension(path: str) -> bool:
        """Validate file extension is allowed.

        Args:
            path: File path to check.

        Returns:
            bool: True if extension is allowed, False otherwise.
        """
        if not path:
            return False

        ext = Path(path).suffix.lower()
        return ext in InputValidator.ALLOWED_FILE_EXTENSIONS

    @staticmethod
    def sanitize_content(content: str, file_type: str) -> tuple[str, list[str]]:
        r"""Sanitize file content based on type.

        Removes potentially malicious content and validates structure for
        structured file formats.

        Args:
            content: Content to sanitize.
            file_type: File type (json, yaml, toml, python, etc.).

        Returns:
            tuple: (sanitized_content, warnings) where warnings is a list of
                   security issues found.

        Example:
            >>> content = "data: value\\x00"
            >>> clean, warnings = InputValidator.sanitize_content(content, "yaml")
            >>> "\\x00" not in clean
            True
        """
        if not content:
            return content, []

        warnings: list[str] = []

        # Remove null bytes (common in exploits)
        if "\x00" in content:
            content = content.replace("\x00", "")
            warnings.append("Removed null bytes from content")

        # Validate structure for structured formats
        file_type_lower = file_type.lower()

        if file_type_lower in ("json", ".json"):
            content, json_warnings = InputValidator._sanitize_json(content)
            warnings.extend(json_warnings)

        elif file_type_lower in ("yaml", "yml", ".yaml", ".yml"):
            content, yaml_warnings = InputValidator._sanitize_yaml(content)
            warnings.extend(yaml_warnings)

        elif file_type_lower in ("toml", ".toml"):
            content, toml_warnings = InputValidator._sanitize_toml(content)
            warnings.extend(toml_warnings)

        # Check for suspicious patterns
        suspicious_patterns = [
            (r"!!python/object", "Detected Python object serialization in YAML"),
            (r"__import__", "Detected __import__ usage"),
            (r"eval\s*\(", "Detected eval() usage"),
            (r"exec\s*\(", "Detected exec() usage"),
            (r"os\.system", "Detected os.system usage"),
            (r"subprocess\.", "Detected subprocess usage"),
        ]

        for pattern, warning_msg in suspicious_patterns:
            if re.search(pattern, content):
                warnings.append(warning_msg)

        return content, warnings

    @staticmethod
    def _sanitize_json(content: str) -> tuple[str, list[str]]:
        """Sanitize and validate JSON content.

        Args:
            content: JSON content to validate.

        Returns:
            tuple: (content, warnings)
        """
        warnings: list[str] = []

        try:
            # Parse JSON to validate structure
            parsed = json.loads(content)

            # Re-serialize to ensure clean format
            content = json.dumps(parsed, indent=2)

        except json.JSONDecodeError as e:
            warnings.append(f"Invalid JSON structure: {e}")

        return content, warnings

    @staticmethod
    def _sanitize_yaml(content: str) -> tuple[str, list[str]]:
        """Sanitize and validate YAML content.

        Args:
            content: YAML content to validate.

        Returns:
            tuple: (content, warnings)
        """
        warnings: list[str] = []

        try:
            # Use safe_load to prevent code execution
            parsed = yaml.safe_load(content)

            # Check for None (empty YAML)
            if parsed is None:
                return content, warnings

            # Re-serialize using safe_dump
            content = yaml.safe_dump(parsed, default_flow_style=False)

        except yaml.YAMLError as e:
            warnings.append(f"Invalid YAML structure: {e}")

        return content, warnings

    @staticmethod
    def _sanitize_toml(content: str) -> tuple[str, list[str]]:
        """Sanitize and validate TOML content.

        Args:
            content: TOML content to validate.

        Returns:
            tuple: (content, warnings)
        """
        warnings: list[str] = []

        try:
            # Parse TOML to validate structure
            parsed = tomli.loads(content)

            # Re-serialize to ensure clean format
            content = tomli_w.dumps(parsed)

        except tomli.TOMLDecodeError as e:
            warnings.append(f"Invalid TOML structure: {e}")

        return content, warnings

    @staticmethod
    def validate_line_range(start_line: int, end_line: int, max_lines: int | None = None) -> bool:
        """Validate line range is valid.

        Args:
            start_line: Starting line number (1-indexed).
            end_line: Ending line number (1-indexed).
            max_lines: Optional maximum line number to check against.

        Returns:
            bool: True if line range is valid, False otherwise.
        """
        # Check basic validity
        if start_line < 1 or end_line < 1:
            return False

        if start_line > end_line:
            return False

        # Check against max_lines if provided
        return max_lines is None or end_line <= max_lines

    @staticmethod
    def sanitize_github_url(url: str) -> bool:
        """Validate GitHub URL is legitimate.

        Args:
            url: URL to validate.

        Returns:
            bool: True if URL is a valid GitHub URL, False otherwise.
        """
        if not url or not isinstance(url, str):
            return False

        # Check for GitHub domains
        allowed_domains = [
            "https://github.com/",
            "https://api.github.com/",
            "https://raw.githubusercontent.com/",
        ]

        return any(url.startswith(domain) for domain in allowed_domains)
