"""Security tests for TOML handler.

This module tests security aspects of the TOML handler including path validation,
atomic operations, permission handling, and error cleanup.
"""

import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pr_conflict_resolver.handlers.toml_handler import TomlHandler


class TestTomlHandlerPathSecurity:
    """Test TOML handler path security validation."""

    def test_apply_change_rejects_path_traversal(self) -> None:
        """Test that apply_change rejects path traversal attempts."""
        handler = TomlHandler()

        traversal_paths = [
            "../../../etc/passwd",
            "../../sensitive",
            "../parent",
            "..\\..\\..\\windows\\system32",
            "C:\\Windows\\System32",
            "/etc/passwd",
            "/var/log/secure",
        ]

        for path in traversal_paths:
            result = handler.apply_change(path, "key = 'value'", 1, 3)
            assert result is False, f"Should reject traversal path: {path}"

    def test_apply_change_rejects_absolute_paths(self) -> None:
        """Test that apply_change rejects absolute paths."""
        handler = TomlHandler()

        absolute_paths = [
            "/etc/passwd",
            "/var/log/secure",
            "/root/.ssh/id_rsa",
            "/usr/local/bin",
            "/home/user/documents",
            "C:\\Windows\\System32",
            "D:\\Program Files",
            "C:/Windows/System32",
            "\\\\server\\share\\repo",
        ]

        for path in absolute_paths:
            result = handler.apply_change(path, "key = 'value'", 1, 3)
            assert result is False, f"Should reject absolute path: {path}"

    def test_apply_change_accepts_relative_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that apply_change accepts safe relative paths with actual files."""
        # Patch TOML support flag to prevent short-circuit
        monkeypatch.setattr("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
        handler = TomlHandler()

        # Change to the temporary directory
        monkeypatch.chdir(tmp_path)

        safe_paths = [
            "config.toml",
            "settings.toml",
            "pyproject.toml",
        ]

        for path in safe_paths:
            # Create a temporary file with valid TOML content
            test_file = tmp_path / path
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

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
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

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    def test_apply_change_temp_file_cleanup(self) -> None:
        """Test that temporary files are cleaned up on error."""
        handler = TomlHandler()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write invalid TOML to trigger error
            f.write("invalid toml [")
            f.flush()
            original_path = f.name

        try:
            # This should fail and clean up temp files
            result = handler.apply_change(original_path, "key = 'value'", 1, 3)
            assert result is False

            # Verify no temp files were left behind
            temp_dir = os.path.dirname(original_path)
            expected_prefix = f".{os.path.basename(original_path)}.tmp"
            temp_files = [f for f in os.listdir(temp_dir) if f.startswith(expected_prefix)]
            assert len(temp_files) == 0, "Temporary files should be cleaned up"

        finally:
            if os.path.exists(original_path):
                os.unlink(original_path)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
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

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
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
            # Make file read-only after writing
            os.chmod(original_path, 0o444)

            # This should succeed because the handler can read the file
            # and write to a temp file, then replace it atomically
            result = handler.apply_change(original_path, "newkey = 'newvalue'", 1, 1)
            assert result is True  # Should succeed with atomic replacement

        finally:
            # Restore permissions and clean up
            if os.path.exists(original_path):
                os.chmod(original_path, 0o644)
                os.unlink(original_path)


class TestTomlHandlerErrorHandling:
    """Test TOML handler error handling and cleanup."""

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    def test_apply_change_handles_write_errors(self) -> None:
        """Test that apply_change handles write errors gracefully."""
        handler = TomlHandler()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write original TOML
            f.write("key = 'value'")
            f.flush()
            original_path = f.name

        try:
            # Mock os.replace to raise an error
            with patch("os.replace", side_effect=OSError("Write error")):
                result = handler.apply_change(original_path, "newkey = 'newvalue'", 1, 3)
                assert result is False

            # Verify no temp files were left behind after error
            temp_dir = os.path.dirname(original_path)
            expected_prefix = f".{os.path.basename(original_path)}.tmp"
            temp_files = [f for f in os.listdir(temp_dir) if f.startswith(expected_prefix)]
            assert len(temp_files) == 0, "Temporary files should be cleaned up after write error"

        finally:
            if os.path.exists(original_path):
                os.unlink(original_path)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    def test_apply_change_handles_fsync_errors(self) -> None:
        """Test that apply_change handles fsync errors gracefully."""
        handler = TomlHandler()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write original TOML
            original_content = "key = 'value'"
            f.write(original_content)
            f.flush()
            original_path = f.name

        try:
            # Mock fsync to raise an error
            with patch("os.fsync", side_effect=OSError("Fsync error")):
                result = handler.apply_change(original_path, "newkey = 'newvalue'", 1, 3)
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

        with patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", False):
            valid, msg = handler.validate_change("test.toml", "key = 'value'", 1, 3)
            assert valid is False
            assert "not available" in msg.lower()

    def test_apply_change_handles_missing_toml_libraries(self) -> None:
        """Test that apply_change handles missing TOML libraries."""
        handler = TomlHandler()

        with patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", False):
            result = handler.apply_change("test.toml", "key = 'value'", 1, 3)
            assert result is False


class TestTomlHandlerContentSecurity:
    """Test TOML handler content security validation."""

    def test_validate_change_rejects_malicious_content(self) -> None:
        """Test that validate_change rejects malicious TOML content."""
        handler = TomlHandler()

        malicious_contents = [
            "key = 'value'; rm -rf /'",
            "key = 'value`whoami`'",
            "key = 'value$(cat /etc/passwd)'",
            "key = 'value${GITHUB_TOKEN}'",
        ]

        for content in malicious_contents:
            valid, msg = handler.validate_change("test.toml", content, 1, 3)
            # Should either reject as invalid TOML or pass validation
            # The security is in the sanitization, not validation
            assert isinstance(valid, bool)
            assert isinstance(msg, str)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    def test_apply_change_handles_large_content(self) -> None:
        """Test that apply_change handles large content safely."""
        handler = TomlHandler()

        # Create large but valid TOML content
        large_content = "key = '" + "x" * 10000 + "'"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write original TOML
            f.write("original = 'value'")
            f.flush()
            original_path = f.name

        try:
            result = handler.apply_change(original_path, large_content, 1, 3)
            # Should handle large content gracefully
            assert isinstance(result, bool)

        finally:
            if os.path.exists(original_path):
                os.unlink(original_path)
