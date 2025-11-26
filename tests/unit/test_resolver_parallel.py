"""Test parallel processing functionality in ConflictResolver."""

from pathlib import Path
from unittest.mock import patch

from review_bot_automator import Change, ConflictResolver, FileType


class TestParallelProcessing:
    """Test parallel processing features in ConflictResolver.apply_changes()."""

    # ========================================================================
    # Phase 1: Basic Parallel Processing Tests
    # ========================================================================

    def test_apply_changes_parallel_multiple_files(self, temp_workspace: Path) -> None:
        """Test parallel processing applies changes to multiple files correctly."""
        # Create multiple test files
        file1 = temp_workspace / "test1.txt"
        file2 = temp_workspace / "test2.txt"
        file3 = temp_workspace / "test3.txt"

        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nline2\nline3\n")
        file3.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        # Create changes for different files
        changes = [
            Change(
                path=str(file1),
                start_line=2,
                end_line=2,
                content="file1_modified",
                metadata={},
                fingerprint="fp1",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(file2),
                start_line=2,
                end_line=2,
                content="file2_modified",
                metadata={},
                fingerprint="fp2",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(file3),
                start_line=2,
                end_line=2,
                content="file3_modified",
                metadata={},
                fingerprint="fp3",
                file_type=FileType.PLAINTEXT,
            ),
        ]

        # Apply changes in parallel
        applied, skipped, failed = resolver.apply_changes(
            changes, validate=True, parallel=True, max_workers=3
        )

        # Verify all changes were applied
        assert len(applied) == 3
        assert len(skipped) == 0
        assert len(failed) == 0

        # Verify files were modified correctly
        assert "file1_modified" in file1.read_text()
        assert "file2_modified" in file2.read_text()
        assert "file3_modified" in file3.read_text()

    def test_apply_changes_parallel_same_file_sequential(self, temp_workspace: Path) -> None:
        """Test parallel processing handles multiple changes to same file sequentially."""
        # Create a test file
        test_file = temp_workspace / "test.txt"
        test_file.write_text("line1\nline2\nline3\nline4\nline5\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        # Create multiple changes for the same file (should be processed sequentially)
        changes = [
            Change(
                path=str(test_file),
                start_line=1,
                end_line=1,
                content="modified_line1",
                metadata={},
                fingerprint="fp1",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(test_file),
                start_line=3,
                end_line=3,
                content="modified_line3",
                metadata={},
                fingerprint="fp2",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(test_file),
                start_line=5,
                end_line=5,
                content="modified_line5",
                metadata={},
                fingerprint="fp3",
                file_type=FileType.PLAINTEXT,
            ),
        ]

        # Apply changes in parallel (same file changes processed sequentially)
        applied, skipped, failed = resolver.apply_changes(
            changes, validate=True, parallel=True, max_workers=4
        )

        # Verify all changes were applied
        assert len(applied) == 3
        assert len(skipped) == 0
        assert len(failed) == 0

        # Verify file content contains all modifications
        content = test_file.read_text()
        assert "modified_line1" in content
        assert "modified_line3" in content
        assert "modified_line5" in content

    def test_apply_changes_parallel_vs_sequential_equivalence(self, temp_workspace: Path) -> None:
        """Test parallel and sequential processing produce equivalent results."""
        # Create multiple test files
        files_parallel = [temp_workspace / f"parallel_{i}.txt" for i in range(5)]
        files_sequential = [temp_workspace / f"sequential_{i}.txt" for i in range(5)]

        for file in files_parallel + files_sequential:
            file.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        # Create parallel changes
        changes_parallel = [
            Change(
                path=str(file),
                start_line=2,
                end_line=2,
                content="modified",
                metadata={},
                fingerprint=f"fp_parallel_{i}",
                file_type=FileType.PLAINTEXT,
            )
            for i, file in enumerate(files_parallel)
        ]

        # Create sequential changes
        changes_sequential = [
            Change(
                path=str(file),
                start_line=2,
                end_line=2,
                content="modified",
                metadata={},
                fingerprint=f"fp_sequential_{i}",
                file_type=FileType.PLAINTEXT,
            )
            for i, file in enumerate(files_sequential)
        ]

        # Apply changes in parallel
        applied_p, skipped_p, failed_p = resolver.apply_changes(
            changes_parallel, validate=True, parallel=True, max_workers=4
        )

        # Apply changes sequentially
        applied_s, skipped_s, failed_s = resolver.apply_changes(
            changes_sequential, validate=True, parallel=False
        )

        # Results should be equivalent
        assert len(applied_p) == len(applied_s) == 5
        assert len(skipped_p) == len(skipped_s) == 0
        assert len(failed_p) == len(failed_s) == 0

    # ========================================================================
    # Phase 2: Thread Safety Tests
    # ========================================================================

    def test_apply_changes_parallel_thread_safe_collections(self, temp_workspace: Path) -> None:
        """Test parallel processing uses thread-safe collections correctly."""
        # Create many test files to ensure concurrent execution
        files = [temp_workspace / f"test_{i}.txt" for i in range(10)]
        for file in files:
            file.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        # Create changes for all files
        changes = [
            Change(
                path=str(file),
                start_line=2,
                end_line=2,
                content=f"modified_{i}",
                metadata={},
                fingerprint=f"fp{i}",
                file_type=FileType.PLAINTEXT,
            )
            for i, file in enumerate(files)
        ]

        # Apply with high parallelism to stress test thread safety
        applied, skipped, failed = resolver.apply_changes(
            changes, validate=True, parallel=True, max_workers=8
        )

        # Verify no race conditions occurred
        assert len(applied) == 10
        assert len(skipped) == 0
        assert len(failed) == 0

        # Verify all fingerprints are unique and accounted for
        applied_fingerprints = {c.fingerprint for c in applied}
        expected_fingerprints = {f"fp{i}" for i in range(10)}
        assert applied_fingerprints == expected_fingerprints

    def test_apply_changes_parallel_mixed_success_failure(self, temp_workspace: Path) -> None:
        """Test parallel processing correctly tracks mixed success/failure results."""
        # Create some valid files
        file1 = temp_workspace / "valid1.txt"
        file2 = temp_workspace / "valid2.txt"
        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        # Mix of valid and invalid changes
        changes = [
            # Valid changes
            Change(
                path=str(file1),
                start_line=2,
                end_line=2,
                content="modified1",
                metadata={},
                fingerprint="fp1",
                file_type=FileType.PLAINTEXT,
            ),
            # Invalid: non-existent file
            Change(
                path=str(temp_workspace / "nonexistent.txt"),
                start_line=1,
                end_line=1,
                content="test",
                metadata={},
                fingerprint="fp2",
                file_type=FileType.PLAINTEXT,
            ),
            # Valid change
            Change(
                path=str(file2),
                start_line=2,
                end_line=2,
                content="modified2",
                metadata={},
                fingerprint="fp3",
                file_type=FileType.PLAINTEXT,
            ),
        ]

        # Apply in parallel
        applied, skipped, failed = resolver.apply_changes(
            changes, validate=True, parallel=True, max_workers=3
        )

        # Verify correct categorization
        assert len(applied) == 2
        assert len(skipped) == 1
        assert len(failed) == 0

        # Verify valid changes were applied
        assert {c.fingerprint for c in applied} == {"fp1", "fp3"}
        assert {c.fingerprint for c in skipped} == {"fp2"}

    # ========================================================================
    # Phase 3: Error Handling Tests
    # ========================================================================

    def test_apply_changes_parallel_with_exceptions(self, temp_workspace: Path) -> None:
        """Test parallel processing handles exceptions in worker threads."""
        file1 = temp_workspace / "test1.txt"
        file2 = temp_workspace / "test2.txt"
        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        changes = [
            Change(
                path=str(file1),
                start_line=2,
                end_line=2,
                content="modified1",
                metadata={},
                fingerprint="fp1",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(file2),
                start_line=2,
                end_line=2,
                content="modified2",
                metadata={},
                fingerprint="fp2",
                file_type=FileType.PLAINTEXT,
            ),
        ]

        # Mock _apply_change to raise exception for one file
        original_apply = resolver._apply_change

        def mock_apply(change: Change) -> bool:
            if change.fingerprint == "fp1":
                raise OSError("Disk full")
            return original_apply(change)

        with patch.object(resolver, "_apply_change", side_effect=mock_apply):
            applied, skipped, failed = resolver.apply_changes(
                changes, validate=False, parallel=True, max_workers=2
            )

            # Verify exception handling
            assert len(applied) == 1  # fp2 succeeded
            assert len(skipped) == 0
            assert len(failed) == 1  # fp1 failed

            # Verify error details
            failed_change, error_msg = failed[0]
            assert failed_change.fingerprint == "fp1"
            assert "OSError" in error_msg
            assert "Disk full" in error_msg

    def test_apply_changes_parallel_validation_with_failures(self, temp_workspace: Path) -> None:
        """Test parallel processing with validation enabled tracks skipped changes."""
        # Create one valid file
        valid_file = temp_workspace / "valid.txt"
        valid_file.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        changes = [
            # Valid change
            Change(
                path=str(valid_file),
                start_line=2,
                end_line=2,
                content="modified",
                metadata={},
                fingerprint="fp1",
                file_type=FileType.PLAINTEXT,
            ),
            # Invalid: path traversal
            Change(
                path="../../../etc/passwd",
                start_line=1,
                end_line=1,
                content="malicious",
                metadata={},
                fingerprint="fp2",
                file_type=FileType.PLAINTEXT,
            ),
            # Invalid: non-existent file
            Change(
                path=str(temp_workspace / "missing.txt"),
                start_line=1,
                end_line=1,
                content="test",
                metadata={},
                fingerprint="fp3",
                file_type=FileType.PLAINTEXT,
            ),
        ]

        applied, skipped, failed = resolver.apply_changes(
            changes, validate=True, parallel=True, max_workers=3
        )

        # Verify validation worked in parallel
        assert len(applied) == 1
        assert len(skipped) == 2
        assert len(failed) == 0

        assert {c.fingerprint for c in applied} == {"fp1"}
        assert {c.fingerprint for c in skipped} == {"fp2", "fp3"}

    def test_apply_changes_parallel_worker_thread_exception_propagation(
        self, temp_workspace: Path
    ) -> None:
        """Test parallel processing logs worker thread exceptions correctly."""
        file1 = temp_workspace / "test1.txt"
        file2 = temp_workspace / "test2.txt"
        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        changes = [
            Change(
                path=str(file1),
                start_line=2,
                end_line=2,
                content="modified1",
                metadata={},
                fingerprint="fp1",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(file2),
                start_line=2,
                end_line=2,
                content="modified2",
                metadata={},
                fingerprint="fp2",
                file_type=FileType.PLAINTEXT,
            ),
        ]

        # Mock _validate_change to raise exception
        with (
            patch.object(
                resolver, "_validate_change", side_effect=RuntimeError("Validation crashed")
            ),
            patch.object(resolver.logger, "error") as mock_error,
        ):
            applied, skipped, failed = resolver.apply_changes(
                changes, validate=True, parallel=True, max_workers=2
            )

            # Worker thread exceptions should add affected changes to failed list
            assert len(applied) == 0
            assert len(skipped) == 0
            assert len(failed) == 2  # Both changes should be in failed list

            # Verify the correct changes are in the failed list
            failed_fingerprints = {change.fingerprint for change, _ in failed}
            assert failed_fingerprints == {"fp1", "fp2"}

            # Verify error messages contain proper context
            for _, error_msg in failed:
                assert "Worker thread exception" in error_msg
                assert "RuntimeError" in error_msg
                assert "Validation crashed" in error_msg

            # Verify exceptions were logged
            assert mock_error.call_count >= 2
            error_messages = [str(call[0][0]) for call in mock_error.call_args_list]
            assert any("Worker thread raised exception" in msg for msg in error_messages)

    # ========================================================================
    # Phase 4: Configuration Tests
    # ========================================================================

    def test_apply_changes_parallel_max_workers_configuration(self, temp_workspace: Path) -> None:
        """Test parallel processing respects max_workers configuration."""
        # Create many files
        files = [temp_workspace / f"test_{i}.txt" for i in range(20)]
        for file in files:
            file.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        changes = [
            Change(
                path=str(file),
                start_line=2,
                end_line=2,
                content=f"modified_{i}",
                metadata={},
                fingerprint=f"fp{i}",
                file_type=FileType.PLAINTEXT,
            )
            for i, file in enumerate(files)
        ]

        # Test with different max_workers values
        for max_workers in [1, 4, 8]:
            # Reset files for each iteration to ensure clean state
            for file in files:
                file.write_text("line1\nline2\nline3\n")

            applied, skipped, failed = resolver.apply_changes(
                changes, validate=True, parallel=True, max_workers=max_workers
            )

            # Results should be the same regardless of max_workers
            assert len(applied) == 20
            assert len(skipped) == 0
            assert len(failed) == 0

    def test_apply_changes_parallel_disabled(self, temp_workspace: Path) -> None:
        """Test apply_changes with parallel=False uses sequential processing."""
        file1 = temp_workspace / "test1.txt"
        file2 = temp_workspace / "test2.txt"
        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        changes = [
            Change(
                path=str(file1),
                start_line=2,
                end_line=2,
                content="modified1",
                metadata={},
                fingerprint="fp1",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(file2),
                start_line=2,
                end_line=2,
                content="modified2",
                metadata={},
                fingerprint="fp2",
                file_type=FileType.PLAINTEXT,
            ),
        ]

        # Verify parallel=False doesn't call _apply_changes_parallel
        with (
            patch.object(
                resolver, "_apply_changes_parallel", wraps=resolver._apply_changes_parallel
            ) as mock_parallel,
            patch.object(
                resolver, "_apply_changes_sequential", wraps=resolver._apply_changes_sequential
            ) as mock_sequential,
        ):
            applied, _skipped, _failed = resolver.apply_changes(
                changes, validate=True, parallel=False
            )

            # Verify sequential was called, parallel was not
            mock_sequential.assert_called_once()
            mock_parallel.assert_not_called()

            assert len(applied) == 2

    def test_apply_changes_parallel_enabled(self, temp_workspace: Path) -> None:
        """Test apply_changes with parallel=True uses parallel processing."""
        file1 = temp_workspace / "test1.txt"
        file2 = temp_workspace / "test2.txt"
        file1.write_text("line1\nline2\nline3\n")
        file2.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        changes = [
            Change(
                path=str(file1),
                start_line=2,
                end_line=2,
                content="modified1",
                metadata={},
                fingerprint="fp1",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(file2),
                start_line=2,
                end_line=2,
                content="modified2",
                metadata={},
                fingerprint="fp2",
                file_type=FileType.PLAINTEXT,
            ),
        ]

        # Verify parallel=True calls _apply_changes_parallel
        with (
            patch.object(
                resolver, "_apply_changes_parallel", wraps=resolver._apply_changes_parallel
            ) as mock_parallel,
            patch.object(
                resolver, "_apply_changes_sequential", wraps=resolver._apply_changes_sequential
            ) as mock_sequential,
        ):
            applied, _skipped, _failed = resolver.apply_changes(
                changes, validate=True, parallel=True, max_workers=4
            )

            # Verify parallel was called, sequential was not
            mock_parallel.assert_called_once()
            mock_sequential.assert_not_called()

            assert len(applied) == 2

    # ========================================================================
    # Phase 5: File Grouping Tests
    # ========================================================================

    def test_apply_changes_parallel_file_grouping(self, temp_workspace: Path) -> None:
        """Test parallel processing correctly groups changes by file."""
        # Create 3 files
        file1 = temp_workspace / "test1.txt"
        file2 = temp_workspace / "test2.txt"
        file3 = temp_workspace / "test3.txt"

        for file in [file1, file2, file3]:
            file.write_text("line1\nline2\nline3\nline4\nline5\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        # Create multiple changes per file (should be grouped)
        changes = [
            # File 1: 2 changes
            Change(
                path=str(file1),
                start_line=1,
                end_line=1,
                content="f1_mod1",
                metadata={},
                fingerprint="f1_fp1",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(file1),
                start_line=3,
                end_line=3,
                content="f1_mod2",
                metadata={},
                fingerprint="f1_fp2",
                file_type=FileType.PLAINTEXT,
            ),
            # File 2: 3 changes
            Change(
                path=str(file2),
                start_line=1,
                end_line=1,
                content="f2_mod1",
                metadata={},
                fingerprint="f2_fp1",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(file2),
                start_line=3,
                end_line=3,
                content="f2_mod2",
                metadata={},
                fingerprint="f2_fp2",
                file_type=FileType.PLAINTEXT,
            ),
            Change(
                path=str(file2),
                start_line=5,
                end_line=5,
                content="f2_mod3",
                metadata={},
                fingerprint="f2_fp3",
                file_type=FileType.PLAINTEXT,
            ),
            # File 3: 1 change
            Change(
                path=str(file3),
                start_line=2,
                end_line=2,
                content="f3_mod1",
                metadata={},
                fingerprint="f3_fp1",
                file_type=FileType.PLAINTEXT,
            ),
        ]

        applied, skipped, failed = resolver.apply_changes(
            changes, validate=True, parallel=True, max_workers=3
        )

        # All changes should succeed
        assert len(applied) == 6
        assert len(skipped) == 0
        assert len(failed) == 0

        # Verify all fingerprints accounted for
        applied_fps = {c.fingerprint for c in applied}
        expected_fps = {"f1_fp1", "f1_fp2", "f2_fp1", "f2_fp2", "f2_fp3", "f3_fp1"}
        assert applied_fps == expected_fps

    def test_apply_changes_parallel_empty_changes(self, temp_workspace: Path) -> None:
        """Test parallel processing handles empty changes list."""
        resolver = ConflictResolver(workspace_root=temp_workspace)

        applied, skipped, failed = resolver.apply_changes(
            [], validate=True, parallel=True, max_workers=4
        )

        assert len(applied) == 0
        assert len(skipped) == 0
        assert len(failed) == 0

    def test_apply_changes_parallel_single_change(self, temp_workspace: Path) -> None:
        """Test parallel processing handles single change efficiently."""
        test_file = temp_workspace / "test.txt"
        test_file.write_text("line1\nline2\nline3\n")

        resolver = ConflictResolver(workspace_root=temp_workspace)

        change = Change(
            path=str(test_file),
            start_line=2,
            end_line=2,
            content="modified",
            metadata={},
            fingerprint="fp1",
            file_type=FileType.PLAINTEXT,
        )

        applied, skipped, failed = resolver.apply_changes(
            [change], validate=True, parallel=True, max_workers=1
        )

        assert len(applied) == 1
        assert len(skipped) == 0
        assert len(failed) == 0
        assert "modified" in test_file.read_text()
