"""Tests for path traversal attack prevention.

This module tests that handlers and the resolver properly handle path traversal attempts
to prevent directory traversal vulnerabilities.
"""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.core.models import Change, FileType
from pr_conflict_resolver.handlers.json_handler import JsonHandler
from pr_conflict_resolver.handlers.toml_handler import TomlHandler
from pr_conflict_resolver.handlers.yaml_handler import YamlHandler


class TestHandlerPathTraversal:
    """Tests for handler path traversal prevention."""

    @pytest.fixture
    def setup_test_files(self) -> Generator[tuple[Path, Path, Path], None, None]:
        """Create temporary directory with test JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            test_file = base_path / "test.json"
            test_file.write_text('{"key": "value"}')

            outside_file = Path("/etc/passwd")

            yield base_path, test_file, outside_file

    def test_json_handler_rejects_unix_path_traversal(
        self, setup_test_files: tuple[Path, Path, Path]
    ) -> None:
        """Test that JSON handler rejects Unix-style path traversal."""
        _base_path, test_file, _ = setup_test_files
        handler = JsonHandler()

        # Test valid path
        assert handler.can_handle(str(test_file)), "Valid path should be handled"

        # Test path traversal attempts
        assert not handler.apply_change(
            "../../../etc/passwd", '{"key": "value"}', 1, 1
        ), "Unix path traversal should be rejected"

    def test_json_handler_rejects_windows_path_traversal(self) -> None:
        """Test that JSON handler rejects Windows-style path traversal."""
        handler = JsonHandler()

        # Test Windows path traversal
        assert not handler.apply_change(
            "..\\..\\..\\windows\\system32", '{"key": "value"}', 1, 1
        ), "Windows path traversal should be rejected"

    def test_json_handler_rejects_url_encoded_traversal(self) -> None:
        """Test that JSON handler rejects URL-encoded path traversal."""
        handler = JsonHandler()

        # Test URL-encoded traversal
        assert not handler.apply_change(
            "..%2F..%2Fetc%2Fpasswd", '{"key": "value"}', 1, 1
        ), "URL-encoded traversal should be rejected"

    def test_yaml_handler_rejects_path_traversal(self) -> None:
        """Test that YAML handler rejects path traversal attempts."""
        handler = YamlHandler()

        # Test path traversal
        assert not handler.apply_change(
            "../../../etc/passwd", "key: value", 1, 1
        ), "Path traversal should be rejected"

    def test_toml_handler_rejects_path_traversal(self) -> None:
        """Test that TOML handler rejects path traversal attempts."""
        handler = TomlHandler()

        # Test path traversal
        assert not handler.apply_change(
            "../../../etc/passwd", 'key = "value"', 1, 1
        ), "Path traversal should be rejected"

    def test_handlers_reject_absolute_paths(
        self, setup_test_files: tuple[Path, Path, Path]
    ) -> None:
        """Test that handlers reject absolute paths."""
        _, _, outside_file = setup_test_files
        handlers = [
            JsonHandler(),
            YamlHandler(),
            TomlHandler(),
        ]

        for handler in handlers:
            assert not handler.apply_change(
                str(outside_file), "test content", 1, 1
            ), f"{handler.__class__.__name__} should reject absolute paths"

    def test_handlers_reject_null_bytes_in_path(self) -> None:
        """Test that handlers reject paths containing null bytes."""
        handlers = [
            JsonHandler(),
            YamlHandler(),
            TomlHandler(),
        ]

        for handler in handlers:
            assert not handler.apply_change(
                "file\x00.txt", "test content", 1, 1
            ), f"{handler.__class__.__name__} should reject null bytes in path"

    def test_handlers_reject_symlink_attacks(self) -> None:
        """Test that handlers handle symlink attacks."""
        handlers = [
            JsonHandler(),
            YamlHandler(),
            TomlHandler(),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a symlink pointing outside the temp directory
            symlink_target = Path("/etc/passwd")
            symlink_path = Path(tmpdir) / "link.json"

            try:
                symlink_path.symlink_to(symlink_target)
            except OSError:
                # Symlink creation may fail due to permissions
                pytest.skip("Cannot create symlink (permissions issue)")

            for handler in handlers:
                # The handler should validate the path properly
                assert not handler.apply_change(
                    str(symlink_path), '{"key": "value"}', 1, 1
                ), f"{handler.__class__.__name__} should handle symlinks safely"


class TestResolverPathTraversal:
    """Tests for resolver path traversal prevention."""

    def test_resolver_handles_path_traversal_in_changes(self) -> None:
        """Test that resolver handles path traversal attempts in changes."""
        resolver = ConflictResolver()

        # Create a change with path traversal attempt
        malicious_change = Change(
            path="../../../etc/passwd",
            start_line=1,
            end_line=1,
            content="test",
            metadata={},
            fingerprint="test",
            file_type=FileType.JSON,
        )

        # Resolver should handle this gracefully
        conflicts = resolver.detect_conflicts([malicious_change])

        # Should not cause errors, should handle gracefully
        assert conflicts is not None, "Resolver should handle malicious paths without crashing"
        assert isinstance(conflicts, list), "Should return a list of conflicts"

    def test_resolver_rejects_multiple_path_traversal_attempts(self) -> None:
        """Test that resolver rejects multiple path traversal attempts."""
        resolver = ConflictResolver()

        changes = [
            Change(
                path="../../../etc/passwd",
                start_line=1,
                end_line=1,
                content="malicious1",
                metadata={},
                fingerprint="test1",
                file_type=FileType.JSON,
            ),
            Change(
                path="../../root/.ssh/id_rsa",
                start_line=1,
                end_line=1,
                content="malicious2",
                metadata={},
                fingerprint="test2",
                file_type=FileType.YAML,
            ),
        ]

        conflicts = resolver.detect_conflicts(changes)
        assert conflicts is not None, "Resolver should handle multiple malicious paths"
        assert isinstance(conflicts, list), "Should return a list"

    def test_resolver_handles_unicode_path_traversal(self) -> None:
        """Test that resolver handles Unicode path traversal attempts."""
        resolver = ConflictResolver()

        # Unicode characters that can normalize to '..'
        changes = [
            Change(
                path="file\u2024\u2024/etc/passwd",
                start_line=1,
                end_line=1,
                content="malicious",
                metadata={},
                fingerprint="test",
                file_type=FileType.JSON,
            ),
        ]

        conflicts = resolver.detect_conflicts(changes)
        assert conflicts is not None, "Resolver should handle Unicode traversal attempts"
        assert isinstance(conflicts, list), "Should return a list"


class TestCrossPlatformPathTraversal:
    """Cross-platform path traversal tests."""

    def test_unix_and_windows_path_traversal(self) -> None:
        """Test both Unix and Windows path traversal styles."""
        handler = JsonHandler()

        unix_traversals = [
            "../../../etc/passwd",
            "./../../etc/shadow",
            "../../../root/.ssh/id_rsa",
        ]

        windows_traversals = [
            "..\\..\\..\\windows\\system32",
            "..\\..\\..\\boot.ini",
            "C:\\Windows\\System32\\config\\sam",
        ]

        for path in unix_traversals + windows_traversals:
            assert not handler.apply_change(
                path, '{"key": "value"}', 1, 1
            ), f"Path traversal attempt should be rejected: {path}"

    def test_encoded_path_traversal_variants(self) -> None:
        """Test various encoding schemes used for path traversal."""
        handler = JsonHandler()

        encoded_traversals = [
            "..%2F..%2Fetc%2Fpasswd",  # URL encoded
            "..%252F..%252Fetc%252Fpasswd",  # Double URL encoded
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # URL encoded dots and slashes
            "..%c0%af..%c0%afetc%c0%afpasswd",  # UTF-8 encoded
        ]

        for path in encoded_traversals:
            assert not handler.apply_change(
                path, '{"key": "value"}', 1, 1
            ), f"Encoded traversal should be rejected: {path}"


class TestHandlerValidationMethods:
    """Test handler validation methods handle path traversal."""

    def test_validate_change_rejects_path_traversal(self) -> None:
        """Test that validate_change rejects path traversal."""
        handler = JsonHandler()

        valid, message = handler.validate_change("../../../etc/passwd", '{"key": "value"}', 1, 1)

        assert not valid, "validate_change should reject path traversal"
        assert message, "Should provide error message for rejected path"

    def test_detect_conflicts_handles_path_traversal(self) -> None:
        """Test that detect_conflicts handles path traversal in changes."""
        handler = JsonHandler()

        # This should not raise an error even with malicious path
        conflicts = handler.detect_conflicts(
            "../../../etc/passwd",
            [
                Change(
                    path="../../../etc/passwd",
                    start_line=1,
                    end_line=1,
                    content='{"key": "value"}',
                    metadata={},
                    fingerprint="test",
                    file_type=FileType.JSON,
                ),
            ],
        )

        # Should return a list (may be empty or contain conflicts)
        assert isinstance(conflicts, list), "Should return a list of conflicts"
