# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""LLM configuration management for parsing CodeRabbit comments.

This module provides configuration data structures for LLM integration.
Phase 0: Foundation only - configuration structure without implementation.
"""

import os
from dataclasses import dataclass

from review_bot_automator.config.exceptions import ConfigError
from review_bot_automator.llm.constants import VALID_LLM_PROVIDERS


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
        circuit_breaker_enabled: Enable circuit breaker for provider protection (default: True)
        circuit_breaker_threshold: Consecutive failures before circuit opens (default: 5)
        circuit_breaker_cooldown: Seconds to wait before recovery attempt (default: 60.0)
        retry_on_rate_limit: Enable automatic retry on rate limit errors (default: True)
        retry_max_attempts: Maximum retry attempts for rate limit errors (default: 3)
        retry_base_delay: Base delay in seconds for exponential backoff (default: 2.0)
        effort: LLM effort level for speed/cost vs accuracy tradeoff
            (None, "none", "low", "medium", "high")

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
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown: float = 60.0
    # Rate limit retry configuration
    retry_on_rate_limit: bool = True
    retry_max_attempts: int = 3
    retry_base_delay: float = 2.0
    # Effort level for speed/cost vs accuracy tradeoff
    effort: str | None = None

    def __post_init__(self) -> None:
        """Validate LLMConfig fields after initialization.

        Raises:
            ValueError: If any field has an invalid value
        """
        if self.provider not in VALID_LLM_PROVIDERS:
            raise ValueError(
                f"provider must be one of {VALID_LLM_PROVIDERS}, got '{self.provider}'"
            )

        if self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")

        if self.cost_budget is not None and self.cost_budget <= 0:
            raise ValueError(f"cost_budget must be positive, got {self.cost_budget}")

        if self.circuit_breaker_threshold < 1:
            raise ValueError(
                f"circuit_breaker_threshold must be >= 1, got {self.circuit_breaker_threshold}"
            )

        if self.circuit_breaker_cooldown <= 0:
            raise ValueError(
                f"circuit_breaker_cooldown must be > 0, got {self.circuit_breaker_cooldown}"
            )

        if self.retry_max_attempts < 1:
            raise ValueError(f"retry_max_attempts must be >= 1, got {self.retry_max_attempts}")

        if self.retry_base_delay <= 0:
            raise ValueError(f"retry_base_delay must be > 0, got {self.retry_base_delay}")

        # Normalize and validate effort level
        if self.effort is not None:
            normalized_effort = self.effort.lower()
            valid_efforts = {"none", "low", "medium", "high"}
            if normalized_effort not in valid_efforts:
                raise ValueError(
                    "effort must be one of {'none', 'low', 'medium', 'high'}, "
                    f"got '{self.effort}'"
                )
            # dataclass is frozen, so use object.__setattr__
            object.__setattr__(self, "effort", normalized_effort)

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
        - CR_LLM_CIRCUIT_BREAKER_ENABLED: "true"/"false"
        - CR_LLM_CIRCUIT_BREAKER_THRESHOLD: Integer value (minimum 1)
        - CR_LLM_CIRCUIT_BREAKER_COOLDOWN: Float value in seconds
        - CR_LLM_RETRY_ON_RATE_LIMIT: "true"/"false" (default: true)
        - CR_LLM_RETRY_MAX_ATTEMPTS: Integer value (default: 3)
        - CR_LLM_RETRY_BASE_DELAY: Float value in seconds (default: 2.0)
        - CR_LLM_EFFORT: LLM effort level (default: None, options: none/low/medium/high)

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

        circuit_breaker_enabled = (
            os.getenv("CR_LLM_CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"
        )

        circuit_breaker_threshold_str = os.getenv("CR_LLM_CIRCUIT_BREAKER_THRESHOLD", "5")
        try:
            circuit_breaker_threshold = int(circuit_breaker_threshold_str)
        except ValueError as e:
            raise ConfigError(
                f"CR_LLM_CIRCUIT_BREAKER_THRESHOLD must be a valid integer, "
                f"got '{circuit_breaker_threshold_str}'"
            ) from e

        circuit_breaker_cooldown_str = os.getenv("CR_LLM_CIRCUIT_BREAKER_COOLDOWN", "60.0")
        try:
            circuit_breaker_cooldown = float(circuit_breaker_cooldown_str)
        except ValueError as e:
            raise ConfigError(
                f"CR_LLM_CIRCUIT_BREAKER_COOLDOWN must be a valid float, "
                f"got '{circuit_breaker_cooldown_str}'"
            ) from e

        retry_on_rate_limit = os.getenv("CR_LLM_RETRY_ON_RATE_LIMIT", "true").lower() == "true"

        retry_max_attempts_str = os.getenv("CR_LLM_RETRY_MAX_ATTEMPTS", "3")
        try:
            retry_max_attempts = int(retry_max_attempts_str)
        except ValueError as e:
            raise ConfigError(
                f"CR_LLM_RETRY_MAX_ATTEMPTS must be a valid integer, "
                f"got '{retry_max_attempts_str}'"
            ) from e

        retry_base_delay_str = os.getenv("CR_LLM_RETRY_BASE_DELAY", "2.0")
        try:
            retry_base_delay = float(retry_base_delay_str)
        except ValueError as e:
            raise ConfigError(
                f"CR_LLM_RETRY_BASE_DELAY must be a valid float, " f"got '{retry_base_delay_str}'"
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
            circuit_breaker_enabled=circuit_breaker_enabled,
            circuit_breaker_threshold=circuit_breaker_threshold,
            circuit_breaker_cooldown=circuit_breaker_cooldown,
            retry_on_rate_limit=retry_on_rate_limit,
            retry_max_attempts=retry_max_attempts,
            retry_base_delay=retry_base_delay,
            effort=(os.getenv("CR_LLM_EFFORT", "").strip().lower() or None),
        )
