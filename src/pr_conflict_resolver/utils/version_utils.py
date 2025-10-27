"""Version validation utilities for dependency constraint checking.

This module provides functions to validate version constraints in requirements
files to ensure proper dependency pinning for security.
"""

import re


def validate_version_constraint(
    line: str, require_exact_pin: bool = False, dependency_type: str = "dependency"
) -> tuple[bool, str]:
    """Check if a requirements file line has proper version constraints.

    Args:
        line: Line from requirements file (may contain leading/trailing whitespace).
        require_exact_pin: If True, require exact pinning (== or ~=). If False,
            allow any version constraint (>=, <=, ~=, ==, etc.).
        dependency_type: Type of dependency for error messages
            (e.g., "dependency", "dev dependency").

    Returns:
        tuple[bool, str]: (is_valid, error_message) where is_valid is True
            if the line has appropriate version constraints, False otherwise.
            error_message contains an explanation when is_valid is False.
    """
    line = line.strip()

    # Skip comments and empty lines
    if not line or line.startswith("#"):
        return True, ""

    # Skip -r includes
    if line.startswith(("-r ", "--requirement")):
        return True, ""

    # Skip hash-only lines (continuation lines for package hashes)
    if line.startswith("--hash="):
        return True, ""

    # Check if version is pinned or has reasonable constraints
    # Allow ==, ~=, or range constraints like >=x.y.z,<a.b.c
    version_pattern = r"(>=|<=|==|~=|!=|>|<)\s*\d[\d\w\.\+\-]*"
    has_version_constraint = bool(re.search(version_pattern, line))

    if require_exact_pin:
        # For production requirements.txt, require exact pinning (== or ~=)
        exact_pin_pattern = r"(==|~=)\s*\d[\d\w\.\+\-]*"
        has_exact_pin = bool(re.search(exact_pin_pattern, line))

        if not has_exact_pin:
            return False, (
                f"'{line}' does not specify exact version pinning. "
                f"{dependency_type.capitalize()} dependencies must use "
                f"'==1.2.3' or '~=1.2.3' for security"
            )
        return True, ""
    else:
        # For dev requirements, allow range constraints but require some constraint
        if not has_version_constraint:
            return False, (
                f"'{line}' does not specify a version constraint. "
                "Use '==1.2.3', '~=1.2.3', or '>=1.2.3,<2.0.0' for security"
            )
        return True, ""
