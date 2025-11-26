"""Tests for secure file operations."""

import contextlib
import os
import shutil
import tempfile
import unittest.mock
from pathlib import Path
from typing import IO, Any

import pytest

from review_bot_automator.security.secure_file_handler import SecureFileHandler


class TestSecureTempFile:
    """Tests for secure temporary file creation."""

    def test_create_and_cleanup(self) -> None:
        """Test temporary file is created and cleaned up automatically."""
        with SecureFileHandler.secure_temp_file() as temp_path:
            # File should exist
            assert temp_path.exists()

            # Write to file
            temp_path.write_text("test content")

        # File should be deleted after context exits
        assert not temp_path.exists()

    def test_with_suffix(self) -> None:
        """Test temporary file with suffix."""
        with SecureFileHandler.secure_temp_file(suffix=".json") as temp_path:
            assert temp_path.suffix == ".json"
            assert temp_path.exists()

    def test_with_content(self) -> None:
        """Test temporary file with pre-written content."""
        content = '{"key": "value"}'

        with SecureFileHandler.secure_temp_file(content=content) as temp_path:
            assert temp_path.read_text() == content

    def test_with_empty_content(self) -> None:
        """Test temporary file with empty string content."""
        with SecureFileHandler.secure_temp_file(content="") as temp_path:
            assert temp_path.read_text() == ""

    def test_multiple_temp_files(self) -> None:
        """Test creating multiple temporary files."""
        paths = []
        with SecureFileHandler.secure_temp_file() as temp1:
            paths.append(temp1)
            with SecureFileHandler.secure_temp_file() as temp2:
                paths.append(temp2)
                assert temp1 != temp2

        # All files should be cleaned up
        for path in paths:
            assert not path.exists()


class TestAtomicWrite:
    """Tests for atomic file writes."""

    def test_atomic_write_new_file(self) -> None:
        """Test atomic write to a new file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            content = "new file content"

            SecureFileHandler.atomic_write(file_path, content)

            assert file_path.exists()
            assert file_path.read_text() == content

    def test_atomic_write_existing_file(self) -> None:
        """Test atomic write to an existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            original_content = "original content"
            file_path.write_text(original_content)

            new_content = "new content"
            SecureFileHandler.atomic_write(file_path, new_content)

            assert file_path.read_text() == new_content

    def test_atomic_write_with_backup(self) -> None:
        """Test atomic write creates and removes backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("original")

            # Backup should be created and then removed
            SecureFileHandler.atomic_write(file_path, "new", backup=True)

            backup_path = file_path.with_suffix(file_path.suffix + ".bak")
            assert not backup_path.exists()

    def test_atomic_write_without_backup(self) -> None:
        """Test atomic write without backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("original")

            SecureFileHandler.atomic_write(file_path, "new", backup=False)

            assert file_path.read_text() == "new"

    def test_atomic_write_rollback_on_failure(self) -> None:
        """Test atomic write handles errors gracefully with proper rollback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            original_content = "original content"
            file_path.write_text(original_content)

            # Track calls to replace method to be more specific about when to fail
            replace_call_count = 0
            original_replace = Path.replace

            def mock_replace(self: Path, target: Path) -> None:
                nonlocal replace_call_count
                replace_call_count += 1
                # Only fail on the first call (the main atomic move), not the backup restoration
                if replace_call_count == 1:
                    raise OSError("Simulated filesystem error during atomic move")
                # For backup restoration, use the original method
                original_replace(self, target)

            # Use unittest.mock.patch to avoid type issues
            with unittest.mock.patch.object(Path, "replace", new=mock_replace):
                # Should raise OSError
                with pytest.raises(OSError, match="Atomic write failed"):
                    SecureFileHandler.atomic_write(file_path, "new content")

                # Verify original content is preserved (backup restored)
                assert file_path.read_text() == original_content

                # Verify no temp files remain
                temp_files = list(Path(tmpdir).glob("*.tmp"))
                assert len(temp_files) == 0, f"Temp files not cleaned up: {temp_files}"

                # Verify backup file is cleaned up after successful restoration
                backup_files = list(Path(tmpdir).glob("*.bak"))
                assert len(backup_files) == 0, f"Backup files not cleaned up: {backup_files}"

    def test_atomic_write_empty_content(self) -> None:
        """Test atomic write with empty content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            SecureFileHandler.atomic_write(file_path, "")

            assert file_path.exists()
            assert file_path.read_text() == ""


class TestSafeDelete:
    """Tests for safe file deletion."""

    def test_delete_file(self) -> None:
        """Test safe deletion of a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("content")

            result = SecureFileHandler.safe_delete(file_path)

            assert result is True
            assert not file_path.exists()

    def test_delete_nonexistent_file(self) -> None:
        """Test safe deletion of non-existent file."""
        result = SecureFileHandler.safe_delete(Path("/nonexistent/file.txt"))

        assert result is True  # Should return True, nothing to delete

    def test_delete_directory(self) -> None:
        """Test safe deletion of a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_dir"
            test_dir.mkdir()
            (test_dir / "file.txt").write_text("content")

            result = SecureFileHandler.safe_delete(test_dir)

            assert result is True
            assert not test_dir.exists()


class TestSafeCopy:
    """Tests for safe file copying."""

    def test_copy_file(self) -> None:
        """Test safe copy of a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.txt"
            destination = Path(tmpdir) / "dest.txt"
            source.write_text("content")

            result = SecureFileHandler.safe_copy(source, destination)

            assert result is True
            assert destination.exists()
            assert destination.read_text() == "content"

    def test_copy_nonexistent_file(self) -> None:
        """Test safe copy of non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "nonexistent.txt"
            destination = Path(tmpdir) / "dest.txt"

            result = SecureFileHandler.safe_copy(source, destination)

            assert result is False

    def test_copy_to_nonexistent_directory(self) -> None:
        """Test safe copy creates destination directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.txt"
            destination = Path(tmpdir) / "new_dir" / "dest.txt"
            source.write_text("content")

            result = SecureFileHandler.safe_copy(source, destination)

            assert result is True
            assert destination.exists()
            assert destination.read_text() == "content"


class TestIntegration:
    """Integration tests for secure file operations."""

    def test_atomic_write_then_copy(self) -> None:
        """Test atomic write followed by safe copy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.txt"
            destination = Path(tmpdir) / "dest.txt"

            # Atomic write
            SecureFileHandler.atomic_write(source, "content")

            # Safe copy
            result = SecureFileHandler.safe_copy(source, destination)

            assert result is True
            assert destination.read_text() == "content"

    def test_temp_file_then_atomic_write(self) -> None:
        """Test temp file followed by atomic write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            final_file = Path(tmpdir) / "final.txt"

            # Create temp file with content
            with SecureFileHandler.secure_temp_file(content="temp content") as temp_path:
                # Atomic write to final location
                SecureFileHandler.atomic_write(final_file, temp_path.read_text())

            assert final_file.exists()
            assert final_file.read_text() == "temp content"

    def test_complete_workflow(self) -> None:
        """Test complete workflow: temp file -> atomic write -> copy -> cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temp file
            with SecureFileHandler.secure_temp_file(content="workflow content") as temp_path:
                # Atomic write to intermediate file
                intermediate = Path(tmpdir) / "intermediate.txt"
                SecureFileHandler.atomic_write(intermediate, temp_path.read_text())

                # Copy to final location
                final = Path(tmpdir) / "final.txt"
                SecureFileHandler.safe_copy(intermediate, final)

                # Verify
                assert final.read_text() == "workflow content"

                # Cleanup
                SecureFileHandler.safe_delete(intermediate)

            assert not intermediate.exists()


class TestEdgeCases:
    """Edge case tests for secure file operations."""

    @pytest.mark.parametrize("backup", [True, False])
    def test_atomic_write_replace_failure(
        self, backup: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test atomic_write when replace/rename step fails to ensure no silent data loss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            original_content = "original content"
            new_content = "new content"

            # Create original file if backup is enabled
            if backup:
                file_path.write_text(original_content)

            # Mock Path.replace to raise OSError during atomic move
            def mock_replace(self: Path, target: Path) -> None:
                raise OSError("Simulated filesystem error during replace")

            monkeypatch.setattr(Path, "replace", mock_replace)

            # Should raise OSError and not lose data
            with pytest.raises(OSError, match="Atomic write failed"):
                SecureFileHandler.atomic_write(file_path, new_content)

            # Verify original content is preserved (backup case) or file doesn't exist (no backup)
            if backup:
                assert file_path.read_text() == original_content
            else:
                assert not file_path.exists()

            # Verify temp file is cleaned up
            temp_file = file_path.with_suffix(file_path.suffix + ".tmp")
            assert not temp_file.exists()

    @pytest.mark.parametrize(
        "target_type,target_content",
        [
            ("file", "file content"),
            ("directory", None),
        ],
    )
    def test_safe_delete_symlink_behavior(
        self, target_type: str, target_content: str | None
    ) -> None:
        """Test safe_delete behavior on symlinks pointing to files and directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create target
            if target_type == "file":
                target = tmpdir_path / "target_file.txt"
                target.write_text(target_content or "")
            else:  # directory
                target = tmpdir_path / "target_dir"
                target.mkdir()
                (target / "nested_file.txt").write_text("nested content")

            # Create symlink
            symlink = tmpdir_path / "symlink"
            symlink.symlink_to(target)

            # Verify symlink exists and points to target
            assert symlink.is_symlink()
            assert symlink.exists()
            assert target.exists()

            # Delete symlink (should only delete the link, not the target)
            result = SecureFileHandler.safe_delete(symlink)

            # Verify deletion was successful
            assert result is True
            assert not symlink.exists()  # Symlink should be gone
            assert target.exists()  # Target should still exist

            # Verify target content is preserved
            if target_type == "file":
                assert target.read_text() == target_content
            else:
                assert target.is_dir()
                assert (target / "nested_file.txt").exists()

    def test_secure_temp_file_explicit_empty_string(self) -> None:
        """Test secure_temp_file with explicit empty string content."""
        with SecureFileHandler.secure_temp_file(content="") as temp_path:
            # File should be created
            assert temp_path.exists()

            # File should contain exactly empty string
            assert temp_path.read_text() == ""

            # File should be empty (0 bytes)
            assert temp_path.stat().st_size == 0

            # Should be able to write to it
            temp_path.write_text("additional content")
            assert temp_path.read_text() == "additional content"

        # File should be cleaned up
        assert not temp_path.exists()

    def test_secure_temp_file_empty_vs_none_content(self) -> None:
        """Test distinction between empty string and None content."""
        # Test with None (should create empty file)
        with SecureFileHandler.secure_temp_file(content=None) as temp_path_none:
            assert temp_path_none.exists()
            assert temp_path_none.read_text() == ""

        # Test with empty string (should create file with empty content)
        with SecureFileHandler.secure_temp_file(content="") as temp_path_empty:
            assert temp_path_empty.exists()
            assert temp_path_empty.read_text() == ""

        # Both should behave the same way
        assert not temp_path_none.exists()
        assert not temp_path_empty.exists()

    def test_safe_delete_nonexistent_symlink(self) -> None:
        """Test safe_delete on nonexistent symlink."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_symlink = Path(tmpdir) / "nonexistent_symlink"

            # Should return True for nonexistent path
            result = SecureFileHandler.safe_delete(nonexistent_symlink)
            assert result is True

    def test_safe_delete_broken_symlink(self) -> None:
        """Test safe_delete on broken symlink."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a symlink to nonexistent target
            broken_symlink = tmpdir_path / "broken_symlink"
            broken_symlink.symlink_to("nonexistent_target")

            # Verify it's a broken symlink
            assert broken_symlink.is_symlink()
            assert not broken_symlink.exists()  # Broken symlink

            # Should successfully delete the symlink
            result = SecureFileHandler.safe_delete(broken_symlink)
            assert result is True
            assert not broken_symlink.exists()

    def test_atomic_write_file_write_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test atomic_write when file write fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"

            # Mock open to raise OSError during file write
            original_open = open

            def mock_open(*args: object, **kwargs: object) -> IO[Any]:
                if len(args) > 0 and str(args[0]).endswith(".tmp"):
                    raise OSError("Permission denied during file write")
                return original_open(*args, **kwargs)  # type: ignore[call-overload,no-any-return]

            monkeypatch.setattr("builtins.open", mock_open)

            # Should raise OSError
            with pytest.raises(OSError, match="Atomic write failed"):
                SecureFileHandler.atomic_write(file_path, "content")

            # Verify temp file is cleaned up
            temp_file = file_path.with_suffix(file_path.suffix + ".tmp")
            assert not temp_file.exists()

    def test_secure_temp_file_cleanup_failure(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test secure_temp_file cleanup failure logging (lines 57-58)."""

        # Mock Path.unlink to raise OSError during cleanup
        def mock_unlink(self: Path, missing_ok: bool = False) -> None:
            raise OSError("Permission denied during cleanup")

        monkeypatch.setattr(Path, "unlink", mock_unlink)

        with SecureFileHandler.secure_temp_file() as temp_path:
            # File should be created successfully
            assert temp_path.exists()

        # Verify warning is logged for cleanup failure
        assert "Failed to remove temporary file" in caplog.text

    def test_atomic_write_dir_fsync_not_directory_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test NotADirectoryError during directory fsync (lines 108-111)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"

            # Store original os.open
            original_open = os.open

            # Mock os.open to raise NotADirectoryError for directory operations
            def mock_open(path: str, flags: int, **kwargs: object) -> int:
                if hasattr(os, "O_DIRECTORY") and (flags & os.O_DIRECTORY):
                    raise NotADirectoryError("Not a directory")
                return original_open(path, flags, **kwargs)  # type: ignore[arg-type]

            monkeypatch.setattr(os, "open", mock_open)

            # Should complete successfully despite directory fsync failure
            SecureFileHandler.atomic_write(file_path, "content")
            assert file_path.exists()
            assert file_path.read_text() == "content"

    def test_atomic_write_dir_fsync_is_directory_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test IsADirectoryError during directory fsync (lines 108-111)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"

            # Store original os.open
            original_open = os.open

            # Mock os.open to raise IsADirectoryError for directory operations
            def mock_open(path: str, flags: int, **kwargs: object) -> int:
                if hasattr(os, "O_DIRECTORY") and (flags & os.O_DIRECTORY):
                    raise IsADirectoryError("Is a directory")
                return original_open(path, flags, **kwargs)  # type: ignore[arg-type]

            monkeypatch.setattr(os, "open", mock_open)

            # Should complete successfully despite directory fsync failure
            SecureFileHandler.atomic_write(file_path, "content")
            assert file_path.exists()
            assert file_path.read_text() == "content"

    def test_atomic_write_temp_cleanup_failure_during_rollback(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test temp file cleanup failure during rollback (lines 125-126)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("original")

            # Mock Path.replace to fail (triggering rollback)
            def mock_replace(self: Path, target: Path) -> None:
                raise OSError("Simulated filesystem error during replace")

            # Store original unlink method before patching
            original_unlink = Path.unlink

            # Mock Path.unlink to fail during temp file cleanup
            def mock_unlink(self: Path, missing_ok: bool = False) -> None:
                if str(self).endswith(".tmp"):
                    raise OSError("Permission denied during temp cleanup")
                # Use original unlink for other cases
                return original_unlink(self, missing_ok=missing_ok)

            monkeypatch.setattr(Path, "replace", mock_replace)
            monkeypatch.setattr(Path, "unlink", mock_unlink)

            # Should raise OSError
            with pytest.raises(OSError, match="Atomic write failed"):
                SecureFileHandler.atomic_write(file_path, "new content")

            # Verify warning is logged for temp file cleanup failure
            assert "Failed to remove temporary file" in caplog.text

    def test_safe_delete_unknown_file_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test safe_delete with unknown file type (line 160)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "unknown_file"
            file_path.write_text("content")

            # Mock all file type checks to return False (unknown type)
            def mock_is_file(self: Path) -> bool:
                return False

            def mock_is_dir(self: Path) -> bool:
                return False

            def mock_is_symlink(self: Path) -> bool:
                return False

            monkeypatch.setattr(Path, "is_file", mock_is_file)
            monkeypatch.setattr(Path, "is_dir", mock_is_dir)
            monkeypatch.setattr(Path, "is_symlink", mock_is_symlink)

            # Should attempt unlink for unknown type
            result = SecureFileHandler.safe_delete(file_path)
            assert result is True
            assert not file_path.exists()

    def test_safe_delete_failure(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test safe_delete failure logging (lines 164-166)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("content")

            # Mock Path.unlink to raise OSError
            def mock_unlink(self: Path, missing_ok: bool = False) -> None:
                raise OSError("Permission denied during deletion")

            monkeypatch.setattr(Path, "unlink", mock_unlink)

            # Should return False and log error
            result = SecureFileHandler.safe_delete(file_path)
            assert result is False
            assert "Failed to delete" in caplog.text

    def test_safe_copy_operation_failure(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test safe_copy when shutil.copy2 raises OSError (lines 200-202)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.txt"
            destination = Path(tmpdir) / "dest.txt"
            source.write_text("content")

            # Mock shutil.copy2 to raise OSError
            def mock_copy2(src: Path, dst: Path) -> None:
                raise OSError("Permission denied during copy")

            monkeypatch.setattr(shutil, "copy2", mock_copy2)

            # Should return False and log exception
            result = SecureFileHandler.safe_copy(source, destination)
            assert result is False
            assert "Failed to copy" in caplog.text


class TestSecureFileHandlerLogging:
    """Tests for logging behavior in secure file handler."""

    def test_cleanup_error_warning_logging(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test warning logging when temp file cleanup fails."""
        caplog.set_level("WARNING")

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            file_path.write_text("test content")

            # Track which files should fail to unlink
            temp_files_to_fail: set[Path] = set()

            # Mock temp file unlink to fail for specific temp files
            original_unlink = Path.unlink

            def mock_unlink(self: Path, missing_ok: bool = False) -> None:
                if self in temp_files_to_fail:
                    raise OSError("Permission denied during cleanup")
                return original_unlink(self, missing_ok=missing_ok)

            monkeypatch.setattr(Path, "unlink", mock_unlink)

            # Mock the atomic move operation to fail, which will trigger cleanup
            def mock_replace(self: Path, target: Path) -> None:
                # Add the temp file to the set of files that should fail to unlink
                temp_files_to_fail.add(self)
                # Raise an error to trigger the cleanup path
                raise OSError("Atomic move failed")

            monkeypatch.setattr(Path, "replace", mock_replace)

            # Call the real atomic_write method
            with contextlib.suppress(OSError):
                # Expected to fail due to our mock
                # Pass backup=False to avoid backup restoration side effects
                SecureFileHandler.atomic_write(file_path, "new content", backup=False)

            # Verify warning was logged
            assert any(
                "Failed to remove temporary file" in record.message for record in caplog.records
            )
