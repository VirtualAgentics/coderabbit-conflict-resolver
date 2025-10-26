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
        """Test that handlers respect read-only file permissions."""
        handler = JsonHandler()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            try:
                # Make file read-only
                os.chmod(f.name, 0o444)

                # Handler should not be able to modify read-only file
                result = handler.apply_change(f.name, '{"key": "new_value"}', 1, 1)
                assert not result, "Should not modify read-only file"
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
    def test_handlers_validate_directory_permissions(self) -> None:
        """Test that handlers validate directory permissions."""
        handler = JsonHandler()

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text('{"key": "value"}')

            # Make directory read-only
            os.chmod(tmpdir, 0o555)  # noqa: S103

            try:
                # Store original content for verification
                original_content = test_file.read_text()

                # Handler should fail to write to read-only directory
                result = handler.apply_change(str(test_file), '{"key": "new"}', 1, 1)

                # Should fail (return False) due to permission error
                assert result is False, "Handler should fail to write to read-only directory"

                # Verify file contents were not modified
                current_content = test_file.read_text()
                assert current_content == original_content, (
                    f"File contents should not be modified. "
                    f"Original: {original_content}, Current: {current_content}"
                )
            finally:
                # Restore permissions for cleanup
                os.chmod(tmpdir, 0o755)  # noqa: S103

    @pytest.mark.skipif(os.name == "nt", reason="Unix-specific permission test")
    def test_handlers_handle_permission_denied_error(self) -> None:
        """Test that handlers handle PermissionDenied errors."""
        handler = JsonHandler()

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text('{"key": "value"}')

            # Remove write permission from directory
            os.chmod(tmpdir, 0o555)  # noqa: S103

            try:
                original = test_file.read_text()
                result = handler.apply_change(str(test_file), '{"key": "new"}', 1, 1)
                assert result is False, "Handler should fail to write in read-only directory"
                assert test_file.read_text() == original, "File must remain unchanged"
            finally:
                # Restore permissions for cleanup
                os.chmod(tmpdir, 0o755)  # noqa: S103
                Path(test_file).unlink()

    @pytest.mark.skipif(os.name == "nt", reason="chmod unreliable on Windows")
    def test_resolver_detect_conflicts_readonly_file(self) -> None:
        """detect_conflicts should not depend on filesystem permissions."""
        resolver = ConflictResolver()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            try:
                # Make file read-only
                os.chmod(f.name, 0o444)

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
            finally:
                # Restore permissions for cleanup
                os.chmod(f.name, 0o644)
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
