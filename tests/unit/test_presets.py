"""Unit tests for configuration presets in review_bot_automator.config.presets."""

from review_bot_automator import PresetConfig


def test_conservative_preset_keys() -> None:
    cfg = PresetConfig.CONSERVATIVE
    assert cfg["mode"] == "conservative"
    assert cfg["skip_all_conflicts"] is True
    assert cfg["manual_review_required"] is True
    assert cfg["semantic_merging"] is False
    assert cfg["priority_system"] is False


def test_balanced_preset_priority_rules_present() -> None:
    cfg = PresetConfig.BALANCED
    assert cfg["mode"] == "balanced"
    rules = cfg["priority_rules"]
    expected = {
        "user_selections",
        "security_fixes",
        "syntax_errors",
        "regular_suggestions",
        "formatting",
    }
    assert expected <= set(rules.keys())
    # Ensure ordering intent (relative magnitudes)
    assert (
        rules["user_selections"]
        > rules["security_fixes"]
        > rules["syntax_errors"]
        > rules["regular_suggestions"]
        > rules["formatting"]
    )


def test_aggressive_preset_flags() -> None:
    cfg = PresetConfig.AGGRESSIVE
    assert cfg["mode"] == "aggressive"
    assert cfg["semantic_merging"] is True
    assert cfg["priority_system"] is True
    assert cfg.get("max_automation") is True
    assert cfg.get("user_selections_always_win") is True


def test_semantic_preset_flags() -> None:
    cfg = PresetConfig.SEMANTIC
    assert cfg["mode"] == "semantic"
    assert cfg["semantic_merging"] is True
    assert cfg["priority_system"] is False
    assert cfg.get("focus_on_structured_files") is True
    assert cfg.get("structure_aware_merging") is True
