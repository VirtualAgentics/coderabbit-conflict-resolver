# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Secret detection and prevention system."""

import logging
import re
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from re import Pattern
from typing import TYPE_CHECKING, ClassVar, TypeAlias

if TYPE_CHECKING:
    from review_bot_automator.security.config import SecurityConfig

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Severity levels for secret findings."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Type alias for the complete summary including dynamic keys
# Contains fixed fields: "total", "high", "medium", "low"
# Plus dynamic fields: "type_<secret_type>" for each secret type found
SummaryDict: TypeAlias = dict[str, int]

# Type alias for secret detection patterns
# Tuple containing: (regex pattern, secret type name, severity level)
PatternDef: TypeAlias = tuple[Pattern[str], str, Severity]


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """Represents a detected secret.

    This dataclass is immutable and memory-efficient, storing information
    about a secret that was found during scanning.

    Attributes:
        secret_type: The type of secret detected (e.g., 'github_personal_token').
        matched_text: The redacted/truncated secret text for safety.
        line_number: The line number where the secret was found (1-based).
        column: The column position where the secret starts (1-based).
        severity: The severity level of the secret (Severity.HIGH/MEDIUM/LOW).
        context: Surrounding text for false positive detection. Defaults to empty string.
    """

    secret_type: str
    matched_text: str  # Redacted/truncated for safety
    line_number: int
    column: int
    severity: Severity
    context: str = ""  # Surrounding text for false positive detection


class SecretScanner:
    """Scan for accidental secret exposure.

    This class provides pattern-based detection of common secrets including:
    - API keys and tokens
    - Passwords
    - Private keys
    - OAuth tokens
    - Cloud provider credentials
    """

    # Common secret patterns (compiled regex, type, severity)
    # NOTE: Order matters - more specific patterns should come before generic ones
    PATTERNS: ClassVar[list[PatternDef]] = [
        # GitHub tokens (most specific first)
        (re.compile(r"ghp_[A-Za-z0-9]{36}"), "github_personal_token", Severity.HIGH),
        (re.compile(r"gho_[A-Za-z0-9]{36}"), "github_oauth_token", Severity.HIGH),
        (re.compile(r"ghs_[A-Za-z0-9]{36}"), "github_server_token", Severity.HIGH),
        (re.compile(r"ghr_[A-Za-z0-9]{36}"), "github_refresh_token", Severity.HIGH),
        # AWS keys
        (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws_access_key", Severity.HIGH),
        (
            re.compile(r"(?i)aws(.{0,20})?['\"][0-9a-zA-Z/+]{30,}['\"]"),
            "aws_secret_key",
            Severity.HIGH,
        ),
        # OpenAI API keys
        (re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"), "openai_api_key", Severity.HIGH),
        # JWT tokens
        (
            re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
            "jwt_token",
            Severity.HIGH,
        ),
        # Private keys
        (re.compile(r"-----BEGIN.*PRIVATE KEY-----"), "private_key", Severity.HIGH),
        # Slack tokens
        (
            re.compile(r"\bxox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24,}\b"),
            "slack_token",
            Severity.HIGH,
        ),
        # Google OAuth
        (re.compile(r"\bya29\.[0-9A-Za-z\-_]+\b"), "google_oauth", Severity.HIGH),
        # Azure connection strings
        (
            re.compile(r"(?i)DefaultEndpointsProtocol=https;.*AccountKey=[A-Za-z0-9+/=]{88}"),
            "azure_connection_string",
            Severity.HIGH,
        ),
        # Database URLs with passwords
        (
            re.compile(r"(?i)(postgres|mysql|mongodb)://[^:\s]+:[^@\s]+@[^/\s]+"),
            "database_url_with_password",
            Severity.HIGH,
        ),
        # Generic API keys (less specific, lower priority)
        (
            re.compile(r"(?i)\bapi[_-]?key['\"\s:=]+[A-Za-z0-9_\-]{20,}\b"),
            "generic_api_key",
            Severity.MEDIUM,
        ),
        # Passwords in common formats
        (
            re.compile(r"(?i)\b(password|passwd|pwd)['\"\s:=]+[^\s'\">]{8,}\b"),
            "password",
            Severity.MEDIUM,
        ),
        # Secrets in common formats
        (
            re.compile(r"(?i)\bsecret['\"\s:=]+[A-Za-z0-9_\-]{20,}\b"),
            "generic_secret",
            Severity.MEDIUM,
        ),
        # Generic tokens (lowest priority, most generic)
        (
            re.compile(r"(?i)\btoken['\"\s:=]+[A-Za-z0-9_\-]{32,}\b"),
            "generic_token",
            Severity.MEDIUM,
        ),
    ]

    # False positive patterns - common test/example values (precompiled for performance)
    FALSE_POSITIVE_PATTERNS: ClassVar[list[Pattern[str]]] = [
        re.compile(r"(?i)(example|test|dummy|fake|sample|placeholder|your[-_])"),
        re.compile(r"(?i)(xxx+|yyy+|zzz+|aaa+)"),
        re.compile(r"(?i)(replace[-_]me|change[-_]me|insert[-_]here)"),
        re.compile(r"(?i)(<your|<api|<secret|<token)"),
        re.compile(r"^\*+$"),  # All asterisks
        re.compile(r"^x+$"),  # All x's
        re.compile(r"(?i)(redacted|hidden|masked)"),
    ]

    @staticmethod
    def scan_content(
        content: str, stop_on_first: bool = False, config: "SecurityConfig | None" = None
    ) -> list[SecretFinding]:
        """Scan content for potential secrets.

        Args:
            content: Text content to scan.
            stop_on_first: If True, stop scanning after finding the first secret.
            config: Optional SecurityConfig to use for scanning behavior.
                    If None or enable_secret_scanning is True, scanning proceeds.
                    If enable_secret_scanning is False, returns empty list.

        Returns:
            list[SecretFinding]: List of detected secrets.

        Example:
            >>> scanner = SecretScanner()
            >>> content = "api_key=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            >>> findings = scanner.scan_content(content)
            >>> len(findings) > 0
            True
        """
        # Check if secret scanning is disabled in config
        if config and not config.enable_secret_scanning:
            logger.debug("Secret scanning disabled by configuration")
            return []

        logger.debug("Starting content scan, %d lines to process", len(content.split("\n")))
        findings: list[SecretFinding] = []

        # Delegate to generator and collect findings
        for finding in SecretScanner.scan_content_generator(content):
            findings.append(finding)

            # Early exit if we only need to find the first secret
            if stop_on_first:
                logger.debug("Found first secret, stopping scan at line %d", finding.line_number)
                break

        logger.debug("Content scan completed, found %d total secrets", len(findings))
        return findings

    @staticmethod
    def scan_content_generator(content: str) -> Generator[SecretFinding, None, None]:
        """Scan content for potential secrets, yielding findings as they are found.

        This is a generator version that yields findings one at a time, allowing
        for early exit when only checking if secrets exist.

        Args:
            content: Text content to scan.

        Yields:
            SecretFinding: Individual secret findings as they are discovered.

        Example:
            >>> scanner = SecretScanner()
            >>> content = "api_key=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
            >>> for finding in scanner.scan_content_generator(content):
            ...     print(f"Found {finding.secret_type}")
            ...     break  # Early exit on first finding
        """
        logger.debug(
            "Starting generator content scan, %d lines to process", len(content.split("\n"))
        )
        lines = content.split("\n")
        findings_count = 0

        for line_num, line in enumerate(lines, start=1):
            # Track occupied spans to prevent duplicate findings from overlapping patterns
            occupied_spans: list[tuple[int, int]] = []

            for pattern, secret_type, severity in SecretScanner.PATTERNS:
                matches = pattern.finditer(line)

                for match in matches:
                    matched_text = match.group(0)
                    match_start = match.start()
                    match_end = match.end()

                    # Skip match if it overlaps any occupied span
                    # Two spans overlap if: new starts before span ends AND
                    # new ends after span starts
                    if any(
                        match_start < span_end and match_end > span_start
                        for span_start, span_end in occupied_spans
                    ):
                        continue

                    # Check for false positives
                    if SecretScanner._is_false_positive(matched_text, line):
                        continue

                    # Redact the matched text for safety
                    redacted_text = SecretScanner._redact_secret(matched_text)

                    finding = SecretFinding(
                        secret_type=secret_type,
                        matched_text=redacted_text,
                        line_number=line_num,
                        column=match_start + 1,
                        severity=severity,
                        context=line.strip()[:50],  # First 50 chars of line
                    )
                    findings_count += 1
                    # Mark this span as occupied
                    occupied_spans.append((match_start, match_end))
                    yield finding

            # Throttled logging: only log every 100 lines to reduce noise
            if line_num % 100 == 0:
                logger.debug("Scanned line %d: total findings so far: %d", line_num, findings_count)

        logger.debug("Generator content scan completed")

    @staticmethod
    def scan_file(file_path: Path, config: "SecurityConfig | None" = None) -> list[SecretFinding]:
        """Scan a file for potential secrets.

        Args:
            file_path: Path to the file to scan.
            config: Optional SecurityConfig to use for scanning behavior.
                    If None or enable_secret_scanning is True, scanning proceeds.
                    If enable_secret_scanning is False, returns empty list.

        Returns:
            list[SecretFinding]: List of detected secrets.

        Raises:
            FileNotFoundError: If file does not exist.
            OSError: If file cannot be read.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path.resolve()}")

        try:
            logger.debug("Scanning file for secrets: %s", file_path)
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            findings = SecretScanner.scan_content(content, config=config)
            logger.debug("Finished scanning %s: %d findings", file_path, len(findings))
            return findings
        except OSError as e:
            logger.exception("Failed to read file %s", file_path)
            raise OSError(f"Failed to read file {file_path.resolve()}: {e}") from e

    @staticmethod
    def _is_false_positive(matched_text: str, context: str) -> bool:
        """Check if a finding is likely a false positive.

        Args:
            matched_text: The matched secret text.
            context: Surrounding context (full line).

        Returns:
            bool: True if likely a false positive, False otherwise.
        """
        # Check against false positive patterns
        for pattern in SecretScanner.FALSE_POSITIVE_PATTERNS:
            if pattern.search(matched_text) or pattern.search(context):
                # Log only numeric metadata - no secret-like content
                match_length = len(matched_text)
                context_length = len(context)
                has_special_chars = any(c in context for c in ["#", "//", "/*", "<!--"])

                logger.debug(
                    "False positive detected: match_length=%d, context_length=%d, has_comment=%s",
                    match_length,
                    context_length,
                    has_special_chars,
                )
                return True

        # Check if it's in a comment or documentation
        context_lower = context.lower()
        has_comment_marker = any(
            marker in context_lower
            for marker in ["#", "//", "/*", "<!--", "example:", "e.g.", "```"]
        )
        has_test_keyword = any(
            keyword in context_lower for keyword in ["example", "test", "dummy", "sample"]
        )
        return has_comment_marker and has_test_keyword

    @staticmethod
    def _redact_secret(secret: str) -> str:
        """Redact a secret for safe display.

        Args:
            secret: The secret to redact.

        Returns:
            str: Redacted version showing only first few and last few characters.
        """
        if len(secret) <= 8:
            return "*" * len(secret)

        # Show first 4 and last 4 characters
        return f"{secret[:4]}...{secret[-4:]}"

    @staticmethod
    def has_secrets(content: str, config: "SecurityConfig | None" = None) -> bool:
        """Check if content contains any secrets.

        Args:
            content: Text content to check.
            config: Optional SecurityConfig to use for scanning behavior.
                    If None or enable_secret_scanning is True, scanning proceeds.
                    If enable_secret_scanning is False, returns False.

        Returns:
            bool: True if any secrets are found, False otherwise.
        """
        # Check if secret scanning is disabled in config
        if config and not config.enable_secret_scanning:
            logger.debug("Secret scanning disabled by configuration, skipping has_secrets check")
            return False

        return bool(SecretScanner.scan_content(content, stop_on_first=True, config=config))

    @staticmethod
    def get_summary(findings: list[SecretFinding]) -> SummaryDict:
        """Get a summary of findings by type and severity.

        Args:
            findings: List of secret findings.

        Returns:
            SummaryDict: Dictionary containing:
                - "total": Total number of findings
                - "high": Number of high severity findings
                - "medium": Number of medium severity findings
                - "low": Number of low severity findings
                - "type_<secret_type>": Number of findings for each secret type
                  (e.g., "type_github_personal_token", "type_aws_access_key")
        """
        summary: SummaryDict = {
            "total": len(findings),
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        type_counts: dict[str, int] = {}

        for finding in findings:
            # Count by severity
            severity_value = finding.severity.value
            summary[severity_value] = summary.get(severity_value, 0) + 1

            # Count by type
            type_counts[finding.secret_type] = type_counts.get(finding.secret_type, 0) + 1

        # Add type counts to summary (dict is extensible)
        for secret_type, count in type_counts.items():
            summary[f"type_{secret_type}"] = count

        return summary
