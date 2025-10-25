"""Tests for secure file operations."""

import tempfile
from pathlib import Path

import pytest

from pr_conflict_resolver.security.secure_file_handler import SecureFileHandler


class TestSecureTempFile:
    """Tests for secure temporary file creation."""

    def test_create_and_cleanup(self) -> None:
        """Test temporary file is created and cleaned up automatically."""
        with SecureFileHandler.secure_temp_file() as temp_path:
            # File should exist
            assert Path(temp_path).exists()

            # Write to file
            Path(temp_path).write_text("test content")

        # File should be deleted after context exits
        assert not Path(temp_path).exists()

    def test_with_suffix(self) -> None:
        """Test temporary file with suffix."""
        with SecureFileHandler.secure_temp_file(suffix=".json") as temp_path:
            assert temp_path.endswith(".json")
            assert Path(temp_path).exists()

    def test_with_content(self) -> None:
        """Test temporary file with pre-written content."""
        content = '{"key": "value"}'

        with SecureFileHandler.secure_temp_file(content=content) as temp_path:
            assert Path(temp_path).read_text() == content

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
            assert not Path(path).exists()


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
        """Test atomic write handles errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"
            original_content = "original content"
            file_path.write_text(original_content)

            # Test with invalid path that will cause failure
            invalid_path = Path("/root/inaccessible/file.txt")  # Will fail to write

            # Should raise OSError
            with pytest.raises(OSError):
                SecureFileHandler.atomic_write(invalid_path, "content")

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
                SecureFileHandler.atomic_write(final_file, Path(temp_path).read_text())

            assert final_file.exists()
            assert final_file.read_text() == "temp content"

    def test_complete_workflow(self) -> None:
        """Test complete workflow: temp file -> atomic write -> copy -> cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temp file
            with SecureFileHandler.secure_temp_file(content="workflow content") as temp_path:
                # Atomic write to intermediate file
                intermediate = Path(tmpdir) / "intermediate.txt"
                SecureFileHandler.atomic_write(intermediate, Path(temp_path).read_text())

                # Copy to final location
                final = Path(tmpdir) / "final.txt"
                SecureFileHandler.safe_copy(intermediate, final)

                # Verify
                assert final.read_text() == "workflow content"

                # Cleanup
                SecureFileHandler.safe_delete(intermediate)

            assert not Path(tmpdir).exists() or not intermediate.exists()
