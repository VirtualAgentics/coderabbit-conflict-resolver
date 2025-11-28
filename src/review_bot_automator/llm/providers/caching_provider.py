# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Caching wrapper for LLM providers.

This module provides a transparent caching layer that wraps any LLMProvider
implementation to reduce API costs through response caching. The cache uses
SHA256-based keys and file-based storage with TTL expiration and LRU eviction.

Phase 5 - Issue #221: Cache Integration with LLM Providers
"""

import logging
from pathlib import Path

from review_bot_automator.llm.cache.prompt_cache import CacheStats, PromptCache
from review_bot_automator.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class CachingProvider:
    """Transparent caching wrapper for any LLMProvider.

    Intercepts generate() calls to check cache before making API requests.
    Cache hits return immediately without consuming API credits.
    Cache misses delegate to the wrapped provider and store the response.

    Implements the LLMProvider protocol for drop-in replacement of any provider.

    Examples:
        Basic usage with Anthropic provider:
        >>> from review_bot_automator.llm.providers.anthropic_api import AnthropicAPIProvider
        >>> base = AnthropicAPIProvider(api_key="sk-...")
        >>> cached = CachingProvider(base)
        >>> response = cached.generate("Parse this comment...")  # API call
        >>> response = cached.generate("Parse this comment...")  # Cache hit!

        Check cache statistics:
        >>> stats = cached.get_cache_stats()
        >>> print(f"Hit rate: {stats.hit_rate * 100:.1f}%")

    Attributes:
        provider: The wrapped LLMProvider instance
        cache: PromptCache instance for response storage
        provider_name: Name used in cache keys (e.g., "anthropic")
        model: Model name used in cache keys (e.g., "claude-sonnet-4-5")

    Note:
        The caching wrapper preserves all provider functionality including
        token counting and cost tracking. Cost tracking only reflects actual
        API calls (cache hits don't increment costs).
    """

    def __init__(
        self,
        provider: LLMProvider,
        cache: PromptCache | None = None,
        *,
        cache_dir: Path | None = None,
    ) -> None:
        """Initialize caching provider wrapper.

        Args:
            provider: LLMProvider instance to wrap. Must have `model` attribute.
            cache: Optional PromptCache instance. If None, creates a new cache
                with default settings (7-day TTL, 100MB max size).
            cache_dir: Optional cache directory override. Only used if cache
                is None. Defaults to ~/.cache/review-bot-automator/llm/

        Raises:
            AttributeError: If provider doesn't have required `model` attribute
                or if `model` is empty/falsy

        Examples:
            >>> provider = AnthropicAPIProvider(api_key="sk-...")
            >>> cached = CachingProvider(provider)  # Default cache
            >>> cached = CachingProvider(provider, cache_dir=Path("/tmp/cache"))
        """
        self.provider = provider
        self.cache = cache if cache is not None else PromptCache(cache_dir=cache_dir)

        # Extract provider name from class name (e.g., "AnthropicAPIProvider" -> "anthropic")
        # Iteratively remove known suffixes until none match for order-independent extraction
        class_name = provider.__class__.__name__.lower()
        suffixes = ("provider", "api")
        while True:
            for suffix in suffixes:
                if class_name.endswith(suffix):
                    class_name = class_name.removesuffix(suffix)
                    break
            else:
                # No suffix matched, we're done
                break
        self.provider_name = class_name

        # Validate and get model from provider - required for cache key integrity
        if not hasattr(provider, "model"):
            raise AttributeError(
                f"Provider {provider.__class__.__name__} must have a 'model' attribute"
            )
        model = provider.model
        if not model or not isinstance(model, str) or not model.strip():
            raise AttributeError(
                f"Provider {provider.__class__.__name__} has invalid 'model' attribute: "
                f"expected non-empty string, got {model!r}"
            )
        self.model: str = model

        logger.debug(f"Initialized CachingProvider for {self.provider_name}/{self.model}")

    def generate(self, prompt: str, max_tokens: int = 2000) -> str | None:
        """Generate text completion with caching.

        Checks cache first using a key derived from the prompt, provider name,
        and model. On cache hit, returns the cached response immediately without
        making an API call. On cache miss, delegates to the wrapped provider
        and stores the response for future requests.

        Args:
            prompt: Input prompt text for generation
            max_tokens: Maximum tokens to generate in response (default: 2000)

        Returns:
            Generated text from cache or provider, or None if the provider
            returns None. Format depends on prompt design (e.g., JSON for
            structured output).

        Raises:
            RuntimeError: If generation fails after retries (from wrapped provider)
            ValueError: If prompt is empty or max_tokens is invalid
            ConnectionError: If provider is unreachable
            LLMAuthenticationError: If API credentials are invalid

        Note:
            Cache hits do not increment the provider's token usage or cost
            tracking. Only actual API calls affect those metrics.

            Empty or None responses from the wrapped provider are not cached.
            This treats empty responses as transient failures that may succeed
            on retry. Prompts that consistently return empty responses will
            trigger repeated provider calls.

        Examples:
            >>> cached = CachingProvider(provider)
            >>> response1 = cached.generate("Parse this code")  # API call
            >>> response2 = cached.generate("Parse this code")  # Cache hit
            >>> assert response1 == response2
        """
        # Compute cache key from prompt + provider + model
        cache_key = self.cache.compute_key(prompt, self.provider_name, self.model)

        # Try cache first
        cached_response = self.cache.get(cache_key)
        if cached_response is not None:
            logger.debug(f"Cache hit for {self.provider_name}/{self.model}")
            return cached_response

        # Cache miss - call the wrapped provider
        logger.debug(f"Cache miss for {self.provider_name}/{self.model}, calling provider")
        response = self.provider.generate(prompt, max_tokens)

        # Store in cache for future requests (skip empty responses)
        if response:
            self.cache.set(
                cache_key,
                response,
                {
                    "prompt": prompt,
                    "provider": self.provider_name,
                    "model": self.model,
                },
            )

        return response

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using wrapped provider's tokenizer.

        Delegates to the wrapped provider's count_tokens method for accurate
        tokenization based on the specific model being used.

        Args:
            text: Text to tokenize and count

        Returns:
            Number of tokens according to the provider's tokenizer

        Examples:
            >>> cached = CachingProvider(provider)
            >>> tokens = cached.count_tokens("Hello, world!")
        """
        return self.provider.count_tokens(text)

    def get_total_cost(self) -> float:
        """Get total cost from wrapped provider.

        Returns the cumulative cost of all API calls made through the wrapped
        provider. Cache hits do not contribute to cost.

        Returns:
            Total cost in USD

        Examples:
            >>> cached = CachingProvider(provider)
            >>> cached.generate("expensive prompt")
            >>> print(f"Cost: ${cached.get_total_cost():.4f}")
        """
        val = getattr(self.provider, "get_total_cost", None)
        if callable(val):
            return float(val())
        elif isinstance(val, (int, float)):
            return float(val)
        return 0.0

    def reset_usage_tracking(self) -> None:
        """Reset usage tracking on wrapped provider.

        Resets token counts and cost tracking on the wrapped provider.
        Does not affect cache statistics.

        Examples:
            >>> cached = CachingProvider(provider)
            >>> cached.generate("prompt")
            >>> cached.reset_usage_tracking()
            >>> assert cached.get_total_cost() == 0.0
        """
        fn = getattr(self.provider, "reset_usage_tracking", None)
        if callable(fn):
            fn()

    def get_cache_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns statistics about cache usage including hit rate, total size,
        and entry count.

        Returns:
            CacheStats with hits, misses, hit_rate, cache_size_bytes, entry_count

        Examples:
            >>> cached = CachingProvider(provider)
            >>> stats = cached.get_cache_stats()
            >>> print(f"Hit rate: {stats.hit_rate * 100:.1f}%")
            >>> print(f"Entries: {stats.entry_count}")
        """
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        """Clear all cached responses.

        Removes all entries from the cache and resets statistics.
        Use with caution as this will cause all future requests to
        result in cache misses until repopulated.

        Examples:
            >>> cached = CachingProvider(provider)
            >>> cached.clear_cache()
            >>> assert cached.get_cache_stats().entry_count == 0
        """
        self.cache.clear()
        logger.info(f"Cleared cache for {self.provider_name}/{self.model}")

    def evict_expired(self) -> int:
        """Evict expired cache entries.

        Removes all cache entries that have exceeded their TTL.
        Can be called periodically to clean up stale entries.

        Returns:
            Number of entries evicted

        Examples:
            >>> cached = CachingProvider(provider)
            >>> evicted = cached.evict_expired()
            >>> print(f"Evicted {evicted} expired entries")
        """
        return self.cache.evict_expired()

    def warm_up(self, entries: list[dict[str, str]] | None = None) -> tuple[int, int]:
        """Pre-populate cache with entries for cold start optimization.

        This method allows restoring cache state from a previous session or
        pre-populating with known entries to avoid cold start latency.

        Args:
            entries: Optional list of cache entries to load. Each entry must have:
                - prompt: Original prompt text
                - provider: LLM provider name (e.g., "anthropic", "openai")
                - model: Model name (e.g., "claude-sonnet-4-5", "gpt-4o")
                - response: The cached LLM response

                If None, no entries are loaded but the method logs available
                common patterns.

        Returns:
            Tuple of (loaded_count, skipped_count):
                - loaded_count: Number of entries successfully loaded
                - skipped_count: Number of entries skipped (invalid or duplicates)

        Examples:
            Load entries from a backup file:
            >>> import json
            >>> with open("cache_backup.json") as f:
            ...     entries = json.load(f)
            >>> cached = CachingProvider(provider)
            >>> loaded, skipped = cached.warm_up(entries)

            Get common patterns without loading:
            >>> cached.warm_up()  # Logs available patterns

        Note:
            - Entries for different providers/models can be loaded but will only
              be useful if they match the current provider configuration
            - Thread-safe operation
        """
        if entries is None:
            # Log available patterns for documentation purposes
            patterns = self.cache.get_common_patterns()
            logger.info(f"Cache warm-up called without entries. Common patterns: {len(patterns)}")
            for pattern in patterns:
                logger.debug(f"  Pattern: {pattern}")
            return (0, 0)

        loaded, skipped = self.cache.warm_cache(entries)
        logger.info(
            f"Cache warm-up for {self.provider_name}/{self.model}: "
            f"loaded={loaded}, skipped={skipped}"
        )
        return (loaded, skipped)

    def export_cache(self) -> list[dict[str, str | int | float]]:
        """Export cache entries for backup or transfer.

        Exports all current cache entries for analytics and backup purposes.
        Note that exported entries contain prompt_hash (not original prompts)
        and cannot be directly re-imported via warm_up().

        Returns:
            List of cache entry dictionaries (includes timestamp as int/float)

        Examples:
            >>> cached = CachingProvider(provider)
            >>> entries = cached.export_cache()
            >>> import json
            >>> with open("cache_backup.json", "w") as f:
            ...     json.dump(entries, f)

        Note:
            Original prompts are not exported (only hashes) for privacy.
        """
        return self.cache.export_entries()
