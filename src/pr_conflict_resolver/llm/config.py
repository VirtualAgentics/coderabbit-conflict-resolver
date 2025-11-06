"""LLM configuration management for parsing CodeRabbit comments.

This module provides configuration data structures for LLM integration.
Phase 0: Foundation only - configuration structure without implementation.
"""

import os
from dataclasses import dataclass

from pr_conflict_resolver.config.runtime_config import ConfigError


@dataclass(frozen=True, slots=True)
class LLMConfig:
    """Configuration for LLM-based parsing.

    This immutable configuration object controls all aspects of LLM integration,
    including provider selection, model parameters, caching, and cost controls.

    Args:
        enabled: Whether LLM parsing is enabled (default: False for backward compatibility)
        provider: LLM provider name ("claude-cli", "openai", "anthropic", "ollama")
        model: Model identifier (e.g., "claude-sonnet-4-5", "gpt-4")
        api_key: API key for the provider (if required)
        fallback_to_regex: Fall back to regex parsing if LLM fails (default: True)
        cache_enabled: Cache LLM responses to reduce cost (default: True)
        max_tokens: Maximum tokens per LLM request (default: 2000)
        cost_budget: Maximum cost per run in USD (None = unlimited)

    Example:
        >>> config = LLMConfig.from_defaults()
        >>> config.enabled
        False
        >>> config.provider
        'claude-cli'

        >>> config = LLMConfig.from_env()  # Reads CR_LLM_* environment variables
        >>> config.enabled  # True if CR_LLM_ENABLED=true
        True
    """

    enabled: bool = False
    provider: str = "claude-cli"
    model: str = "claude-sonnet-4-5"
    api_key: str | None = None
    fallback_to_regex: bool = True
    cache_enabled: bool = True
    max_tokens: int = 2000
    cost_budget: float | None = None

    def __post_init__(self) -> None:
        """Validate LLMConfig fields after initialization.

        Raises:
            ValueError: If any field has an invalid value
        """
        valid_providers = {"claude-cli", "openai", "anthropic", "codex-cli", "ollama"}
        if self.provider not in valid_providers:
            raise ValueError(f"provider must be one of {valid_providers}, got '{self.provider}'")

        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")

        if self.cost_budget is not None and self.cost_budget <= 0:
            raise ValueError(f"cost_budget must be positive, got {self.cost_budget}")

        # Validate that API-based providers have an API key if enabled
        if self.enabled and self.provider in {"openai", "anthropic"} and not self.api_key:
            raise ValueError(
                f"api_key is required when enabled=True and provider='{self.provider}'"
            )

    @classmethod
    def from_defaults(cls) -> "LLMConfig":
        """Create an LLMConfig with safe default values.

        Returns:
            LLMConfig with all defaults (LLM disabled)

        Example:
            >>> config = LLMConfig.from_defaults()
            >>> config.enabled
            False
        """
        return cls()

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create an LLMConfig from environment variables.

        Reads the following environment variables:
        - CR_LLM_ENABLED: "true"/"false" to enable/disable
        - CR_LLM_PROVIDER: Provider name
        - CR_LLM_MODEL: Model identifier
        - CR_LLM_API_KEY: API key (if required)
        - CR_LLM_FALLBACK_TO_REGEX: "true"/"false"
        - CR_LLM_CACHE_ENABLED: "true"/"false"
        - CR_LLM_MAX_TOKENS: Integer value
        - CR_LLM_COST_BUDGET: Float value in USD

        Returns:
            LLMConfig with values from environment, falling back to defaults

        Example:
            >>> os.environ["CR_LLM_ENABLED"] = "true"
            >>> config = LLMConfig.from_env()
            >>> config.enabled
            True
        """
        enabled = os.getenv("CR_LLM_ENABLED", "false").lower() == "true"
        provider = os.getenv("CR_LLM_PROVIDER", "claude-cli")
        model = os.getenv("CR_LLM_MODEL", "claude-sonnet-4-5")
        api_key = os.getenv("CR_LLM_API_KEY")
        fallback_to_regex = os.getenv("CR_LLM_FALLBACK_TO_REGEX", "true").lower() == "true"
        cache_enabled = os.getenv("CR_LLM_CACHE_ENABLED", "true").lower() == "true"

        max_tokens_str = os.getenv("CR_LLM_MAX_TOKENS", "2000")
        try:
            max_tokens = int(max_tokens_str)
        except ValueError as e:
            raise ConfigError(
                f"CR_LLM_MAX_TOKENS must be a valid integer, got '{max_tokens_str}'"
            ) from e

        cost_budget_str = os.getenv("CR_LLM_COST_BUDGET")
        cost_budget = None
        if cost_budget_str:
            try:
                cost_budget = float(cost_budget_str)
            except ValueError as e:
                raise ConfigError(
                    f"CR_LLM_COST_BUDGET must be a valid float, got '{cost_budget_str}'"
                ) from e

        return cls(
            enabled=enabled,
            provider=provider,
            model=model,
            api_key=api_key,
            fallback_to_regex=fallback_to_regex,
            cache_enabled=cache_enabled,
            max_tokens=max_tokens,
            cost_budget=cost_budget,
        )
