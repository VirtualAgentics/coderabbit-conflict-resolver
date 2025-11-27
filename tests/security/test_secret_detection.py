"""Tests for secret detection and prevention."""

import tempfile
from pathlib import Path

import pytest

from review_bot_automator import SecretScanner


def make_token(prefix: str, suffix_length: int = 36, charset: str | None = None) -> str:
    """Create a test token with the given prefix and suffix length.

    Args:
        prefix: The token prefix (e.g., 'ghp_', 'AKIA', 'sk-')
        suffix_length: The length of the suffix after the prefix (default: 36)
        charset: The character set to use for the suffix (default: alphanumeric lowercase)

    Returns:
        A test token string with the specified prefix and suffix length.
    """
    # Build charset at runtime to avoid hard-coded strings that trigger scanners
    if charset is None:
        charset = "".join([str(i) for i in range(10)]) + "".join(
            [chr(ord("a") + i) for i in range(26)]
        )

    # Create a repeating pattern to ensure we have enough characters
    suffix = (charset * ((suffix_length // len(charset)) + 1))[:suffix_length]
    return f"{prefix}{suffix}"


def build_jwt_token(header: str, payload: str, signature: str) -> str:
    """Build a JWT token from its three parts.

    Args:
        header: The JWT header part
        payload: The JWT payload part
        signature: The JWT signature part

    Returns:
        A complete JWT token string.
    """
    return f"{header}.{payload}.{signature}"


class TestGitHubTokenDetection:
    """Tests for GitHub token detection."""

    @pytest.mark.parametrize(
        "token_prefix,expected_type",
        [
            ("ghp_", "github_personal_token"),
        ],
    )
    def test_github_personal_token(self, token_prefix: str, expected_type: str) -> None:
        """Test detection of GitHub personal access token."""
        # Use clearly fake synthetic token to avoid static analysis flags
        # Pattern requires alphanumeric characters, use a realistic mix
        token = make_token(token_prefix, 36)
        content = f"GITHUB_TOKEN={token}"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        assert any(f.secret_type == expected_type for f in findings)

    def test_github_oauth_token(self) -> None:
        """Test detection of GitHub OAuth token."""
        # Use clearly fake token that matches pattern but cannot be real
        token = make_token("gho_", 36)
        content = f"token: {token}"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        expected_type = "github_oauth_token"
        assert any(f.secret_type == expected_type for f in findings)

    def test_github_server_token(self) -> None:
        """Test detection of GitHub server token with multiple realistic examples."""
        # Test multiple clearly fake but pattern-matching GitHub server tokens
        test_tokens = [
            "ghs_0000000000000000000000000000000000AA",  # All zeros with AA suffix
            "ghs_1111111111111111111111111111111111BB",  # All ones with BB suffix
            "ghs_abcdefghijklmnopqrstuvwxyz1234567890",  # Mixed alphanumeric
            "ghs_1234567890abcdefghijklmnopqrstuvwxyz",  # Mixed alphanumeric (different order)
        ]

        # Test each token individually and collect all findings
        all_findings = []
        for token in test_tokens:
            content = f"server_token = {token}"
            findings = SecretScanner.scan_content(content)
            all_findings.extend(findings)

        # Verify we found at least one GitHub server token
        assert len(all_findings) >= 1
        expected_type = "github_server_token"
        server_token_findings = [f for f in all_findings if f.secret_type == expected_type]
        assert (
            len(server_token_findings) >= 1
        ), f"Expected at least one {expected_type}, found {len(server_token_findings)}"

        # Verify all server token findings have the correct type
        for finding in server_token_findings:
            assert finding.secret_type == expected_type

    def test_github_refresh_token(self) -> None:
        """Test detection of GitHub refresh token."""
        suffix = "".join(["D" for _ in range(36)])
        content = f"refresh: ghr_{suffix}"
        findings = SecretScanner.scan_content(content)

        assert len(findings) == 1
        expected_type = "github_refresh_token"
        assert findings[0].secret_type == expected_type

    def test_no_duplicate_findings_on_overlapping_patterns(self) -> None:
        """Test that overlapping patterns produce a single finding (specific pattern wins)."""
        # GitHub token pattern will match, and generic API key pattern would also match
        # the same substring
        token = make_token("ghp_", 36)
        content = f"api_key={token}"
        findings = SecretScanner.scan_content(content)

        # Should only produce one finding (github_personal_token),
        # not duplicate with generic_api_key
        assert len(findings) == 1
        assert findings[0].secret_type == "github_personal_token"  # noqa: S105


class TestAWSCredentials:
    """Tests for AWS credential detection."""

    def test_aws_access_key(self) -> None:
        """Test detection of AWS access key."""
        token = make_token(
            "AKIA", 16, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        )  # AKIA + 16 uppercase chars
        content = f"AWS_ACCESS_KEY_ID={token}"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        expected_type = "aws_access_key"
        assert any(f.secret_type == expected_type for f in findings)

    def test_aws_secret_key(self) -> None:
        """Test detection of AWS secret key."""
        # Build AWS secret key dynamically to avoid hard-coded secrets
        secret_parts = [
            "wJalrXUtnFEMI",  # First part
            "/K7MDENG/",  # Middle part
            "bPxRfiCY",  # Third part
            "WMXYZ123KEY",  # Final part
        ]
        secret_key = "".join(secret_parts)
        content = f'AWS_SECRET="{secret_key}"'
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        expected_type = "aws_secret_key"
        assert any(f.secret_type == expected_type for f in findings)


class TestAPIKeys:
    """Tests for API key detection."""

    def test_openai_api_key(self) -> None:
        """Test detection of OpenAI API key."""
        # Generate OpenAI API key using shared helper
        token = make_token("sk-", 32)
        content = f"OPENAI_API_KEY={token}"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        expected_type = "openai_api_key"
        assert any(f.secret_type == expected_type for f in findings)


class TestPasswords:
    """Tests for password detection."""

    def test_password_detection(self) -> None:
        """Test detection of passwords."""
        content = 'password="SuperSecret123!"'
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        expected_type = "password"
        assert any(f.secret_type == expected_type for f in findings)


class TestJWTTokens:
    """Tests for JWT token detection."""

    def test_jwt_token(self) -> None:
        """Test detection of JWT tokens."""
        # JWT token parts to avoid hardcoded password warning
        part1 = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        part2 = "eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        part3 = "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        jwt_token = build_jwt_token(part1, part2, part3)
        content = f"token: {jwt_token}"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        # Find JWT-specific finding and verify its classification
        jwt_findings = [f for f in findings if f.secret_type == "jwt_token"]  # noqa: S105
        assert len(jwt_findings) >= 1, "Expected at least one JWT token finding"
        assert jwt_findings[0].severity.name == "HIGH", "JWT tokens should have HIGH severity"


class TestPrivateKeys:
    """Tests for private key detection."""

    def test_private_key(self) -> None:
        """Test detection of private keys."""
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        # Verify the finding is classified as a private key
        private_key_findings = [f for f in findings if f.secret_type == "private_key"]  # noqa: S105
        assert len(private_key_findings) >= 1, "Expected at least one private key finding"


class TestSecretRedaction:
    """Tests for secret redaction functionality."""

    def test_redact_short_secret(self) -> None:
        """Test redaction of secrets 8 characters or less."""
        # Test with various short secrets
        short_secrets = [
            "short",  # 5 chars
            "secret",  # 6 chars
            "pass123",  # 7 chars
            "testpass",  # 8 chars
        ]

        for secret in short_secrets:
            redacted = SecretScanner._redact_secret(secret)
            # Should be all asterisks for short secrets
            assert redacted == "*" * len(secret)
            assert len(redacted) == len(secret)

    def test_redact_long_secret(self) -> None:
        """Test redaction of secrets longer than 8 characters."""
        long_secret = "this_is_a_long_secret_key_12345"  # noqa: S105
        redacted = SecretScanner._redact_secret(long_secret)

        # Should show first 4 and last 4 characters
        assert redacted.startswith(long_secret[:4])
        assert redacted.endswith(long_secret[-4:])
        assert "..." in redacted


class TestDatabaseURLs:
    """Tests for database URL detection."""

    def test_postgres_url_with_password(self) -> None:
        """Test detection of PostgreSQL URL with password."""
        content = "DATABASE_URL=postgres://user:SecretPass123@localhost:5432/db"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1

    def test_mongodb_url_with_password(self) -> None:
        """Test detection of MongoDB URL with password."""
        db_url = "mongodb://admin:MyP4ssw0rd!@prod-db-cluster.us-east-1.mongodb.net:27017/"
        content = f"MONGO_URI={db_url}"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1


class TestFalsePositives:
    """Tests for false positive detection."""

    @pytest.mark.parametrize(
        "content",
        [
            "api_key: your_api_key_here",
            "token: <your-token-here>",
            "password: replace_me_with_actual_password",
        ],
    )
    def test_example_tokens_not_detected(self, content: str) -> None:
        """Test that example tokens are not flagged."""
        findings = SecretScanner.scan_content(content)
        assert len(findings) == 0

    def test_comment_with_test_keyword_not_detected(self) -> None:
        """Test that secrets in comments with test keywords are filtered."""
        # Test various comment styles with test keywords
        test_cases = [
            "# example: api_key=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "// test token: ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "<!-- sample password='MyTestPass123' -->",
        ]

        for content in test_cases:
            findings = SecretScanner.scan_content(content)
            assert len(findings) == 0, f"False positive not filtered: {content}"


class TestFileScanning:
    """Tests for file scanning."""

    def test_scan_file(self) -> None:
        """Test scanning a file for secrets."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            # Construct GitHub PAT dynamically to avoid hard-coded secrets
            prefix = "ghp_"
            suffix_parts = [
                "0123456789",  # First part
                "abcdefghij",  # Second part
                "klmnopqrst",  # Third part
                "uvwxyz1234",  # Final part
            ]
            suffix = "".join(suffix_parts)
            token = f"{prefix}{suffix}"
            f.write(f"api_key={token}\n")
            f.flush()
            file_path = Path(f.name)

        try:
            findings = SecretScanner.scan_file(file_path)
            assert len(findings) >= 1
        finally:
            file_path.unlink()

    def test_scan_file_not_found(self) -> None:
        """Test scan_file raises FileNotFoundError for non-existent file."""
        non_existent_path = Path("/tmp/this_file_does_not_exist_12345.txt")

        with pytest.raises(FileNotFoundError, match="File not found"):
            SecretScanner.scan_file(non_existent_path)

    def test_scan_file_os_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test scan_file handles OSError when file cannot be read."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test content")
            f.flush()
            file_path = Path(f.name)

        try:
            # Use monkeypatch to force Path.read_text to raise OSError
            def raise_oserror(*args: object, **kwargs: object) -> None:
                raise OSError("Failed to read file")

            monkeypatch.setattr(Path, "read_text", raise_oserror)

            with pytest.raises(OSError, match="Failed to read file"):
                SecretScanner.scan_file(file_path)
        finally:
            file_path.unlink()


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_has_secrets_returns_true_when_secrets_exist(self) -> None:
        """Test has_secrets returns True when secrets exist."""
        token = make_token("ghp_")
        content = f"api_key={token}"

        assert SecretScanner.has_secrets(content) is True

    def test_scan_content_findings_have_valid_severity_levels(self) -> None:
        """Test scan_content findings have valid severity levels."""
        token = make_token("ghp_")
        content = f"api_key={token}"

        findings = SecretScanner.scan_content(content)
        for finding in findings:
            assert finding.severity.value in ["high", "medium", "low"]

    def test_get_summary_returns_expected_structure(self) -> None:
        """Test get_summary returns expected structure with totals and severity keys."""
        token = make_token("ghp_")
        content = f"api_key={token}"

        findings = SecretScanner.scan_content(content)
        summary = SecretScanner.get_summary(findings)

        assert summary["total"] > 0
        assert "high" in summary or "medium" in summary or "low" in summary
        assert any(key.startswith("type_") for key in summary)

    def test_has_secrets_false(self) -> None:
        """Test has_secrets returns False when no secrets."""
        content = "Just some regular text without secrets"

        # Test boolean presence
        assert SecretScanner.has_secrets(content) is False

        # Test detailed results show no findings
        findings = SecretScanner.scan_content(content)
        assert len(findings) == 0

        # Validate empty summary
        summary = SecretScanner.get_summary(findings)
        assert summary["total"] == 0
        assert summary["high"] == 0
        assert summary["medium"] == 0
        assert summary["low"] == 0

    def test_has_secrets_early_exit_performance(self) -> None:
        """Test that has_secrets uses early exit for better performance."""
        # Create a large content with a secret early in the text
        token = make_token("ghp_")
        large_content = f"api_key={token}\n" + "This is just regular text.\n" * 1000

        # has_secrets should return True quickly due to early exit
        assert SecretScanner.has_secrets(large_content) is True

    def test_scan_content_stop_on_first(self) -> None:
        """Test scan_content with stop_on_first parameter."""
        # Create content with multiple secrets using tokens that don't trigger false positives
        token1 = "ghp_" + "1" * 36  # GitHub token with numbers
        token2 = "sk-" + "1" * 32  # OpenAI API key with numbers
        content = f"api_key={token1}\nopenai_key={token2}\nmore_text=value"

        # With stop_on_first=True, should only return first finding
        findings = SecretScanner.scan_content(content, stop_on_first=True)
        assert len(findings) == 1
        assert findings[0].secret_type == "github_personal_token"  # noqa: S105

        # Without stop_on_first, should return all findings
        all_findings = SecretScanner.scan_content(content, stop_on_first=False)
        assert len(all_findings) >= 2

    def test_scan_content_generator_early_exit(self) -> None:
        """Test scan_content_generator allows early exit iteration."""
        # Create content with multiple secrets using tokens that don't trigger false positives
        token1 = "ghp_" + "1" * 36  # GitHub token with numbers
        token2 = "sk-" + "1" * 32  # OpenAI API key with numbers
        content = f"api_key={token1}\nopenai_key={token2}\nmore_text=value"

        # Test generator allows early exit
        findings = []
        for finding in SecretScanner.scan_content_generator(content):
            findings.append(finding)
            if len(findings) == 1:  # Early exit after first finding
                break

        assert len(findings) == 1
        assert findings[0].secret_type == "github_personal_token"  # noqa: S105

    def test_scan_content_generator_complete_scan(self) -> None:
        """Test scan_content_generator can scan all content when needed."""
        # Create content with multiple secrets using tokens that don't trigger false positives
        token1 = "ghp_" + "1" * 36  # GitHub token with numbers
        token2 = "sk-" + "1" * 32  # OpenAI API key with numbers
        content = f"api_key={token1}\nopenai_key={token2}\nmore_text=value"

        # Test generator can find all secrets
        findings = list(SecretScanner.scan_content_generator(content))
        assert len(findings) >= 2

        # Verify we found both types of secrets
        secret_types = {finding.secret_type for finding in findings}
        assert "github_personal_token" in secret_types
        assert "openai_api_key" in secret_types

    def test_scan_content_generator_with_throttled_logging(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that throttled logging occurs every 100 lines."""
        # Configure caplog to capture debug level logs
        caplog.set_level("DEBUG")

        # Create content with 150 lines, including secrets at various positions
        token = make_token("ghp_")
        lines = [f"line {i}: some text" for i in range(150)]
        lines[50] = f"api_key={token}"  # Add secret at line 51
        content = "\n".join(lines)

        # Scan content - this will trigger logging at line 100
        findings = list(SecretScanner.scan_content_generator(content))
        assert len(findings) >= 1

        # Verify that throttled logging occurred at line 100
        log_messages = [record.message for record in caplog.records]
        throttled_log_found = any(
            "Scanned line 100" in message and "total findings so far" in message
            for message in log_messages
        )
        assert (
            throttled_log_found
        ), f"Expected throttled logging at line 100, but found logs: {log_messages}"


class TestSecretScannerLogging:
    """Tests for debug logging behavior in secret scanner."""

    def test_scan_content_disabled_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test debug logging when secret scanning is disabled."""
        caplog.set_level("DEBUG")

        from review_bot_automator.security.config import SecurityConfig

        # Create config with scanning disabled
        config = SecurityConfig(enable_secret_scanning=False)

        # Scan content - should log that scanning is disabled
        findings = SecretScanner.scan_content("api_key=secret123", config=config)
        assert len(findings) == 0

        # Verify debug log was recorded
        assert any(
            "Secret scanning disabled by configuration" in record.message
            for record in caplog.records
        )

    def test_scan_content_start_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test debug logging when scan starts."""
        caplog.set_level("DEBUG")

        # Use a proper secret pattern that will be detected
        token = make_token("ghp_")
        content = f"api_key={token}"

        # Scan content - should log start message
        findings = SecretScanner.scan_content(content)
        assert len(findings) >= 1

        # Verify start log was recorded
        assert any(
            "Starting content scan" in record.message and "lines to process" in record.message
            for record in caplog.records
        )

    def test_scan_content_stop_on_first_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test debug logging when stop_on_first is enabled."""
        caplog.set_level("DEBUG")

        # Create content with multiple secrets using proper patterns
        token1 = make_token("ghp_")
        token2 = make_token("sk-")
        content = f"api_key={token1}\npassword={token2}\n"

        # Scan with stop_on_first=True
        findings = SecretScanner.scan_content(content, stop_on_first=True)
        assert len(findings) == 1

        # Verify stop log was recorded
        assert any(
            "Found first secret, stopping scan" in record.message for record in caplog.records
        )

    def test_scan_content_completion_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test debug logging when scan completes."""
        caplog.set_level("DEBUG")

        # Use a proper secret pattern that will be detected
        token = make_token("ghp_")
        content = f"api_key={token}"

        # Scan content - should log completion message
        findings = SecretScanner.scan_content(content)
        assert len(findings) >= 1

        # Verify completion log was recorded
        assert any(
            "Content scan completed" in record.message
            and "found" in record.message
            and "total secrets" in record.message
            for record in caplog.records
        )
