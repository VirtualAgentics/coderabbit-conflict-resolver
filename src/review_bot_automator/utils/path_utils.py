# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Path resolution utilities for consistent file path handling across handlers."""

import os
from pathlib import Path


def resolve_file_path(
    path: str | os.PathLike[str],
    workspace_root: Path,
    allow_absolute: bool = False,
    validate_workspace: bool = True,
    enforce_containment: bool = True,
) -> Path:
    """Resolve file path relative to workspace_root.

    Handles both absolute and relative paths:
    - Absolute paths are rejected when allow_absolute is False
    - Relative paths are resolved against workspace_root

    Args:
        path: File path to resolve (can be absolute or relative)
        workspace_root: Base directory for resolving relative paths
        allow_absolute: If False (default), absolute paths are rejected outright. If True,
            absolute paths are permitted. When used with enforce_containment=True (default),
            absolute paths are validated to be contained within workspace_root.
        validate_workspace: If True (default), validate that workspace_root exists and is a
            directory. This does not perform containment checks. If False, skip existence/dir
            validation (assumes caller has verified these already).
        enforce_containment: Controls containment checks for absolute inputs when
            allow_absolute=True. Relative inputs are always required to resolve within
            workspace_root for security (containment enforced regardless of this flag).
            Set to False only if callers will validate containment for absolute paths
            themselves.

    Returns:
        Path: Resolved absolute Path object

    Raises:
        TypeError: If `path` is not a `str` or `os.PathLike[str]` (raised by
            `os.fspath(path)`).
        ValueError: If `path` is empty/whitespace-only, or if `workspace_root`
            does not exist/is not a directory. Also raised when an absolute
            path is provided while `allow_absolute=False`, or when a resolved
            path is outside `workspace_root` (per containment rules).
        OSError: In rare OS-level failures during resolution (platform-specific).
            Note: `Path.resolve()` is called with `strict=False`, so non-existent
            paths typically do not raise.

    Example:
        >>> from pathlib import Path
        >>> workspace = Path('/workspace')
        >>> resolve_file_path('config.json', workspace)
        PosixPath('/workspace/config.json')
        >>> resolve_file_path('/absolute/path.json', workspace)
        Traceback (most recent call last):
        ...
        ValueError: Absolute paths are not allowed when allow_absolute=False: /absolute/path.json
        >>> resolve_file_path('/workspace/file.json', workspace, allow_absolute=True)
        PosixPath('/workspace/file.json')
        >>> resolve_file_path(
        ...     '/outside/path.json', workspace, allow_absolute=True, enforce_containment=True
        ... )
        Traceback (most recent call last):
        ...
        ValueError: Absolute path '/outside/path.json' resolved to '/outside/path.json' which is
        ... outside workspace_root: /workspace
        >>> resolve_file_path(
        ...     '/absolute/path.json', workspace, allow_absolute=True, enforce_containment=False
        ... )
        PosixPath('/absolute/path.json')
    """
    # Validate path input (accept str/Path/PathLike)
    path_str = os.fspath(path)
    if isinstance(path_str, str) and not path_str.strip():
        raise ValueError("path cannot be empty or whitespace-only")

    # Validate workspace_root (skip if caller has already validated)
    if validate_workspace:
        if not workspace_root.exists():
            raise ValueError(f"workspace_root does not exist: {workspace_root}")
        if not workspace_root.is_dir():
            raise ValueError(f"workspace_root must be a directory: {workspace_root}")

    # Resolve workspace_root once and store for reuse
    workspace_root_resolved = workspace_root.resolve()

    path_obj = Path(path_str)
    if path_obj.is_absolute():
        if not allow_absolute:
            raise ValueError(f"Absolute paths are not allowed when allow_absolute=False: {path}")
        resolved = path_obj.resolve(strict=False)
        # Enforce containment for absolute inputs when requested
        if enforce_containment and not resolved.is_relative_to(workspace_root_resolved):
            raise ValueError(
                f"Absolute path '{path}' resolved to '{resolved}' which is outside "
                f"workspace_root: {workspace_root}"
            )
    else:
        resolved = (workspace_root_resolved / path_obj).resolve(strict=False)
        # Ensure containment for relative inputs
        if not resolved.is_relative_to(workspace_root_resolved):
            raise ValueError(
                f"Path '{path}' resolved to '{resolved}' which is outside "
                f"workspace_root: {workspace_root}"
            )

    return resolved
