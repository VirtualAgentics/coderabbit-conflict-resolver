"""
TOML handler for applying CodeRabbit suggestions with AST validation.

This handler provides TOML-aware suggestion application with structure validation.
"""

from pathlib import Path
from typing import Any, List, Tuple

from .base import BaseHandler

try:
    import tomli
    import tomli_w
    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False


class TomlHandler(BaseHandler):
    """Handler for TOML files with structure validation."""
    
    def __init__(self):
        """Initialize the TOML handler."""
        if not TOML_AVAILABLE:
            print("Warning: tomli/tomli-w not available. Install with: pip install tomli tomli-w")
    
    def can_handle(self, file_path: str) -> bool:
        """Check if this handler can process TOML files."""
        return file_path.lower().endswith('.toml')
    
    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply suggestion to TOML file with validation."""
        if not TOML_AVAILABLE:
            print("ERROR: tomli/tomli-w not available. Install with: pip install tomli tomli-w")
            return False
        
        file_path = Path(path)
        
        # Parse original file
        try:
            original_content = file_path.read_text(encoding="utf-8")
            original_data = tomli.loads(original_content)
        except Exception as e:
            print(f"Error parsing original TOML: {e}")
            return False
        
        # Parse suggestion
        try:
            suggestion_data = tomli.loads(content)
        except Exception as e:
            print(f"Error parsing TOML suggestion: {e}")
            return False
        
        # Apply suggestion using smart merge
        merged_data = self._smart_merge_toml(original_data, suggestion_data, start_line, end_line)
        
        # Write with proper formatting
        try:
            with open(file_path, 'wb') as f:
                tomli_w.dump(merged_data, f)
            return True
        except Exception as e:
            print(f"Error writing TOML: {e}")
            return False
    
    def validate_change(self, path: str, content: str, start_line: int, end_line: int) -> Tuple[bool, str]:
        """Validate TOML suggestion without applying it."""
        if not TOML_AVAILABLE:
            return False, "tomli/tomli-w not available"
        
        try:
            tomli.loads(content)
            return True, "Valid TOML"
        except Exception as e:
            return False, f"Invalid TOML: {e}"
    
    def detect_conflicts(self, path: str, changes: List[dict]) -> List[dict]:
        """Detect conflicts between TOML changes."""
        conflicts = []
        
        # Group changes by section
        section_changes = {}
        for change in changes:
            try:
                data = tomli.loads(change.get("content", "{}"))
                sections = self._extract_sections(data)
                for section in sections:
                    if section not in section_changes:
                        section_changes[section] = []
                    section_changes[section].append(change)
            except Exception:
                continue
        
        # Find conflicts (multiple changes to same section)
        for section, section_change_list in section_changes.items():
            if len(section_change_list) > 1:
                conflicts.append({
                    "type": "section_conflict",
                    "section": section,
                    "changes": section_change_list,
                    "severity": "medium"
                })
        
        return conflicts
    
    def _smart_merge_toml(self, original: dict, suggestion: dict, start_line: int, end_line: int) -> dict:
        """Intelligently merge TOML based on structure."""
        # For TOML, we typically want to merge at the top level
        result = original.copy()
        for key, value in suggestion.items():
            result[key] = value
        return result
    
    def _extract_sections(self, data: dict, prefix: str = "") -> List[str]:
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
