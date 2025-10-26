"""Path resolution utilities for consistent file path handling across handlers."""

from pathlib import Path


def resolve_file_path(path: str, workspace_root: Path) -> Path:
    """Resolve file path relative to workspace_root.

    Handles both absolute and relative paths:
    - Absolute paths are resolved as-is
    - Relative paths are resolved against workspace_root

    Args:
        path: File path to resolve (can be absolute or relative)
        workspace_root: Base directory for resolving relative paths

    Returns:
        Path: Resolved absolute Path object

    Example:
        >>> from pathlib import Path
        >>> workspace = Path('/workspace')
        >>> resolve_file_path('config.json', workspace)
        PosixPath('/workspace/config.json')
        >>> resolve_file_path('/absolute/path.json', workspace)
        PosixPath('/absolute/path.json')
    """
    path_obj = Path(path)
    return path_obj.resolve() if path_obj.is_absolute() else (workspace_root / path_obj).resolve()
