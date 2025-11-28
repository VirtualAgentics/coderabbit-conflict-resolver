# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Input validation and sanitization for security."""

import json
import logging
import re
import tomllib
import unicodedata
from collections.abc import Set
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urlparse

import tomli_w
import yaml

if TYPE_CHECKING:
    from review_bot_automator.security.config import SecurityConfig

# Module-level logger for structured logging
logger = logging.getLogger(__name__)


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
    # Safe part pattern (single segment) - excludes path separators
    SAFE_PART_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")

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

    # GitHub token prefixes for all supported token types
    GITHUB_TOKEN_PREFIXES: ClassVar[tuple[str, ...]] = (
        "github_pat_",  # Fine-grained Personal Access Token (current best practice)
        "ghp_",  # Classic Personal Access Token
        "gho_",  # OAuth Token
        "ghu_",  # User Token
        "ghs_",  # Server Token
        "ghr_",  # Refresh Token
    )

    # GitHub token minimum length requirements (post-prefix body length)
    GITHUB_PAT_BODY_MIN_LENGTH = 47  # Fine-grained Personal Access Token minimum body length
    GITHUB_CLASSIC_BODY_MIN_LENGTH = 40  # Classic token minimum body length

    # GitHub token prefix lengths (computed dynamically from GITHUB_TOKEN_PREFIXES)
    GITHUB_PAT_PREFIX_LENGTH = len(GITHUB_TOKEN_PREFIXES[0])  # Computed dynamically
    GITHUB_CLASSIC_PREFIX_LENGTH = len(GITHUB_TOKEN_PREFIXES[1])  # Computed dynamically

    @staticmethod
    def validate_file_path(
        path: str, base_dir: str | None = None, allow_absolute: bool = False
    ) -> bool:
        r"""Validate file path is safe (no directory traversal).

        This method implements comprehensive path validation with three explicit cases
        for handling absolute paths, ensuring security while providing flexibility for
        legitimate use cases.

        Security Features:
            - Directory traversal protection (../, ..\\, etc.)
            - Absolute path containment checking
            - Unsafe character detection (;, |, &, `, $, etc.)
            - Null byte detection
            - Unicode normalization (NFC) applied before validation to prevent homograph attacks

        Args:
            path: File path to validate.
            base_dir: Optional base directory to restrict access to. When provided with
                allow_absolute=True, absolute paths must be contained within this directory.
                Required when allow_absolute=True to ensure secure containment.
            allow_absolute: Whether to allow absolute paths (default: False). When True,
                base_dir must also be provided for security containment, otherwise the
                path will be rejected.

        Returns:
            bool: True if the path is safe, False otherwise.

        Three-Case Logic for Absolute Paths:
            1. allow_absolute=True AND base_dir provided: Allow for containment check
            2. allow_absolute=False: Reject unconditionally (default behavior)
            3. allow_absolute=True AND no base_dir: Reject for security
               (prevents unrestricted access)

        Example:
            >>> # Case 1: Absolute path with both allow_absolute=True AND base_dir (allowed)
            >>> InputValidator.validate_file_path("/tmp/file.py",
            ...     base_dir="/tmp", allow_absolute=True)
            True
            >>> # Case 2: Absolute path with default settings (rejected)
            >>> InputValidator.validate_file_path("/tmp/file.py")
            False
            >>> # Case 3: Absolute path with allow_absolute=True but NO base_dir (rejected)
            >>> # This is rejected for security - base_dir is required with allow_absolute=True
            >>> InputValidator.validate_file_path("/tmp/file.py", allow_absolute=True)
            False
            >>> # Relative paths work normally without base_dir
            >>> InputValidator.validate_file_path("src/file.py")
            True
            >>> # Path traversal attempts always rejected
            >>> InputValidator.validate_file_path("../../etc/passwd")
            False

        Warning:
            This method is critical for preventing directory traversal attacks.
            Always validate file paths before using them in file operations.

        See Also:
            validate_github_url: URL validation for GitHub API calls
            validate_github_token: Token format validation
        """
        if not path or not isinstance(path, str):
            logger.warning("File path validation failed: path is None or not a string")
            return False

        # Normalize path to NFC to prevent Unicode homograph attacks
        path = unicodedata.normalize("NFC", path)

        try:
            # Create Path object from normalized input
            input_path = Path(path)

            # Check for directory traversal attempts by examining path parts
            if ".." in input_path.parts:
                logger.warning("Directory traversal attempt detected: %s", path)
                return False

            # Check for absolute paths - handle three explicit cases
            if input_path.is_absolute():
                # Case 1: allow_absolute=True AND base_dir set -> Allow for containment check
                if allow_absolute and base_dir:
                    pass  # Allow for later containment check
                # Case 2: allow_absolute=False/not set -> Reject unconditionally
                elif not allow_absolute:
                    logger.warning("Absolute path disallowed when allow_absolute=False: %s", path)
                    return False
                # Case 3: allow_absolute=True AND no base_dir -> Reject for security
                else:
                    logger.warning(
                        "Absolute path requires base_dir when allow_absolute=True: %s", path
                    )
                    return False

            # Check for safe characters in non-anchor segments only
            anchors = {input_path.drive, input_path.root, input_path.anchor}
            anchors.discard("")  # remove empties
            for part in input_path.parts:
                if part in anchors:
                    continue  # Skip drive/root/anchor (e.g., 'C:' or '/' on POSIX/Windows)
                # Normalize each segment to NFC before validation
                normalized_part = unicodedata.normalize("NFC", part)
                # Validate each part against segment-safe pattern (no '/')
                if normalized_part and not InputValidator.SAFE_PART_PATTERN.match(normalized_part):
                    logger.warning("Unsafe path segment detected in: %s", path)
                    return False

            # If base_dir is specified, ensure path is within it
            if base_dir:
                try:
                    # Resolve base directory strictly to prevent symlink escapes
                    abs_base = Path(base_dir).resolve(strict=True)

                    # Build candidate target by joining base and normalized path
                    candidate = abs_base / input_path

                    # Resolve the candidate path
                    resolved_candidate = candidate.resolve()

                    # Verify containment using is_relative_to
                    if not resolved_candidate.is_relative_to(abs_base):
                        raise ValueError(
                            f"Path {resolved_candidate} is not contained within {abs_base}"
                        )

                except (OSError, RuntimeError, ValueError) as e:
                    # Resolution error or path not contained in base
                    logger.warning("Path containment check failed: %s, error: %s", path, e)
                    return False
        except (OSError, ValueError) as e:
            # Invalid path or path resolution failed
            logger.error("Path validation error for %s: %s", path, e)
            return False

        return True

    @staticmethod
    def validate_file_size(file_path: Path, config: "SecurityConfig | None" = None) -> bool:
        """Validate file size is within limits.

        Args:
            file_path: Path to the file to validate.
            config: Optional SecurityConfig to use for max_file_size limit.
                    If None, uses class default MAX_FILE_SIZE.

        Returns:
            bool: True if file size is within limits, False otherwise.

        Raises:
            FileNotFoundError: If file does not exist.
            OSError: If file cannot be accessed.
        """
        if not file_path.exists():
            logger.error("File not found for size validation: %s", file_path)
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            logger.warning("Path is not a file: %s", file_path)
            return False

        # Use config max_file_size if provided, otherwise use class default
        max_file_size = config.max_file_size if config else InputValidator.MAX_FILE_SIZE

        file_size = file_path.stat().st_size
        if file_size > max_file_size:
            logger.warning(
                "File size exceeds limit: %s (%d bytes > %d bytes)",
                file_path,
                file_size,
                max_file_size,
            )
        return file_size <= max_file_size

    @staticmethod
    def validate_file_extension(path: str, config: "SecurityConfig | None" = None) -> bool:
        """Validate file extension is allowed.

        Args:
            path: File path to check.
            config: Optional SecurityConfig to use for allowed extensions.
                    If None, uses class default ALLOWED_FILE_EXTENSIONS.

        Returns:
            bool: True if extension is allowed, False otherwise.
        """
        if not path:
            return False

        # Use config allowed_extensions if provided, otherwise use class default
        allowed_extensions: Set[str] = (
            config.allowed_extensions if config else InputValidator.ALLOWED_FILE_EXTENSIONS
        )

        ext = Path(path).suffix.lower()
        if ext not in allowed_extensions:
            logger.warning("File extension not allowed: %s in path %s", ext, path)
        return ext in allowed_extensions

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
            logger.warning("Security threat detected: null bytes found in content (removed)")
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
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning("Security threat detected in content: %s", warning_msg)
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
            logger.error("Invalid JSON structure detected: %s", e)
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
            logger.error("Invalid YAML structure detected: %s", e)
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
            parsed = tomllib.loads(content)

            # Re-serialize to ensure clean format
            content = tomli_w.dumps(parsed)

        except tomllib.TOMLDecodeError as e:
            logger.error("Invalid TOML structure detected: %s", e)
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
            logger.warning(
                "Invalid line range: start=%d, end=%d (lines must be >= 1)",
                start_line,
                end_line,
            )
            return False

        if start_line > end_line:
            logger.warning("Invalid line range: start=%d > end=%d", start_line, end_line)
            return False

        # Check against max_lines if provided
        if max_lines is not None and end_line > max_lines:
            logger.warning("Line range exceeds maximum: end=%d > max=%d", end_line, max_lines)
        return max_lines is None or end_line <= max_lines

    # Explicit allowlist of approved GitHub domains and subdomains
    # This prevents subdomain-spoofing attacks (e.g., github.com.evil.com)
    ALLOWED_GITHUB_DOMAINS: ClassVar[frozenset[str]] = frozenset(
        {
            "github.com",
            "api.github.com",
            "raw.githubusercontent.com",
            "gist.github.com",
            "codeload.github.com",  # For downloading repository archives
            # GitHub Enterprise customers may add their domains here
            # Example: "github.internal.company.com"
        }
    )

    @staticmethod
    def validate_github_url(url: str) -> bool:
        """Validate GitHub URL is legitimate using an explicit allowlist.

        Uses an explicit list of approved GitHub domains to prevent
        subdomain spoofing attacks. Only exact domain matches are allowed
        from the predefined allowlist.

        Args:
            url: URL to validate.

        Returns:
            bool: True if URL is a valid GitHub URL, False otherwise.

        Example:
            >>> InputValidator.validate_github_url("https://github.com/user/repo")
            True
            >>> InputValidator.validate_github_url("https://github.com.evil.com/repo")
            False
        """
        if not url or not isinstance(url, str):
            logger.warning("GitHub URL validation failed: URL is None or not a string")
            return False

        try:
            parsed = urlparse(url)

            # Check scheme is https
            if parsed.scheme != "https":
                logger.warning(
                    "GitHub URL validation failed: scheme must be https, got %s",
                    parsed.scheme,
                )
                return False

            # Use hostname instead of netloc to avoid port issues
            hostname = parsed.hostname
            if hostname is None:
                logger.warning("GitHub URL validation failed: no hostname in %s", url)
                return False

            # Normalize hostname to lowercase for case-insensitive comparison
            normalized_hostname = hostname.lower()

            # Check if hostname is in explicit allowlist (exact match only)
            # This prevents attacks like github.com.evil.com from being accepted
            is_allowed = normalized_hostname in InputValidator.ALLOWED_GITHUB_DOMAINS

            if not is_allowed:
                logger.warning("GitHub URL validation failed: hostname not allowed: %s", hostname)
            return is_allowed

        except (ValueError, AttributeError) as e:
            logger.error("GitHub URL validation error for %s: %s", url, e)
            return False

    @staticmethod
    def validate_github_token(token: str | None) -> bool:
        """Validate GitHub token format.

        Validates that a GitHub token has the correct format. GitHub tokens
        typically start with specific prefixes:
        - github_pat_ (Fine-grained Personal Access Token - current best practice)
        - ghp_ (Classic Personal Access Token)
        - gho_ (OAuth Token)
        - ghu_ (User Token)
        - ghs_ (Server Token)
        - ghr_ (Refresh Token)

        Args:
            token: Token string to validate.

        Returns:
            bool: True if token has valid GitHub format, False otherwise.

        Example:
            >>> # Classic token example (ghp_ + base62 body, realistic length)
            >>> InputValidator.validate_github_token(
            ...     "ghp_" + "A1b2C3d4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3"
            ... )
            True
            >>> # Fine-grained token example (github_pat_ + longer base62 body)
            >>> token = "github_pat_" + "Z9Y8X7W6V5U4T3S2R1Q0P9O8N7M6L5K4J3I2H1G0F9E8D7C6B"
            >>> InputValidator.validate_github_token(token)
            True
            >>> InputValidator.validate_github_token("invalid_token")
            False
        """
        if not token or not isinstance(token, str):
            logger.warning("GitHub token validation failed: token is None or not a string")
            return False

        # Normalize whitespace
        token = token.strip()

        # Build regex pattern from class variable prefixes
        # GitHub token pattern: valid prefix + base62 characters only (A-Za-z0-9)
        # Prefixes: github_pat_ (fine-grained PAT ~47 chars), ghp_/gho_/ghu_/ghs_/ghr_ (~40 chars)
        prefix_pattern = "|".join(
            re.escape(prefix) for prefix in InputValidator.GITHUB_TOKEN_PREFIXES
        )
        pattern = rf"^(?:{prefix_pattern})[A-Za-z0-9]+$"
        if not re.match(pattern, token):
            logger.warning(
                "GitHub token validation failed: invalid prefix or characters (expected one of %s)",
                InputValidator.GITHUB_TOKEN_PREFIXES,
            )
            return False

        # Length validation: enforce per-prefix expected lengths
        # Fine-grained PAT: prefix (11 chars) + ~47 base62 = ~58 total
        # Classic tokens (ghp_/gho_/ghu_/ghs_/ghr_): prefix (4 chars) + ~40 base62 = ~44 total
        if token.startswith("github_pat_"):
            # Compute expected length dynamically
            expected_length = (
                InputValidator.GITHUB_PAT_PREFIX_LENGTH + InputValidator.GITHUB_PAT_BODY_MIN_LENGTH
            )
            if len(token) < expected_length:
                logger.warning(
                    "GitHub token validation failed: github_pat_ token too short "
                    "(expected %d chars, got %d)",
                    expected_length,
                    len(token),
                )
                return False
        else:
            # Compute expected length dynamically for classic tokens
            expected_length = (
                InputValidator.GITHUB_CLASSIC_PREFIX_LENGTH
                + InputValidator.GITHUB_CLASSIC_BODY_MIN_LENGTH
            )
            if len(token) < expected_length:
                logger.warning(
                    "GitHub token validation failed: classic token too short "
                    "(expected %d chars, got %d)",
                    expected_length,
                    len(token),
                )
                return False

        return True
