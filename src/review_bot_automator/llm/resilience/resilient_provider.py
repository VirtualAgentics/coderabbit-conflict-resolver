# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Resilient LLM provider wrapper with circuit breaker protection.

This module provides a transparent wrapper for LLM providers that adds
circuit breaker protection to prevent cascading failures during provider
outages.

Phase 5 - Issue #222: Circuit Breaker Pattern Implementation
Phase 5 - Issue #119: Rate limit retry with exponential backoff
"""

import logging
import threading
import time

from review_bot_automator.llm.exceptions import LLMRateLimitError
from review_bot_automator.llm.providers.base import LLMProvider
from review_bot_automator.llm.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from review_bot_automator.security.secret_scanner import SecretScanner

logger = logging.getLogger(__name__)


class ResilientLLMProvider(LLMProvider):
    """Transparent resilient wrapper for any LLMProvider.

    Adds circuit breaker protection to LLM provider calls. When the wrapped
    provider experiences repeated failures, the circuit breaker trips and
    blocks subsequent requests to allow the provider time to recover.

    Implements the LLMProvider protocol for drop-in replacement of any provider.

    Examples:
        Basic usage with Anthropic provider:
        >>> from review_bot_automator.llm.providers.anthropic_api import AnthropicAPIProvider
        >>> base = AnthropicAPIProvider(api_key="sk-...")
        >>> resilient = ResilientLLMProvider(base)
        >>> response = resilient.generate("Parse this code")

        With custom circuit breaker settings:
        >>> resilient = ResilientLLMProvider(
        ...     base,
        ...     failure_threshold=3,
        ...     cooldown_seconds=30.0
        ... )

        Check circuit breaker state:
        >>> if resilient.circuit_state == CircuitState.OPEN:
        ...     print(f"Provider down, retry in {resilient.remaining_cooldown:.1f}s")

    Attributes:
        provider: The wrapped LLMProvider instance
        circuit_breaker: CircuitBreaker instance for failure protection
        model: Model name from wrapped provider (for compatibility)

    Note:
        When the circuit is open, generate() raises CircuitBreakerOpen
        instead of attempting the API call. This prevents wasting API
        credits and reduces load on struggling providers.
    """

    def __init__(
        self,
        provider: LLMProvider,
        circuit_breaker: CircuitBreaker | None = None,
        *,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
        retry_on_rate_limit: bool = True,
        retry_max_attempts: int = 3,
        retry_base_delay: float = 2.0,
    ) -> None:
        """Initialize resilient provider wrapper.

        Args:
            provider: LLMProvider instance to wrap. Must have `model` attribute.
            circuit_breaker: Optional CircuitBreaker instance. If None, creates
                a new circuit breaker with the specified settings.
            failure_threshold: Number of consecutive failures before opening
                circuit. Only used if circuit_breaker is None. Default: 5
            cooldown_seconds: Seconds to wait before recovery attempt.
                Only used if circuit_breaker is None. Default: 60.0
            retry_on_rate_limit: Enable automatic retry on rate limit errors.
                Default: True
            retry_max_attempts: Maximum retry attempts for rate limit errors.
                Default: 3 (delays: 2s, 4s, 8s with base_delay=2.0)
            retry_base_delay: Base delay in seconds for exponential backoff.
                Default: 2.0 (delays: 2s, 4s, 8s)

        Raises:
            AttributeError: If provider doesn't have required `model` attribute
                or if `model` is empty/falsy

        Examples:
            >>> provider = AnthropicAPIProvider(api_key="sk-...")
            >>> resilient = ResilientLLMProvider(provider)
            >>> resilient = ResilientLLMProvider(provider, failure_threshold=3)
            >>> resilient = ResilientLLMProvider(
            ...     provider, retry_max_attempts=5, retry_base_delay=1.0
            ... )
        """
        self.provider = provider

        # Validate and get model from provider - required for protocol compatibility
        if not hasattr(provider, "model"):
            raise AttributeError(
                f"Provider {provider.__class__.__name__} must have a 'model' attribute"
            )
        model = provider.model
        if not isinstance(model, str):
            raise AttributeError(
                f"Provider {provider.__class__.__name__} has invalid 'model' attribute: "
                f"expected string, got {type(model).__name__}"
            )
        if not model.strip():
            raise AttributeError(
                f"Provider {provider.__class__.__name__} has invalid 'model' attribute: "
                f"expected non-empty string, got {model!r}"
            )
        self.model: str = model

        # Use provided circuit breaker or create new one
        if circuit_breaker is not None:
            self.circuit_breaker = circuit_breaker
        else:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=failure_threshold,
                cooldown_seconds=cooldown_seconds,
            )

        # Retry configuration for rate limit errors
        self.retry_on_rate_limit = retry_on_rate_limit
        self.retry_max_attempts = retry_max_attempts
        self.retry_base_delay = retry_base_delay

        # Retry statistics tracking (thread-safe)
        self._retry_count = 0
        self._retry_total_delay = 0.0
        self._retry_lock = threading.Lock()

        logger.debug(
            f"Initialized ResilientLLMProvider for {provider.__class__.__name__} "
            f"with threshold={self.circuit_breaker.failure_threshold}, "
            f"cooldown={self.circuit_breaker.cooldown_seconds}s, "
            f"retry_on_rate_limit={retry_on_rate_limit}, "
            f"retry_max_attempts={retry_max_attempts}, "
            f"retry_base_delay={retry_base_delay}s"
        )

    @property
    def circuit_state(self) -> CircuitState:
        """Current circuit breaker state."""
        return self.circuit_breaker.state

    @property
    def remaining_cooldown(self) -> float:
        """Seconds remaining until circuit recovery attempt."""
        return self.circuit_breaker.get_remaining_cooldown()

    @property
    def failure_count(self) -> int:
        """Current consecutive failure count."""
        return self.circuit_breaker.failure_count

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text completion with circuit breaker protection and rate limit retry.

        Checks circuit state before calling the wrapped provider. If the
        circuit is open, raises CircuitBreakerOpen immediately without
        making an API call. Otherwise, delegates to the wrapped provider
        and updates circuit state based on success or failure.

        On rate limit errors (LLMRateLimitError), automatically retries with
        exponential backoff if retry_on_rate_limit is enabled.

        Args:
            prompt: Input prompt text for generation
            max_tokens: Maximum tokens to generate in response (default: 2000)

        Returns:
            Generated text from provider

        Raises:
            CircuitBreakerOpen: If circuit is open and cooldown hasn't elapsed
            LLMRateLimitError: If rate limit exceeded after all retries
            RuntimeError: If generation fails (from wrapped provider)
            ValueError: If prompt is empty or max_tokens is invalid
            ConnectionError: If provider is unreachable
            LLMAuthenticationError: If API credentials are invalid

        Note:
            Failures from the wrapped provider increment the failure counter.
            After failure_threshold consecutive failures, the circuit opens
            and blocks requests for cooldown_seconds.

            Rate limit errors are retried with exponential backoff:
            - Attempt 1: immediate
            - Attempt 2: base_delay (2s)
            - Attempt 3: base_delay * 2 (4s)
            - Attempt 4: base_delay * 4 (8s)
            - etc.

        Examples:
            >>> resilient = ResilientLLMProvider(provider)
            >>> try:
            ...     response = resilient.generate("Parse this code")
            ... except CircuitBreakerOpen as e:
            ...     print(f"Service unavailable, retry in {e.remaining_cooldown:.1f}s")
        """
        return self._generate_with_retry(prompt, max_tokens)

    def _generate_with_retry(self, prompt: str, max_tokens: int) -> str:
        """Internal generate implementation with rate limit retry logic.

        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text from provider

        Raises:
            CircuitBreakerOpen: If circuit is open
            LLMRateLimitError: After all retries exhausted
            Exception: Other provider errors
        """
        request_delay = 0.0  # Track delay for this specific request

        for attempt in range(self.retry_max_attempts):
            try:
                return self._call_provider(prompt, max_tokens)
            except CircuitBreakerOpen:
                # Re-raise circuit breaker exceptions without retry
                raise
            except LLMRateLimitError as e:
                if not self.retry_on_rate_limit:
                    # Retry disabled, raise immediately
                    raise

                if attempt < self.retry_max_attempts - 1:
                    # Calculate delay with exponential backoff: 2^attempt * base_delay
                    delay = self.retry_base_delay * (2**attempt)

                    # Check if provider returned a retry_after hint
                    retry_after = e.details.get("retry_after") if hasattr(e, "details") else None
                    if retry_after and isinstance(retry_after, (int, float)) and retry_after > 0:
                        delay = max(delay, float(retry_after))

                    # Track retry statistics (thread-safe)
                    with self._retry_lock:
                        self._retry_count += 1
                        self._retry_total_delay += delay
                    request_delay += delay

                    logger.warning(
                        f"Rate limit hit, retrying in {delay:.1f}s "
                        f"(attempt {attempt + 1}/{self.retry_max_attempts})"
                    )
                    time.sleep(delay)
                else:
                    # Final attempt failed, raise the exception
                    logger.error(
                        f"Rate limit exceeded after {self.retry_max_attempts} attempts, "
                        f"total delay: {request_delay:.1f}s"
                    )
                    raise
            except Exception as e:
                # Non-rate-limit errors: sanitize and raise immediately
                error_str = str(e)
                if SecretScanner.has_secrets(error_str):
                    logger.error(
                        "Provider error occurred (details redacted - potential secret in error)"
                    )
                    raise RuntimeError("Provider error (details redacted)") from None
                raise

        # Unreachable: the loop either returns or raises
        raise AssertionError("Unreachable: retry loop should return or raise")

    def _call_provider(self, prompt: str, max_tokens: int) -> str:
        """Call the wrapped provider through the circuit breaker.

        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text from provider
        """
        return self.circuit_breaker.call(self.provider.generate, prompt, max_tokens=max_tokens)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using wrapped provider's tokenizer.

        This method does not use the circuit breaker since tokenization
        is typically a local operation that doesn't require API calls.

        Args:
            text: Text to tokenize and count

        Returns:
            Number of tokens according to the provider's tokenizer

        Examples:
            >>> resilient = ResilientLLMProvider(provider)
            >>> tokens = resilient.count_tokens("Hello, world!")
        """
        return self.provider.count_tokens(text)

    def get_total_cost(self) -> float:
        """Get total cost from wrapped provider.

        Returns the cumulative cost of all API calls made through the
        wrapped provider.

        Returns:
            Total cost in USD

        Examples:
            >>> resilient = ResilientLLMProvider(provider)
            >>> resilient.generate("expensive prompt")
            >>> print(f"Cost: ${resilient.get_total_cost():.4f}")
        """
        val = getattr(self.provider, "get_total_cost", None)
        if callable(val):
            result = val()
            return float(result) if result is not None else 0.0
        elif isinstance(val, (int, float)):
            return float(val)
        return 0.0

    def reset_usage_tracking(self) -> None:
        """Reset usage tracking on wrapped provider.

        Resets token counts and cost tracking on the wrapped provider.
        Does not affect circuit breaker state.

        Examples:
            >>> resilient = ResilientLLMProvider(provider)
            >>> resilient.generate("prompt")
            >>> resilient.reset_usage_tracking()
            >>> assert resilient.get_total_cost() == 0.0
        """
        fn = getattr(self.provider, "reset_usage_tracking", None)
        if callable(fn):
            fn()

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker to initial closed state.

        Clears failure count and resets state to CLOSED. Useful for
        testing or manual recovery after external verification that
        the provider is available.

        Examples:
            >>> resilient.reset_circuit_breaker()
            >>> assert resilient.circuit_state == CircuitState.CLOSED
        """
        self.circuit_breaker.reset()

    def get_retry_stats(self) -> tuple[int, float]:
        """Get retry statistics for monitoring.

        Returns:
            Tuple of (retry_count, total_delay_seconds):
                - retry_count: Total number of retries performed
                - total_delay_seconds: Total time spent waiting on retries

        Examples:
            >>> resilient = ResilientLLMProvider(provider)
            >>> # After some operations...
            >>> count, delay = resilient.get_retry_stats()
            >>> print(f"Retried {count} times, total delay: {delay:.1f}s")
        """
        with self._retry_lock:
            return (self._retry_count, self._retry_total_delay)

    def reset_retry_stats(self) -> None:
        """Reset retry statistics counters.

        Useful for testing or starting fresh tracking for a new PR.

        Examples:
            >>> resilient.reset_retry_stats()
            >>> count, _ = resilient.get_retry_stats()
            >>> assert count == 0
        """
        with self._retry_lock:
            self._retry_count = 0
            self._retry_total_delay = 0.0
        logger.debug("Reset retry statistics counters")
