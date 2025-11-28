# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Git-based rollback manager for safe change application.

This module provides the RollbackManager class for creating checkpoints and rolling back
changes using git stash functionality. It ensures that changes can be safely applied with
the ability to revert if something goes wrong.
"""

import logging
import shutil
import subprocess  # nosec B404  # Required for git operations with validated inputs
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


class RollbackError(Exception):
    """Exception raised when rollback operations fail."""


class RollbackManager:
    """Manages git-based rollback for safe change application.

    Uses git stash to create checkpoints before applying changes, allowing for
    safe rollback if something goes wrong during the application process.

    Example:
        >>> manager = RollbackManager("/path/to/repo")
        >>> checkpoint_id = manager.create_checkpoint()
        >>> try:
        >>>     # Apply changes...
        >>>     manager.commit()  # Success, clear checkpoint
        >>> except Exception:
        >>>     manager.rollback()  # Revert to checkpoint
    """

    def __init__(self, repo_path: str | Path) -> None:
        """Initialize the RollbackManager.

        Args:
            repo_path: Path to the git repository root.

        Raises:
            ValueError: If repo_path is invalid or not a git repository.
            RollbackError: If git is not available on the system.
        """
        # NOTE: We don't use InputValidator here because it's designed for validating
        # untrusted user input (CLI args, API payloads) with path traversal protection.
        # RollbackManager paths are internal/programmatic, not user-supplied, so we use
        # direct Path validation instead. This maintains defense-in-depth while using
        # the appropriate validation layer for each use case.

        # Validate and resolve repository path
        # Note: resolve() always returns an absolute path
        self.repo_path = Path(repo_path).resolve()

        if not self.repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repo_path}")

        if not self.repo_path.is_dir():
            raise ValueError(f"Repository path is not a directory: {self.repo_path}")

        # Check if git is available
        if not self._is_git_available():
            raise RollbackError(
                "git command not found. Git must be installed to use RollbackManager."
            )

        # Verify it's a git repository
        if not self._is_git_repo():
            raise ValueError(f"Path is not a git repository: {self.repo_path}")

        self.checkpoint_id: str | None = None
        self.logger = logger

    def _is_git_available(self) -> bool:
        """Check if git command is available on the system.

        Returns:
            True if git is available, False otherwise.
        """
        return shutil.which("git") is not None

    def _is_git_repo(self) -> bool:
        """Check if the repo_path is a valid git repository.

        Returns:
            True if it's a git repository, False otherwise.
        """
        try:
            result = subprocess.run(  # nosec B603, B607  # Git command with hardcoded args
                ["git", "rev-parse", "--git-dir"],  # noqa: S607
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False

    def _run_git_command(
        self, args: list[str], check: bool = True, timeout: float = 30
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command in the repository.

        Args:
            args: Git command arguments (without 'git' prefix).
            check: If True, raise CalledProcessError on non-zero exit (default: True).
            timeout: Command timeout in seconds (default: 30).

        Returns:
            CompletedProcess instance with stdout, stderr, and returncode.

        Raises:
            subprocess.CalledProcessError: If check=True and command fails.
            subprocess.TimeoutExpired: If command exceeds timeout.
            RollbackError: If git command fails in a way that prevents rollback operations.
        """
        try:
            result = (
                subprocess.run(  # nosec B603, B607  # noqa: S603  # Git command with validated args
                    ["git", *args],  # noqa: S607
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=check,
                )
            )
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git command failed: git {' '.join(args)}\nError: {e.stderr}")
            raise RollbackError(f"Git command failed: {e.stderr}") from e
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Git command timed out after {timeout}s: git {' '.join(args)}")
            raise RollbackError(f"Git command timed out after {timeout}s") from e
        except (OSError, subprocess.SubprocessError) as e:
            self.logger.error(f"Failed to execute git command: {e}")
            raise RollbackError(f"Failed to execute git command: {e}") from e

    def create_checkpoint(self) -> str:
        """Create a checkpoint of the current working directory state.

        Uses `git stash push --include-untracked` to save both tracked and untracked changes,
        then immediately reapplies them to restore the working directory. The stash is kept
        for later rollback or dropped on commit.

        Returns:
            Checkpoint ID (stash SHA) that can be used to restore this state.

        Raises:
            RollbackError: If checkpoint creation fails or a checkpoint already exists.

        Example:
            >>> checkpoint = manager.create_checkpoint()
            >>> print(f"Created checkpoint: {checkpoint}")
        """
        if self.checkpoint_id is not None:
            raise RollbackError(
                f"Checkpoint already exists: {self.checkpoint_id}. "
                "Commit or rollback before creating a new checkpoint."
            )

        # Check for uncommitted changes
        status_result = self._run_git_command(["status", "--porcelain"], check=True)
        if not status_result.stdout.strip():
            self.logger.warning("No uncommitted changes to checkpoint")
            # Create empty checkpoint marker (we'll just use a special value)
            self.checkpoint_id = "EMPTY_CHECKPOINT"
            return self.checkpoint_id

        # Create stash using push (create doesn't support --include-untracked)
        # We use push, capture the ref, then apply to restore working directory
        self._run_git_command(
            ["stash", "push", "--include-untracked", "-m", "RollbackManager checkpoint"],
            check=True,
        )

        # Store the stash reference (not SHA) for later use with apply/drop
        # Git stash commands require references like "stash@{0}", not SHA hashes
        stash_ref = "stash@{0}"

        # Get the SHA for logging/verification purposes only
        result = self._run_git_command(
            ["rev-parse", stash_ref],
            check=True,
        )
        stash_sha = result.stdout.strip()

        if not stash_sha:
            raise RollbackError("Failed to create checkpoint: could not get stash reference")

        # Immediately apply (not pop) to restore working directory to original state
        # This keeps the stash for later rollback while restoring files now
        try:
            self._run_git_command(["stash", "apply", stash_ref], check=True)
        except RollbackError as e:
            # If apply fails, try to clean up the stash
            self._run_git_command(["stash", "drop", stash_ref], check=False)
            raise RollbackError(
                "Failed to restore working directory after checkpoint creation"
            ) from e

        # Store the reference (not SHA) so apply/drop work correctly later
        self.checkpoint_id = stash_ref
        self.logger.info(f"Created checkpoint: {stash_ref} (SHA: {stash_sha})")
        return stash_ref

    def rollback(self) -> bool:
        """Roll back to the checkpoint state.

        Restores the working directory to the state captured by create_checkpoint().
        This uses `git reset --hard` and `git stash apply` to restore both tracked
        and untracked changes.

        Returns:
            True if rollback was successful, False if no checkpoint exists.

        Raises:
            RollbackError: If rollback operation fails.

        Example:
            >>> if not manager.rollback():
            >>>     print("No checkpoint to roll back to")
        """
        if self.checkpoint_id is None:
            self.logger.warning("No checkpoint to roll back to")
            return False

        if self.checkpoint_id == "EMPTY_CHECKPOINT":
            self.logger.info("Rolling back empty checkpoint (reset to clean state)")
            try:
                # Reset to clean state (no stashed changes to apply)
                self._run_git_command(["reset", "--hard", "HEAD"], check=True)
                self._run_git_command(["clean", "-fd"], check=True)
                self.checkpoint_id = None
                return True
            except RollbackError as e:
                self.logger.error(f"Empty checkpoint rollback failed: {e}")
                raise

        try:
            # First, reset any uncommitted changes
            self.logger.info("Resetting working directory to HEAD")
            self._run_git_command(["reset", "--hard", "HEAD"], check=True)

            # Remove untracked files and directories created after checkpoint
            self.logger.info("Removing untracked files")
            self._run_git_command(["clean", "-fd"], check=True)

            # Then apply the stashed changes
            self.logger.info(f"Applying checkpoint: {self.checkpoint_id}")
            self._run_git_command(["stash", "apply", self.checkpoint_id], check=True)

            # Drop the stash after successful apply
            try:
                self._run_git_command(["stash", "drop", self.checkpoint_id], check=False)
            except RollbackError:
                # Non-fatal if stash was already removed
                self.logger.warning(f"Could not drop stash {self.checkpoint_id} after rollback")

            self.logger.info("Rollback successful")
            self.checkpoint_id = None
            return True

        except RollbackError as e:
            # Keep checkpoint_id for potential retry
            self.logger.error(f"Rollback failed: {e}")
            raise

    def commit(self) -> None:
        """Commit the checkpoint (mark changes as successful).

        Clears the checkpoint without rolling back, indicating that changes were
        successfully applied and should be kept. Drops the stash to clean up.

        Example:
            >>> manager.create_checkpoint()
            >>> # ... apply changes successfully ...
            >>> manager.commit()  # Keep the changes
        """
        if self.checkpoint_id is None:
            self.logger.warning("No checkpoint to commit")
            return

        # Drop the stash if it's not the empty checkpoint marker
        if self.checkpoint_id != "EMPTY_CHECKPOINT":
            try:
                # Drop the stash by reference (e.g., "stash@{0}")
                self._run_git_command(["stash", "drop", self.checkpoint_id], check=False)
            except RollbackError:
                # Non-fatal if stash was already removed
                self.logger.warning(
                    f"Could not drop stash {self.checkpoint_id} (may have been removed)"
                )

        self.logger.info(f"Committing checkpoint: {self.checkpoint_id}")
        self.checkpoint_id = None

    def has_checkpoint(self) -> bool:
        """Check if a checkpoint currently exists.

        Returns:
            True if a checkpoint exists, False otherwise.
        """
        return self.checkpoint_id is not None

    def __enter__(self) -> "RollbackManager":
        """Context manager entry: create checkpoint.

        Returns:
            Self for use in with statement.

        Example:
            >>> with RollbackManager("/path/to/repo") as manager:
            >>>     # Changes will be automatically rolled back on exception
            >>>     apply_changes()
            >>>     manager.commit()  # Explicitly commit on success
        """
        self.create_checkpoint()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,  # noqa: ANN401
    ) -> Literal[False]:
        """Context manager exit: rollback on exception, commit on success.

        Args:
            exc_type: Exception type if an exception occurred, None otherwise.
            exc_val: Exception instance if an exception occurred, None otherwise.
            exc_tb: Exception traceback if an exception occurred, None otherwise.

        Returns:
            False to propagate any exception that occurred.
        """
        if exc_type is not None:
            # Exception occurred, rollback
            self.logger.warning(f"Exception occurred: {exc_type.__name__}. Rolling back...")
            try:
                self.rollback()
            except RollbackError as e:
                self.logger.error(f"Rollback failed during exception handling: {e}")
        elif self.has_checkpoint():
            # No exception but checkpoint still exists, auto-commit
            self.logger.info("Auto-committing checkpoint (no exception occurred)")
            self.commit()

        # Don't suppress the exception
        return False
