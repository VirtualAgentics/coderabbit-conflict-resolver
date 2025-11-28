# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""LLM Provider Factory and Selection Logic.

This module provides factory functions for creating and validating LLM provider
instances. It supports 5 providers with polymorphic usage through a common
protocol interface.

Supported Providers:
    - openai: OpenAI API (requires API key)
    - anthropic: Anthropic API (requires API key)
    - claude-cli: Claude CLI (no API key, CLI must be installed)
    - codex-cli: Codex CLI (no API key, CLI must be installed)
    - ollama: Ollama HTTP API (no API key, service must be running)

Usage Examples:
    Create an API-based provider:
        >>> provider = create_provider("anthropic", api_key="sk-ant-...")
        >>> response = provider.generate("Hello")

    Create a CLI-based provider:
        >>> provider = create_provider("claude-cli", model="claude-sonnet-4-5")
        >>> response = provider.generate("Hello")

    Create from configuration:
        >>> config = LLMConfig.from_env()
        >>> provider = create_provider_from_config(config)
        >>> response = provider.generate("Hello")

    Validate provider health:
        >>> if validate_provider(provider):
        ...     response = provider.generate("Hello")
"""

import logging
from typing import Any

from review_bot_automator.llm.config import LLMConfig
from review_bot_automator.llm.constants import VALID_LLM_PROVIDERS
from review_bot_automator.llm.exceptions import LLMAPIError, LLMConfigurationError
from review_bot_automator.llm.providers.anthropic_api import AnthropicAPIProvider
from review_bot_automator.llm.providers.claude_cli import ClaudeCLIProvider
from review_bot_automator.llm.providers.codex_cli import CodexCLIProvider
from review_bot_automator.llm.providers.ollama import OllamaProvider
from review_bot_automator.llm.providers.openai_api import OpenAIAPIProvider

logger = logging.getLogger(__name__)

# Provider registry mapping provider names to classes
PROVIDER_REGISTRY: dict[str, type[Any]] = {
    "openai": OpenAIAPIProvider,
    "anthropic": AnthropicAPIProvider,
    "claude-cli": ClaudeCLIProvider,
    "codex-cli": CodexCLIProvider,
    "ollama": OllamaProvider,
}

# Providers that require API keys
_PROVIDERS_REQUIRING_API_KEY: frozenset[str] = frozenset({"openai", "anthropic"})


def create_provider(
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
    timeout: int | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Create LLM provider instance with validation.

    This factory function creates and configures an LLM provider instance with
    comprehensive validation of provider name, API key requirements, and parameters.
    It supports all 5 LLM providers with provider-specific parameter handling.

    Args:
        provider: Provider name (openai, anthropic, claude-cli, codex-cli, ollama).
            Must be one of the values in VALID_LLM_PROVIDERS.
        model: Model identifier (optional, uses provider defaults if not specified).
            Examples: "claude-sonnet-4-5", "gpt-4", "llama3.3:70b"
        api_key: API key for API-based providers. Required for "openai" and "anthropic",
            not used for CLI and local providers. Set via CR_LLM_API_KEY environment
            variable or pass explicitly.
        timeout: Request timeout in seconds (optional, uses provider-specific defaults
            if not specified). Used for API calls and CLI command execution.
        **kwargs: Provider-specific parameters passed through to provider constructor.
            Examples: base_url for Ollama, custom headers for API providers.

    Returns:
        Configured provider instance implementing the LLMProvider protocol. The instance
        can be used polymorphically with .generate() and .count_tokens() methods.

    Raises:
        LLMConfigurationError: If provider name is invalid, API key is missing for
            API-based providers, or provider constructor detects invalid configuration
            (e.g., CLI not installed, Ollama service unavailable).
        ValueError: If timeout is invalid (non-positive).
        Exception: Provider constructor exceptions are propagated. Callers should
            expect arbitrary exceptions if providers fail during initialization
            (e.g., network errors, authentication failures, missing dependencies).

    Examples:
        Create OpenAI provider:
            >>> provider = create_provider(
            ...     "openai",
            ...     model="gpt-4",
            ...     api_key=os.getenv("OPENAI_API_KEY")
            ... )

        Create Anthropic provider:
            >>> provider = create_provider(
            ...     "anthropic",
            ...     model="claude-sonnet-4",
            ...     api_key=os.getenv("ANTHROPIC_API_KEY")
            ... )

        Create Claude CLI provider:
            >>> provider = create_provider("claude-cli", model="claude-sonnet-4-5")

        Create Ollama provider with custom base URL:
            >>> provider = create_provider(
            ...     "ollama",
            ...     model="llama3.3:70b",
            ...     base_url="http://localhost:11434"
            ... )
    """
    # Validate provider name
    if provider not in VALID_LLM_PROVIDERS:
        valid_list = ", ".join(sorted(VALID_LLM_PROVIDERS))
        raise LLMConfigurationError(
            f"Invalid provider '{provider}'. Valid providers: {valid_list}",
            details={"provider": provider, "valid_providers": list(VALID_LLM_PROVIDERS)},
        )

    # Validate API key requirement for API-based providers
    if provider in _PROVIDERS_REQUIRING_API_KEY:
        if not api_key:
            raise LLMConfigurationError(
                f"API key required for '{provider}' provider. "
                f"Set CR_LLM_API_KEY environment variable or pass api_key parameter.",
                details={"provider": provider, "env_var": "CR_LLM_API_KEY"},
            )
        if not api_key.strip():
            raise LLMConfigurationError(
                f"API key cannot be empty for '{provider}' provider.",
                details={"provider": provider},
            )

    # Validate timeout if provided
    if timeout is not None and timeout <= 0:
        raise ValueError(f"timeout must be positive, got {timeout}")

    # Get provider class from registry
    provider_class = PROVIDER_REGISTRY[provider]

    # Build provider-specific kwargs
    provider_kwargs: dict[str, Any] = {}

    # Add model if specified
    if model is not None:
        provider_kwargs["model"] = model

    # Add timeout if explicitly specified (otherwise use provider defaults)
    if timeout is not None:
        provider_kwargs["timeout"] = timeout

    # Add API key for API-based providers
    if provider in _PROVIDERS_REQUIRING_API_KEY:
        provider_kwargs["api_key"] = api_key

    # Pass through any additional provider-specific kwargs
    provider_kwargs.update(kwargs)

    # Create and return provider instance
    timeout_str = f"{timeout}s" if timeout is not None else "provider default"
    logger.info(
        f"Creating {provider} provider: model={model}, timeout={timeout_str}, "
        f"kwargs={list(kwargs.keys())}"
    )

    try:
        return provider_class(**provider_kwargs)
    except Exception as e:
        logger.error(f"Failed to create {provider} provider: {e}")
        raise


def validate_provider(provider: Any) -> bool:  # noqa: ANN401
    """Validate provider connectivity with health check.

    Performs a lightweight health check by attempting to count tokens on a minimal
    test string. This validates that the provider is properly configured and can
    communicate with the underlying service (API, CLI, or local service).

    Args:
        provider: Provider instance to validate. Must implement the LLMProvider
            protocol with a count_tokens() method.

    Returns:
        True if provider is healthy and can process requests. Always returns True
        on success (never returns False).

    Raises:
        LLMAPIError: If health check fails due to connectivity, authentication,
            or service unavailability issues.
        LLMConfigurationError: If provider is not properly configured (e.g., CLI
            not installed, service not running).

    Examples:
        Validate provider before use:
            >>> provider = create_provider("anthropic", api_key="sk-ant-...")
            >>> if validate_provider(provider):
            ...     response = provider.generate("Hello")
    """
    try:
        # Use token counting as lightweight health check
        # This validates provider is accessible without consuming API credits
        # No timeout needed - count_tokens() is typically fast and local for most
        # providers, but may invoke an API call for some (e.g., Anthropic). For
        # true local behavior, use provider-specific token counters or guard checks.
        test_string = "test"
        _ = provider.count_tokens(test_string)

        logger.debug(f"Provider health check passed: {provider.__class__.__name__}")
        return True

    except Exception as e:
        logger.error(f"Provider health check failed: {e}")
        # Re-raise the exception with context
        if isinstance(e, (LLMAPIError, LLMConfigurationError)):
            raise
        raise LLMAPIError(
            f"Provider health check failed: {e}",
            details={"provider_class": provider.__class__.__name__, "error": str(e)},
        ) from e


def create_provider_from_config(config: LLMConfig) -> Any:  # noqa: ANN401
    """Create provider from LLMConfig dataclass.

    Convenience helper that extracts provider settings from an LLMConfig instance
    and delegates to create_provider(). This simplifies provider creation when
    configuration is managed via LLMConfig (e.g., from environment variables).

    If config.cache_enabled is True, the provider is wrapped with CachingProvider
    for transparent response caching to reduce API costs.

    If config.circuit_breaker_enabled is True, the provider is wrapped with
    ResilientLLMProvider for circuit breaker protection against cascading failures.

    Wrapper order: base -> circuit breaker -> cache. This ensures cache hits don't
    affect circuit breaker state.

    Args:
        config: LLMConfig instance with provider settings. Must have valid provider,
            model, and api_key (if required) fields.

    Returns:
        Configured provider instance created from config values. If caching is
        enabled, returns a CachingProvider wrapper around the actual provider.

    Raises:
        LLMConfigurationError: If config contains invalid provider settings or
            missing required fields.
        ValueError: If config validation fails.

    Examples:
        Create from default config:
            >>> config = LLMConfig.from_defaults()
            >>> provider = create_provider_from_config(config)

        Create from environment variables:
            >>> # Assumes CR_LLM_PROVIDER, CR_LLM_MODEL, CR_LLM_API_KEY are set
            >>> config = LLMConfig.from_env()
            >>> provider = create_provider_from_config(config)

        Create from custom config:
            >>> config = LLMConfig(
            ...     enabled=True,
            ...     provider="anthropic",
            ...     model="claude-sonnet-4",
            ...     api_key="sk-ant-..."
            ... )
            >>> provider = create_provider_from_config(config)

        Create with caching enabled:
            >>> config = LLMConfig(enabled=True, cache_enabled=True)
            >>> provider = create_provider_from_config(config)
            >>> # provider is now a CachingProvider wrapper
    """
    logger.info(
        f"Creating provider from config: provider={config.provider}, "
        f"model={config.model}, cache_enabled={config.cache_enabled}, "
        f"circuit_breaker_enabled={config.circuit_breaker_enabled}"
    )

    provider = create_provider(
        provider=config.provider,
        model=config.model,
        api_key=config.api_key,
        # Don't specify timeout - let providers use their own defaults
    )

    # Wrap with circuit breaker if enabled (inner wrapper)
    if config.circuit_breaker_enabled:
        from review_bot_automator.llm.resilience import ResilientLLMProvider

        provider = ResilientLLMProvider(
            provider,
            failure_threshold=config.circuit_breaker_threshold,
            cooldown_seconds=config.circuit_breaker_cooldown,
        )
        logger.info(
            f"Circuit breaker enabled for {config.provider} provider: "
            f"threshold={config.circuit_breaker_threshold}, "
            f"cooldown={config.circuit_breaker_cooldown}s"
        )

    # Wrap with caching if enabled (outer wrapper)
    if config.cache_enabled:
        from review_bot_automator.llm.providers.caching_provider import CachingProvider

        provider = CachingProvider(provider)
        logger.info(f"Cache enabled for {config.provider} provider")

    return provider
