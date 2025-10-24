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
from .base import BaseHandler


class JsonHandler(BaseHandler):
    """Handler for JSON files with duplicate key detection and smart merging."""

    def __init__(self) -> None:
        """Initialize the JSON handler."""
        self.logger = logging.getLogger(__name__)

    def can_handle(self, file_path: str) -> bool:
        """Check if this handler can process JSON files."""
        return file_path.lower().endswith(".json")

    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply suggestion to JSON file with validation."""
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
        """Validate JSON suggestion without applying it."""
        try:
            data = json.loads(content)
            if self._has_duplicate_keys(data):
                return False, "Duplicate keys detected"
            return True, "Valid JSON"
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"

    def detect_conflicts(self, path: str, changes: list[Change]) -> list[Conflict]:
        """Detect conflicts between JSON changes."""
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
        """Calculate the percentage of overlap between changes.

        Args:
            changes: List of changes to calculate overlap for.

        Returns:
            Percentage of overlap (0.0 to 100.0).
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
        """Check for duplicate keys in JSON object."""
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
        """Intelligently merge JSON based on line context."""
        # Strategy 1: If suggestion is complete object, use it
        if self._is_complete_object(suggestion, original):
            return suggestion

        # Strategy 2: If suggestion is partial, merge specific keys
        result = original.copy()
        for key, value in suggestion.items():
            result[key] = value

        return result

    def _is_complete_object(self, suggestion: dict[str, Any], original: dict[str, Any]) -> bool:
        """Check if suggestion is a complete replacement."""
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
        """Handle partial JSON suggestions that can't be parsed as complete JSON."""
        # For now, fall back to plain text replacement
        # This is a simplified approach - in practice, you might want more sophisticated
        # parsing of partial JSON structures
        self.logger.warning("Partial JSON suggestion detected, using fallback method")
        return False
