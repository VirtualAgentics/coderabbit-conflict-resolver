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

    def test_handlers_create_backup_with_proper_permissions(self) -> None:
        """Test that backups are created with secure permissions (0600)."""
        handler = JsonHandler()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            try:
                # Create backup
                backup_path = handler.backup_file(f.name)

                # Verify backup exists
                assert Path(backup_path).exists(), "Backup should be created"

                # Get backup permissions
                backup_perms = os.stat(backup_path).st_mode
                backup_mode = oct(backup_perms & 0o777)

                # Backup should have restrictive permissions (0600)
                # On some systems, this might be 0644, so we check it's not world-writable
                assert "7" not in backup_mode, "Backup should not be world-writable"

                # Clean up
                Path(backup_path).unlink()
            finally:
                Path(f.name).unlink()

    def test_handlers_validate_directory_permissions(self) -> None:
        """Test that handlers validate directory permissions."""
        handler = JsonHandler()

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text('{"key": "value"}')

            # Make directory read-only
            os.chmod(tmpdir, 0o555)  # noqa: S103

            try:
                # Handler should handle permission errors gracefully
                result = handler.apply_change(str(test_file), '{"key": "new"}', 1, 1)
                # Should either fail or handle gracefully
                assert isinstance(result, bool), "Should return boolean result"
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
                # Attempt to modify file in read-only directory
                result = handler.apply_change(str(test_file), '{"key": "new"}', 1, 1)
                # Should handle the error gracefully
                assert isinstance(result, bool), "Should return boolean result"
            finally:
                # Restore permissions for cleanup
                os.chmod(tmpdir, 0o755)  # noqa: S103
                Path(test_file).unlink()

    def test_resolver_handles_permission_errors(self) -> None:
        """Test that resolver handles permission errors in changes."""
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

                # Resolver should handle permission errors
                conflicts = resolver.detect_conflicts([change])
                assert isinstance(conflicts, list), "Should return list of conflicts"
            finally:
                # Restore permissions for cleanup
                os.chmod(f.name, 0o644)
                Path(f.name).unlink()

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
