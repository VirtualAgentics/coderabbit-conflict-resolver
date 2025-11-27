"""Tests for file permission handling security.

This module tests that handlers and the resolver properly handle file permissions
to prevent unauthorized access and modification.
"""

import os
import tempfile
from pathlib import Path

import pytest

from review_bot_automator import ConflictResolver
from review_bot_automator.core.models import Change, FileType
from review_bot_automator.handlers.json_handler import JsonHandler


class TestFilePermissionSecurity:
    """Tests for file permission security."""

    @pytest.mark.skipif(os.name == "nt", reason="POSIX file modes not available on Windows")
    def test_handlers_create_backup_with_proper_permissions(
        self, tmp_path: Path, json_handler: JsonHandler
    ) -> None:
        """Test that backups are created with secure permissions (0600)."""
        # Create test file in tmp_path
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        # Create backup
        backup_path = json_handler.backup_file(str(test_file))

        # Verify backup exists
        assert Path(backup_path).exists(), "Backup should be created"

        # Get backup permissions
        backup_perms = os.stat(backup_path).st_mode
        mode_bits = backup_perms & 0o777

        # Backup should have secure permissions (0o600: owner read/write only)
        assert mode_bits == 0o600, f"Backup should have 0o600 permissions, got {oct(mode_bits)}"

    @pytest.mark.parametrize(
        "new_content,expected_string",
        [
            ('{"key": "new_value"}', "new_value"),
            ('{"key": "new"}', "new"),
            ('{"key": "updated"}', "updated"),
        ],
    )
    @pytest.mark.skipif(os.name == "nt", reason="chmod unreliable on Windows")
    def test_handlers_can_modify_readonly_files(
        self, new_content: str, expected_string: str
    ) -> None:
        """Test that atomic writes allow handlers to modify read-only files.

        With atomic writes (using temp files and os.replace), handlers can
        successfully modify read-only target files. This test verifies this
        behavior with multiple content variations.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = JsonHandler(workspace_root=tmpdir)
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text('{"key": "value"}')
            original_content = test_file.read_text()

            # Make file read-only
            os.chmod(test_file, 0o444)

            try:
                # With atomic writes, the handler can successfully modify the file
                # even if the target is read-only, because os.replace() works
                result = handler.apply_change(str(test_file), new_content, 1, 1)

                # Should succeed because atomic replace bypasses read-only target
                assert result is True, "Handler should succeed with atomic writes"

                # Verify file contents were actually modified
                current_content = test_file.read_text()
                assert current_content != original_content, "File should be modified"
                assert (
                    expected_string in current_content
                ), f"File should contain '{expected_string}'. Got: {current_content}"
            finally:
                # Restore permissions for cleanup
                os.chmod(test_file, 0o644)

    @pytest.mark.skipif(os.name == "nt", reason="chmod unreliable on Windows")
    def test_resolver_detect_conflicts_on_readonly_file(self) -> None:
        """Test that detect_conflicts works on read-only files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            try:
                # Make file read-only
                os.chmod(f.name, 0o444)

                # Use temp file's parent directory as workspace_root
                resolver = ConflictResolver(workspace_root=Path(f.name).parent)

                change = Change(
                    path=f.name,
                    start_line=1,
                    end_line=1,
                    content='{"key": "new_value"}',
                    metadata={},
                    fingerprint="test",
                    file_type=FileType.JSON,
                )

                # detect_conflicts should work on read-only files
                conflicts = resolver.detect_conflicts([change])
                assert isinstance(conflicts, list)

                # No conflicts expected for single change
                assert len(conflicts) == 0, "No conflicts expected for single change"
            finally:
                # Restore permissions for cleanup
                os.chmod(f.name, 0o644)
                Path(f.name).unlink()

    @pytest.mark.skipif(os.name == "nt", reason="POSIX file modes not available on Windows")
    def test_json_preserves_permissions(self) -> None:
        """Ensure JsonHandler preserves original file permissions on atomic write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            handler = JsonHandler(workspace_root=tmpdir)
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text('{"key": "value"}')

            # Make file read-only and then record the mode to preserve
            os.chmod(test_file, 0o444)
            original_mode = os.stat(test_file).st_mode
            original_mode_bits = original_mode & 0o777

            try:
                # Perform atomic write via handler
                result = handler.apply_change(str(test_file), '{"key": "new"}', 1, 1)
                assert result is True

                # Permissions should be preserved
                current_mode_bits = os.stat(test_file).st_mode & 0o777
                assert (
                    current_mode_bits == original_mode_bits
                ), f"Permissions changed: {oct(current_mode_bits)} != {oct(original_mode_bits)}"
            finally:
                # Restore for cleanup
                os.chmod(test_file, 0o644)
