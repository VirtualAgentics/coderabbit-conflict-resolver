# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Abstract base classes and protocols for LLM providers.

This module defines the core interfaces that all LLM providers must implement,
enabling polymorphic provider usage and type-safe provider implementations.

The provider abstraction supports:
- API-based providers (OpenAI, Anthropic)
- CLI-based providers (Claude CLI, Codex CLI)
- Local providers (Ollama)

All providers must implement the LLMProvider protocol for type checking and
the core methods for text generation and token counting.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining the interface for all LLM providers.

    This protocol ensures type safety across different provider implementations
    while allowing flexible provider-specific initialization and configuration.

    All providers must implement:
    - Text generation with token limits
    - Token counting for cost estimation
    - Error handling for provider-specific failures

    Examples:
        >>> provider = OpenAIAPIProvider(api_key="sk-...")
        >>> assert isinstance(provider, LLMProvider)
        >>> response = provider.generate("Explain Python", max_tokens=100)
        >>> tokens = provider.count_tokens("Some text")
    """

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text completion from prompt.

        This method handles the core LLM generation, including:
        - Sending the prompt to the provider
        - Handling retries and rate limits (provider-specific)
        - Returning the generated text

        Args:
            prompt: Input prompt text for generation
            max_tokens: Maximum tokens to generate in response

        Returns:
            Generated text from the LLM. Format depends on prompt design
            (e.g., JSON for structured output, plain text for general completion).

        Raises:
            RuntimeError: If generation fails after retries
            ValueError: If prompt is empty or max_tokens is invalid
            ConnectionError: If provider is unreachable
            LLMAuthenticationError: If API credentials are invalid

        Note:
            Implementations should handle provider-specific errors
            (API timeouts, rate limits, authentication) and convert
            them to the standard exceptions above.
        """
        pass

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using provider's tokenizer.

        Token counting is essential for:
        - Cost estimation before making API calls
        - Ensuring prompts fit within model context windows
        - Tracking usage for budget management

        Args:
            text: Text to tokenize and count

        Returns:
            Number of tokens in the text according to the provider's
            tokenization method. Different providers may use different
            tokenizers (e.g., tiktoken for OpenAI, custom for others).

        Raises:
            ValueError: If text is None

        Note:
            Token counts are approximate for some providers (CLI, Ollama)
            that don't expose tokenization APIs. API providers should
            return exact counts using their official tokenizers.
        """
        pass

    def get_total_cost(self) -> float:
        """Get total accumulated cost of all API calls.

        This method tracks cumulative cost across all provider calls,
        enabling budget tracking and cost management.

        Returns:
            Total cost in USD accumulated since provider initialization.
            Returns 0.0 if cost tracking is not supported by the provider.

        Note:
            Cost calculation is provider-specific. API providers track
            actual API costs, while CLI providers may return 0.0.
        """
        pass
