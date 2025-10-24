"""TOML handler for applying CodeRabbit suggestions with AST validation.

This handler provides TOML-aware suggestion application with structure validation.
"""

import logging
from pathlib import Path
from typing import Any

from ..core.models import Change, Conflict
from .base import BaseHandler

try:
    import tomli
    import tomli_w

    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False


class TomlHandler(BaseHandler):
    """Handler for TOML files with structure validation."""

    def __init__(self) -> None:
        """Initialize the TOML handler."""
        self.logger = logging.getLogger(__name__)
        if not TOML_AVAILABLE:
            self.logger.warning(
                "tomli/tomli-w not available. Install with: pip install tomli tomli-w"
            )

    def can_handle(self, file_path: str) -> bool:
        """Check if this handler can process TOML files."""
        return file_path.lower().endswith(".toml")

    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply suggestion to TOML file with validation."""
        if not TOML_AVAILABLE:
            self.logger.error(
                "tomli/tomli-w not available. Install with: pip install tomli tomli-w"
            )
            return False

        file_path = Path(path)

        # Parse original file
        try:
            original_content = file_path.read_text(encoding="utf-8")
            original_data = tomli.loads(original_content)
        except Exception as e:
            self.logger.error(f"Error parsing original TOML: {e}")
            return False

        # Parse suggestion
        try:
            suggestion_data = tomli.loads(content)
        except Exception as e:
            self.logger.error(f"Error parsing TOML suggestion: {e}")
            return False

        # Apply suggestion using smart merge
        merged_data = self._smart_merge_toml(original_data, suggestion_data, start_line, end_line)

        # Write with proper formatting
        try:
            with open(file_path, "wb") as f:
                tomli_w.dump(merged_data, f)
            return True
        except Exception as e:
            self.logger.error(f"Error writing TOML: {e}")
            return False

    def validate_change(
        self, path: str, content: str, start_line: int, end_line: int
    ) -> tuple[bool, str]:
        """Validate TOML suggestion without applying it."""
        if not TOML_AVAILABLE:
            return False, "tomli/tomli-w not available"

        try:
            tomli.loads(content)
            return True, "Valid TOML"
        except Exception as e:
            return False, f"Invalid TOML: {e}"

    def detect_conflicts(self, path: str, changes: list[Change]) -> list[Conflict]:
        """Detect conflicts between TOML changes."""
        conflicts: list[Conflict] = []

        # Group changes by section
        section_changes: dict[str, list[Change]] = {}
        for change in changes:
            try:
                data = tomli.loads(change.content)
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
        """Calculate the percentage of overlap between changes.

        Args:
            changes: List of changes to calculate overlap for.

        Returns:
            Percentage of overlap (0.0 to 100.0).
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
        """Intelligently merge TOML based on structure."""
        # For TOML, we typically want to merge at the top level
        result = original.copy()
        for key, value in suggestion.items():
            result[key] = value
        return result

    def _extract_sections(self, data: dict[str, Any], prefix: str = "") -> list[str]:
        """Extract all section paths from TOML data."""
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
