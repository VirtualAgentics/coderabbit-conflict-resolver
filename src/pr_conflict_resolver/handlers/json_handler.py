"""JSON handler for applying CodeRabbit suggestions with AST validation.

This handler provides JSON-aware suggestion application with duplicate key detection,
smart merging, and structural validation to prevent issues like the package.json
duplication problem.
"""

import contextlib
import json
import logging
import os
import stat
import tempfile
from os import PathLike
from pathlib import Path
from typing import Any

from pr_conflict_resolver.core.models import Change, Conflict
from pr_conflict_resolver.handlers.base import BaseHandler
from pr_conflict_resolver.security.input_validator import InputValidator
from pr_conflict_resolver.utils.path_utils import resolve_file_path

type JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


class JsonHandler(BaseHandler):
    """Handler for JSON files with duplicate key detection and smart merging."""

    def __init__(self, workspace_root: str | PathLike[str] | None = None) -> None:
        """Initialize the JsonHandler instance and configure a module-level logger.

        Args:
            workspace_root: Root directory for validating absolute paths.
                If None, defaults to current working directory.
        """
        super().__init__(workspace_root)
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
        # Use workspace root for absolute path containment check
        if not InputValidator.validate_file_path(
            path, allow_absolute=True, base_dir=str(self.workspace_root)
        ):
            self.logger.error(f"Invalid file path rejected: {path}")
            return False

        # Resolve path relative to workspace_root with strict containment to workspace
        file_path = resolve_file_path(
            path,
            self.workspace_root,
            allow_absolute=True,
            validate_workspace=True,
            enforce_containment=True,
        )

        # Parse original file
        try:
            original_content = file_path.read_text(encoding="utf-8")
            original_data = self._parse_json_dict(original_content, f"JSON file {file_path}")
            if original_data is None:
                self.logger.error(f"Failed to parse JSON file {file_path}")
                return False
        except (OSError, UnicodeDecodeError) as e:
            self.logger.error(f"Error reading JSON file {file_path}: {type(e).__name__}: {e}")
            return False

        # Parse suggestion
        suggestion_data = self._parse_json_dict(content, "JSON suggestion")
        if suggestion_data is None:
            # Suggestion might be partial or has duplicate keys - try smart merge
            return self._apply_partial_suggestion(
                file_path, original_data, content, start_line, end_line
            )

        # Apply suggestion
        merged_data = self._smart_merge_json(original_data, suggestion_data, start_line, end_line)

        # Validate merged result
        if self._has_duplicate_keys(merged_data):
            self.logger.error("Merge would create duplicate keys")
            return False

        # Write with atomic operation
        original_mode = None
        temp_path: Path | None = None

        try:
            # Capture original file permissions if file exists
            if file_path.exists():
                original_mode = os.stat(file_path).st_mode

            # Create temp file in same directory
            temp_dir = file_path.parent
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=temp_dir,
                prefix=f".{file_path.name}.tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                # Write JSON content
                temp_file.write(json.dumps(merged_data, indent=2, ensure_ascii=False) + "\n")
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Ensure data written to disk

            # Apply original permissions if we have them
            if original_mode is not None:
                os.chmod(temp_path, stat.S_IMODE(original_mode))

            # Atomically replace the original file
            os.replace(temp_path, file_path)
            return True

        except OSError as e:
            temp_path_str = str(temp_path) if temp_path is not None else "N/A"
            self.logger.error(
                f"Error writing JSON file {path}: {e} (temp: {temp_path_str}, target: {file_path})"
            )
            return False

        finally:
            # Always clean up temp file if it exists
            if temp_path is not None and temp_path.exists():
                with contextlib.suppress(OSError):
                    temp_path.unlink()  # Ignore cleanup errors

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
        # Use workspace root for absolute path containment check
        if not InputValidator.validate_file_path(
            path, allow_absolute=True, base_dir=str(self.workspace_root)
        ):
            return False, "Invalid file path: path traversal detected"

        try:
            self._loads_strict(content)
            return True, "Valid JSON"
        except (json.JSONDecodeError, ValueError) as e:
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
                data = self._loads_strict(change.content)
                if isinstance(data, dict):
                    for key in data:
                        if key not in key_changes:
                            key_changes[key] = []
                        key_changes[key].append(change)
            except (json.JSONDecodeError, ValueError):
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

        # Line-sweep algorithm: convert each inclusive range to two events (start:+1, end+1:-1),
        # sort events, sweep while tracking active count; accumulate union when active>0 and
        # overlap when active>1. Using end+1 models inclusive ranges correctly.
        events: list[tuple[int, int]] = []
        for c in changes:
            start = min(c.start_line, c.end_line)
            end = max(c.start_line, c.end_line)
            events.append((start, +1))
            events.append((end + 1, -1))  # inclusive end
        events.sort()

        active = 0
        prev: int | None = None
        union_len = 0
        overlap_len = 0

        for pos, delta in events:
            if prev is not None:
                span = pos - prev
                if active > 0:
                    union_len += span
                if active > 1:
                    overlap_len += span
            active += delta
            prev = pos

        if union_len <= 0:
            return 0.0
        return (overlap_len / union_len) * 100.0

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

    def _parse_json_dict(self, content: str, context: str) -> dict[str, Any] | None:
        """Parse JSON content and validate it's a dictionary.

        Args:
            content: JSON string to parse.
            context: Context string for error messages.

        Returns:
            dict[str, Any] | None: Parsed dict on success; None if parsing fails or the
            content is not a JSON object. Parsing errors (including malformed JSON or
            duplicate keys) are caught and logged; they are not propagated.
        """
        try:
            result = self._loads_strict(content)
            if not isinstance(result, dict):
                self.logger.error(f"Expected JSON object in {context}, got {type(result).__name__}")
                return None
            return result
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Error parsing {context}: {type(e).__name__}: {e}")
            return None

    def _loads_strict(self, s: str) -> JsonValue:
        """Parse JSON and raise ValueError on duplicate keys.

        Args:
            s: JSON string to parse.

        Returns:
            Parsed JSON data (dict, list, or primitive).

        Raises:
            json.JSONDecodeError: If the JSON is malformed.
            ValueError: If duplicate keys are detected.
        """

        def _no_dupes_object_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            obj: dict[str, Any] = {}
            for k, v in pairs:
                if k in obj:
                    raise ValueError(f"Duplicate key detected: {k}")
                obj[k] = v
            return obj

        result: JsonValue = json.loads(s, object_pairs_hook=_no_dupes_object_pairs_hook)
        return result
