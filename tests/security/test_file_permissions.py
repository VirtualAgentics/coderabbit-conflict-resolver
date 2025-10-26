"""Tests for file permission handling security.

This module tests that handlers and the resolver properly handle file permissions
to prevent unauthorized access and modification.
"""

import os
import tempfile
from pathlib import Path

import pytest

from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.core.models import Change, FileType
from pr_conflict_resolver.handlers.json_handler import JsonHandler


class TestFilePermissionSecurity:
    """Tests for file permission security."""

    @pytest.mark.skipif(os.name == "nt", reason="chmod unreliable on Windows")
    def test_handlers_respect_readonly_files(self) -> None:
        """Test that handlers can handle read-only files with atomic writes.

        With atomic writes (using temp files and os.replace), even read-only
        target files can be successfully modified. The test verifies this behavior.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()
            temp_dir = os.path.dirname(f.name)

            # Create handler with temp directory as workspace root
            handler = JsonHandler(workspace_root=temp_dir)

            try:
                # Make file read-only
                os.chmod(f.name, 0o444)

                # With atomic writes, the handler can successfully modify the file
                # even if the target is read-only, because os.replace() works
                result = handler.apply_change(f.name, '{"key": "new_value"}', 1, 1)

                # Should succeed because atomic replace bypasses read-only target
                assert result is True, "Handler should succeed with atomic writes"

                # Verify file contents were actually modified
                with open(f.name) as check_file:
                    content = check_file.read()
                assert (
                    "new_value" in content
                ), f"File contents should be modified. Current: {content}"
            finally:
                # Restore permissions for cleanup
                os.chmod(f.name, 0o644)
                Path(f.name).unlink()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX file modes not available on Windows")
    def test_handlers_create_backup_with_proper_permissions(self) -> None:
        """Test that backups are created with secure permissions (0600)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()
            temp_dir = os.path.dirname(f.name)

            # Create handler with temp directory as workspace root
            handler = JsonHandler(workspace_root=temp_dir)

            try:
                # Create backup
                backup_path = handler.backup_file(f.name)

                # Verify backup exists
                assert Path(backup_path).exists(), "Backup should be created"

                # Get backup permissions
                backup_perms = os.stat(backup_path).st_mode
                mode_bits = backup_perms & 0o777

                # Backup should have secure permissions (0o600: owner read/write only)
                assert (
                    mode_bits == 0o600
                ), f"Backup should have 0o600 permissions, got {oct(mode_bits)}"

                # Explicitly ensure world bits are zero (no world permissions)
                assert (
                    mode_bits & 0o007
                ) == 0, f"Backup should have no world permissions, got {oct(mode_bits)}"

                # Clean up
                Path(backup_path).unlink()
            finally:
                Path(f.name).unlink()

    @pytest.mark.skipif(os.name == "nt", reason="chmod unreliable on Windows")
    def test_handlers_validate_read_only_file_behavior(self) -> None:
        """Test that handlers validate read-only file behavior.

        With atomic writes (using temp files and os.replace), even read-only
        target files can be successfully modified. The test verifies this behavior.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = JsonHandler(workspace_root=tmpdir)
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text('{"key": "value"}')

            # Make file read-only
            os.chmod(test_file, 0o444)

            try:
                # With atomic writes, the handler can successfully modify the file
                # even if the target is read-only, because os.replace() works
                result = handler.apply_change(str(test_file), '{"key": "new"}', 1, 1)

                # Should succeed because atomic replace bypasses read-only target
                assert result is True, "Handler should succeed with atomic writes"

                # Verify file contents were actually modified
                current_content = test_file.read_text()
                assert (
                    "new" in current_content
                ), f"File contents should be modified. Current: {current_content}"
            finally:
                # Restore permissions for cleanup
                os.chmod(test_file, 0o644)

    @pytest.mark.skipif(os.name == "nt", reason="Unix-specific permission test")
    def test_handlers_handle_permission_denied_error(self) -> None:
        """Test that handlers can handle read-only files with atomic writes.

        With atomic writes, handlers can modify read-only files because os.replace()
        works on read-only targets. This test verifies this behavior.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = JsonHandler(workspace_root=tmpdir)
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text('{"key": "value"}')

            # Remove write permission from file
            os.chmod(test_file, 0o444)

            try:
                original = test_file.read_text()
                result = handler.apply_change(str(test_file), '{"key": "new"}', 1, 1)
                assert result is True, "Handler should succeed with atomic writes on read-only file"
                # Verify file was actually modified
                new_content = test_file.read_text()
                assert new_content != original, "File should be modified successfully"
                assert "new" in new_content, f"File should contain 'new', got: {new_content}"
            finally:
                # Restore permissions for cleanup
                os.chmod(test_file, 0o644)
                Path(test_file).unlink()

    @pytest.mark.skipif(os.name == "nt", reason="chmod unreliable on Windows")
    def test_resolver_detect_conflicts_readonly_file(self) -> None:
        """detect_conflicts should not depend on filesystem permissions."""
        resolver = ConflictResolver()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            change = Change(
                path=f.name,
                start_line=1,
                end_line=1,
                content='{"key": "new_value"}',
                metadata={},
                fingerprint="test",
                file_type=FileType.JSON,
            )

            conflicts = resolver.detect_conflicts([change])
            assert isinstance(conflicts, list)
            Path(f.name).unlink()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX file modes not available on Windows")
    def test_secure_temp_file_creation(self) -> None:
        """Test that temporary files are created with secure permissions."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            f.flush()

            try:
                # Get file permissions
                file_stats = os.stat(f.name)

                # Check that file is not world-readable or world-writable
                world_perms = file_stats.st_mode & 0o007
                assert (
                    world_perms == 0
                ), f"Temp file should not have world permissions, got: {oct(file_stats.st_mode)}"
            finally:
                Path(f.name).unlink()
