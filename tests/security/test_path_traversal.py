"""Tests for path traversal attack prevention.

This module tests that handlers and the resolver properly handle path traversal attempts
to prevent directory traversal vulnerabilities.
"""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from review_bot_automator import ConflictResolver
from review_bot_automator.core.models import Change, FileType
from review_bot_automator.handlers.base import BaseHandler
from review_bot_automator.handlers.json_handler import JsonHandler
from review_bot_automator.handlers.toml_handler import TomlHandler
from review_bot_automator.handlers.yaml_handler import YamlHandler


class TestHandlerPathTraversal:
    """Tests for handler path traversal prevention."""

    def _create_handler_and_content(
        self, file_type: str, base_path: Path
    ) -> tuple[JsonHandler | YamlHandler | TomlHandler, str]:
        """Create handler and content for given file type.

        Args:
            file_type: Type of file ("json", "yaml", or "toml")
            base_path: Base path for the handler workspace

        Returns:
            Tuple of (handler, content) for the file type
        """
        if file_type == "json":
            return JsonHandler(workspace_root=str(base_path)), '{"key": "value"}'
        elif file_type == "yaml":
            return YamlHandler(workspace_root=str(base_path)), "key: value"
        else:  # toml
            return TomlHandler(workspace_root=str(base_path)), 'key = "value"'

    @pytest.fixture(params=["json", "yaml", "toml"])
    def setup_test_files(
        self, request: pytest.FixtureRequest
    ) -> Generator[tuple[Path, Path, Path, str], None, None]:
        """Create temporary directory with test file for different file types.

        Returns:
            A tuple of (base_path, test_file, outside_file, file_type) where:
            - base_path: Temporary base directory Path
            - test_file: Created test file Path (e.g., test.json/test.yaml/test.toml)
            - outside_file: Outside file Path (e.g., /etc/passwd)
            - file_type: File type string ("json", "yaml", or "toml")
        """
        file_type = request.param

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            outside_file = Path("/etc/passwd")

            # Create appropriate test file based on type
            if file_type == "json":
                test_file = base_path / "test.json"
                test_file.write_text('{"key": "value"}')
            elif file_type == "yaml":
                test_file = base_path / "test.yaml"
                test_file.write_text("key: value\n")
            elif file_type == "toml":
                test_file = base_path / "test.toml"
                test_file.write_text('key = "value"\n')

            yield base_path, test_file, outside_file, file_type

    def test_handlers_reject_unix_path_traversal(
        self, setup_test_files: tuple[Path, Path, Path, str]
    ) -> None:
        """Test that handlers reject Unix-style path traversal."""
        base_path, test_file, _, file_type = setup_test_files

        # Create handler and content using helper function
        handler, content = self._create_handler_and_content(file_type, base_path)

        # Test valid path
        assert handler.can_handle(str(test_file)), "Valid path should be handled"

        # Test path traversal attempts
        assert not handler.apply_change(
            "../../../etc/passwd", content, 1, 1
        ), "Unix path traversal should be rejected"

    @pytest.mark.parametrize(
        "attack_path",
        [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "..%2F..%2Fetc%2Fpasswd",
        ],
    )
    def test_json_handler_rejects_path_traversal_variants(
        self, tmp_path: Path, attack_path: str
    ) -> None:
        """Parametrized test covering Unix, Windows, and URL-encoded traversal paths."""
        handler = JsonHandler(workspace_root=str(tmp_path))
        assert not handler.apply_change(
            attack_path, '{"key": "value"}', 1, 1
        ), f"Path traversal should be rejected: {attack_path}"

    def test_yaml_handler_rejects_path_traversal(self, yaml_handler: YamlHandler) -> None:
        """Test that YAML handler rejects path traversal attempts."""
        # Test path traversal
        assert not yaml_handler.apply_change(
            "../../../etc/passwd", "key: value", 1, 1
        ), "Path traversal should be rejected"

    def test_toml_handler_rejects_path_traversal(self, toml_handler: TomlHandler) -> None:
        """Test that TOML handler rejects path traversal attempts."""
        # Test path traversal
        assert not toml_handler.apply_change(
            "../../../etc/passwd", 'key = "value"', 1, 1
        ), "Path traversal should be rejected"

    def test_handlers_reject_absolute_paths(
        self, setup_test_files: tuple[Path, Path, Path, str], subtests: pytest.Subtests
    ) -> None:
        """Test that handlers reject absolute paths using subtests."""
        base_path, _, outside_file, _file_type = setup_test_files
        handlers = [
            JsonHandler(workspace_root=str(base_path)),
            YamlHandler(workspace_root=str(base_path)),
            TomlHandler(workspace_root=str(base_path)),
        ]

        for handler in handlers:
            with subtests.test(
                msg=f"Handler: {handler.__class__.__name__}", handler=handler.__class__.__name__
            ):
                assert not handler.apply_change(
                    str(outside_file), "test content", 1, 1
                ), f"{handler.__class__.__name__} should reject absolute paths"

    def test_handlers_reject_null_bytes_in_path(
        self, tmp_path: Path, subtests: pytest.Subtests
    ) -> None:
        """Test that handlers reject paths containing null bytes using subtests."""
        handlers = [
            JsonHandler(workspace_root=str(tmp_path)),
            YamlHandler(workspace_root=str(tmp_path)),
            TomlHandler(workspace_root=str(tmp_path)),
        ]

        for handler in handlers:
            with subtests.test(
                msg=f"Handler: {handler.__class__.__name__}", handler=handler.__class__.__name__
            ):
                assert not handler.apply_change(
                    "file\x00.txt", "test content", 1, 1
                ), f"{handler.__class__.__name__} should reject null bytes in path"

    def test_handlers_reject_symlink_attacks(self, subtests: pytest.Subtests) -> None:
        """Test that handlers handle symlink attacks using subtests."""
        handlers = [
            ("json", "link.json", '{"key": "value"}'),
            ("yaml", "link.yaml", "key: value"),
            ("toml", "link.toml", 'key = "value"'),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a symlink target outside the temp directory
            symlink_target = Path("/etc/passwd")

            try:
                for kind, filename, content in handlers:
                    with subtests.test(msg=f"Handler: {kind}", handler=kind):
                        base_path = Path(tmpdir)
                        # Instantiate handler with workspace_root bound to tmpdir
                        if kind == "json":
                            handler: BaseHandler = JsonHandler(workspace_root=str(base_path))
                        elif kind == "yaml":
                            handler = YamlHandler(workspace_root=str(base_path))
                        else:
                            handler = TomlHandler(workspace_root=str(base_path))

                        # Create symlink within workspace pointing to external target
                        handler_symlink = base_path / filename
                        handler_symlink.unlink(missing_ok=True)
                        try:
                            handler_symlink.symlink_to(symlink_target)
                        except OSError:
                            pytest.skip("Cannot create symlink (permissions issue)")

                        # The handler should validate the path properly and reject
                        assert not handler.apply_change(
                            str(handler_symlink), content, 1, 1
                        ), f"{handler.__class__.__name__} should handle symlinks safely"

                        # Clean up symlink for next iteration
                        if handler_symlink.exists():
                            handler_symlink.unlink()
            finally:
                pass

    def test_handlers_reject_symlink_in_parent_directories(self) -> None:
        """Test that handlers reject files when any parent directory is a symlink."""
        content = 'key = "value"'

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            handler = TomlHandler(workspace_root=str(base_path))

            # Create a normal subdirectory structure
            subdir = base_path / "subdir" / "nested"
            subdir.mkdir(parents=True, exist_ok=True)

            # Create a file within the nested directory
            nested_file = subdir / "config.toml"
            nested_file.write_text('name = "test"')

            # Create a symlink pointing to /etc
            symlink_target = Path("/etc")
            symlink_parent = base_path / "evil_symlink"
            symlink_target_file = symlink_parent / "nested" / "config.toml"

            try:
                symlink_parent.symlink_to(symlink_target)
            except OSError:
                pytest.skip("Cannot create symlink (permissions issue)")

            try:
                # Try to access a file where one parent is a symlink; provide workspace_root
                assert not handler.apply_change(
                    str(symlink_target_file), content, 1, 2
                ), "Handler should reject path when parent directory is a symlink"
            finally:
                # Cleanup
                if symlink_parent.exists():
                    symlink_parent.unlink()


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

        # Verify handler unambiguously rejects malicious path
        # Instantiate without workspace_root to ensure rejection is independent of
        # workspace configuration
        handler = JsonHandler()
        handler_rejected_path = not handler.apply_change(
            malicious_change.path, malicious_change.content, 1, 1
        )

        assert (
            handler_rejected_path
        ), "Handler must unambiguously reject malicious paths to prevent path traversal"

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

    def test_resolver_handles_unicode_path_traversal(self, subtests: pytest.Subtests) -> None:
        """Test that resolver handles Unicode path traversal attempts using subtests."""
        resolver = ConflictResolver()
        json_handler = JsonHandler()
        yaml_handler = YamlHandler()
        toml_handler = TomlHandler()

        # Unicode attack vectors that normalize to '..' or similar
        attack_paths = [
            # Fullwidth dots that normalize to '..'
            "\uff0e\uff0e/etc/passwd",
            # Fullwidth dots with slashes
            "\uff0e\uff0e/\uff0e\uff0e/etc/passwd",
            # Multiple fullwidth dot variations
            "file\uff0e\uff0e/etc/passwd",
            # Mixed fullwidth and regular dots
            "\uff0e./etc/passwd",
            # Regular dots (normalized form)
            "\u002e\u002e/etc/passwd",  # Regular dots
            "\u002e\u002e/\u002e\u002e/etc/passwd",  # Multiple regular dots
        ]

        for attack_path in attack_paths:
            with subtests.test(msg=f"Unicode path traversal: {attack_path!r}", path=attack_path):
                change = Change(
                    path=attack_path,
                    start_line=1,
                    end_line=1,
                    content="malicious",
                    metadata={},
                    fingerprint=f"test-{attack_path}",
                    file_type=FileType.JSON,
                )

                conflicts = resolver.detect_conflicts([change])
                assert conflicts is not None
                assert isinstance(conflicts, list)

                # Handlers must reject Unicode path traversal attempts
                assert not json_handler.apply_change(attack_path, "malicious", 1, 1)
                assert not yaml_handler.apply_change(attack_path, "malicious", 1, 1)
                assert not toml_handler.apply_change(attack_path, "malicious", 1, 1)


class TestCrossPlatformPathTraversal:
    """Cross-platform path traversal tests."""

    def test_unix_and_windows_path_traversal(self, subtests: pytest.Subtests) -> None:
        """Test both Unix and Windows path traversal styles using subtests."""
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
            platform = "Unix" if "/" in path else "Windows"
            with subtests.test(msg=f"{platform} path traversal: {path}", path=path):
                assert not handler.apply_change(path, '{"key": "value"}', 1, 1)

    def test_encoded_path_traversal_variants(self, subtests: pytest.Subtests) -> None:
        """Test various encoding schemes used for path traversal using subtests."""
        handler = JsonHandler()

        encoded_traversals = [
            ("URL encoded", "..%2F..%2Fetc%2Fpasswd"),
            ("Double URL encoded", "..%252F..%252Fetc%252Fpasswd"),
            ("URL encoded dots/slashes", "%2e%2e%2f%2e%2e%2fetc%2fpasswd"),
            ("UTF-8 encoded", "..%c0%af..%c0%afetc%c0%afpasswd"),
        ]

        for encoding_type, path in encoded_traversals:
            with subtests.test(msg=f"{encoding_type}: {path}", encoding=encoding_type):
                assert not handler.apply_change(path, '{"key": "value"}', 1, 1)


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
