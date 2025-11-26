"""Tests for LLM configuration presets.

This module tests the preset system for zero-config LLM setup, ensuring that
all presets are correctly configured and can be loaded without errors.
"""

import pytest

from review_bot_automator.llm.config import LLMConfig
from review_bot_automator.llm.presets import LLMPreset, LLMPresetConfig


class TestLLMPreset:
    """Tests for LLMPreset dataclass."""

    def test_preset_creation(self) -> None:
        """Test creating an LLMPreset."""
        config = LLMConfig(
            enabled=True,
            provider="codex-cli",
            model="codex",
        )
        preset = LLMPreset(
            name="test-preset",
            description="Test preset",
            config=config,
        )

        assert preset.name == "test-preset"
        assert preset.description == "Test preset"
        assert preset.config == config
        assert preset.config.provider == "codex-cli"
        assert preset.config.model == "codex"

    def test_preset_immutability(self) -> None:
        """Test that LLMPreset is immutable."""
        preset = LLMPreset(
            name="test",
            description="Test",
            config=LLMConfig(),
        )

        with pytest.raises((AttributeError, TypeError)):
            preset.name = "modified"  # type: ignore[misc]


class TestLLMPresetConfig:
    """Tests for LLMPresetConfig preset management."""

    def test_list_presets(self) -> None:
        """Test listing all available presets."""
        presets = LLMPresetConfig.list_presets()

        # Should have exactly 5 presets
        assert len(presets) == 5

        # Should contain all expected presets
        expected = [
            "anthropic-api-balanced",
            "claude-cli-sonnet",
            "codex-cli-free",
            "ollama-local",
            "openai-api-mini",
        ]
        assert presets == expected

    def test_get_preset_valid(self) -> None:
        """Test getting a valid preset."""
        preset = LLMPresetConfig.get_preset("codex-cli-free")

        assert isinstance(preset, LLMPreset)
        assert preset.name == "codex-cli-free"
        assert "Codex" in preset.description
        assert preset.config.provider == "codex-cli"
        assert preset.config.model == "codex"
        assert preset.config.enabled is True

    def test_get_preset_invalid(self) -> None:
        """Test getting an invalid preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset 'invalid-preset'"):
            LLMPresetConfig.get_preset("invalid-preset")

    def test_load_preset_without_api_key(self) -> None:
        """Test loading a preset without API key override."""
        config = LLMPresetConfig.load_preset("codex-cli-free")

        assert isinstance(config, LLMConfig)
        assert config.enabled is True
        assert config.provider == "codex-cli"
        assert config.model == "codex"
        assert config.api_key is None

    def test_load_preset_with_api_key_override(self) -> None:
        """Test loading a preset with API key override."""
        config = LLMPresetConfig.load_preset("openai-api-mini", api_key="sk-test123")

        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.api_key == "sk-test123"

    def test_describe_preset(self) -> None:
        """Test describing a preset."""
        description = LLMPresetConfig.describe_preset("codex-cli-free")

        assert "codex-cli-free" in description
        assert "codex-cli" in description
        assert "codex" in description
        assert "Requires API key: No" in description

    def test_describe_all_presets(self) -> None:
        """Test describing all presets."""
        description = LLMPresetConfig.describe_all_presets()

        assert "Available LLM Presets:" in description
        assert "codex-cli-free" in description
        assert "ollama-local" in description
        assert "claude-cli-sonnet" in description
        assert "openai-api-mini" in description
        assert "anthropic-api-balanced" in description


class TestPresetConfigurations:
    """Tests for individual preset configurations."""

    def test_codex_cli_free_preset(self) -> None:
        """Test Codex CLI Free preset configuration."""
        config = LLMPresetConfig.load_preset("codex-cli-free")

        assert config.enabled is True
        assert config.provider == "codex-cli"
        assert config.model == "codex"
        assert config.api_key is None
        assert config.fallback_to_regex is True
        assert config.cache_enabled is True
        assert config.max_tokens == 2000
        assert config.cost_budget is None

    def test_ollama_local_preset(self) -> None:
        """Test Ollama Local preset configuration."""
        config = LLMPresetConfig.load_preset("ollama-local")

        assert config.enabled is True
        assert config.provider == "ollama"
        assert config.model == "qwen2.5-coder:7b"
        assert config.api_key is None
        assert config.fallback_to_regex is True
        assert config.cache_enabled is True
        assert config.max_tokens == 2000
        assert config.cost_budget is None

    def test_claude_cli_sonnet_preset(self) -> None:
        """Test Claude CLI Sonnet preset configuration."""
        config = LLMPresetConfig.load_preset("claude-cli-sonnet")

        assert config.enabled is True
        assert config.provider == "claude-cli"
        assert config.model == "claude-sonnet-4-5"
        assert config.api_key is None
        assert config.fallback_to_regex is True
        assert config.cache_enabled is True
        assert config.max_tokens == 2000
        assert config.cost_budget is None

    def test_openai_api_mini_preset(self) -> None:
        """Test OpenAI API Mini preset configuration."""
        config = LLMPresetConfig.load_preset("openai-api-mini")

        assert config.enabled is False  # Disabled until API key provided
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.api_key is None  # Must be provided separately
        assert config.fallback_to_regex is True
        assert config.cache_enabled is True
        assert config.max_tokens == 2000
        assert config.cost_budget == 5.0

    def test_anthropic_api_balanced_preset(self) -> None:
        """Test Anthropic API Balanced preset configuration."""
        config = LLMPresetConfig.load_preset("anthropic-api-balanced")

        assert config.enabled is False  # Disabled until API key provided
        assert config.provider == "anthropic"
        assert config.model == "claude-haiku-4"
        assert config.api_key is None  # Must be provided separately
        assert config.fallback_to_regex is True
        assert config.cache_enabled is True
        assert config.max_tokens == 2000
        assert config.cost_budget == 5.0


class TestPresetValidation:
    """Tests for preset validation and error handling."""

    def test_api_preset_without_api_key_is_disabled(self) -> None:
        """Test that API-based presets are disabled without API key."""
        # Load preset without API key - should be disabled
        config = LLMPresetConfig.load_preset("openai-api-mini")

        # Preset should be disabled without API key
        assert config.enabled is False
        assert config.provider == "openai"
        assert config.api_key is None

    def test_api_preset_with_api_key_enabled_and_validates(self) -> None:
        """Test that API-based presets are enabled and validate with API key."""
        config = LLMPresetConfig.load_preset("openai-api-mini", api_key="sk-test123")

        # Should not raise - validation passes with API key
        assert config.enabled is True  # Automatically enabled with API key
        assert config.provider == "openai"
        assert config.api_key == "sk-test123"

    def test_cli_preset_without_api_key_succeeds(self) -> None:
        """Test that CLI-based presets work without API key."""
        config = LLMPresetConfig.load_preset("codex-cli-free")

        # Should not raise - CLI providers don't require API keys
        assert config.enabled is True
        assert config.provider == "codex-cli"
        assert config.api_key is None


class TestPresetRegistry:
    """Tests for preset registry consistency."""

    def test_all_presets_registered(self) -> None:
        """Test that all preset constants are registered."""
        # All class attributes should be in registry
        expected_presets = {
            LLMPresetConfig.CODEX_CLI_FREE.name,
            LLMPresetConfig.OLLAMA_LOCAL.name,
            LLMPresetConfig.CLAUDE_CLI_SONNET.name,
            LLMPresetConfig.OPENAI_API_MINI.name,
            LLMPresetConfig.ANTHROPIC_API_BALANCED.name,
        }

        registered_presets = set(LLMPresetConfig.list_presets())

        assert registered_presets == expected_presets

    def test_preset_names_lowercase_with_hyphens(self) -> None:
        """Test that all preset names follow naming convention."""
        presets = LLMPresetConfig.list_presets()

        for name in presets:
            # Should be lowercase with hyphens only
            assert name == name.lower()
            assert " " not in name
            assert "_" not in name

    def test_all_presets_have_unique_names(self) -> None:
        """Test that all presets have unique names."""
        presets = LLMPresetConfig.list_presets()
        assert len(presets) == len(set(presets))

    def test_cli_presets_enabled_api_presets_disabled_by_default(self) -> None:
        """Test that CLI presets are enabled, API presets disabled by default."""
        cli_presets = {"codex-cli-free", "ollama-local", "claude-cli-sonnet"}
        api_presets = {"openai-api-mini", "anthropic-api-balanced"}

        for preset_name in LLMPresetConfig.list_presets():
            config = LLMPresetConfig.load_preset(preset_name)
            if preset_name in cli_presets:
                assert config.enabled is True, f"CLI preset '{preset_name}' should be enabled"
            elif preset_name in api_presets:
                assert (
                    config.enabled is False
                ), f"API preset '{preset_name}' should be disabled without API key"

    def test_all_presets_have_fallback_enabled(self) -> None:
        """Test that all presets have fallback_to_regex=True."""
        for preset_name in LLMPresetConfig.list_presets():
            config = LLMPresetConfig.load_preset(preset_name)
            assert (
                config.fallback_to_regex is True
            ), f"Preset '{preset_name}' should have fallback enabled"

    def test_all_presets_have_cache_enabled(self) -> None:
        """Test that all presets have cache_enabled=True."""
        for preset_name in LLMPresetConfig.list_presets():
            config = LLMPresetConfig.load_preset(preset_name)
            assert config.cache_enabled is True, f"Preset '{preset_name}' should have cache enabled"


class TestPresetProviderTypes:
    """Tests for preset provider type coverage."""

    def test_presets_cover_all_provider_types(self) -> None:
        """Test that presets cover all 5 provider types."""
        providers = set()
        for preset_name in LLMPresetConfig.list_presets():
            config = LLMPresetConfig.load_preset(preset_name)
            providers.add(config.provider)

        expected_providers = {
            "codex-cli",
            "ollama",
            "claude-cli",
            "openai",
            "anthropic",
        }

        assert providers == expected_providers

    def test_cli_presets_no_api_key(self) -> None:
        """Test that CLI-based presets have no API key."""
        cli_presets = ["codex-cli-free", "ollama-local", "claude-cli-sonnet"]

        for preset_name in cli_presets:
            config = LLMPresetConfig.load_preset(preset_name)
            assert config.api_key is None, f"CLI preset '{preset_name}' should not have API key"

    def test_api_presets_have_cost_budget(self) -> None:
        """Test that API-based presets have cost budgets."""
        api_presets = ["openai-api-mini", "anthropic-api-balanced"]

        for preset_name in api_presets:
            config = LLMPresetConfig.load_preset(preset_name)
            assert (
                config.cost_budget is not None and config.cost_budget > 0
            ), f"API preset '{preset_name}' should have cost budget"
