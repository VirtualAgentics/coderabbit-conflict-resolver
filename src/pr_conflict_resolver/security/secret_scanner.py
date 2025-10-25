"""Secret detection and prevention system."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar


@dataclass
class SecretFinding:
    """Represents a detected secret."""

    secret_type: str
    matched_text: str  # Redacted/truncated for safety
    line_number: int
    column: int
    severity: str  # "high", "medium", "low"
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

    # Common secret patterns (regex, type, severity)
    # NOTE: Order matters - more specific patterns should come before generic ones
    PATTERNS: ClassVar[list[tuple[str, str, str]]] = [
        # GitHub tokens (most specific first)
        (r"ghp_[A-Za-z0-9]{36}", "github_personal_token", "high"),
        (r"gho_[A-Za-z0-9]{36}", "github_oauth_token", "high"),
        (r"ghs_[A-Za-z0-9]{36}", "github_server_token", "high"),
        (r"ghr_[A-Za-z0-9]{36}", "github_refresh_token", "high"),
        # AWS keys
        (r"\bAKIA[0-9A-Z]{16}\b", "aws_access_key", "high"),
        (
            r"(?i)aws(.{0,20})?['\"][0-9a-zA-Z/+]{30,}['\"]",
            "aws_secret_key",
            "high",
        ),
        # OpenAI API keys
        (r"\bsk-[A-Za-z0-9]{32,}\b", "openai_api_key", "high"),
        # JWT tokens
        (
            r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
            "jwt_token",
            "high",
        ),
        # Private keys
        (r"-----BEGIN.*PRIVATE KEY-----", "private_key", "high"),
        # Slack tokens
        (
            r"\bxox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[A-Za-z0-9]{24,}\b",
            "slack_token",
            "high",
        ),
        # Google OAuth
        (r"\bya29\.[0-9A-Za-z\-_]+\b", "google_oauth", "high"),
        # Azure connection strings
        (
            r"(?i)DefaultEndpointsProtocol=https;.*AccountKey=[A-Za-z0-9+/=]{88}",
            "azure_connection_string",
            "high",
        ),
        # Database URLs with passwords
        (
            r"(?i)(postgres|mysql|mongodb)://[^:\s]+:[^@\s]+@[^/\s]+",
            "database_url_with_password",
            "high",
        ),
        # Generic API keys (less specific, lower priority)
        (
            r"(?i)\bapi[_-]?key['\"\s:=]+[A-Za-z0-9_\-]{20,}\b",
            "generic_api_key",
            "medium",
        ),
        # Passwords in common formats
        (
            r"(?i)\b(password|passwd|pwd)['\"\s:=]+[^\s'\">]{8,}\b",
            "password",
            "medium",
        ),
        # Secrets in common formats
        (
            r"(?i)\bsecret['\"\s:=]+[A-Za-z0-9_\-]{20,}\b",
            "generic_secret",
            "medium",
        ),
        # Generic tokens (lowest priority, most generic)
        (r"(?i)\btoken['\"\s:=]+[A-Za-z0-9_\-]{32,}\b", "generic_token", "medium"),
    ]

    # False positive patterns - common test/example values
    FALSE_POSITIVE_PATTERNS: ClassVar[list[str]] = [
        r"(?i)(example|test|dummy|fake|sample|placeholder|your[-_])",
        r"(?i)(xxx+|yyy+|zzz+|aaa+)",
        r"(?i)(replace[-_]me|change[-_]me|insert[-_]here)",
        r"(?i)(<your|<api|<secret|<token)",
        r"^\*+$",  # All asterisks
        r"^x+$",  # All x's
        r"(?i)(redacted|hidden|masked)",
    ]

    @staticmethod
    def scan_content(content: str) -> list[SecretFinding]:
        """Scan content for potential secrets.

        Args:
            content: Text content to scan.

        Returns:
            list[SecretFinding]: List of detected secrets.

        Example:
            >>> scanner = SecretScanner()
            >>> findings = scanner.scan_content("api_key=ghp_1234567890123456789012345678901234")
            >>> len(findings) > 0
            True
        """
        findings: list[SecretFinding] = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, start=1):
            for pattern, secret_type, severity in SecretScanner.PATTERNS:
                matches = re.finditer(pattern, line)

                for match in matches:
                    matched_text = match.group(0)

                    # Check for false positives
                    if SecretScanner._is_false_positive(matched_text, line):
                        continue

                    # Redact the matched text for safety
                    redacted_text = SecretScanner._redact_secret(matched_text)

                    finding = SecretFinding(
                        secret_type=secret_type,
                        matched_text=redacted_text,
                        line_number=line_num,
                        column=match.start() + 1,
                        severity=severity,
                        context=line.strip()[:50],  # First 50 chars of line
                    )
                    findings.append(finding)

        return findings

    @staticmethod
    def scan_file(file_path: Path) -> list[SecretFinding]:
        """Scan a file for potential secrets.

        Args:
            file_path: Path to the file to scan.

        Returns:
            list[SecretFinding]: List of detected secrets.

        Raises:
            FileNotFoundError: If file does not exist.
            OSError: If file cannot be read.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            return SecretScanner.scan_content(content)
        except OSError as e:
            raise OSError(f"Failed to read file {file_path}: {e}") from e

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
            if re.search(pattern, matched_text) or re.search(pattern, context):
                return True

        # Check if it's in a comment or documentation
        return any(
            marker in context.lower()
            for marker in ["#", "//", "/*", "<!--", "example:", "e.g.", "```"]
        ) and any(keyword in context.lower() for keyword in ["example", "test", "dummy", "sample"])

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
    def has_secrets(content: str) -> bool:
        """Check if content contains any secrets.

        Args:
            content: Text content to check.

        Returns:
            bool: True if secrets are detected, False otherwise.
        """
        return len(SecretScanner.scan_content(content)) > 0

    @staticmethod
    def get_summary(findings: list[SecretFinding]) -> dict[str, int]:
        """Get a summary of findings by type and severity.

        Args:
            findings: List of secret findings.

        Returns:
            dict: Summary with counts by type and severity.
        """
        summary: dict[str, int] = {
            "total": len(findings),
            "high": 0,
            "medium": 0,
            "low": 0,
        }

        type_counts: dict[str, int] = {}

        for finding in findings:
            # Count by severity
            summary[finding.severity] = summary.get(finding.severity, 0) + 1

            # Count by type
            type_counts[finding.secret_type] = type_counts.get(finding.secret_type, 0) + 1

        # Add type counts to summary (dict is extensible)
        for secret_type, count in type_counts.items():
            summary[f"type_{secret_type}"] = count

        return summary
