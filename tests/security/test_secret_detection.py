"""Tests for secret detection and prevention."""

import tempfile
from pathlib import Path

from pr_conflict_resolver.security.secret_scanner import SecretScanner


class TestGitHubTokenDetection:
    """Tests for GitHub token detection."""

    def test_github_personal_token(self) -> None:
        """Test detection of GitHub personal access token."""
        content = "GITHUB_TOKEN=ghp_1234567890123456789012345678901234AB"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        # Use variable to avoid S105 warning
        expected_type = "github_personal_token"
        assert any(f.secret_type == expected_type for f in findings)

    def test_github_oauth_token(self) -> None:
        """Test detection of GitHub OAuth token."""
        content = "token: gho_1234567890123456789012345678901234AB"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        expected_type = "github_oauth_token"
        assert any(f.secret_type == expected_type for f in findings)

    def test_github_server_token(self) -> None:
        """Test detection of GitHub server token."""
        content = "server_token = ghs_1234567890123456789012345678901234AB"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        expected_type = "github_server_token"
        assert any(f.secret_type == expected_type for f in findings)

    def test_github_refresh_token(self) -> None:
        """Test detection of GitHub refresh token."""
        content = "refresh: ghr_1234567890123456789012345678901234AB"
        findings = SecretScanner.scan_content(content)

        assert len(findings) == 1
        expected_type = "github_refresh_token"
        assert findings[0].secret_type == expected_type


class TestAWSCredentials:
    """Tests for AWS credential detection."""

    def test_aws_access_key(self) -> None:
        """Test detection of AWS access key."""
        content = "AWS_ACCESS_KEY_ID=AKIAZQR4NKPB7WMXYZ12"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        expected_type = "aws_access_key"
        assert any(f.secret_type == expected_type for f in findings)

    def test_aws_secret_key(self) -> None:
        """Test detection of AWS secret key."""
        content = 'AWS_SECRET="wJalrXUtnFEMI/K7MDENG/bPxRfiCYWMXYZ123KEY"'
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1
        expected_type = "aws_secret_key"
        assert any(f.secret_type == expected_type for f in findings)


class TestAPIKeys:
    """Tests for API key detection."""

    def test_openai_api_key(self) -> None:
        """Test detection of OpenAI API key."""
        content = "OPENAI_API_KEY=sk-1234567890abcdefghijklmnopqrstuv"
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
        jwt_token = f"{part1}.{part2}.{part3}"
        content = f"token: {jwt_token}"
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1


class TestPrivateKeys:
    """Tests for private key detection."""

    def test_private_key(self) -> None:
        """Test detection of private keys."""
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        findings = SecretScanner.scan_content(content)

        assert len(findings) >= 1


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

    def test_example_tokens_not_detected(self) -> None:
        """Test that example tokens are not flagged."""
        test_cases = [
            "api_key: your_api_key_here",
            "token: <your-token-here>",
            "password: replace_me_with_actual_password",
        ]

        for content in test_cases:
            findings = SecretScanner.scan_content(content)
            assert len(findings) == 0


class TestFileScanning:
    """Tests for file scanning."""

    def test_scan_file(self) -> None:
        """Test scanning a file for secrets."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("api_key=ghp_1234567890123456789012345678901234AB\n")
            f.flush()
            file_path = Path(f.name)

        try:
            findings = SecretScanner.scan_file(file_path)
            assert len(findings) >= 1
        finally:
            file_path.unlink()


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_has_secrets_true(self) -> None:
        """Test has_secrets returns True when secrets exist."""
        content = "api_key=ghp_1234567890123456789012345678901234AB"
        assert SecretScanner.has_secrets(content) is True

    def test_has_secrets_false(self) -> None:
        """Test has_secrets returns False when no secrets."""
        content = "Just some regular text without secrets"
        assert SecretScanner.has_secrets(content) is False
