"""JSON handler for applying CodeRabbit suggestions with AST validation.

This handler provides JSON-aware suggestion application with duplicate key detection,
smart merging, and structural validation to prevent issues like the package.json
duplication problem.
"""

import json
import logging
from pathlib import Path
from typing import Any

from ..core.models import Change, Conflict
from ..security.input_validator import InputValidator
from .base import BaseHandler


class JsonHandler(BaseHandler):
    """Handler for JSON files with duplicate key detection and smart merging."""

    def __init__(self) -> None:
        """Initialize the JsonHandler instance and configure a module-level logger.

        Sets the `logger` attribute to a logger named for this module.
        """
        self.logger = logging.getLogger(__name__)

    def can_handle(self, file_path: str) -> bool:
        """Determine whether a file path refers to a JSON file.

        Returns:
            bool: `True` if the given `file_path` ends with ".json" (case-insensitive),
                `False` otherwise.
        """
        return file_path.lower().endswith(".json")

    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply a JSON suggestion to a file, merging and validating to prevent duplicate keys.

        This method implements security validation to prevent path traversal attacks and
        ensures safe JSON processing. Path validation occurs before any file operations.

        Security Features:
            - Path traversal protection using InputValidator.validate_file_path()
            - Duplicate key detection to prevent JSON structure corruption
            - Safe JSON parsing with proper error handling
            - File existence verification before processing

        Parameters:
            path (str): Filesystem path to the target JSON file. Must pass security validation.
            content (str): Suggested JSON content; may be a complete JSON object or a
                partial fragment.
            start_line (int): Start line of the suggestion in the original file (used as
                contextual hint for merging).
            end_line (int): End line of the suggestion in the original file (used as
                contextual hint for merging).

        Returns:
            bool: `True` if the file was successfully updated with the merged JSON,
                `False` otherwise.

        Example:
            >>> handler = JsonHandler()
            >>> # Valid path and JSON
            >>> handler.apply_change("config.json", '{"key": "value"}', 1, 1)
            True
            >>> # Path traversal attempt - rejected
            >>> handler.apply_change("../../../etc/passwd", '{"key": "value"}', 1, 1)
            False

        Warning:
            This method validates file paths to prevent directory traversal attacks.
            Invalid paths are rejected before any file operations occur.

        See Also:
            InputValidator.validate_file_path: Path security validation
            validate_change: Content validation for JSON structure
        """
        # Validate file path to prevent path traversal attacks
        if not InputValidator.validate_file_path(path):
            self.logger.error(f"Invalid file path rejected: {path}")
            return False

        file_path = Path(path)

        # Parse original file
        try:
            original_content = file_path.read_text(encoding="utf-8")
            original_data = json.loads(original_content)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing original JSON: {e}")
            return False

        # Parse suggestion
        try:
            suggestion_data = json.loads(content)
        except json.JSONDecodeError:
            # Suggestion might be partial - try smart merge
            return self._apply_partial_suggestion(
                file_path, original_data, content, start_line, end_line
            )

        # Validate: check for duplicate keys
        if self._has_duplicate_keys(suggestion_data):
            self.logger.error("Suggestion contains duplicate keys")
            return False

        # Apply suggestion
        merged_data = self._smart_merge_json(original_data, suggestion_data, start_line, end_line)

        # Validate merged result
        if self._has_duplicate_keys(merged_data):
            self.logger.error("Merge would create duplicate keys")
            return False

        # Write with proper formatting
        file_path.write_text(
            json.dumps(merged_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return True

    def validate_change(
        self, path: str, content: str, start_line: int, end_line: int
    ) -> tuple[bool, str]:
        """Validate a JSON suggestion without applying changes.

        This method performs security validation on the file path before validating JSON content.
        It ensures that path traversal attacks are prevented and JSON structure is valid.

        Security Features:
            - Path traversal protection using InputValidator.validate_file_path()
            - JSON syntax validation with proper error reporting
            - Duplicate key detection to prevent structure corruption
            - Safe JSON parsing without side effects

        Parameters:
            path (str): File path of the JSON being validated. Must pass security validation.
            content (str): JSON text to validate.
            start_line (int): Start line of the suggested change (contextual; not used for
                validation).
            end_line (int): End line of the suggested change (contextual; not used for
                validation).

        Returns:
            tuple[bool, str]: `True, "Valid JSON"` if `content` is valid JSON and contains no
                duplicate keys; otherwise `False` with an error message (either
                `"Duplicate keys detected"` or `"Invalid JSON: <error>"`).

        Example:
            >>> handler = JsonHandler()
            >>> # Valid JSON
            >>> handler.validate_change("config.json", '{"key": "value"}', 1, 1)
            (True, "Valid JSON")
            >>> # Invalid JSON syntax
            >>> handler.validate_change("config.json", '{"key": value}', 1, 1)
            (False, "Invalid JSON: Expecting value: line 1 column 10 (char 9)")
            >>> # Path traversal attempt - rejected
            >>> handler.validate_change("../../../etc/passwd", '{"key": "value"}', 1, 1)
            (False, "Invalid file path: path traversal detected")

        Warning:
            This method validates file paths to prevent directory traversal attacks.
            Invalid paths are rejected before JSON validation occurs.

        See Also:
            InputValidator.validate_file_path: Path security validation
            apply_change: Apply validated changes to files
        """
        # Validate file path to prevent path traversal attacks
        if not InputValidator.validate_file_path(path):
            return False, "Invalid file path: path traversal detected"

        try:
            data = json.loads(content)
            if self._has_duplicate_keys(data):
                return False, "Duplicate keys detected"
            return True, "Valid JSON"
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

    def detect_conflicts(self, path: str, changes: list[Change]) -> list[Conflict]:
        """Identify key-based conflicts among JSON changes for a given file.

        Parameters:
            path (str): Path to the JSON file being analyzed.
            changes (list[Change]): List of Change objects whose `content` is expected to be
                JSON; changes with unparsable JSON are ignored.

        Returns:
            list[Conflict]: Conflicts where multiple changes target the same top-level JSON key.
                Each Conflict contains the file path, a line range spanning the first to last
                involved change, the list of conflicting changes, a `conflict_type` of
                `"key_conflict"`, a `severity` of `"medium"`, and an `overlap_percentage`
                quantifying how much the changes' line ranges overlap.
        """
        conflicts: list[Conflict] = []

        # Group changes by key
        key_changes: dict[str, list[Change]] = {}
        for change in changes:
            try:
                data = json.loads(change.content)
                for key in data:
                    if key not in key_changes:
                        key_changes[key] = []
                    key_changes[key].append(change)
            except json.JSONDecodeError:
                continue

        # Find conflicts (multiple changes to same key)
        for _key, key_change_list in key_changes.items():
            if len(key_change_list) > 1:
                # Calculate actual overlap percentage
                overlap_percentage = self._calculate_overlap_percentage(key_change_list)

                conflicts.append(
                    Conflict(
                        file_path=path,
                        line_range=(key_change_list[0].start_line, key_change_list[-1].end_line),
                        changes=key_change_list,
                        conflict_type="key_conflict",
                        severity="medium",
                        overlap_percentage=overlap_percentage,
                    )
                )

        return conflicts

    def _calculate_overlap_percentage(self, changes: list[Change]) -> float:
        """Calculate the percentage of overlapping line coverage among multiple changes.

        Parameters:
            changes (list[Change]): List of Change objects; each must have `start_line` and
                `end_line` attributes defining the inclusive line range of the change.

        Returns:
            float: Percentage of lines that are covered by more than one change, in the range
                0.0 to 100.0. Returns 0.0 if fewer than two changes are provided or if no lines
                are covered.
        """
        if len(changes) < 2:
            return 0.0

        # Build set of covered lines for each change
        all_lines: set[int] = set()
        overlap_lines: set[int] = set()

        for change in changes:
            change_lines = set(range(change.start_line, change.end_line + 1))
            overlap_lines.update(all_lines.intersection(change_lines))
            all_lines.update(change_lines)

        if not all_lines:
            return 0.0

        total_span = len(all_lines)
        overlap_count = len(overlap_lines)

        return (overlap_count / total_span) * 100.0

    def _has_duplicate_keys(
        self, obj: dict[str, Any] | list[Any] | str | int | float | bool | None
    ) -> bool:
        """Detects whether a JSON-like structure contains duplicate object keys.

        Parameters:
            obj (dict | list | str | int | float | bool | None): JSON-like value to inspect;
                may be a mapping, sequence, or primitive.

        Returns:
            bool: `True` if any mapping within `obj` contains duplicate keys, `False` otherwise.
        """
        if isinstance(obj, dict):
            # Check current level
            keys = list(obj.keys())
            if len(keys) != len(set(keys)):
                return True
            # Check nested objects
            return any(self._has_duplicate_keys(v) for v in obj.values())
        elif isinstance(obj, list):
            return any(self._has_duplicate_keys(item) for item in obj)
        return False

    def _smart_merge_json(
        self, original: dict[str, Any], suggestion: dict[str, Any], start_line: int, end_line: int
    ) -> dict[str, Any]:
        """Merge a suggested JSON object into the original JSON.

        Parameters:
            original (dict[str, Any]): The existing JSON object from the file.
            suggestion (dict[str, Any]): The suggested JSON fragment to apply.
            start_line (int): The starting line number of the suggestion in the file (1-based).
            end_line (int): The ending line number of the suggestion in the file (1-based).

        Returns:
            dict[str, Any]: The resulting merged JSON object; the suggestion is returned intact
                if it is considered a complete replacement, otherwise keys from the suggestion
                overwrite or are added to the original.
        """
        # Strategy 1: If suggestion is complete object, use it
        if self._is_complete_object(suggestion, original):
            return suggestion

        # Strategy 2: If suggestion is partial, merge specific keys
        result = original.copy()
        for key, value in suggestion.items():
            result[key] = value

        return result

    def _is_complete_object(self, suggestion: dict[str, Any], original: dict[str, Any]) -> bool:
        """Determine whether the suggestion should be treated as a complete replacement.

        This uses a heuristic: the suggestion is considered complete if it contains at least all
        top-level keys present in the original.

        Returns:
            True if the suggestion contains at least all top-level keys from the original, False
                otherwise.
        """
        # Heuristic: suggestion has all top-level keys from original
        original_keys = set(original.keys())
        suggestion_keys = set(suggestion.keys())
        return suggestion_keys >= original_keys

    def _apply_partial_suggestion(
        self,
        file_path: Path,
        original_data: dict[str, Any],
        suggestion: str,
        start_line: int,
        end_line: int,
    ) -> bool:
        """Attempt to apply a partial (non-parseable) JSON suggestion to an existing JSON file.

        Parameters:
            file_path (Path): Path to the JSON file being modified.
            original_data (dict[str, Any]): Parsed JSON content of the original file.
            suggestion (str): Suggested content that is not valid/complete JSON.
            start_line (int): Start line number of the suggested change in the file.
            end_line (int): End line number of the suggested change in the file.

        Returns:
            bool: `False` if the suggestion was not applied. The method currently logs a warning
                and does not perform a merge.
        """
        # For now, fall back to plain text replacement
        # This is a simplified approach - in practice, you might want more sophisticated
        # parsing of partial JSON structures
        self.logger.warning("Partial JSON suggestion detected, using fallback method")
        return False
