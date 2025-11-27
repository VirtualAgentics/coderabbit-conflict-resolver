"""Integration tests for RollbackManager with real git repositories."""

import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from review_bot_automator.core.rollback import RollbackError, RollbackManager


class TestRollbackManagerIntegration:
    """Integration tests for RollbackManager with actual git operations."""

    @pytest.fixture
    def git_repo(self) -> Generator[Path, None, None]:
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Initialize git repo
            subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )

            # Create initial commit
            test_file = repo_path / "test.txt"
            test_file.write_text("initial content\n")
            subprocess.run(
                ["git", "add", "test.txt"],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )

            yield repo_path

    def test_init_with_valid_repo(self, git_repo: Path) -> None:
        """Test RollbackManager initialization with valid git repository."""
        manager = RollbackManager(git_repo)
        assert manager.repo_path == git_repo
        assert manager.checkpoint_id is None

    def test_init_with_invalid_path(self) -> None:
        """Test RollbackManager initialization with invalid path."""
        with pytest.raises(ValueError, match="Repository path does not exist"):
            RollbackManager("/nonexistent/path")

    def test_init_with_non_git_directory(self) -> None:
        """Test RollbackManager initialization with non-git directory."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(ValueError, match="Path is not a git repository"),
        ):
            RollbackManager(tmpdir)

    def test_create_checkpoint_with_changes(self, git_repo: Path) -> None:
        """Test creating a checkpoint when there are uncommitted changes."""
        manager = RollbackManager(git_repo)

        # Make some changes
        test_file = git_repo / "test.txt"
        test_file.write_text("modified content\n")

        # Create checkpoint
        checkpoint_id = manager.create_checkpoint()

        assert checkpoint_id is not None
        # Checkpoint ID should be a stash reference like "stash@{0}"
        assert checkpoint_id.startswith("stash@{")
        assert manager.checkpoint_id == checkpoint_id
        assert manager.has_checkpoint()

        # Verify changes still exist in working directory
        assert test_file.read_text() == "modified content\n"

    def test_create_checkpoint_without_changes(self, git_repo: Path) -> None:
        """Test creating a checkpoint when there are no uncommitted changes."""
        manager = RollbackManager(git_repo)

        # No changes made
        checkpoint_id = manager.create_checkpoint()

        assert checkpoint_id == "EMPTY_CHECKPOINT"
        assert manager.checkpoint_id == "EMPTY_CHECKPOINT"
        assert manager.has_checkpoint()

    def test_create_checkpoint_twice_raises_error(self, git_repo: Path) -> None:
        """Test that creating a checkpoint twice raises an error."""
        manager = RollbackManager(git_repo)

        # Make changes and create first checkpoint
        test_file = git_repo / "test.txt"
        test_file.write_text("modified content\n")
        manager.create_checkpoint()

        # Try to create second checkpoint without committing first
        with pytest.raises(RollbackError, match="Checkpoint already exists"):
            manager.create_checkpoint()

    def test_rollback_restores_changes(self, git_repo: Path) -> None:
        """Test that rollback restores the working directory to checkpoint state."""
        manager = RollbackManager(git_repo)
        test_file = git_repo / "test.txt"

        # Create checkpoint with modified content
        test_file.write_text("checkpoint content\n")
        manager.create_checkpoint()

        # Make additional changes after checkpoint
        test_file.write_text("new content after checkpoint\n")
        new_file = git_repo / "new_file.txt"
        new_file.write_text("new file\n")

        # Rollback
        result = manager.rollback()

        assert result is True
        assert manager.checkpoint_id is None
        assert not manager.has_checkpoint()

        # Verify rollback restored checkpoint state
        assert test_file.read_text() == "checkpoint content\n"
        assert not new_file.exists()

    def test_rollback_empty_checkpoint(self, git_repo: Path) -> None:
        """Test rolling back an empty checkpoint (no-op)."""
        manager = RollbackManager(git_repo)

        # Create empty checkpoint (no changes)
        manager.create_checkpoint()
        assert manager.checkpoint_id == "EMPTY_CHECKPOINT"

        # Rollback should be a no-op
        result = manager.rollback()

        assert result is True
        assert manager.checkpoint_id is None

    def test_rollback_without_checkpoint(self, git_repo: Path) -> None:
        """Test that rollback without checkpoint returns False."""
        manager = RollbackManager(git_repo)

        result = manager.rollback()

        assert result is False
        assert manager.checkpoint_id is None

    def test_commit_clears_checkpoint(self, git_repo: Path) -> None:
        """Test that commit clears the checkpoint without rolling back."""
        manager = RollbackManager(git_repo)
        test_file = git_repo / "test.txt"

        # Create checkpoint with modified content
        test_file.write_text("modified content\n")
        manager.create_checkpoint()
        assert manager.has_checkpoint()

        # Commit (keep changes)
        manager.commit()

        assert manager.checkpoint_id is None
        assert not manager.has_checkpoint()

        # Verify changes are still present
        assert test_file.read_text() == "modified content\n"

    def test_commit_without_checkpoint(self, git_repo: Path) -> None:
        """Test that commit without checkpoint is a no-op."""
        manager = RollbackManager(git_repo)

        # Should not raise error
        manager.commit()

        assert manager.checkpoint_id is None

    def test_context_manager_with_exception_rolls_back(self, git_repo: Path) -> None:
        """Test that context manager rolls back on exception."""
        test_file = git_repo / "test.txt"
        initial_content = test_file.read_text()

        with pytest.raises(ValueError, match="Test error"), RollbackManager(git_repo) as manager:
            # Modify file
            test_file.write_text("modified in context\n")
            assert manager.has_checkpoint()

            # Raise exception to trigger rollback
            raise ValueError("Test error")

        # Verify rollback occurred
        assert test_file.read_text() == initial_content

    def test_context_manager_without_exception_auto_commits(self, git_repo: Path) -> None:
        """Test that context manager auto-commits on success."""
        test_file = git_repo / "test.txt"

        with RollbackManager(git_repo) as manager:
            # Modify file
            test_file.write_text("modified in context\n")
            assert manager.has_checkpoint()
            # Don't explicitly call commit - should auto-commit

        # Verify changes were kept (auto-commit)
        assert test_file.read_text() == "modified in context\n"

    def test_context_manager_with_explicit_commit(self, git_repo: Path) -> None:
        """Test context manager with explicit commit call."""
        test_file = git_repo / "test.txt"

        with RollbackManager(git_repo) as manager:
            test_file.write_text("explicitly committed\n")
            manager.commit()  # Explicit commit

        # Verify changes were kept
        assert test_file.read_text() == "explicitly committed\n"

    def test_multiple_file_modifications(self, git_repo: Path) -> None:
        """Test rollback with multiple file modifications."""
        manager = RollbackManager(git_repo)

        # Create initial files
        file1 = git_repo / "file1.txt"
        file2 = git_repo / "file2.txt"
        file1.write_text("file1 initial\n")
        file2.write_text("file2 initial\n")

        # Stage and commit
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add files"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        # Modify both files
        file1.write_text("file1 modified\n")
        file2.write_text("file2 modified\n")

        # Create checkpoint
        manager.create_checkpoint()

        # Make more changes
        file1.write_text("file1 further changed\n")
        file2.write_text("file2 further changed\n")
        file3 = git_repo / "file3.txt"
        file3.write_text("file3 new\n")

        # Rollback
        manager.rollback()

        # Verify rollback restored checkpoint state
        assert file1.read_text() == "file1 modified\n"
        assert file2.read_text() == "file2 modified\n"
        assert not file3.exists()

    def test_integration_with_conflict_resolver(self, git_repo: Path) -> None:
        """Test RollbackManager integration with ConflictResolver workflow."""
        # Setup: Create a Python file in the repo
        test_file = git_repo / "test.py"
        test_file.write_text('def foo():\n    return "original"\n')
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add test.py"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        # Test successful application with rollback
        with RollbackManager(git_repo):
            # Apply change would happen here
            # For this test, just modify the file directly
            test_file.write_text('def foo():\n    return "modified"\n')

            # Verify change was applied
            assert 'return "modified"' in test_file.read_text()
            # Context manager will auto-commit on success

        # Verify changes persisted
        assert 'return "modified"' in test_file.read_text()

        # Test failed application with rollback
        original_content = test_file.read_text()
        with pytest.raises(ValueError), RollbackManager(git_repo):
            test_file.write_text("corrupted content")
            raise ValueError("Simulated application failure")

        # Verify rollback occurred
        assert test_file.read_text() == original_content

    def test_has_checkpoint_status(self, git_repo: Path) -> None:
        """Test has_checkpoint() method accurately reflects checkpoint state."""
        manager = RollbackManager(git_repo)

        # Initially no checkpoint
        assert not manager.has_checkpoint()

        # After creating checkpoint
        test_file = git_repo / "test.txt"
        test_file.write_text("modified\n")
        manager.create_checkpoint()
        assert manager.has_checkpoint()

        # After rollback
        manager.rollback()
        assert not manager.has_checkpoint()

        # Create again and commit
        test_file.write_text("modified again\n")
        manager.create_checkpoint()
        assert manager.has_checkpoint()
        manager.commit()
        assert not manager.has_checkpoint()
