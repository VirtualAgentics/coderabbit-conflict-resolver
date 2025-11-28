# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
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
        require_exact_pin: If True, require exact pins including '==', '~=', and '==='. If False,
            allow any version constraint (>=, <=, ~=, ==, ===, etc.). Wildcards ('*') are only
            valid with '==' and '!=' (not with '===', which performs arbitrary string equality).
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

    # Skip includes/constraints (accept both with and without space)
    if line.startswith(("-r", "--requirement", "-c", "--constraint")):
        return ValidationResult(is_valid=True, message="")

    # Skip hash-only lines (continuation lines for package hashes)
    if line.startswith("--hash="):
        return ValidationResult(is_valid=True, message="")

    # Strip inline comments to avoid false positives
    line_without_comment = line.split("#", 1)[0].rstrip()

    # Check if version is pinned or has reasonable constraints
    # PEP 440 compliance adjustments:
    # - '===' accepts arbitrary string (non-numeric identifiers allowed), no '*'
    # - '*' allowed only for '==' and '!=', as trailing wildcard (e.g. 1.2.* or 1.*)
    #   We do not fully validate position here; stricter checks handled below when
    #   require_exact_pin.
    version_pattern = (
        r"("  # start group
        r"===\s*[^*\s]+"  # identity, any non-space string without '*'
        r"|"  # or
        r"(==|!=)\s*\d[0-9A-Za-z.+-]*(?:\.\*)?"  # equality/inequality with optional trailing '.*'
        r"|"  # or
        r"~=\s*\d[0-9A-Za-z.+\-]*"  # compatible release, no '*'
        r"|"  # or
        r"(>=|<=|>|<)\s*\d[0-9A-Za-z.+\-]*"  # ranges, no '*'
        r")"
    )
    has_version_constraint = bool(re.search(version_pattern, line_without_comment))

    if require_exact_pin:
        # For production requirements.txt, require exact pinning (==, ~=, or ===)
        # - '===' must not include '*', accepts arbitrary identifier
        # - '~=' must not include '*'
        # - '==' may include trailing wildcard only on final segment: v*, or 1.* or 1.2.*
        exact_pin_ok = False

        # Identity pin
        if re.search(r"===\s*[^*\s]+", line_without_comment) or re.search(
            r"~=\s*\d[0-9A-Za-z.+\-]*", line_without_comment
        ):
            exact_pin_ok = True
        # Equality with optional trailing wildcard on final segment
        else:
            m = re.search(r"==\s*([0-9A-Za-z.+\-.*]+)", line_without_comment)
            if m:
                ver = m.group(1)
                if "*" not in ver:
                    exact_pin_ok = True
                else:
                    # allow only forms like '1.*' or '1.2.*' (no middle wildcards like '1.*.2')
                    if ver.endswith(".*") and ver.count("*") == 1:
                        core = ver[:-2]
                        # core must be digits and dots (PEP 440 segment approximation)
                        if re.fullmatch(r"\d+(?:\.\d+)*", core):
                            exact_pin_ok = True

        if not exact_pin_ok:
            return ValidationResult(
                is_valid=False,
                message=(
                    f"'{line}' does not specify exact version pinning. "
                    f"{dependency_type.capitalize()} dependencies must use "
                    f"'==1.2.3', '~=1.2.3', or '===1.2.3' for security"
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
