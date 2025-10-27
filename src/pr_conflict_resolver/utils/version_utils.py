"""Version validation utilities for dependency constraint checking.

This module provides functions to validate version constraints in requirements
files to ensure proper dependency pinning for security.
"""

import re
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of version constraint validation.

    Attributes:
        is_valid: True if the version constraint is valid, False otherwise.
        message: Error message when is_valid is False, empty string otherwise.
    """

    is_valid: bool
    message: str


def validate_version_constraint(
    line: str, require_exact_pin: bool = False, dependency_type: str = "dependency"
) -> ValidationResult:
    """Check if a requirements file line has proper version constraints.

    Args:
        line: Line from requirements file (may contain leading/trailing whitespace).
        require_exact_pin: If True, require exact pinning (== or ~=). If False,
            allow any version constraint (>=, <=, ~=, ==, etc.).
        dependency_type: Type of dependency for error messages
            (e.g., "dependency", "dev dependency").

    Returns:
        ValidationResult: Result containing is_valid flag and error message.
            is_valid is True if the line has appropriate version constraints,
            False otherwise. message contains an explanation when
            is_valid is False.
    """
    line = line.strip()

    # Skip comments and empty lines
    if not line or line.startswith("#"):
        return ValidationResult(is_valid=True, message="")

    # Skip -r includes
    if line.startswith(("-r ", "--requirement")):
        return ValidationResult(is_valid=True, message="")

    # Skip hash-only lines (continuation lines for package hashes)
    if line.startswith("--hash="):
        return ValidationResult(is_valid=True, message="")

    # Strip inline comments to avoid false positives
    line_without_comment = line.split("#", 1)[0].rstrip()

    # Check if version is pinned or has reasonable constraints
    # Allow ==, ~=, or range constraints like >=x.y.z,<a.b.c
    version_pattern = r"(>=|<=|==|~=|!=|>|<)\s*\d[0-9A-Za-z.+-]*"
    has_version_constraint = bool(re.search(version_pattern, line_without_comment))

    if require_exact_pin:
        # For production requirements.txt, require exact pinning (== or ~=)
        exact_pin_pattern = r"(==|~=)\s*\d[0-9A-Za-z.+-]*"
        has_exact_pin = bool(re.search(exact_pin_pattern, line_without_comment))

        if not has_exact_pin:
            return ValidationResult(
                is_valid=False,
                message=(
                    f"'{line}' does not specify exact version pinning. "
                    f"{dependency_type.capitalize()} dependencies must use "
                    f"'==1.2.3' or '~=1.2.3' for security"
                ),
            )
        return ValidationResult(is_valid=True, message="")
    else:
        # For dev requirements, allow range constraints but require some constraint
        if not has_version_constraint:
            return ValidationResult(
                is_valid=False,
                message=(
                    f"'{line}' does not specify a version constraint. "
                    "Use '==1.2.3', '~=1.2.3', or '>=1.2.3,<2.0.0' for security"
                ),
            )
        return ValidationResult(is_valid=True, message="")
