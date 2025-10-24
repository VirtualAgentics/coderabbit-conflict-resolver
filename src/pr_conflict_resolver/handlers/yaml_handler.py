"""YAML handler for applying CodeRabbit suggestions with AST validation.

This handler provides YAML-aware suggestion application with structure validation
and comment preservation using ruamel.yaml.
"""

import logging
from pathlib import Path
from typing import Any

from ..core.models import Change, Conflict
from .base import BaseHandler

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
        """Check if this handler can process YAML files."""
        return file_path.lower().endswith((".yaml", ".yml"))

    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply suggestion to YAML file with validation."""
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
        """Validate YAML suggestion without applying it."""
        if not YAML_AVAILABLE:
            return False, "ruamel.yaml not available"

        try:
            yaml = YAML()
            yaml.load(content)
            return True, "Valid YAML"
        except Exception as e:
            return False, f"Invalid YAML: {e}"

    def detect_conflicts(self, path: str, changes: list[Change]) -> list[Conflict]:
        """Detect conflicts between YAML changes."""
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
        self, original: Any, suggestion: Any, start_line: int, end_line: int
    ) -> Any:
        """Intelligently merge YAML based on structure."""
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

    def _extract_keys(self, data: Any, prefix: str = "") -> list[str]:
        """Extract all key paths from YAML data."""
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
