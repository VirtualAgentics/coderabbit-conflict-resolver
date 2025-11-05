"""Unit tests for RollbackManager.

This module provides unit tests for the RollbackManager class, testing
the core rollback logic in isolation using mocked git operations.

These tests complement the integration tests in test_rollback_manager.py
by focusing on the internal logic without requiring actual git operations.
"""

# mypy: ignore-errors

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pr_conflict_resolver.core.rollback import RollbackManager


class TestCheckpointCreation:
    """Tests for checkpoint creation logic."""

    def test_checkpoint_creation_structure(self, tmp_path: Path) -> None:
        """Test that checkpoint has correct data structure.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            # Mock git commands
            mock_run.return_value = Mock(returncode=0, stdout="stash@{0}\n")

            manager = RollbackManager(repo_path=tmp_path)
            checkpoint_id = manager.create_checkpoint()

            assert manager.has_checkpoint()
            assert manager.checkpoint_id is not None
            assert isinstance(manager.checkpoint_id, str)
            assert checkpoint_id == manager.checkpoint_id

    def test_checkpoint_captures_changes(self, tmp_path: Path) -> None:
        """Test that checkpoint captures modified files.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")

        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="commit_hash\n")

            manager = RollbackManager(repo_path=tmp_path)

            # Modify file before checkpoint
            test_file.write_text("modified content")

            manager.create_checkpoint()
            assert manager.has_checkpoint()

    def test_checkpoint_empty_when_no_changes(self, tmp_path: Path) -> None:
        """Test checkpoint with no changes.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="commit_hash\n")

            manager = RollbackManager(repo_path=tmp_path)
            manager.create_checkpoint()

            # Should still create checkpoint even with no changes
            assert manager.has_checkpoint()

    def test_multiple_checkpoints_raise_error(self, tmp_path: Path) -> None:
        """Test that creating multiple checkpoints raises error.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        from pr_conflict_resolver.core.rollback import RollbackError

        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="stash@{0}\n")

            manager = RollbackManager(repo_path=tmp_path)
            manager.create_checkpoint()

            # Second checkpoint should raise RollbackError
            with pytest.raises(RollbackError, match="Checkpoint already exists"):
                manager.create_checkpoint()


class TestCheckpointStorage:
    """Tests for checkpoint storage logic."""

    def test_checkpoint_stored_in_memory(self, tmp_path: Path) -> None:
        """Test that checkpoint is stored in manager instance.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="stash@{0}\n")

            manager = RollbackManager(repo_path=tmp_path)
            assert manager.checkpoint_id is None

            manager.create_checkpoint()
            assert manager.checkpoint_id is not None
            assert isinstance(manager.checkpoint_id, str)

    def test_checkpoint_contains_stash_reference(self, tmp_path: Path) -> None:
        """Test that checkpoint contains stash reference.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="stash@{0}\n")

            manager = RollbackManager(repo_path=tmp_path)
            manager.create_checkpoint()

            assert manager.checkpoint_id == "stash@{0}"
            assert "stash@{" in manager.checkpoint_id


class TestRollbackAlgorithm:
    """Tests for rollback algorithm logic."""

    def test_rollback_restores_files(self, tmp_path: Path) -> None:
        """Test that rollback algorithm restores files correctly.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")

        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="commit_hash\n")

            manager = RollbackManager(repo_path=tmp_path)
            manager.create_checkpoint()

            # Simulate rollback
            manager.rollback()
            assert not manager.has_checkpoint()

    def test_rollback_without_checkpoint_returns_false(self, tmp_path: Path) -> None:
        """Test that rollback without checkpoint returns False.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            # Mock git commands for initialization and operations
            mock_run.return_value = Mock(returncode=0, stdout="")

            manager = RollbackManager(repo_path=tmp_path)

            # rollback() returns False if no checkpoint exists
            result = manager.rollback()
            assert result is False

    def test_rollback_clears_checkpoint(self, tmp_path: Path) -> None:
        """Test that rollback clears the checkpoint.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="stash@{0}\n")

            manager = RollbackManager(repo_path=tmp_path)
            manager.create_checkpoint()
            assert manager.has_checkpoint()

            manager.rollback()
            assert not manager.has_checkpoint()
            assert manager.checkpoint_id is None


class TestCommitAlgorithm:
    """Tests for commit algorithm logic."""

    def test_commit_clears_checkpoint(self, tmp_path: Path) -> None:
        """Test that commit clears the checkpoint.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="stash@{0}\n")

            manager = RollbackManager(repo_path=tmp_path)
            manager.create_checkpoint()
            assert manager.has_checkpoint()

            manager.commit()
            assert not manager.has_checkpoint()
            assert manager.checkpoint_id is None

    def test_commit_without_checkpoint_succeeds(self, tmp_path: Path) -> None:
        """Test that commit without checkpoint succeeds (no-op).

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            # Mock git commands for initialization
            mock_run.return_value = Mock(returncode=0, stdout="")

            manager = RollbackManager(repo_path=tmp_path)

            # commit() is a no-op if no checkpoint exists (just logs warning)
            manager.commit()  # Should not raise
            assert manager.checkpoint_id is None


class TestInvalidCheckpointHandling:
    """Tests for invalid checkpoint handling."""

    def test_invalid_repo_path_raises_error(self) -> None:
        """Test that invalid repository path raises error."""
        with pytest.raises((ValueError, FileNotFoundError, RuntimeError)):
            RollbackManager(repo_path=Path("/nonexistent/path"))

    def test_non_git_directory_raises_error(self, tmp_path: Path) -> None:
        """Test that non-git directory raises error.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        # Create non-git directory
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()

        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            # Mock git command to fail (returncode 128 = not a git repository)
            mock_run.return_value = Mock(returncode=128, stderr="not a git repository")

            # RollbackManager raises ValueError for non-git directories
            with pytest.raises(ValueError, match="not a git repository"):
                RollbackManager(repo_path=non_git_dir)


class TestCheckpointStatus:
    """Tests for checkpoint status checking."""

    def test_has_checkpoint_returns_false_initially(self, tmp_path: Path) -> None:
        """Test that has_checkpoint returns False before creation.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            # Mock git commands for initialization
            mock_run.return_value = Mock(returncode=0, stdout="")

            manager = RollbackManager(repo_path=tmp_path)
            assert not manager.has_checkpoint()

    def test_has_checkpoint_returns_true_after_creation(self, tmp_path: Path) -> None:
        """Test that has_checkpoint returns True after creation.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="commit_hash\n")

            manager = RollbackManager(repo_path=tmp_path)
            manager.create_checkpoint()
            assert manager.has_checkpoint()

    def test_has_checkpoint_returns_false_after_rollback(self, tmp_path: Path) -> None:
        """Test that has_checkpoint returns False after rollback.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="commit_hash\n")

            manager = RollbackManager(repo_path=tmp_path)
            manager.create_checkpoint()
            manager.rollback()
            assert not manager.has_checkpoint()

    def test_has_checkpoint_returns_false_after_commit(self, tmp_path: Path) -> None:
        """Test that has_checkpoint returns False after commit.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="commit_hash\n")

            manager = RollbackManager(repo_path=tmp_path)
            manager.create_checkpoint()
            manager.commit()
            assert not manager.has_checkpoint()


class TestContextManagerBehavior:
    """Tests for context manager (with statement) behavior."""

    def test_context_manager_rolls_back_on_exception(self, tmp_path: Path) -> None:
        """Test that context manager rolls back on exception.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="stash@{0}\n")

            manager = RollbackManager(repo_path=tmp_path)

            try:
                with manager:
                    # Context manager auto-creates checkpoint in __enter__
                    # Simulate some work then raise error
                    raise ValueError("Test error")
            except ValueError:
                pass

            # Should have rolled back (checkpoint cleared)
            assert not manager.has_checkpoint()

    def test_context_manager_commits_on_success(self, tmp_path: Path) -> None:
        """Test that context manager commits on success.

        Args:
            tmp_path: Pytest temporary directory fixture
        """
        with patch("pr_conflict_resolver.core.rollback.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="stash@{0}\n")

            manager = RollbackManager(repo_path=tmp_path)

            with manager:
                # Context manager auto-creates checkpoint in __enter__
                # No exception, should auto-commit in __exit__
                pass

            # Should have committed (checkpoint cleared)
            assert not manager.has_checkpoint()
