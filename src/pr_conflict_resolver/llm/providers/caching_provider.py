"""Caching wrapper for LLM providers.

This module provides a transparent caching layer that wraps any LLMProvider
implementation to add response caching with PromptCache. The wrapper:
- Intercepts generate() calls and checks cache first
- Falls back to the wrapped provider on cache miss
- Stores responses in cache for future reuse
- Maintains provider interface (transparent wrapping)
- Tracks cache hit/miss statistics
- Respects cache configuration (enabled/disabled, TTL, max size)

Usage:
    >>> from pr_conflict_resolver.llm.providers.openai_api import OpenAIAPIProvider
    >>> from pr_conflict_resolver.llm.cache.prompt_cache import PromptCache
    >>> base_provider = OpenAIAPIProvider(api_key="sk-...")
    >>> cache = PromptCache()
    >>> cached_provider = CachingProvider(base_provider, cache, enabled=True)
    >>> response = cached_provider.generate("prompt")  # Cache miss, calls API
    >>> response = cached_provider.generate("prompt")  # Cache hit, no API call
"""

import logging
import threading

from pr_conflict_resolver.llm.cache.prompt_cache import (
    CacheStats,
    DeleteStatus,
    PromptCache,
)
from pr_conflict_resolver.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Provider name registry: maps lowercased class names to canonical provider IDs
PROVIDER_NAME_REGISTRY = {
    "claudecliprovider": "claude-cli",
    "codexcliprovider": "codex-cli",
    "openaiapiprovider": "openai",
    "anthropicapiprovider": "anthropic",
    "ollamaprovider": "ollama",
}


class CachingProvider:
    """Caching wrapper for LLM providers.

    Wraps any LLMProvider implementation to add transparent response caching.
    Maintains the LLMProvider interface so it can be used as a drop-in replacement.

    Attributes:
        provider: The wrapped LLM provider
        cache: PromptCache instance for storing responses
        enabled: Whether caching is enabled (default: True)
        provider_name: Name identifier for the wrapped provider
        model_name: Model identifier for cache key construction

    Examples:
        Wrap an OpenAI provider:
        >>> provider = OpenAIAPIProvider(api_key="sk-...")
        >>> cache = PromptCache()
        >>> cached = CachingProvider(provider, cache)
        >>> response = cached.generate("Explain Python")  # Cached

        Disable caching:
        >>> cached = CachingProvider(provider, cache, enabled=False)
        >>> response = cached.generate("prompt")  # Always calls API

        Check cache statistics:
        >>> stats = cached.get_cache_stats()
        >>> print(f"Hit rate: {stats.hit_rate * 100}%")
    """

    def __init__(
        self,
        provider: LLMProvider,
        cache: PromptCache | None = None,
        enabled: bool = True,
        provider_name: str | None = None,
        model_name: str | None = None,
    ) -> None:
        """Initialize caching provider wrapper.

        Args:
            provider: The LLM provider to wrap (must implement LLMProvider protocol)
            cache: PromptCache instance (creates new one if None)
            enabled: Whether caching is enabled (default: True)
            provider_name: Provider identifier for cache keys (auto-detected if None)
            model_name: Model identifier for cache keys (auto-detected if None)

        Examples:
            >>> provider = ClaudeCLIProvider()
            >>> cached = CachingProvider(provider)  # Auto-detect names

            >>> cached = CachingProvider(
            ...     provider,
            ...     cache=PromptCache(max_size_mb=200),
            ...     enabled=True,
            ...     provider_name="claude-cli",
            ...     model_name="claude-sonnet-4-5"
            ... )
        """
        # Validate provider is not None
        if provider is None:
            raise TypeError("provider must be provided and cannot be None")

        # Validate provider implements LLMProvider protocol
        # Use isinstance() check if possible, otherwise fall back to duck-typing
        # (isinstance doesn't work with Mock objects, so we need both checks)
        if not isinstance(provider, LLMProvider):
            # isinstance failed - check if it's a mock/test object or genuinely missing methods
            missing_methods = []  # type: ignore[unreachable]  # Reachable with Mock objects
            if not callable(getattr(provider, "generate", None)):
                missing_methods.append("generate")
            if not callable(getattr(provider, "count_tokens", None)):
                missing_methods.append("count_tokens")

            # If methods are actually missing, raise error
            if missing_methods:
                raise TypeError(
                    f"Provider {type(provider).__name__} does not implement LLMProvider protocol. "
                    f"Missing methods: {', '.join(missing_methods)}"
                )
            # Otherwise it's a duck-typed object (like Mock) - allow it

        self.provider = provider
        self.cache = cache or PromptCache()
        self.enabled = enabled

        # Single-flight mechanism for concurrent cache misses
        self._in_flight: dict[str, threading.Event] = {}
        self._in_flight_lock = threading.Lock()

        # Auto-detect provider and model names from wrapped provider
        self.provider_name = provider_name or self._detect_provider_name()
        self.model_name = model_name or self._detect_model_name()

        logger.info(
            f"Initialized CachingProvider: provider={self.provider_name}, "
            f"model={self.model_name}, enabled={self.enabled}"
        )

    def _detect_provider_name(self) -> str:
        """Auto-detect provider name from wrapped provider.

        Returns:
            str: Provider name (e.g., "claude-cli", "openai", "anthropic")

        Note:
            Uses centralized provider registry for lookup. Falls back to class name
            if not found in registry.
        """
        class_name = self.provider.__class__.__name__.lower()

        # Look up in registry first
        if class_name in PROVIDER_NAME_REGISTRY:
            return PROVIDER_NAME_REGISTRY[class_name]

        # Fallback to pattern matching for backward compatibility
        if "claude" in class_name and "cli" in class_name:
            return "claude-cli"
        elif "codex" in class_name and "cli" in class_name:
            return "codex-cli"
        elif "openai" in class_name:
            return "openai"
        elif "anthropic" in class_name:
            return "anthropic"
        elif "ollama" in class_name:
            return "ollama"
        else:
            # Fallback: use class name
            logger.warning(
                f"Could not auto-detect provider name from {class_name}, using class name"
            )
            return class_name

    def _detect_model_name(self) -> str:
        """Auto-detect model name from wrapped provider.

        Returns:
            str: Model name (e.g., "claude-sonnet-4-5", "gpt-4o")

        Note:
            Looks for 'model' attribute on provider. Falls back to "unknown" if not found.
        """
        if hasattr(self.provider, "model"):
            return str(self.provider.model)
        else:
            logger.warning(f"Provider {self.provider.__class__.__name__} has no 'model' attribute")
            return "unknown"

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text with caching support and single-flight mechanism.

        Checks cache first. On cache hit, returns cached response immediately.
        On cache miss, uses single-flight pattern to ensure only one thread calls
        the provider for identical prompts - other threads wait and reuse the result.

        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate (passed to provider)

        Returns:
            str: Generated text (from cache or provider)

        Raises:
            Same exceptions as wrapped provider's generate() method

        Note:
            Cache keys include provider, model, and prompt to avoid collisions.
            Identical prompts to different providers/models get separate cache entries.
            Thread-safe: Multiple concurrent requests for the same prompt will only
            trigger one provider call.
        """
        # If caching disabled, pass through to provider
        if not self.enabled:
            logger.debug("Cache disabled, calling provider directly")
            return self.provider.generate(prompt, max_tokens=max_tokens)

        # Compute cache key
        cache_key = self.cache.compute_key(prompt, self.provider_name, self.model_name)

        # Check cache
        cached_response = self.cache.get(cache_key)
        if cached_response is not None:
            logger.debug(
                f"Cache HIT for {self.provider_name}/{self.model_name} "
                f"(prompt hash: {cache_key[:16]}...)"
            )
            return cached_response

        # Cache miss - use single-flight mechanism
        # Check if another thread is already fetching this key
        wait_event: threading.Event | None = None
        with self._in_flight_lock:
            if cache_key in self._in_flight:
                # Another thread is fetching, wait for it
                wait_event = self._in_flight[cache_key]
                logger.debug(f"Another thread is fetching {cache_key[:16]}..., waiting for result")
            else:
                # This thread will fetch - create event for others to wait on
                self._in_flight[cache_key] = threading.Event()

        # If another thread is fetching, wait for it to complete
        if wait_event is not None:
            wait_event.wait()
            # Re-check cache after waiting
            cached_response = self.cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache populated by other thread for {cache_key[:16]}...")
                return cached_response
            else:
                # Other thread failed or cache was evicted - check for concurrent re-registration
                logger.warning(
                    f"Other thread completed but cache miss for {cache_key[:16]}..., "
                    "will fetch from provider"
                )
                # Re-register this thread's upcoming fetch in _in_flight
                # Check if another thread already re-registered while we were outside the lock
                with self._in_flight_lock:
                    if cache_key in self._in_flight:
                        # Another thread re-registered, wait on their event instead
                        wait_event = self._in_flight[cache_key]
                        logger.debug(
                            f"Another thread re-registered {cache_key[:16]}..., waiting again"
                        )
                    else:
                        # Safe to register our fetch
                        self._in_flight[cache_key] = threading.Event()
                        wait_event = None

                # If we need to wait again, loop back
                if wait_event is not None:
                    wait_event.wait()
                    cached_response = self.cache.get(cache_key)
                    if cached_response is not None:
                        logger.debug(f"Cache populated by second thread for {cache_key[:16]}...")
                        return cached_response
                    # If still no cache, fall through to fetch (accept potential duplicate)

        # This thread is responsible for fetching
        try:
            logger.debug(f"Cache MISS for {self.provider_name}/{self.model_name}, calling provider")
            response = self.provider.generate(prompt, max_tokens=max_tokens)

            # Store in cache
            metadata = {
                "prompt": prompt,
                "provider": self.provider_name,
                "model": self.model_name,
            }
            self.cache.set(cache_key, response, metadata)

            logger.debug(f"Cached response for key {cache_key[:16]}...")
            return response

        finally:
            # Signal waiting threads and cleanup
            with self._in_flight_lock:
                event = self._in_flight.pop(cache_key, None)
                if event:
                    event.set()

    def count_tokens(self, text: str) -> int:
        """Count tokens using wrapped provider's tokenizer.

        This method is passed through to the wrapped provider without caching,
        as token counting is deterministic and fast.

        Args:
            text: Text to tokenize

        Returns:
            int: Token count from wrapped provider

        Raises:
            ValueError: If text is None (from wrapped provider)
        """
        return self.provider.count_tokens(text)

    def get_cache_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats: Cache hit/miss statistics and storage info

        Examples:
            >>> cached = CachingProvider(provider, cache)
            >>> stats = cached.get_cache_stats()
            >>> print(f"Hit rate: {stats.hit_rate * 100:.1f}%")
            >>> print(f"Total requests: {stats.total_requests}")
            >>> print(f"Cache size: {stats.cache_size_bytes / 1024 / 1024:.1f} MB")
        """
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        """Clear all cached entries.

        Note:
            This clears the ENTIRE cache, affecting all providers sharing the cache.
            Use with caution in production.

        Examples:
            >>> cached = CachingProvider(provider, cache)
            >>> cached.clear_cache()  # Delete all entries
        """
        self.cache.clear()
        logger.info("Cleared cache entries")

    def invalidate_prompt(self, prompt: str) -> DeleteStatus:
        """Invalidate cache entry for specific prompt.

        Args:
            prompt: The prompt whose cache entry should be invalidated

        Returns:
            DeleteStatus: Status of the invalidation operation:
                - DELETED: Entry was found and successfully removed
                - NOT_FOUND: Entry was not in cache (already invalidated or never cached)
                - ERROR: Entry existed but deletion failed (permission error, etc.)

        Examples:
            >>> from pr_conflict_resolver.llm.cache.prompt_cache import DeleteStatus
            >>> cached = CachingProvider(provider, cache)
            >>> cached.generate("Explain Python")  # Cached
            >>> status = cached.invalidate_prompt("Explain Python")
            >>> if status == DeleteStatus.DELETED:
            ...     print("Successfully removed from cache")
            >>> cached.generate("Explain Python")  # Cache miss, calls API again
        """
        cache_key = self.cache.compute_key(prompt, self.provider_name, self.model_name)
        status = self.cache.delete(cache_key)

        if status == DeleteStatus.DELETED:
            logger.info(f"Invalidated cache entry for key {cache_key[:16]}...")
        elif status == DeleteStatus.NOT_FOUND:
            logger.debug(f"Cache entry not found for key {cache_key[:16]}... (already invalidated)")
        else:  # DeleteStatus.ERROR
            logger.error(
                f"Failed to invalidate cache entry for key {cache_key[:16]}... (deletion error)"
            )

        return status

    def set_cache_enabled(self, enabled: bool) -> None:
        """Enable or disable caching at runtime.

        Args:
            enabled: True to enable caching, False to disable

        Examples:
            >>> cached = CachingProvider(provider, cache)
            >>> cached.set_cache_enabled(False)  # Disable caching
            >>> response = cached.generate("prompt")  # Always calls API
            >>> cached.set_cache_enabled(True)  # Re-enable caching
        """
        old_state = self.enabled
        self.enabled = enabled
        new_state = "enabled" if enabled else "disabled"
        prev_state = "enabled" if old_state else "disabled"
        logger.info(f"Cache {new_state} (was {prev_state})")

    def __repr__(self) -> str:
        """String representation of caching provider.

        Returns:
            str: Human-readable representation

        Examples:
            >>> cached = CachingProvider(provider, cache)
            >>> print(cached)
            CachingProvider(provider=claude-cli, model=claude-sonnet-4-5, enabled=True)
        """
        return (
            f"CachingProvider(provider={self.provider_name}, "
            f"model={self.model_name}, enabled={self.enabled})"
        )
