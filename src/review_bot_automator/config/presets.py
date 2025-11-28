# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Configuration presets for different use cases."""

from typing import Any, ClassVar


class PresetConfig:
    """Predefined configuration presets."""

    CONSERVATIVE: ClassVar[dict[str, Any]] = {
        "mode": "conservative",
        "skip_all_conflicts": True,
        "manual_review_required": True,
        "semantic_merging": False,
        "priority_system": False,
    }

    BALANCED: ClassVar[dict[str, Any]] = {
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
            "formatting": 10,
        },
    }

    AGGRESSIVE: ClassVar[dict[str, Any]] = {
        "mode": "aggressive",
        "skip_all_conflicts": False,
        "manual_review_required": False,
        "semantic_merging": True,
        "priority_system": True,
        "max_automation": True,
        "user_selections_always_win": True,
    }

    SEMANTIC: ClassVar[dict[str, Any]] = {
        "mode": "semantic",
        "skip_all_conflicts": False,
        "manual_review_required": False,
        "semantic_merging": True,
        "priority_system": False,
        "focus_on_structured_files": True,
        "structure_aware_merging": True,
    }

    LLM_ENABLED: ClassVar[dict[str, Any]] = {
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
            "formatting": 10,
        },
        "llm_enabled": True,
        "llm_provider": "claude-cli",
        "llm_model": "claude-sonnet-4-5",
        "llm_fallback_to_regex": True,
        "llm_cache_enabled": True,
        "llm_max_tokens": 2000,
    }
