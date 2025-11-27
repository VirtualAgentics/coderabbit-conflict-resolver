from pathlib import Path

import pytest

from review_bot_automator.utils.path_utils import resolve_file_path


def test_resolve_relative_and_absolute_contained(tmp_path: Path) -> None:
    """resolve_file_path returns resolved paths for relative inside and allowed absolute."""
    workspace = tmp_path
    (workspace / "sub").mkdir()

    p = resolve_file_path("sub/file.txt", workspace)
    assert p == (workspace / "sub/file.txt").resolve()

    abs_inside = workspace / "a.txt"
    r = resolve_file_path(str(abs_inside), workspace, allow_absolute=True)
    assert r == abs_inside.resolve()


def test_reject_absolute_when_not_allowed(tmp_path: Path) -> None:
    """Reject absolute paths when allow_absolute is False with appropriate error."""
    workspace = tmp_path
    # Construct an absolute path outside the workspace using the parent of tmp_path
    abs_outside = (tmp_path.parent / "nonexistent" / "path.txt").resolve()
    with pytest.raises(ValueError, match=r"Absolute paths are not allowed"):
        resolve_file_path(str(abs_outside), workspace, allow_absolute=False)


def test_reject_outside_workspace(tmp_path: Path) -> None:
    """Reject paths that resolve outside the workspace with clear error message."""
    workspace = tmp_path
    outside = (tmp_path.parent / "outside-file.txt").resolve()
    with pytest.raises(ValueError, match=r"outside\s+workspace_root"):
        resolve_file_path(str(outside), workspace, allow_absolute=True, enforce_containment=True)


def test_empty_path_rejected(tmp_path: Path) -> None:
    """Reject empty/whitespace-only path with specific ValueError message."""
    with pytest.raises(ValueError, match=r"cannot be empty or whitespace"):
        resolve_file_path("   ", tmp_path)


def test_reject_relative_escape_attempt(tmp_path: Path) -> None:
    """Reject relative paths that attempt to escape workspace via '..' traversal."""
    workspace = tmp_path
    with pytest.raises(ValueError, match=r"outside\s+workspace_root"):
        resolve_file_path("../../etc/passwd", workspace)
