"""Tests for GitHub integration security.

This module tests token handling, SSRF prevention, and GitHub API security.
"""

import io
import secrets
import string

import pytest

from review_bot_automator.integrations.github import GitHubCommentExtractor
from review_bot_automator.security.input_validator import InputValidator


def generate_github_token(prefix: str, total_length: int) -> str:
    """Generate a random GitHub token with the specified prefix and total length.

    Args:
        prefix: Token prefix (e.g., "ghp_", "gho_")
        total_length: Total token length including prefix

    Returns:
        A random token with the correct format.
    """
    remaining_length = total_length - len(prefix)
    # Generate random alphanumeric characters
    random_chars = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(remaining_length)
    )
    return f"{prefix}{random_chars}"


class TestGitHubTokenSecurity:
    """Tests for GitHub token handling and security."""

    def test_token_not_exposed_in_errors(self, github_logger_capture: io.StringIO) -> None:
        """Test that tokens are not leaked in error messages."""
        from unittest.mock import patch

        from requests import RequestException

        # Test token that should not appear in error messages (synthetic example)
        test_token = "ghp_example_token_not_real"  # noqa: S105

        # Create GitHubCommentExtractor with test token
        extractor = GitHubCommentExtractor(token=test_token)

        # Mock a request that will fail and potentially expose the token
        with patch.object(extractor.session, "get") as mock_get:
            # Simulate a RequestException that might include token in error
            mock_get.side_effect = RequestException(f"Request failed with token {test_token}")

            # This should not raise an exception, but return empty list
            result = extractor.fetch_pr_comments("owner", "repo", 123)
            assert result == []

            # Check that the token is not present in any log messages
            log_output = github_logger_capture.getvalue()
            assert (
                test_token not in log_output
            ), f"Token '{test_token}' found in log output: {log_output}"

        # Clear previous logs before the next scenario to isolate assertions
        github_logger_capture.truncate(0)
        github_logger_capture.seek(0)

        # Test with a different error scenario - network timeout
        with patch.object(extractor.session, "get") as mock_get:
            mock_get.side_effect = RequestException(f"Timeout occurred for token {test_token}")

            metadata_result = extractor.fetch_pr_metadata("owner", "repo", 123)
            assert metadata_result is None

            # Verify token not in logs
            log_output = github_logger_capture.getvalue()
            assert (
                test_token not in log_output
            ), f"Token '{test_token}' found in log output: {log_output}"

    @pytest.mark.parametrize(
        "token",
        [
            # gitleaks:allow
            pytest.param(generate_github_token("ghp_", 44), id="personal_access_token"),
            # gitleaks:allow
            pytest.param(generate_github_token("gho_", 44), id="oauth_token"),
            # gitleaks:allow
            pytest.param(generate_github_token("ghu_", 44), id="user_token"),
            # gitleaks:allow
            pytest.param(generate_github_token("ghs_", 44), id="server_token"),
            # gitleaks:allow
            pytest.param(generate_github_token("ghr_", 44), id="refresh_token"),
            # gitleaks:allow
            pytest.param(generate_github_token("github_pat_", 68), id="fine_grained_pat_68"),
            # gitleaks:allow
            pytest.param(generate_github_token("github_pat_", 64), id="fine_grained_pat_64_a"),
            # gitleaks:allow
            pytest.param(generate_github_token("github_pat_", 64), id="fine_grained_pat_64_b"),
        ],
    )
    def test_valid_token_formats(self, token: str) -> None:
        """Test that valid GitHub tokens are accepted."""
        assert InputValidator.validate_github_token(
            token
        ), f"Valid token '{token}' should be validated as True"

    @pytest.mark.parametrize(
        "token",
        [
            "invalid",  # No GitHub prefix
            "not-a-token",  # No GitHub prefix
            "123456",  # No GitHub prefix
            "gh_invalid",  # Invalid prefix (missing underscore)
            "ghx_invalid",  # Invalid prefix
            "ghp_",  # Too short
            "gho_short",  # Too short
            "ghp_short",  # Too short (only 10 chars)
            "github_pat_short",  # Too short (<47 chars)
            "github_pat_abc123ABC789xyz",  # Too short (29 chars, needs 47)
            "ghp_with_underscore_char",  # Contains underscore (invalid)
            "",  # Empty string
            pytest.param(None, id="none_value"),  # None value
        ],
    )
    def test_invalid_token_formats(self, token: str | None) -> None:
        """Test that invalid GitHub tokens are rejected."""
        assert not InputValidator.validate_github_token(
            token
        ), f"Invalid token '{token}' should be validated as False"


class TestSSRFPrevention:
    """Tests for SSRF (Server-Side Request Forgery) prevention."""

    def test_github_url_validation_prevents_ssrf(self) -> None:
        """Test that URL validation prevents SSRF attacks."""
        # Test that only GitHub URLs are accepted
        assert InputValidator.validate_github_url("https://github.com/user/repo")
        assert not InputValidator.validate_github_url("http://localhost:8080")
        assert not InputValidator.validate_github_url("http://127.0.0.1:8080")
        assert not InputValidator.validate_github_url("http://169.254.169.254")  # AWS metadata
        assert not InputValidator.validate_github_url("file:///etc/passwd")

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost",
            "http://127.0.0.1",
            "http://[::1]",  # IPv6 localhost
            "http://169.254.169.254",  # AWS metadata
            "http://192.168.1.1",
            "http://10.0.0.1",
            "http://172.16.0.1",
            "http://192.168.1.1/api",
            "http://10.0.0.1/api",
            "http://172.16.0.1/api",
        ],
    )
    def test_internal_and_private_urls_rejected(self, url: str) -> None:
        """Test that internal IPs and private network ranges are rejected to prevent SSRF."""
        assert not InputValidator.validate_github_url(url), f"Should reject: {url}"


class TestGitHubAPIErrorHandling:
    """Tests for GitHub API error handling security."""

    def test_error_messages_dont_leak_internal_info(
        self, github_logger_capture: io.StringIO
    ) -> None:
        """Test that error messages don't leak internal information."""
        from unittest.mock import Mock, patch

        from requests import HTTPError, RequestException

        # Test token and internal paths that should not be exposed
        test_token = "ghp_secret123456789012345678901234567890"  # gitleaks:allow  # noqa: S105
        internal_path = "/home/user/internal/config.json"

        # Create GitHubCommentExtractor with test token
        extractor = GitHubCommentExtractor(token=test_token)

        # Test 1: HTTP 401 Unauthorized - should not expose token
        with patch.object(extractor.session, "get") as mock_get:
            response = Mock()
            response.raise_for_status.side_effect = HTTPError(
                f"401 Client Error: Unauthorized for token {test_token}"
            )
            mock_get.return_value = response

            result = extractor.fetch_pr_comments("owner", "repo", 123)
            assert result == []

            # Check that sensitive info is not in logs
            log_output = github_logger_capture.getvalue()
            assert test_token not in log_output, f"Token found in logs: {log_output}"

        # Test 2: HTTP 403 Forbidden - should not expose internal paths
        with patch.object(extractor.session, "get") as mock_get:
            response = Mock()
            response.raise_for_status.side_effect = HTTPError(
                f"403 Client Error: Forbidden accessing {internal_path}"
            )
            mock_get.return_value = response

            result = extractor.fetch_pr_files("owner", "repo", 123)
            assert result == []

            # Check that internal paths are not in logs
            log_output = github_logger_capture.getvalue()
            assert internal_path not in log_output, f"Internal path found in logs: {log_output}"

        # Test 3: Network error - should not expose stack traces in production
        with patch.object(extractor.session, "get") as mock_get:
            mock_get.side_effect = RequestException(
                f"Connection failed to {internal_path} with token {test_token}"
            )

            metadata_result = extractor.fetch_pr_metadata("owner", "repo", 123)
            assert metadata_result is None

            # Check that neither token nor internal path appear in logs
            log_output = github_logger_capture.getvalue()
            assert test_token not in log_output, f"Token found in logs: {log_output}"
            assert internal_path not in log_output, f"Internal path found in logs: {log_output}"


class TestRateLimitHandling:
    """Tests for GitHub API rate limit handling."""

    def test_rate_limit_handled_gracefully(self, github_logger_capture: io.StringIO) -> None:
        """Test that rate limiting is handled gracefully."""
        from unittest.mock import Mock, patch

        from requests import HTTPError

        # Create GitHubCommentExtractor
        extractor = GitHubCommentExtractor(
            token="ghp_test123456789012345678901234567890"  # gitleaks:allow  # noqa: S106
        )

        # Test 1: HTTP 429 Too Many Requests - should return empty results gracefully
        with patch.object(extractor.session, "get") as mock_get:
            response = Mock()
            response.raise_for_status.side_effect = HTTPError("429 Client Error: Too Many Requests")
            mock_get.return_value = response

            # Should not raise exception, should return empty list
            result = extractor.fetch_pr_comments("owner", "repo", 123)
            assert result == []

            # Should not raise exception, should return None
            metadata_result = extractor.fetch_pr_metadata("owner", "repo", 123)
            assert metadata_result is None

            # Should not raise exception, should return empty list
            result = extractor.fetch_pr_files("owner", "repo", 123)
            assert result == []

        # Test 2: Rate limit with retry-after header - should handle gracefully
        with patch.object(extractor.session, "get") as mock_get:
            response = Mock()
            response.headers = {"Retry-After": "60"}
            response.raise_for_status.side_effect = HTTPError(
                "429 Client Error: Rate limit exceeded"
            )
            mock_get.return_value = response

            # Should handle rate limit gracefully without crashing
            result = extractor.fetch_pr_comments("owner", "repo", 123)
            assert result == []

        # Test 3: Multiple rate limit errors in sequence - should handle all gracefully
        with patch.object(extractor.session, "get") as mock_get:
            response = Mock()
            response.raise_for_status.side_effect = HTTPError(
                "429 Client Error: Rate limit exceeded"
            )
            mock_get.return_value = response

            # Multiple calls should all handle rate limits gracefully
            results = []
            for i in range(3):
                result = extractor.fetch_pr_comments("owner", "repo", i)
                results.append(result)

            # All should return empty lists
            assert all(result == [] for result in results)


class TestURLConstruction:
    """Tests for secure URL construction."""

    def test_no_url_manipulation_attacks(self) -> None:
        """Test that URL manipulation attacks are prevented."""
        # Test for URL manipulation attempts
        malicious_urls = [
            "https://github.com@evil.com",
            "https://github.com.evil.com",
            "https://github-com.evil.com",
        ]

        for url in malicious_urls:
            assert not InputValidator.validate_github_url(url), f"Should reject: {url}"
