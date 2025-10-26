"""TOML handler for applying CodeRabbit suggestions with AST validation.

This handler provides TOML-aware suggestion application with structure validation.
"""

import contextlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from ..core.models import Change, Conflict
from ..security.input_validator import InputValidator
from .base import BaseHandler

try:
    import tomllib

    TOML_READ_AVAILABLE = True
except ImportError:
    TOML_READ_AVAILABLE = False

try:
    import tomli_w

    TOML_WRITE_AVAILABLE = True
except ImportError:
    TOML_WRITE_AVAILABLE = False


class TomlHandler(BaseHandler):
    """Handler for TOML files with structure validation."""

    def __init__(self) -> None:
        """Initialize the TOML handler and its logger.

        Creates a module-level logger on the instance. Uses Python 3.11+ standard library
        tomllib for parsing and tomli-w for writing TOML files. If TOML support is not
        available, logs a warning with installation instructions.

        Note:
            This handler requires Python 3.11+ for tomllib support. For older Python versions,
            consider using the tomli package as an alternative.

        Dependencies:
            - tomllib: Python 3.11+ standard library for TOML parsing
            - tomli-w: Third-party package for TOML writing
        """
        self.logger = logging.getLogger(__name__)
        if not TOML_READ_AVAILABLE:
            self.logger.warning("TOML parsing support unavailable. Install tomllib (Python 3.11+)")
        elif not TOML_WRITE_AVAILABLE:
            self.logger.warning("TOML write support missing. Install with: pip install tomli-w")

    def can_handle(self, file_path: str) -> bool:
        """Determine whether the handler supports the given file path.

        @returns
            `True` if the file path ends with ".toml" (case-insensitive), `False` otherwise.
        """
        return file_path.lower().endswith(".toml")

    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        r"""Apply a TOML suggestion to the file by merging and writing the result back.

        This method implements security validation to prevent path traversal attacks and
        ensures safe TOML processing using Python 3.11+ standard library tomllib.

        Security Features:
            - Path traversal protection using InputValidator.validate_file_path()
            - Safe TOML parsing using tomllib (Python 3.11+ standard library)
            - Structure validation to prevent TOML corruption
            - File existence verification before processing

        Parameters:
            path (str): Filesystem path to the TOML file to modify. Must pass security validation.
            content (str): TOML-formatted suggestion content to merge into the file.
            start_line (int): One-based start line of the region the suggestion targets.
            end_line (int): One-based end line of the region the suggestion targets.

        Returns:
            bool: `True` if the suggestion was successfully merged and written to the file,
                `False` otherwise.

        Example:
            >>> handler = TomlHandler()
            >>> # Valid TOML and path
            >>> handler.apply_change("config.toml", '[section]\nkey = "value"', 1, 2)
            True
            >>> # Path traversal attempt - rejected
            >>> handler.apply_change("../../../etc/passwd", '[section]\nkey = "value"', 1, 2)
            False

        Warning:
            This method validates file paths to prevent directory traversal attacks.
            Invalid paths are rejected before any TOML processing occurs.

        Note:
            Requires Python 3.11+ for tomllib support. Uses tomli-w for writing TOML files.

        See Also:
            InputValidator.validate_file_path: Path security validation
            validate_change: Content validation for TOML structure
        """
        # Validate file path to prevent path traversal attacks
        # For absolute paths, use parent directory as base_dir for containment check
        file_path_obj = Path(path)
        base_dir_for_validation = str(file_path_obj.parent) if file_path_obj.is_absolute() else None

        if not InputValidator.validate_file_path(
            path, allow_absolute=True, base_dir=base_dir_for_validation
        ):
            self.logger.error(f"Invalid file path rejected: {path}")
            return False

        if not TOML_READ_AVAILABLE or not TOML_WRITE_AVAILABLE:
            self.logger.error("TOML support incomplete. Install tomllib (Python 3.11+) and tomli-w")
            return False

        file_path = Path(path)

        # Parse original file
        try:
            original_content = file_path.read_text(encoding="utf-8")
            original_data = tomllib.loads(original_content)
        except (OSError, UnicodeDecodeError) as e:
            self.logger.error(f"Error reading original TOML file: {e}")
            return False
        except tomllib.TOMLDecodeError as e:
            self.logger.error(f"Error parsing original TOML: {e}")
            return False

        # Parse suggestion
        try:
            suggestion_data = tomllib.loads(content)
        except tomllib.TOMLDecodeError as e:
            self.logger.error(f"Error parsing TOML suggestion: {e}")
            return False

        # Apply suggestion using smart merge
        merged_data = self._smart_merge_toml(original_data, suggestion_data, start_line, end_line)

        # Write with proper formatting using atomic operation
        original_mode = None
        temp_path = None
        dir_fd = None

        try:
            # Capture original file mode if it exists
            if file_path.exists():
                original_mode = os.stat(file_path).st_mode

            # Create temporary file in the same directory as the target file
            temp_dir = file_path.parent
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=temp_dir, prefix=f".{file_path.name}.tmp", delete=False
            ) as temp_file:
                temp_path = Path(temp_file.name)
                tomli_w.dump(merged_data, temp_file)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Ensure data is written to disk

            # Apply original file mode to temp file if we have it
            if original_mode is not None:
                os.chmod(temp_path, original_mode)

            # Atomically replace the original file
            os.replace(temp_path, file_path)

            # Ensure directory durability by fsyncing the parent directory
            try:
                dir_fd = os.open(temp_dir, os.O_RDONLY)
                os.fsync(dir_fd)
            except OSError:
                pass  # Ignore directory fsync errors
            finally:
                if dir_fd is not None:
                    os.close(dir_fd)
                    dir_fd = None

            return True
        except (OSError, UnicodeEncodeError) as e:
            self.logger.error(f"Error writing TOML file: {e}")
            return False
        finally:
            # Clean up temporary file if it exists
            if temp_path is not None and temp_path.exists():
                with contextlib.suppress(OSError):
                    temp_path.unlink()

            # Ensure directory file descriptor is closed
            if dir_fd is not None:
                with contextlib.suppress(OSError):
                    os.close(dir_fd)

    def validate_change(
        self, path: str, content: str, start_line: int, end_line: int
    ) -> tuple[bool, str]:
        """Validate the provided TOML suggestion and report whether it parses.

        Parameters:
            path (str): File path the suggestion targets (informational).
            content (str): TOML text to validate.
            start_line (int): Starting line number (1-based) of the suggested range.
            end_line (int): Ending line number (1-based) of the suggested range.

        Returns:
            tuple[bool, str]: `(True, "Valid TOML")` if `content` parses as TOML,
                `(False, "<error message>")` otherwise.
        """
        if not TOML_READ_AVAILABLE:
            return False, "tomllib not available"

        try:
            tomllib.loads(content)
            return True, "Valid TOML"
        except tomllib.TOMLDecodeError as e:
            return False, f"Invalid TOML: {e}"

    def detect_conflicts(self, path: str, changes: list[Change]) -> list[Conflict]:
        """Identify conflicting changes that target the same TOML sections.

        Parses each change's TOML content to collect affected section paths, groups changes by
        section, and creates a Conflict for any section modified by more than one change.
        Changes whose content fails to parse are skipped (a warning is logged). Each Conflict's
        line_range spans from the first change's start_line to the last change's end_line and
        includes an overlap_percentage computed by _calculate_overlap_percentage.

        Parameters:
            path (str): File path for conflicts to report in each Conflict.
            changes (list[Change]): List of Change objects to analyze.

        Returns:
            list[Conflict]: Conflicts detected for sections with multiple changes; empty list if
                no conflicts found.
        """
        conflicts: list[Conflict] = []

        # Group changes by section
        section_changes: dict[str, list[Change]] = {}
        for change in changes:
            try:
                data = tomllib.loads(change.content)
                sections = self._extract_sections(data)
                for section in sections:
                    if section not in section_changes:
                        section_changes[section] = []
                    section_changes[section].append(change)
            except Exception as e:
                self.logger.warning(f"Failed to process change: {e}")
                continue

        # Find conflicts (multiple changes to same section)
        for _section, section_change_list in section_changes.items():
            if len(section_change_list) > 1:
                # Calculate actual overlap percentage
                overlap_percentage = self._calculate_overlap_percentage(section_change_list)

                conflicts.append(
                    Conflict(
                        file_path=path,
                        line_range=(
                            section_change_list[0].start_line,
                            section_change_list[-1].end_line,
                        ),
                        changes=section_change_list,
                        conflict_type="section_conflict",
                        severity="medium",
                        overlap_percentage=overlap_percentage,
                    )
                )

        return conflicts

    def _calculate_overlap_percentage(self, changes: list[Change]) -> float:
        """Compute the percentage of line-range overlap among multiple changes.

        Args:
            changes (list[Change]): List of Change objects each containing `start_line` and
                `end_line`.

        Returns:
            float: Overlap percentage between 0.0 and 100.0. Returns 0.0 if fewer than two changes
                or if there is no overlapping range.
        """
        if len(changes) < 2:
            return 0.0

        # Gather all line ranges
        starts = [change.start_line for change in changes]
        ends = [change.end_line for change in changes]

        # Calculate intersection (overlapping lines)
        intersection_start = max(starts)
        intersection_end = min(ends)
        intersection_lines = max(0, intersection_end - intersection_start + 1)

        # Calculate union (total span)
        union_start = min(starts)
        union_end = max(ends)
        union_lines = union_end - union_start + 1

        if union_lines == 0:
            return 0.0

        return (intersection_lines / union_lines) * 100.0

    def _smart_merge_toml(
        self, original: dict[str, Any], suggestion: dict[str, Any], start_line: int, end_line: int
    ) -> dict[str, Any]:
        """Merge two TOML mappings by applying suggestion top-level keys onto the original.

        The suggestion's top-level keys overwrite or add to the original mapping; nested tables
        are not merged recursively. The start_line and end_line parameters are accepted for API
        compatibility but do not affect the merge behavior.

        Parameters:
            original (dict[str, Any]): Original TOML data as a mapping.
            suggestion (dict[str, Any]): Suggested TOML data to apply on top of the original.
            start_line (int): Starting line of the change (ignored).
            end_line (int): Ending line of the change (ignored).

        Returns:
            dict[str, Any]: A new mapping containing the merged TOML data.
        """
        # For TOML, we typically want to merge at the top level
        result = original.copy()
        for key, value in suggestion.items():
            result[key] = value
        return result

    def _extract_sections(self, data: dict[str, Any], prefix: str = "") -> list[str]:
        """Collects dot-separated section paths from a nested TOML mapping.

        Parameters:
            data (dict[str, Any]): Parsed TOML data (mapping of keys to values or nested tables).
            prefix (str): Optional section path prefix used when descending into nested tables.

        Returns:
            list[str]: A list of section path strings (dot-separated) for each table and leaf key
                in `data`.
        """
        sections = []

        for key, value in data.items():
            if isinstance(value, dict):
                current_section = f"{prefix}.{key}" if prefix else key
                sections.append(current_section)
                sections.extend(self._extract_sections(value, current_section))
            else:
                current_section = f"{prefix}.{key}" if prefix else key
                sections.append(current_section)

        return sections
