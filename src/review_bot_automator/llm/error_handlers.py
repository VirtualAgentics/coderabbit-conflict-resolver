# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Error handling utilities for LLM operations.

This module provides user-friendly error messages and troubleshooting guidance
for LLM-related errors, with provider-specific formatting and setup instructions.
"""

import re
from typing import ClassVar

from review_bot_automator.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class LLMErrorHandler:
    """Central error handler for LLM operations with provider-specific guidance.

    Provides formatted error messages with:
    - Provider-specific troubleshooting steps
    - Setup documentation links
    - Sanitized error output (no API key leaks)
    - Actionable next steps

    Example:
        >>> from review_bot_automator.llm.exceptions import LLMAuthenticationError
        >>> error = LLMAuthenticationError("Invalid API key")
        >>> message = LLMErrorHandler.format_auth_error("anthropic")
        >>> print(message)
        Authentication Error (Anthropic)
        ...
    """

    # API key patterns for sanitization (match common formats)
    _API_KEY_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"sk-ant-[a-zA-Z0-9\-_]+"),  # Anthropic keys
        re.compile(r"sk-proj-[a-zA-Z0-9\-_]+"),  # OpenAI project keys
        re.compile(r"sk-[a-zA-Z0-9\-_]{20,}"),  # OpenAI keys (generic)
        re.compile(r"api[_-]?key[:\s=]+['\"]?([a-zA-Z0-9\-_]{10,})['\"]?", re.I),
        re.compile(r"token[:\s=]+['\"]?([a-zA-Z0-9\-_]{10,})['\"]?", re.I),
    ]

    @staticmethod
    def sanitize_error_message(message: str) -> str:
        """Remove API keys and sensitive data from error messages.

        Args:
            message: Raw error message that may contain sensitive data.

        Returns:
            Sanitized error message with API keys redacted.

        Example:
            >>> msg = "Auth failed with key sk-ant-abc123..."
            >>> LLMErrorHandler.sanitize_error_message(msg)
            'Auth failed with key [REDACTED_API_KEY]'
        """
        sanitized = message

        # Redact all API key patterns
        for pattern in LLMErrorHandler._API_KEY_PATTERNS:
            sanitized = pattern.sub("[REDACTED_API_KEY]", sanitized)

        return sanitized

    @staticmethod
    def get_setup_link(provider: str) -> str:
        """Get setup documentation link for a provider.

        Args:
            provider: LLM provider name (e.g., "anthropic", "openai").

        Returns:
            URL to provider setup documentation.

        Example:
            >>> LLMErrorHandler.get_setup_link("anthropic")
            'https://console.anthropic.com/'
        """
        links = {
            "anthropic": "https://console.anthropic.com/",
            "openai": "https://platform.openai.com/api-keys",
            "ollama": "https://github.com/ollama/ollama#quickstart",
            "claude-cli": "https://claude.ai/settings/subscriptions",
            "codex-cli": "https://github.com/features/copilot",
        }

        return links.get(
            provider.lower(), "https://github.com/VirtualAgentics/review-bot-automator/docs"
        )

    @staticmethod
    def format_auth_error(provider: str) -> str:
        """Format authentication error with setup guidance.

        Args:
            provider: LLM provider name.

        Returns:
            Formatted error message with troubleshooting steps.

        Example:
            >>> print(LLMErrorHandler.format_auth_error("anthropic"))
            Authentication Error (Anthropic)
            ...
        """
        # Special case for OpenAI capitalization
        provider_name = "OpenAI" if provider.lower() == "openai" else provider.capitalize()
        setup_link = LLMErrorHandler.get_setup_link(provider)

        if provider.lower() == "anthropic":
            env_var = "CR_LLM_API_KEY"
            key_format = "sk-ant-..."
        elif provider.lower() == "openai":
            env_var = "CR_LLM_API_KEY"
            key_format = "sk-..."
        elif provider.lower() == "ollama":
            return (
                f"❌ Connection Error ({provider_name})\n\n"
                "Failed to connect to Ollama server.\n\n"
                "Troubleshooting steps:\n"
                "  1. Verify Ollama is installed:\n"
                "     ollama --version\n"
                "     \n"
                "  2. Start Ollama server:\n"
                "     ollama serve\n"
                "     \n"
                "  3. Verify server is running:\n"
                "     curl http://localhost:11434/api/version\n"
                "     \n"
                "  4. Install a model:\n"
                "     ollama pull llama3.3:70b\n"
                "     \n"
                f"For installation help, see:\n  {setup_link}\n\n"
                "Run with --log-level DEBUG for details."
            )
        elif provider.lower() in ("claude-cli", "codex-cli"):
            return (
                f"❌ CLI Error ({provider_name})\n\n"
                f"Failed to execute {provider_name} command.\n\n"
                "Troubleshooting steps:\n"
                f"  1. Verify {provider_name} is installed:\n"
                f"     which {provider.lower()}\n"
                "     \n"
                "  2. Check subscription status:\n"
                f"     {setup_link}\n"
                "     \n"
                f"  3. Verify {provider_name} works standalone:\n"
                f"     {provider.lower()} --version\n"
                "     \n"
                "Run with --log-level DEBUG for details."
            )
        else:
            env_var = "CR_LLM_API_KEY"
            key_format = "<key>"

        return (
            f"❌ Authentication Error ({provider_name})\n\n"
            f"Failed to authenticate with {provider_name} API.\n\n"
            "Troubleshooting steps:\n"
            "  1. Verify your API key is set:\n"
            f'     export {env_var}="{key_format}"\n'
            "     \n"
            "  2. Get an API key from:\n"
            f"     {setup_link}\n"
            "     \n"
            "  3. Check the key has not expired\n"
            "     \n"
            "  4. Ensure you're using the correct provider:\n"
            f"     --llm-provider {provider.lower()}\n"
            "     \n"
            f"For more help, see:\n  {setup_link}\n\n"
            "Run with --log-level DEBUG for details."
        )

    @staticmethod
    def format_config_error(field: str, value: int | float | str) -> str:
        """Format configuration error with suggestions.

        Args:
            field: Configuration field that has an error.
            value: Invalid value provided.

        Returns:
            Formatted error message with valid options.

        Example:
            >>> print(LLMErrorHandler.format_config_error("provider", "invalid"))
            Configuration Error: provider
            ...
        """
        suggestions = {
            "provider": (
                "Valid providers: anthropic, openai, ollama, claude-cli, codex-cli\n"
                "Example: --llm-provider anthropic"
            ),
            "model": (
                "Check model name is valid for your provider:\n"
                "  - Anthropic: claude-haiku-4, claude-sonnet-4, claude-opus-4\n"
                "  - OpenAI: gpt-4o, gpt-4o-mini, gpt-4-turbo\n"
                "  - Ollama: llama3.3:70b, mistral, codellama\n"
                "Example: --llm-model claude-haiku-4"
            ),
            "max_tokens": (
                "max_tokens must be a positive integer (typically 1000-8000)\n"
                "Example: --llm-max-tokens 4000"
            ),
            "temperature": (
                "temperature must be between 0.0 and 1.0\n"
                "Example: --llm-temperature 0.0 (deterministic)"
            ),
            "confidence_threshold": (
                "confidence_threshold must be between 0.0 and 1.0\n"
                "Example: --llm-confidence-threshold 0.7"
            ),
        }

        suggestion = suggestions.get(field, f"Check {field} value is valid for your provider")
        sanitized_value = LLMErrorHandler.sanitize_error_message(str(value))

        return (
            f"⚠️ Configuration Error: {field}\n\n"
            f"Invalid value: {sanitized_value}\n\n"
            f"{suggestion}\n\n"
            "Run with --log-level DEBUG for details."
        )

    @staticmethod
    def format_model_error(provider: str, model: str) -> str:
        """Format model not available error with suggestions.

        Args:
            provider: LLM provider name.
            model: Model name that is not available.

        Returns:
            Formatted error message with available models.

        Example:
            >>> print(LLMErrorHandler.format_model_error("ollama", "invalid"))
            Model Not Available (Ollama)
            ...
        """
        provider_name = provider.capitalize()
        sanitized_model = LLMErrorHandler.sanitize_error_message(model)

        if provider.lower() == "ollama":
            return (
                f"❌ Model Not Available ({provider_name})\n\n"
                f"Model '{sanitized_model}' is not installed locally.\n\n"
                "Install the model:\n"
                f"  ollama pull {sanitized_model}\n"
                "  \n"
                "Or list available models:\n"
                "  ollama list\n"
                "  \n"
                "Popular models:\n"
                "  - llama3.3:70b (recommended for quality)\n"
                "  - mistral (fast)\n"
                "  - codellama (code-focused)\n"
                "  \n"
                "Run with --log-level DEBUG for details."
            )
        elif provider.lower() == "anthropic":
            return (
                f"❌ Model Not Available ({provider_name})\n\n"
                f"Model '{sanitized_model}' is not valid.\n\n"
                "Available Anthropic models:\n"
                "  - claude-haiku-4-5 (fast, cheap - $1/$5 per MTok)\n"
                "  - claude-sonnet-4-5 (balanced - $3/$15 per MTok)\n"
                "  - claude-opus-4-5 (flagship - $5/$25 per MTok, 67% cheaper than 4.1!)\n"
                "  \n"
                "Example:\n"
                "  --llm-model claude-haiku-4-5\n"
                "  \n"
                "Run with --log-level DEBUG for details."
            )
        elif provider.lower() == "openai":
            return (
                f"❌ Model Not Available ({provider_name})\n\n"
                f"Model '{sanitized_model}' is not valid.\n\n"
                "Available OpenAI models:\n"
                "  - gpt-5-nano (fastest, cheapest - $0.05/$0.40 per MTok)\n"
                "  - gpt-5-mini (best value - $0.25/$2 per MTok)\n"
                "  - gpt-5.1 (latest flagship - $1.25/$10 per MTok)\n"
                "  - gpt-4o-mini (legacy, still good - $0.15/$0.60 per MTok)\n"
                "  \n"
                "Example:\n"
                "  --llm-model gpt-5-mini\n"
                "  \n"
                "Run with --log-level DEBUG for details."
            )
        else:
            return (
                f"❌ Model Not Available ({provider_name})\n\n"
                f"Model '{sanitized_model}' is not valid for {provider_name}.\n\n"
                "Check your provider's documentation for available models.\n"
                "Run with --log-level DEBUG for details."
            )

    @staticmethod
    def format_provider_error(provider: str, error: Exception) -> str:
        """Format provider-specific error with context.

        Args:
            provider: LLM provider name.
            error: Exception raised by provider.

        Returns:
            Formatted error message with provider-specific guidance.

        Example:
            >>> from review_bot_automator.llm.exceptions import LLMAPIError
            >>> error = LLMAPIError("Rate limit exceeded")
            >>> print(LLMErrorHandler.format_provider_error("anthropic", error))
            API Error (Anthropic)
            ...
        """
        # Special case for OpenAI capitalization
        provider_name = "OpenAI" if provider.lower() == "openai" else provider.capitalize()
        error_message = LLMErrorHandler.sanitize_error_message(str(error))
        error_type = type(error).__name__

        # Provider-specific guidance based on error type
        if isinstance(error, LLMAuthenticationError):
            return LLMErrorHandler.format_auth_error(provider)

        elif isinstance(error, LLMRateLimitError):
            return (
                f"⚠️ Rate Limit Exceeded ({provider_name})\n\n"
                f"{error_message}\n\n"
                "You've hit the API rate limit.\n\n"
                "Options:\n"
                "  1. Wait a few minutes and try again\n"
                "  2. Reduce batch size or parallel processing\n"
                "  3. Upgrade your API plan for higher limits\n"
                "  4. Use prompt caching to reduce API calls\n"
                "  5. Switch to a free provider (Ollama)\n"
                "  \n"
                "Run with --log-level DEBUG for details."
            )

        elif isinstance(error, LLMTimeoutError):
            return (
                f"⏱️ Timeout Error ({provider_name})\n\n"
                f"{error_message}\n\n"
                "The API request timed out.\n\n"
                "Options:\n"
                "  1. Check your internet connection\n"
                "  2. Try again (may be temporary)\n"
                "  3. Reduce max_tokens to speed up responses\n"
                "  4. Use a faster model (e.g., haiku, gpt-4o-mini)\n"
                "  \n"
                "Run with --log-level DEBUG for details."
            )

        elif isinstance(error, LLMAPIError):
            return (
                f"❌ API Error ({provider_name})\n\n"
                f"{error_message}\n\n"
                "An API error occurred.\n\n"
                "Options:\n"
                "  1. Check the error message above\n"
                "  2. Verify your API key and permissions\n"
                "  3. Check provider status page\n"
                "  4. Try again in a few moments\n"
                "  \n"
                "Run with --log-level DEBUG for details."
            )

        elif isinstance(error, LLMConfigurationError):
            return (
                f"⚠️ Configuration Error ({provider_name})\n\n"
                f"{error_message}\n\n"
                "Check your LLM configuration.\n\n"
                "Run with --log-level DEBUG for details."
            )

        else:
            # Generic error formatting
            return (
                f"❌ {error_type} ({provider_name})\n\n"
                f"{error_message}\n\n"
                "An unexpected error occurred.\n\n"
                "Run with --log-level DEBUG for details."
            )
