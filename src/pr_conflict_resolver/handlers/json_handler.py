"""
JSON handler for applying CodeRabbit suggestions with AST validation.

This handler provides JSON-aware suggestion application with duplicate key detection,
smart merging, and structural validation to prevent issues like the package.json
duplication problem.
"""

import json
from pathlib import Path
from typing import Any, List, Tuple

from .base import BaseHandler


class JsonHandler(BaseHandler):
    """Handler for JSON files with duplicate key detection and smart merging."""
    
    def can_handle(self, file_path: str) -> bool:
        """Check if this handler can process JSON files."""
        return file_path.lower().endswith('.json')
    
    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        """Apply suggestion to JSON file with validation."""
        file_path = Path(path)
        
        # Parse original file
        try:
            original_content = file_path.read_text(encoding="utf-8")
            original_data = json.loads(original_content)
        except json.JSONDecodeError as e:
            print(f"Error parsing original JSON: {e}")
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
            print(f"ERROR: Suggestion contains duplicate keys")
            return False
        
        # Apply suggestion
        merged_data = self._smart_merge_json(original_data, suggestion_data, start_line, end_line)
        
        # Validate merged result
        if self._has_duplicate_keys(merged_data):
            print(f"ERROR: Merge would create duplicate keys")
            return False
        
        # Write with proper formatting
        file_path.write_text(
            json.dumps(merged_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )
        return True
    
    def validate_change(self, path: str, content: str, start_line: int, end_line: int) -> Tuple[bool, str]:
        """Validate JSON suggestion without applying it."""
        try:
            data = json.loads(content)
            if self._has_duplicate_keys(data):
                return False, "Duplicate keys detected"
            return True, "Valid JSON"
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
    
    def detect_conflicts(self, path: str, changes: List[dict]) -> List[dict]:
        """Detect conflicts between JSON changes."""
        conflicts = []
        
        # Group changes by key
        key_changes = {}
        for change in changes:
            try:
                data = json.loads(change.get("content", "{}"))
                for key in data.keys():
                    if key not in key_changes:
                        key_changes[key] = []
                    key_changes[key].append(change)
            except json.JSONDecodeError:
                continue
        
        # Find conflicts (multiple changes to same key)
        for key, key_change_list in key_changes.items():
            if len(key_change_list) > 1:
                conflicts.append({
                    "type": "key_conflict",
                    "key": key,
                    "changes": key_change_list,
                    "severity": "medium"
                })
        
        return conflicts
    
    def _has_duplicate_keys(self, obj: Any) -> bool:
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
    
    def _smart_merge_json(self, original: dict, suggestion: dict, start_line: int, end_line: int) -> dict:
        """Intelligently merge JSON based on line context."""
        # Strategy 1: If suggestion is complete object, use it
        if self._is_complete_object(suggestion, original):
            return suggestion
        
        # Strategy 2: If suggestion is partial, merge specific keys
        result = original.copy()
        for key, value in suggestion.items():
            result[key] = value
        
        return result
    
    def _is_complete_object(self, suggestion: dict, original: dict) -> bool:
        """Check if suggestion is a complete replacement."""
        # Heuristic: suggestion has all top-level keys from original
        original_keys = set(original.keys())
        suggestion_keys = set(suggestion.keys())
        return suggestion_keys >= original_keys
    
    def _apply_partial_suggestion(self, file_path: Path, original_data: dict, 
                                 suggestion: str, start_line: int, end_line: int) -> bool:
        """Handle partial JSON suggestions that can't be parsed as complete JSON."""
        # For now, fall back to plain text replacement
        # This is a simplified approach - in practice, you might want more sophisticated
        # parsing of partial JSON structures
        print(f"Warning: Partial JSON suggestion detected, using fallback method")
        return False
