"""Resilient LLM provider wrapper with circuit breaker protection.

This module provides a transparent wrapper for LLM providers that adds
circuit breaker protection to prevent cascading failures during provider
outages.

Phase 5 - Issue #222: Circuit Breaker Pattern Implementation
"""

import logging

from pr_conflict_resolver.llm.providers.base import LLMProvider
from pr_conflict_resolver.llm.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)

logger = logging.getLogger(__name__)


class ResilientLLMProvider:
    """Transparent resilient wrapper for any LLMProvider.

    Adds circuit breaker protection to LLM provider calls. When the wrapped
    provider experiences repeated failures, the circuit breaker trips and
    blocks subsequent requests to allow the provider time to recover.

    Implements the LLMProvider protocol for drop-in replacement of any provider.

    Examples:
        Basic usage with Anthropic provider:
        >>> from pr_conflict_resolver.llm.providers.anthropic_api import AnthropicAPIProvider
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

        Raises:
            AttributeError: If provider doesn't have required `model` attribute
                or if `model` is empty/falsy

        Examples:
            >>> provider = AnthropicAPIProvider(api_key="sk-...")
            >>> resilient = ResilientLLMProvider(provider)
            >>> resilient = ResilientLLMProvider(provider, failure_threshold=3)
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

        logger.debug(
            f"Initialized ResilientLLMProvider for {provider.__class__.__name__} "
            f"with threshold={self.circuit_breaker.failure_threshold}, "
            f"cooldown={self.circuit_breaker.cooldown_seconds}s"
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

    def generate(self, prompt: str, max_tokens: int = 2000) -> str | None:
        """Generate text completion with circuit breaker protection.

        Checks circuit state before calling the wrapped provider. If the
        circuit is open, raises CircuitBreakerOpen immediately without
        making an API call. Otherwise, delegates to the wrapped provider
        and updates circuit state based on success or failure.

        Args:
            prompt: Input prompt text for generation
            max_tokens: Maximum tokens to generate in response (default: 2000)

        Returns:
            Generated text from provider, or None if provider returns None

        Raises:
            CircuitBreakerOpen: If circuit is open and cooldown hasn't elapsed
            RuntimeError: If generation fails (from wrapped provider)
            ValueError: If prompt is empty or max_tokens is invalid
            ConnectionError: If provider is unreachable
            LLMAuthenticationError: If API credentials are invalid

        Note:
            Failures from the wrapped provider increment the failure counter.
            After failure_threshold consecutive failures, the circuit opens
            and blocks requests for cooldown_seconds.

        Examples:
            >>> resilient = ResilientLLMProvider(provider)
            >>> try:
            ...     response = resilient.generate("Parse this code")
            ... except CircuitBreakerOpen as e:
            ...     print(f"Service unavailable, retry in {e.remaining_cooldown:.1f}s")
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
