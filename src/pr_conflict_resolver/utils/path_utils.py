"""Path resolution utilities for consistent file path handling across handlers."""

from pathlib import Path


def resolve_file_path(
    path: str, workspace_root: Path, allow_absolute: bool = False, validate_workspace: bool = True
) -> Path:
    """Resolve file path relative to workspace_root.

    Handles both absolute and relative paths:
    - Absolute paths are resolved as-is
    - Relative paths are resolved against workspace_root

    Args:
        path: File path to resolve (can be absolute or relative)
        workspace_root: Base directory for resolving relative paths
        allow_absolute: If False (default), resolved paths must be within workspace_root.
                        If True, allows paths outside workspace_root.
        validate_workspace: If True (default), validate that workspace_root exists
                            and is a directory. If False, skip validation
                            (caller has already validated).

    Returns:
        Path: Resolved absolute Path object

    Raises:
        ValueError: If path is not a string, empty string, or whitespace-only. If
            workspace_root does not exist or is not a directory. If resolved path
            is outside workspace_root when allow_absolute=False.
        OSError:             If path resolution fails due to permission errors or broken
            symlinks. Note: Path.resolve() is called with strict=False, so
            non-existent paths will not raise OSError.
        RuntimeError: If path resolution encounters an unexpected error
            (propagated from Path.resolve()).

    Example:
        >>> from pathlib import Path
        >>> workspace = Path('/workspace')
        >>> resolve_file_path('config.json', workspace)
        PosixPath('/workspace/config.json')
        >>> resolve_file_path('/absolute/path.json', workspace)
        PosixPath('/absolute/path.json')
    """
    # Validate path input
    if not isinstance(path, str):
        raise ValueError("path must be a string")
    if not path or not path.strip():
        raise ValueError("path cannot be empty or whitespace-only")

    # Validate workspace_root (skip if caller has already validated)
    if validate_workspace:
        if not workspace_root.exists():
            raise ValueError(f"workspace_root does not exist: {workspace_root}")
        if not workspace_root.is_dir():
            raise ValueError(f"workspace_root must be a directory: {workspace_root}")

    # Resolve workspace_root once and store for reuse
    workspace_root_resolved = workspace_root.resolve()

    path_obj = Path(path)
    if path_obj.is_absolute():
        resolved = path_obj.resolve(strict=False)
    else:
        resolved = (workspace_root_resolved / path_obj).resolve(strict=False)

    # Check if resolved path is within workspace_root (unless allow_absolute=True)
    if not allow_absolute and not resolved.is_relative_to(workspace_root_resolved):
        raise ValueError(f"Path '{path}' resolves outside workspace_root: {workspace_root}")

    return resolved
