"""LLM security tests for Issue #226.

Tests for secure LLM operations including:
- Prompt sanitization (secret scanning before LLM calls)
- Circuit breaker error sanitization
- Metrics export file permissions
- Parallel parser security limits
"""

import os
import stat
import string
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from review_bot_automator.llm.exceptions import LLMSecretDetectedError
from review_bot_automator.llm.metrics_aggregator import MetricsAggregator
from review_bot_automator.llm.parallel_parser import CommentInput, ParallelLLMParser
from review_bot_automator.llm.parser import UniversalLLMParser
from review_bot_automator.llm.resilience.resilient_provider import ResilientLLMProvider
from review_bot_automator.security.secret_scanner import SecretScanner


def make_token(prefix: str, suffix_length: int = 36) -> str:
    """Create a test token with the given prefix and suffix length."""
    charset = string.digits + string.ascii_lowercase
    suffix = (charset * ((suffix_length // len(charset)) + 1))[:suffix_length]
    return f"{prefix}{suffix}"


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, response: str = "[]") -> None:
        self.model = "test-model"
        self.response = response
        self._total_cost = 0.0
        self.generate_called = False

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        self.generate_called = True
        self._total_cost += 0.001
        return self.response

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def get_total_cost(self) -> float:
        return self._total_cost

    def reset_usage_tracking(self) -> None:
        self._total_cost = 0.0


class TestPromptSanitization:
    """Tests for secret scanning before LLM calls."""

    def test_parser_blocks_github_token_in_comment(self) -> None:
        """Parser raises LLMSecretDetectedError when GitHub token is in comment."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        token = make_token("ghp_", 36)
        comment_body = f"Fix this bug using token: {token}"

        with pytest.raises(LLMSecretDetectedError) as exc_info:
            parser.parse_comment(comment_body)

        assert "github_personal_token" in str(exc_info.value)
        assert not provider.generate_called  # LLM should NOT be called

    def test_parser_blocks_openai_key_in_comment(self) -> None:
        """Parser raises LLMSecretDetectedError when OpenAI key is in comment."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        token = make_token("sk-", 48)
        comment_body = f"Use API key: {token}"

        with pytest.raises(LLMSecretDetectedError) as exc_info:
            parser.parse_comment(comment_body)

        assert "openai_api_key" in str(exc_info.value)
        assert not provider.generate_called

    def test_parser_blocks_aws_credentials(self) -> None:
        """Parser raises LLMSecretDetectedError when AWS credentials are in comment."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        # AWS access key format: AKIA followed by 16 alphanumeric characters
        aws_key = "AKIA" + "0123456789ABCDEF"
        comment_body = f"AWS_ACCESS_KEY_ID={aws_key}"

        with pytest.raises(LLMSecretDetectedError) as exc_info:
            parser.parse_comment(comment_body)

        assert "aws_access_key" in str(exc_info.value)
        assert not provider.generate_called

    def test_parser_allows_clean_comments(self) -> None:
        """Parser allows comments without secrets to proceed to LLM."""
        provider = MockLLMProvider(response="[]")
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        comment_body = "Please fix the bug in the login function"

        result = parser.parse_comment(comment_body)

        assert provider.generate_called
        assert result == []

    def test_parser_raises_when_fallback_disabled(self) -> None:
        """Parser raises LLMSecretDetectedError even when fallback_to_regex=False."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True, fallback_to_regex=False)

        token = make_token("ghp_", 36)
        comment_body = f"Token: {token}"

        with pytest.raises(LLMSecretDetectedError):
            parser.parse_comment(comment_body)

        assert not provider.generate_called

    def test_scan_disabled_allows_all_content(self) -> None:
        """Parser allows all content when scan_for_secrets=False."""
        provider = MockLLMProvider(response="[]")
        parser = UniversalLLMParser(provider, scan_for_secrets=False)

        token = make_token("ghp_", 36)
        comment_body = f"Token: {token}"

        # Should not raise, even with secret present
        result = parser.parse_comment(comment_body)

        assert provider.generate_called
        assert result == []

    def test_secret_detected_error_contains_findings(self) -> None:
        """LLMSecretDetectedError includes findings information."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        token = make_token("ghp_", 36)
        comment_body = f"Token: {token}"

        with pytest.raises(LLMSecretDetectedError) as exc_info:
            parser.parse_comment(comment_body)

        error = exc_info.value
        assert len(error.findings) >= 1
        assert "github_personal_token" in error.secret_types

    def test_secret_detected_error_str_format(self) -> None:
        """LLMSecretDetectedError string format is informative."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        token = make_token("ghp_", 36)
        comment_body = f"Token: {token}"

        with pytest.raises(LLMSecretDetectedError) as exc_info:
            parser.parse_comment(comment_body)

        error_str = str(exc_info.value)
        assert "github_personal_token" in error_str
        assert "count:" in error_str


class TestCircuitBreakerSecurity:
    """Tests for circuit breaker error sanitization."""

    def test_circuit_breaker_sanitizes_secret_in_exception(self) -> None:
        """ResilientLLMProvider sanitizes secrets in exception messages."""
        base_provider = MockLLMProvider()
        token = make_token("sk-", 48)

        # Make the base provider raise an exception containing a secret
        base_provider.generate = MagicMock(  # type: ignore[method-assign]
            side_effect=RuntimeError(f"API error with key: {token}")
        )

        resilient = ResilientLLMProvider(base_provider)

        with pytest.raises(RuntimeError) as exc_info:
            resilient.generate("test prompt")

        # The exception message should be sanitized
        error_msg = str(exc_info.value)
        assert "redacted" in error_msg.lower()
        assert token not in error_msg

    def test_circuit_breaker_preserves_clean_exceptions(self) -> None:
        """ResilientLLMProvider preserves exceptions without secrets."""
        base_provider = MockLLMProvider()

        # Make the base provider raise an exception without secrets
        base_provider.generate = MagicMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("Connection timeout")
        )

        resilient = ResilientLLMProvider(base_provider)

        with pytest.raises(RuntimeError) as exc_info:
            resilient.generate("test prompt")

        assert "Connection timeout" in str(exc_info.value)


class TestMetricsExportSecurity:
    """Tests for metrics export file permissions."""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="POSIX permissions not supported on Windows"
    )
    def test_json_export_restricted_permissions(self) -> None:
        """JSON export files have 0600 permissions."""
        aggregator = MetricsAggregator()
        aggregator.set_pr_info("owner", "repo", 123)

        # Add some test data
        request_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(request_id, success=True, tokens_input=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "metrics.json"
            aggregator.export_json(path)

            # Check permissions
            permissions = stat.S_IMODE(os.stat(path).st_mode)
            assert permissions == 0o600

    @pytest.mark.skipif(
        sys.platform == "win32", reason="POSIX permissions not supported on Windows"
    )
    def test_csv_export_restricted_permissions(self) -> None:
        """CSV export files have 0600 permissions."""
        aggregator = MetricsAggregator()

        # Add some test data
        request_id = aggregator.start_request("anthropic", "claude-haiku-4")
        aggregator.end_request(request_id, success=True, tokens_input=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "metrics.csv"
            aggregator.export_csv(path)

            # Check permissions
            permissions = stat.S_IMODE(os.stat(path).st_mode)
            assert permissions == 0o600


class TestParallelParserSecurity:
    """Tests for parallel parser security."""

    def test_parallel_parser_blocks_secrets(self) -> None:
        """ParallelLLMParser blocks secrets in comments."""
        provider = MockLLMProvider()
        parser = ParallelLLMParser(provider, max_workers=2, scan_for_secrets=True)

        token = make_token("ghp_", 36)
        comments = [
            CommentInput(body=f"Token: {token}", file_path="test.py"),
        ]

        # With fallback_to_regex=True (default), exceptions become empty results
        results = parser.parse_comments(comments)

        # The comment with secret should fail and return empty result
        assert results == [[]]
        assert not provider.generate_called

    def test_parallel_parser_raises_with_fallback_disabled(self) -> None:
        """ParallelLLMParser raises with fallback_to_regex=False."""
        provider = MockLLMProvider()
        parser = ParallelLLMParser(
            provider, max_workers=2, scan_for_secrets=True, fallback_to_regex=False
        )

        token = make_token("ghp_", 36)
        comments = [
            CommentInput(body=f"Token: {token}", file_path="test.py"),
        ]

        with pytest.raises(LLMSecretDetectedError):
            parser.parse_comments(comments)

    def test_max_workers_upper_limit(self) -> None:
        """ParallelLLMParser enforces max_workers limit."""
        provider = MockLLMProvider()

        with pytest.raises(ValueError) as exc_info:
            ParallelLLMParser(provider, max_workers=33)

        assert "cannot exceed 32" in str(exc_info.value)

    def test_max_workers_exactly_at_limit(self) -> None:
        """ParallelLLMParser accepts max_workers at exactly 32."""
        provider = MockLLMProvider()

        parser = ParallelLLMParser(provider, max_workers=32)
        assert parser.max_workers == 32

    def test_max_workers_minimum_one(self) -> None:
        """ParallelLLMParser requires max_workers >= 1."""
        provider = MockLLMProvider()

        with pytest.raises(ValueError) as exc_info:
            ParallelLLMParser(provider, max_workers=0)

        assert "must be >= 1" in str(exc_info.value)


class TestSecretPatternCoverage:
    """Ensure all critical secret patterns are blocked by the parser."""

    @pytest.mark.parametrize(
        "secret_type,prefix,suffix_length",
        [
            ("github_personal_token", "ghp_", 36),
            ("github_oauth_token", "gho_", 36),
            ("github_server_token", "ghs_", 36),
            ("github_refresh_token", "ghr_", 36),
            ("openai_api_key", "sk-", 48),
        ],
    )
    def test_parser_blocks_secret_pattern(
        self, secret_type: str, prefix: str, suffix_length: int
    ) -> None:
        """Parser blocks comments containing various secret patterns."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        token = make_token(prefix, suffix_length)
        comment_body = f"Use this key: {token}"

        with pytest.raises(LLMSecretDetectedError) as exc_info:
            parser.parse_comment(comment_body)

        assert secret_type in str(exc_info.value)
        assert not provider.generate_called

    def test_parser_blocks_aws_access_key(self) -> None:
        """Parser blocks AWS access keys."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        aws_key = "AKIA" + "0123456789ABCDEF"
        comment_body = f"AWS_ACCESS_KEY_ID={aws_key}"

        with pytest.raises(LLMSecretDetectedError) as exc_info:
            parser.parse_comment(comment_body)

        assert "aws_access_key" in str(exc_info.value)
        assert not provider.generate_called

    def test_parser_blocks_private_key(self) -> None:
        """Parser blocks private keys."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        comment_body = """
        Here's my key:
        -----BEGIN RSA PRIVATE KEY-----
        MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyf8Ob
        -----END RSA PRIVATE KEY-----
        """

        with pytest.raises(LLMSecretDetectedError) as exc_info:
            parser.parse_comment(comment_body)

        assert "private_key" in str(exc_info.value)
        assert not provider.generate_called

    def test_parser_blocks_jwt_token(self) -> None:
        """Parser blocks JWT tokens."""
        provider = MockLLMProvider()
        parser = UniversalLLMParser(provider, scan_for_secrets=True)

        # Build a valid JWT structure
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abcdefghijklmnop"
        comment_body = f"Bearer {jwt}"

        with pytest.raises(LLMSecretDetectedError) as exc_info:
            parser.parse_comment(comment_body)

        assert "jwt_token" in str(exc_info.value)
        assert not provider.generate_called


class TestLLMSecretDetectedException:
    """Tests for LLMSecretDetectedError exception class."""

    def test_exception_with_findings(self) -> None:
        """LLMSecretDetectedError correctly stores findings."""
        token = make_token("ghp_", 36)
        findings = SecretScanner.scan_content(f"Token: {token}")

        error = LLMSecretDetectedError("Secret detected", findings=findings)

        assert len(error.findings) >= 1
        assert "github_personal_token" in error.secret_types

    def test_exception_without_findings(self) -> None:
        """LLMSecretDetectedError handles empty findings."""
        error = LLMSecretDetectedError("Secret detected", findings=None)

        assert error.findings == []
        assert error.secret_types == set()

    def test_exception_str_with_multiple_types(self) -> None:
        """LLMSecretDetectedError string includes all secret types."""
        ghp_token = make_token("ghp_", 36)
        openai_key = make_token("sk-", 48)
        findings = SecretScanner.scan_content(f"Tokens: {ghp_token} and {openai_key}")

        error = LLMSecretDetectedError("Multiple secrets detected", findings=findings)

        error_str = str(error)
        # Types should be sorted in the output
        assert "github_personal_token" in error_str
        assert "openai_api_key" in error_str
