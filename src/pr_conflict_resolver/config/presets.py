"""Configuration presets for different use cases."""

from typing import Dict, Any


class PresetConfig:
    """Predefined configuration presets."""
    
    CONSERVATIVE: Dict[str, Any] = {
        "mode": "conservative",
        "skip_all_conflicts": True,
        "manual_review_required": True,
        "semantic_merging": False,
        "priority_system": False
    }
    
    BALANCED: Dict[str, Any] = {
        "mode": "balanced",
        "skip_all_conflicts": False,
        "manual_review_required": False,
        "semantic_merging": True,
        "priority_system": True,
        "priority_rules": {
            "user_selections": 100,
            "security_fixes": 90,
            "syntax_errors": 80,
            "regular_suggestions": 50,
            "formatting": 10
        }
    }
    
    AGGRESSIVE: Dict[str, Any] = {
        "mode": "aggressive",
        "skip_all_conflicts": False,
        "manual_review_required": False,
        "semantic_merging": True,
        "priority_system": True,
        "max_automation": True,
        "user_selections_always_win": True
    }
    
    SEMANTIC: Dict[str, Any] = {
        "mode": "semantic",
        "skip_all_conflicts": False,
        "manual_review_required": False,
        "semantic_merging": True,
        "priority_system": False,
        "focus_on_structured_files": True,
        "structure_aware_merging": True
    }
