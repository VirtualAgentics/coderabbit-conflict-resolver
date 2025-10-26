"""YAML handler for applying CodeRabbit suggestions with AST validation.

This handler provides YAML-aware suggestion application with structure validation
and comment preservation using ruamel.yaml.
"""

import logging
from pathlib import Path
from typing import Any

from ..core.models import Change, Conflict
from ..security.input_validator import InputValidator
from .base import BaseHandler

# Type alias for YAML values to avoid Any usage
YAMLValue = dict[str, Any] | list[Any] | str | int | float | bool | None

try:
    from ruamel.yaml import YAML

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class YamlHandler(BaseHandler):
    """Handler for YAML files with comment preservation and structure validation."""

    def __init__(self) -> None:
        """Initialize the YAML handler."""
        self.logger = logging.getLogger(__name__)
        if not YAML_AVAILABLE:
            self.logger.warning("ruamel.yaml not available. Install with: pip install ruamel.yaml")

    def can_handle(self, file_path: str) -> bool:
        """Determine whether this handler should process the given file path.

        Returns:
            `true` if the path ends with `.yaml` or `.yml` (case-insensitive), `false` otherwise.
        """
        return file_path.lower().endswith((".yaml", ".yml"))

    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply a suggested YAML fragment into a file by merging with current content.

        Parses the target file and the provided YAML suggestion, performs a high-level merge
        (preserving quotes and comments where possible) guided by the given start and end line
        positions, and writes the merged result back to the file. If parsing or writing fails, no
        changes are written.

        Parameters:
            path (str): Filesystem path to the YAML file to update.
            content (str): YAML text containing the suggestion to apply.
            start_line (int): Starting line number in the original file used to guide merging.
            end_line (int): Ending line number in the original file used to guide merging.

        Returns:
            bool: `True` if the merged YAML was written successfully, `False` otherwise.
        """
        # Validate file path to prevent path traversal attacks
        if not InputValidator.validate_file_path(path):
            self.logger.error(f"Invalid file path rejected: {path}")
            return False

        if not YAML_AVAILABLE:
            self.logger.error("ruamel.yaml not available. Install with: pip install ruamel.yaml")
            return False

        file_path = Path(path)

        # Parse original file
        try:
            yaml = YAML()
            yaml.preserve_quotes = True
            original_content = file_path.read_text(encoding="utf-8")
            original_data = yaml.load(original_content)
        except Exception as e:
            self.logger.error(f"Error parsing original YAML: {e}")
            return False

        # Parse suggestion
        try:
            yaml_suggestion = YAML()
            suggestion_data = yaml_suggestion.load(content)
        except Exception as e:
            self.logger.error(f"Error parsing YAML suggestion: {e}")
            return False

        # Apply suggestion using smart merge
        merged_data = self._smart_merge_yaml(original_data, suggestion_data, start_line, end_line)

        # Write with proper formatting and comment preservation
        try:
            yaml.dump(merged_data, file_path)
            return True
        except Exception as e:
            self.logger.error(f"Error writing YAML: {e}")
            return False

    def validate_change(
        self, path: str, content: str, start_line: int, end_line: int
    ) -> tuple[bool, str]:
        """Validate a YAML suggestion string and report whether it parses successfully.

        Parameters:
            path (str): File path associated with the suggestion (used for context only).
            content (str): YAML text to validate.
            start_line (int): Start line of the suggested change in the file (provided for
                context; not used to alter validation).
            end_line (int): End line of the suggested change in the file (provided for context;
                not used to alter validation).

        Returns:
            tuple[bool, str]: `True` and "Valid YAML" if `content` parses as YAML; `False` and an
                error message otherwise.
        """
        if not YAML_AVAILABLE:
            return False, "ruamel.yaml not available"

        # Normalize/sanitize the raw input first
        sanitized_content = self._sanitize_yaml_content(content)

        # Check for dangerous YAML tags that could lead to code execution
        # Defense-in-depth: keep substring check as first line of defense
        dangerous_tags = [
            "!!python/object",
            "!!python/name",
            "!!python/module",
            "!!python/function",
            "!!python/apply",
        ]

        content_lower = sanitized_content.lower()
        for tag in dangerous_tags:
            if tag.lower() in content_lower:
                return False, "YAML contains dangerous Python object tags"

        # Parse with safe loader and perform structural tag checks
        try:
            yaml = YAML(typ="safe")
            parsed_data = yaml.load(sanitized_content)

            # If parsing succeeded, check for dangerous tags in the parsed structure
            if self._contains_dangerous_tags(parsed_data):
                return False, "YAML contains dangerous Python object tags"

            return True, "Valid YAML"
        except Exception as e:
            return False, f"Invalid YAML: {e}"

    def detect_conflicts(self, path: str, changes: list[Change]) -> list[Conflict]:
        """Identify key-level conflicts among a set of YAML changes.

        Parses each change's YAML content to extract key paths, groups changes that target the
        same key path, and returns a Conflict for each key that is modified by more than one
        change.

        Parameters:
            path (str): File path the changes apply to; used as the Conflict.file_path.
            changes (list[Change]): List of Change objects whose `.content` contains YAML
                snippets and which provide `start_line`/`end_line` for conflict ranges.

        Returns:
            list[Conflict]: A list of Conflict objects describing keys modified by multiple
                changes. Each Conflict uses `conflict_type` "key_conflict", `severity` "medium",
                and `overlap_percentage` 100.0; `line_range` spans from the first change's
                start_line to the last change's end_line for that key.
        """
        conflicts: list[Conflict] = []

        # Group changes by key path
        key_changes: dict[str, list[Change]] = {}
        for change in changes:
            try:
                yaml = YAML()
                data = yaml.load(change.content)
                keys = self._extract_keys(data)
                for key in keys:
                    if key not in key_changes:
                        key_changes[key] = []
                    key_changes[key].append(change)
            except Exception as e:
                self.logger.warning(f"Failed to process change: {e}")
                continue

        # Find conflicts (multiple changes to same key)
        for _key, key_change_list in key_changes.items():
            if len(key_change_list) > 1:
                conflicts.append(
                    Conflict(
                        file_path=path,
                        line_range=(key_change_list[0].start_line, key_change_list[-1].end_line),
                        changes=key_change_list,
                        conflict_type="key_conflict",
                        severity="medium",
                        overlap_percentage=100.0,
                    )
                )

        return conflicts

    def _smart_merge_yaml(
        self, original: YAMLValue, suggestion: YAMLValue, start_line: int, end_line: int
    ) -> YAMLValue:
        """Merge two YAML structures, giving precedence to the suggestion.

        Parameters:
            original (Any): The existing YAML-parsed data.
            suggestion (Any): The YAML-parsed suggestion to apply.
            start_line (int): Start line number of the suggested change (used to indicate the
                targeted range).
            end_line (int): End line number of the suggested change (used to indicate the
                targeted range).

        Returns:
            Any: The merged YAML structure. If both inputs are dicts, returns a dict where
                suggestion keys override original keys; if both are lists, returns the suggestion
                list; if types differ, returns the suggestion.
        """
        if isinstance(original, dict) and isinstance(suggestion, dict):
            # Merge dictionaries
            result = original.copy()
            for key, value in suggestion.items():
                result[key] = value
            return result
        elif isinstance(original, list) and isinstance(suggestion, list):
            # For lists, we might want to append or replace based on context
            # For now, simple replacement
            return suggestion
        else:
            # Different types - use suggestion
            return suggestion

    def _extract_keys(self, data: YAMLValue, prefix: str = "") -> list[str]:
        """Recursively collect key paths from parsed YAML data.

        Produces dot-separated paths for mappings and bracketed indices for sequences. For
        example, a mapping {"a": {"b": 1}} yields "a" and "a.b"; a sequence [1, {"x": 2}] yields
        "[0]" and "[1].x".

        Parameters:
            data (Any): Parsed YAML structure (mappings as dict, sequences as list, scalars as
                leaf values).
            prefix (str): Optional starting path to prepend (no leading or trailing separators).

        Returns:
            list[str]: A list of key path strings found in `data`.
        """
        keys = []

        if isinstance(data, dict):
            for key, value in data.items():
                current_key = f"{prefix}.{key}" if prefix else key
                keys.append(current_key)
                keys.extend(self._extract_keys(value, current_key))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_key = f"{prefix}[{i}]" if prefix else f"[{i}]"
                keys.append(current_key)
                keys.extend(self._extract_keys(item, current_key))

        return keys

    def _sanitize_yaml_content(self, content: str) -> str:
        """Sanitize YAML content by removing dangerous characters.

        Parameters:
            content (str): Raw YAML content to sanitize.

        Returns:
            str: Sanitized YAML content with null bytes and control characters removed.
        """
        # Remove null bytes and other dangerous control characters
        # Keep only printable characters, whitespace, and common YAML characters
        sanitized = ""
        for char in content:
            # Allow printable characters, whitespace, and common YAML characters
            if char.isprintable() or char in "\n\r\t ":
                sanitized += char
            # Replace null bytes and other control characters with spaces
            elif ord(char) < 32:
                sanitized += " "

        return sanitized.strip()

    def _contains_dangerous_tags(self, data: YAMLValue) -> bool:
        """Check if parsed YAML data contains dangerous Python-specific tags.

        Parameters:
            data (YAMLValue): Parsed YAML data structure.

        Returns:
            bool: True if dangerous tags are found, False otherwise.
        """
        if data is None:
            return False

        # Check if this is a tagged value (ruamel.yaml preserves tag information)
        if hasattr(data, "tag") and data.tag:
            tag_str = str(data.tag)
            if tag_str.startswith("!!python"):
                return True

        # Recursively check nested structures
        if isinstance(data, dict):
            for value in data.values():
                if self._contains_dangerous_tags(value):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._contains_dangerous_tags(item):
                    return True

        return False
