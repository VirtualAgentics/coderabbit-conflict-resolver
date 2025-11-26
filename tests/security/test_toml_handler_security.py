"""Security tests for TOML handler.

This module tests security aspects of the TOML handler including path validation,
atomic operations, permission handling, and error cleanup.
"""

import os
import stat
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from review_bot_automator.handlers.toml_handler import TomlHandler


@pytest.fixture(scope="module", autouse=True)
def enable_toml_for_tests() -> Generator[None, None, None]:
    """Enable TOML read/write support globally for this test module.

    Ensures all tests exercise the TOML-enabled code path consistently.
    """
    import review_bot_automator.handlers.toml_handler as toml_handler_module

    with (
        patch.object(toml_handler_module, "TOML_READ_AVAILABLE", True, create=True),
        patch.object(toml_handler_module, "TOML_WRITE_AVAILABLE", True, create=True),
    ):
        yield


class TestTomlHandlerPathSecurity:
    """Test TOML handler path security validation."""

    @pytest.mark.parametrize(
        "path",
        [
            "../../../etc/passwd",
            "../../sensitive",
            "../parent",
            "..\\..\\..\\windows\\system32",
            "C:\\Windows\\System32",
            "/etc/passwd",
            "/var/log/secure",
        ],
        ids=[
            "traversal-etc-passwd",
            "traversal-sensitive",
            "traversal-parent",
            "traversal-windows",
            "windows-system32",
            "absolute-etc-passwd",
            "absolute-var-log",
        ],
    )
    def test_apply_change_rejects_path_traversal(self, tmp_path: Path, path: str) -> None:
        """Test that apply_change rejects path traversal attempts."""
        handler = TomlHandler(workspace_root=str(tmp_path))
        result = handler.apply_change(path, "key = 'value'", 1, 3)
        assert result is False, f"Should reject traversal path: {path}"

    @pytest.mark.parametrize(
        "path",
        [
            "/etc/passwd",
            "/var/log/secure",
            "/root/.ssh/id_rsa",
            "/usr/local/bin",
            "/home/user/documents",
            "C:\\Windows\\System32",
            "D:\\Program Files",
            "C:/Windows/System32",
            "\\\\server\\share\\repo",
        ],
        ids=[
            "absolute-etc-passwd",
            "absolute-var-log",
            "absolute-root-ssh",
            "absolute-usr-local",
            "absolute-home-documents",
            "windows-system32",
            "windows-program-files",
            "windows-slash-format",
            "unc-network-path",
        ],
    )
    def test_apply_change_rejects_absolute_paths(self, path: str) -> None:
        """Test that apply_change rejects absolute paths."""
        handler = TomlHandler()
        result = handler.apply_change(path, "key = 'value'", 1, 3)
        assert result is False, f"Should reject absolute path: {path}"

    def test_apply_change_accepts_relative_paths(self, toml_handler: TomlHandler) -> None:
        """Test that apply_change accepts safe relative paths with actual files."""
        # Use shared fixture instead of manual instantiation
        handler = toml_handler

        safe_paths = [
            "config.toml",
            "settings.toml",
            "pyproject.toml",
        ]

        for path in safe_paths:
            # Create the file inside the handler's configured workspace
            test_file = Path(handler.workspace_root) / path
            test_file.write_text("original = 'value'")

            # Apply change to the existing file
            result = handler.apply_change(path, "key = 'value'", 1, 1)
            # Path validation should pass and the operation should complete
            assert result is True, f"Should accept safe relative path: {path}"

    def test_validate_change_accepts_various_path_traversal_forms(self) -> None:
        """Test that validate_change validates TOML content only."""
        handler = TomlHandler()

        traversal_paths = [
            "../../../etc/passwd",
            "../../sensitive",
            "../parent",
            "..\\..\\..\\windows\\system32",
        ]

        for path in traversal_paths:
            valid, _ = handler.validate_change(path, "key = 'value'", 1, 3)
            # validate_change only validates TOML content, not paths - all should pass
            assert valid is True  # TOML content is valid

    def test_validate_change_accepts_various_absolute_paths(self) -> None:
        """Test that validate_change validates TOML content only."""
        handler = TomlHandler()

        absolute_paths = [
            "/etc/passwd",
            "/var/log/secure",
            "C:\\Windows\\System32",
            "D:\\Program Files",
        ]

        for path in absolute_paths:
            valid, _ = handler.validate_change(path, "key = 'value'", 1, 3)
            # validate_change only validates TOML content, not paths - all should pass
            assert valid is True  # TOML content is valid


class TestTomlHandlerAtomicOperations:
    """Test TOML handler atomic file operations."""

    def test_apply_change_atomic_write(self) -> None:
        """Test that apply_change uses atomic file replacement with line-based editing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write original TOML with multiple lines
            f.write("# Configuration\noriginal = 'value'\nother = 'data'\n")
            f.flush()
            original_path = f.name
            temp_dir = os.path.dirname(f.name)

        # Create handler with temp directory as workspace root
        handler = TomlHandler(workspace_root=temp_dir)

        try:
            # Apply change to replace only line 2
            result = handler.apply_change(original_path, "original = 'newvalue'", 2, 2)
            assert result is True

            # Verify file still exists and targeted replacement was performed
            assert os.path.exists(original_path)
            content = Path(original_path).read_text()
            assert "# Configuration" in content  # Comment preserved
            assert "original = 'newvalue'" in content  # Line 2 replaced
            assert "other = 'data'" in content  # Line 3 preserved

        finally:
            if os.path.exists(original_path):
                os.unlink(original_path)

    def test_apply_change_early_return_on_invalid_toml(self) -> None:
        """Test that apply_change returns early when file contains invalid TOML.

        This test verifies early-return behavior: no temp file is created because
        the original file contains invalid TOML which is detected during parsing
        before any temp file creation occurs.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = TomlHandler(workspace_root=tmpdir)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".toml", dir=tmpdir, delete=False
            ) as f:
                # Write invalid TOML to trigger early return
                f.write("invalid toml [")
                f.flush()
                original_path = f.name

            try:
                # This should fail early during TOML parsing, before temp file creation
                result = handler.apply_change(original_path, "key = 'value'", 1, 3)
                assert result is False

                # Verify no temp files were created (early return before temp file creation)
                temp_dir = os.path.dirname(original_path)
                expected_prefix = f".{os.path.basename(original_path)}.tmp"
                temp_files = [f for f in os.listdir(temp_dir) if f.startswith(expected_prefix)]
                assert len(temp_files) == 0, "No temporary files should be created on early return"

            finally:
                if os.path.exists(original_path):
                    os.unlink(original_path)

    @pytest.mark.skipif(sys.platform.startswith("win"), reason="chmod semantics differ on Windows")
    def test_apply_change_preserves_file_permissions(self) -> None:
        """Test that apply_change preserves original file permissions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write original TOML
            f.write("key = 'value'")
            f.flush()
            original_path = f.name
            temp_dir = os.path.dirname(f.name)

            # Set specific permissions
            original_mode = 0o600  # Read/write for owner only
            os.chmod(original_path, original_mode)

        # Create handler with temp directory as workspace root
        handler = TomlHandler(workspace_root=temp_dir)

        try:
            # Apply change
            result = handler.apply_change(original_path, "newkey = 'newvalue'", 1, 1)
            assert result is True

            # Verify permissions were preserved
            current_mode = stat.S_IMODE(os.stat(original_path).st_mode)
            assert current_mode == original_mode, "File permissions should be preserved"

        finally:
            if os.path.exists(original_path):
                os.unlink(original_path)

    def test_apply_change_handles_permission_errors(self) -> None:
        """Test that apply_change handles permission errors gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write original TOML
            f.write("key = 'value'")
            f.flush()
            original_path = f.name
            temp_dir = os.path.dirname(f.name)

        # Create handler with temp directory as workspace root
        handler = TomlHandler(workspace_root=temp_dir)

        try:
            # Make file read-only after writing; on Windows, ensure replacement is permitted
            os.chmod(original_path, 0o444)
            if os.name == "nt":
                # On Windows, clear read-only attribute before atomic replace, then restore
                os.chmod(original_path, 0o644)
            result = handler.apply_change(original_path, "newkey = 'newvalue'", 1, 1)
            assert result is True

        finally:
            # Restore permissions and clean up
            if os.path.exists(original_path):
                os.chmod(original_path, 0o644)
                os.unlink(original_path)


class TestTomlHandlerErrorHandling:
    """Test TOML handler error handling and cleanup."""

    def test_apply_change_handles_write_errors(self) -> None:
        """Test that apply_change handles write errors gracefully."""
        # Anchor temp file inside a dedicated workspace so handler accepts the path
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = TomlHandler(workspace_root=tmpdir)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".toml", dir=tmpdir, delete=False
            ) as f:
                # Write original TOML
                f.write("key = 'value'")
                f.flush()
                original_path = f.name
            try:
                # Mock os.replace to raise an error
                with patch("os.replace", side_effect=OSError("Write error")):
                    result = handler.apply_change(original_path, "newkey = 'newvalue'", 1, 1)
                    assert result is False

                # Verify no temp files were left behind after error
                temp_dir = os.path.dirname(original_path)
                expected_prefix = f".{os.path.basename(original_path)}.tmp"
                temp_files = [fn for fn in os.listdir(temp_dir) if fn.startswith(expected_prefix)]
                assert (
                    len(temp_files) == 0
                ), "Temporary files should be cleaned up after write error"
            finally:
                if os.path.exists(original_path):
                    os.unlink(original_path)

    def test_apply_change_handles_fsync_errors(self) -> None:
        """Test that apply_change handles fsync errors gracefully."""
        # Anchor temp file inside a dedicated workspace so handler accepts the path
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = TomlHandler(workspace_root=tmpdir)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".toml", dir=tmpdir, delete=False
            ) as f:
                # Write original TOML
                original_content = "key = 'value'"
                f.write(original_content)
                f.flush()
                original_path = f.name
            try:
                # Mock fsync to raise an error
                with patch("os.fsync", side_effect=OSError("Fsync error")):
                    result = handler.apply_change(original_path, "newkey = 'newvalue'", 1, 1)
                    # Should fail due to fsync error
                    assert result is False
                    # Verify file content remained unchanged (no partial write)
                    with open(original_path, encoding="utf-8") as f:
                        assert (
                            f.read() == original_content
                        ), "File content should remain unchanged after fsync error"
            finally:
                if os.path.exists(original_path):
                    os.unlink(original_path)

    def test_validate_change_handles_missing_toml_libraries(self) -> None:
        """Test that validate_change handles missing TOML libraries."""
        handler = TomlHandler()

        with patch("review_bot_automator.handlers.toml_handler.TOML_READ_AVAILABLE", False):
            valid, msg = handler.validate_change("test.toml", "key = 'value'", 1, 3)
            assert valid is False
            assert "not available" in msg.lower()

    def test_apply_change_handles_missing_toml_libraries(self) -> None:
        """Test that apply_change handles missing TOML libraries."""
        handler = TomlHandler()

        with patch("review_bot_automator.handlers.toml_handler.TOML_READ_AVAILABLE", False):
            result = handler.apply_change("test.toml", "key = 'value'", 1, 3)
            assert result is False


class TestTomlHandlerContentSecurity:
    """Test TOML handler content security validation."""

    def test_validate_change_accepts_potentially_harmful_content(self) -> None:
        """Test that validate_change handles potentially harmful but valid TOML content."""
        handler = TomlHandler()

        # Use syntactically valid TOML with potentially harmful string content
        # Security is enforced in context of usage, not in TOML parsing itself
        test_cases = [
            ("key = '`echo test`'", "backticks"),
            ("key = '$(whoami)'", "subshell"),
            ("key = '${GITHUB_TOKEN}'", "env-var"),
            ("key = '../../../etc/passwd'", "path-traversal"),
        ]

        for content, description in test_cases:
            valid, msg = handler.validate_change("test.toml", content, 1, 1)
            # Valid TOML syntax should be accepted (security is in usage context)
            assert valid is True, f"Handler should accept valid TOML with {description}"
            assert "Valid TOML" in msg, f"Expected success message for {description}, got: {msg}"

    def test_apply_change_handles_large_content(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that apply_change handles large content safely."""
        handler = TomlHandler()

        # Create large but valid TOML content (~1MB)
        large_content = "key = '" + "x" * 1_000_000 + "'"

        # Set environment variable to allow temp files outside workspace
        # Using monkeypatch ensures automatic cleanup and prevents test interference
        monkeypatch.setenv("ALLOW_TEMP_OUTSIDE_WORKSPACE", "true")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write original TOML
            f.write("original = 'value'")
            f.flush()
            original_path = f.name

        try:
            result = handler.apply_change(original_path, large_content, 1, 1)
            # Should succeed with large content
            assert result is True, "Handler should successfully apply large content"

            # Verify file was updated
            with open(original_path) as f:
                updated_content = f.read()
            assert "x" * 1_000_000 in updated_content, "File should contain the large content"
            assert "key" in updated_content, "File should have the key from large_content"

        finally:
            if os.path.exists(original_path):
                os.unlink(original_path)
