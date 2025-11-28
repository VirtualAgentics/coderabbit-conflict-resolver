# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""LLM configuration presets for zero-config setup.

This module provides predefined LLM configurations that allow users to quickly
get started with different LLM providers without manual configuration. Each preset
is optimized for its specific use case (cost, performance, privacy, etc.).

Usage:
    >>> from review_bot_automator.llm.presets import LLMPresetConfig
    >>> config = LLMPresetConfig.load_preset("codex-cli-free")
    >>> config.provider
    'codex-cli'
    >>> config.model
    'codex'
"""

from dataclasses import dataclass, replace
from typing import ClassVar

from review_bot_automator.llm.config import LLMConfig


@dataclass(frozen=True, slots=True)
class LLMPreset:
    """A named LLM configuration preset.

    Args:
        name: Human-readable preset name (e.g., "codex-cli-free")
        description: Short description of the preset's use case
        config: The LLMConfig for this preset

    Example:
        >>> preset = LLMPreset(
        ...     name="codex-cli-free",
        ...     description="Free Codex CLI (GitHub Copilot subscription required)",
        ...     config=LLMConfig(enabled=True, provider="codex-cli", model="codex")
        ... )
    """

    name: str
    description: str
    config: LLMConfig


class LLMPresetConfig:
    """Manages predefined LLM configuration presets.

    Provides 5 presets covering all provider types:

    1. **codex-cli-free**: Free Codex CLI (GitHub Copilot subscription)
    2. **ollama-local**: Local Ollama (free, private, offline)
    3. **claude-cli-sonnet**: Claude CLI with Sonnet 4.5 (subscription-based)
    4. **openai-api-mini**: OpenAI GPT-4o-mini (low-cost API)
    5. **anthropic-api-balanced**: Anthropic Claude Haiku 4 (balanced cost/performance)

    Example:
        >>> config = LLMPresetConfig.load_preset("codex-cli-free")
        >>> config.enabled
        True
        >>> config.provider
        'codex-cli'
    """

    # Preset 1: Codex CLI - Free (GitHub Copilot subscription required)
    CODEX_CLI_FREE = LLMPreset(
        name="codex-cli-free",
        description="Free Codex CLI - Requires GitHub Copilot subscription",
        config=LLMConfig(
            enabled=True,
            provider="codex-cli",
            model="codex",
            api_key=None,
            fallback_to_regex=True,
            cache_enabled=True,
            max_tokens=2000,
            cost_budget=None,
        ),
    )

    # Preset 2: Ollama Local - Free (requires local Ollama installation)
    OLLAMA_LOCAL = LLMPreset(
        name="ollama-local",
        description="Local Ollama - Free, private, offline (recommended: qwen2.5-coder:7b)",
        config=LLMConfig(
            enabled=True,
            provider="ollama",
            model="qwen2.5-coder:7b",
            api_key=None,
            fallback_to_regex=True,
            cache_enabled=True,
            max_tokens=2000,
            cost_budget=None,
        ),
    )

    # Preset 3: Claude CLI Sonnet - Subscription-based (no API key)
    CLAUDE_CLI_SONNET = LLMPreset(
        name="claude-cli-sonnet",
        description="Claude CLI with Sonnet 4.5 - Requires Claude subscription",
        config=LLMConfig(
            enabled=True,
            provider="claude-cli",
            model="claude-sonnet-4-5",
            api_key=None,
            fallback_to_regex=True,
            cache_enabled=True,
            max_tokens=2000,
            cost_budget=None,
        ),
    )

    # Preset 4: OpenAI API Mini - Low-cost API
    OPENAI_API_MINI = LLMPreset(
        name="openai-api-mini",
        description="OpenAI GPT-4o-mini - Low-cost API (requires API key)",
        config=LLMConfig(
            enabled=False,  # Will be enabled when API key is provided
            provider="openai",
            model="gpt-4o-mini",
            api_key=None,  # Must be set via env var or CLI flag
            fallback_to_regex=True,
            cache_enabled=True,
            max_tokens=2000,
            cost_budget=5.0,  # $5 default budget
        ),
    )

    # Preset 5: Anthropic API Balanced - Balanced cost/performance
    ANTHROPIC_API_BALANCED = LLMPreset(
        name="anthropic-api-balanced",
        description="Anthropic Claude Haiku 4 - Balanced cost/performance (requires API key)",
        config=LLMConfig(
            enabled=False,  # Will be enabled when API key is provided
            provider="anthropic",
            model="claude-haiku-4",
            api_key=None,  # Must be set via env var or CLI flag
            fallback_to_regex=True,
            cache_enabled=True,
            max_tokens=2000,
            cost_budget=5.0,  # $5 default budget
        ),
    )

    # Registry of all available presets
    _PRESETS: ClassVar[dict[str, LLMPreset]] = {
        CODEX_CLI_FREE.name: CODEX_CLI_FREE,
        OLLAMA_LOCAL.name: OLLAMA_LOCAL,
        CLAUDE_CLI_SONNET.name: CLAUDE_CLI_SONNET,
        OPENAI_API_MINI.name: OPENAI_API_MINI,
        ANTHROPIC_API_BALANCED.name: ANTHROPIC_API_BALANCED,
    }

    @classmethod
    def list_presets(cls) -> list[str]:
        """Get list of available preset names.

        Returns:
            List of preset names (e.g., ["codex-cli-free", "ollama-local", ...])

        Example:
            >>> LLMPresetConfig.list_presets()
            ['codex-cli-free', 'ollama-local', 'claude-cli-sonnet', ...]
        """
        return sorted(cls._PRESETS.keys())

    @classmethod
    def get_preset(cls, name: str) -> LLMPreset:
        """Get a preset by name.

        Args:
            name: Preset name (e.g., "codex-cli-free")

        Returns:
            LLMPreset object with name, description, and config

        Raises:
            ValueError: If preset name is invalid

        Example:
            >>> preset = LLMPresetConfig.get_preset("codex-cli-free")
            >>> preset.name
            'codex-cli-free'
            >>> preset.description
            'Free Codex CLI - Requires GitHub Copilot subscription'
        """
        if name not in cls._PRESETS:
            available = ", ".join(cls.list_presets())
            raise ValueError(f"Unknown preset '{name}'. Available presets: {available}")
        return cls._PRESETS[name]

    @classmethod
    def load_preset(cls, name: str, api_key: str | None = None) -> LLMConfig:
        """Load an LLMConfig from a preset name.

        Args:
            name: Preset name (e.g., "codex-cli-free")
            api_key: Optional API key override (for API-based providers)

        Returns:
            LLMConfig object ready to use

        Raises:
            ValueError: If preset name is invalid

        Example:
            >>> # Load preset without API key (CLI-based providers)
            >>> config = LLMPresetConfig.load_preset("codex-cli-free")
            >>> config.provider
            'codex-cli'

            >>> # Load preset with API key override
            >>> config = LLMPresetConfig.load_preset("openai-api-mini", api_key="sk-...")
            >>> config.api_key
            'sk-...'
        """
        preset = cls.get_preset(name)

        # If API key override provided, create new config with updated key and enable it
        if api_key is not None:
            return replace(preset.config, api_key=api_key, enabled=True)

        return preset.config

    @classmethod
    def describe_preset(cls, name: str) -> str:
        """Get human-readable description of a preset.

        Args:
            name: Preset name

        Returns:
            Formatted description string with provider, model, and use case

        Raises:
            ValueError: If preset name is invalid

        Example:
            >>> print(LLMPresetConfig.describe_preset("codex-cli-free"))
            codex-cli-free: Free Codex CLI - Requires GitHub Copilot subscription
              Provider: codex-cli
              Model: codex
              Requires API key: No
        """
        preset = cls.get_preset(name)
        config = preset.config

        requires_api_key = config.provider in {"openai", "anthropic"}
        api_key_str = "Yes" if requires_api_key else "No"

        lines = [
            f"{preset.name}: {preset.description}",
            f"  Provider: {config.provider}",
            f"  Model: {config.model}",
            f"  Requires API key: {api_key_str}",
        ]

        if config.cost_budget is not None:
            lines.append(f"  Cost budget: ${config.cost_budget:.2f}")

        return "\n".join(lines)

    @classmethod
    def describe_all_presets(cls) -> str:
        """Get human-readable descriptions of all presets.

        Returns:
            Formatted string with all preset descriptions

        Example:
            >>> print(LLMPresetConfig.describe_all_presets())
            Available LLM Presets:

            codex-cli-free: Free Codex CLI - Requires GitHub Copilot subscription
              Provider: codex-cli
              Model: codex
              Requires API key: No
            ...
        """
        lines = ["Available LLM Presets:", ""]

        for preset_name in cls.list_presets():
            lines.append(cls.describe_preset(preset_name))
            lines.append("")  # Blank line between presets

        return "\n".join(lines)
