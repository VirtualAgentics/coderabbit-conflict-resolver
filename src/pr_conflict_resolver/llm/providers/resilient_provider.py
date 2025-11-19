"""Resilient LLM provider wrapper with circuit breaker, metrics, and cost control.

This module provides a comprehensive wrapper that adds resilience patterns,
metrics tracking, and cost budgeting to any LLM provider.

Features:
    - Circuit breaker for fault tolerance
    - Metrics tracking (latency, costs, errors)
    - Cost budgeting and limits
    - Automatic error handling and retries

Usage Examples:
    Create resilient provider:
        >>> from pr_conflict_resolver.llm.resilience import CircuitBreaker
        >>> from pr_conflict_resolver.llm.metrics import MetricsAggregator
        >>>
        >>> breaker = CircuitBreaker(failure_threshold=5)
        >>> metrics = MetricsAggregator()
        >>> resilient = ResilientProvider(
        ...     base_provider,
        ...     circuit_breaker=breaker,
        ...     metrics_aggregator=metrics,
        ...     cost_budget_usd=10.0
        ... )
        >>> response = resilient.generate("prompt")

    Check metrics and budget:
        >>> summary = metrics.get_summary()
        >>> print(f"Total cost: ${summary.total_cost:.2f}")
        >>> print(f"Remaining budget: ${resilient.remaining_budget:.2f}")
"""

import logging
import math
import threading

from pr_conflict_resolver.llm.exceptions import LLMAPIError
from pr_conflict_resolver.llm.metrics.metrics_aggregator import MetricsAggregator
from pr_conflict_resolver.llm.providers.base import LLMProvider
from pr_conflict_resolver.llm.resilience.circuit_breaker import (
    CircuitBreaker,
)

logger = logging.getLogger(__name__)


class CostBudgetExceededError(LLMAPIError):
    """Exception raised when cost budget is exceeded.

    Raised when a request would exceed the configured cost budget,
    preventing runaway costs.
    """


class ResilientProvider:
    """Resilient LLM provider with circuit breaker, metrics, and cost control.

    Wraps any LLM provider to add:
    - Circuit breaker pattern for fault tolerance
    - Metrics tracking for observability
    - Cost budgeting to prevent runaway costs

    Maintains the LLMProvider interface for drop-in replacement.

    Attributes:
        provider: Wrapped LLM provider
        circuit_breaker: CircuitBreaker instance (optional)
        metrics_aggregator: MetricsAggregator instance (optional)
        cost_budget_usd: Maximum allowed cost in USD (None = unlimited)
        provider_name: Provider identifier
        model_name: Model identifier

    Examples:
        Full setup with all features:
            >>> breaker = CircuitBreaker(failure_threshold=5)
            >>> metrics = MetricsAggregator()
            >>> resilient = ResilientProvider(
            ...     provider,
            ...     circuit_breaker=breaker,
            ...     metrics_aggregator=metrics,
            ...     cost_budget_usd=10.0,
            ...     provider_name="anthropic",
            ...     model_name="claude-sonnet-4-5"
            ... )

        Minimal setup (just circuit breaker):
            >>> breaker = CircuitBreaker()
            >>> resilient = ResilientProvider(provider, circuit_breaker=breaker)

        Just cost control:
            >>> resilient = ResilientProvider(provider, cost_budget_usd=5.0)
    """

    def __init__(
        self,
        provider: LLMProvider,
        circuit_breaker: CircuitBreaker | None = None,
        metrics_aggregator: MetricsAggregator | None = None,
        cost_budget_usd: float | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        cost_per_1k_input_tokens: float | None = None,
        cost_per_1k_output_tokens: float | None = None,
    ) -> None:
        """Initialize resilient provider wrapper.

        Args:
            provider: Base LLM provider to wrap
            circuit_breaker: Optional CircuitBreaker for fault tolerance
            metrics_aggregator: Optional MetricsAggregator for tracking
            cost_budget_usd: Optional cost limit in USD (None = unlimited)
            provider_name: Provider name for metrics (auto-detected if None)
            model_name: Model name for metrics (auto-detected if None)
            cost_per_1k_input_tokens: Input token cost for budget calculation
            cost_per_1k_output_tokens: Output token cost for budget calculation

        Examples:
            >>> resilient = ResilientProvider(
            ...     provider,
            ...     circuit_breaker=CircuitBreaker(),
            ...     metrics_aggregator=MetricsAggregator(),
            ...     cost_budget_usd=10.0,
            ...     cost_per_1k_input_tokens=0.003,
            ...     cost_per_1k_output_tokens=0.015
            ... )
        """
        self.provider = provider
        self.circuit_breaker = circuit_breaker
        self.metrics_aggregator = metrics_aggregator
        self.cost_budget_usd = cost_budget_usd

        # Auto-detect provider and model names
        self.provider_name = provider_name or self._detect_provider_name()
        self.model_name = model_name or self._detect_model_name()

        # Cost tracking
        self.cost_per_1k_input_tokens = cost_per_1k_input_tokens
        self.cost_per_1k_output_tokens = cost_per_1k_output_tokens
        self._total_cost = 0.0
        self._cost_lock = threading.Lock()  # Thread-safe cost tracking

        logger.info(
            f"Initialized ResilientProvider: provider={self.provider_name}, "
            f"model={self.model_name}, "
            f"circuit_breaker={'yes' if circuit_breaker else 'no'}, "
            f"metrics={'yes' if metrics_aggregator else 'no'}, "
            f"budget=${cost_budget_usd if cost_budget_usd else 'unlimited'}"
        )

    def _detect_provider_name(self) -> str:
        """Auto-detect provider name from wrapped provider.

        Returns:
            Provider name
        """
        class_name = self.provider.__class__.__name__.lower()

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
            return class_name

    def _detect_model_name(self) -> str:
        """Auto-detect model name from wrapped provider.

        Returns:
            Model name
        """
        if hasattr(self.provider, "model"):
            return str(self.provider.model)
        else:
            return "unknown"

    def _check_budget(self, estimated_cost: float) -> None:
        """Check if request would exceed budget.

        Args:
            estimated_cost: Estimated cost for request

        Raises:
            CostBudgetExceededError: If budget would be exceeded
        """
        if self.cost_budget_usd is None:
            return  # No budget limit

        with self._cost_lock:
            projected_cost = self._total_cost + estimated_cost

            if projected_cost > self.cost_budget_usd:
                raise CostBudgetExceededError(
                    f"Request would exceed cost budget: "
                    f"${projected_cost:.4f} > ${self.cost_budget_usd:.2f}. "
                    f"Current cost: ${self._total_cost:.4f}, "
                    f"estimated request cost: ${estimated_cost:.4f}",
                    details={
                        "current_cost": self._total_cost,
                        "estimated_cost": estimated_cost,
                        "budget": self.cost_budget_usd,
                        "projected_cost": projected_cost,
                    },
                )

    def _estimate_cost(self, prompt: str, max_tokens: int) -> float:
        """Estimate cost for a request (rough estimate).

        Args:
            prompt: Input prompt
            max_tokens: Maximum output tokens

        Returns:
            Estimated cost in USD (0.0 if costs are set to 0.0, or if not configured)

        Note:
            None values are treated as "not configured" and will return 0.0.
            Zero (0.0) cost values are valid and will calculate $0.00 cost.
        """
        if self.cost_per_1k_input_tokens is None or self.cost_per_1k_output_tokens is None:
            return 0.0  # Can't estimate without costs configured

        # Token estimation: Try provider's count_tokens if available,
        # else use conservative heuristic
        try:
            estimated_input_tokens = self.provider.count_tokens(prompt)
        except (AttributeError, NotImplementedError):
            # Fallback: Conservative token estimation using 1 token ≈ 3 characters
            # NOTE: This is a rough approximation that varies by language and content:
            # - English text: ~4 chars/token (this uses 3 to slightly overestimate)
            # - Code: ~2-5 chars/token depending on language and density
            # - Non-ASCII languages: ratio varies significantly
            # This heuristic may underestimate costs for some models/languages.
            # For accurate cost tracking, providers should implement count_tokens()
            # or make this ratio configurable per provider/model.
            estimated_input_tokens = math.ceil(len(prompt) / 3)

        estimated_output_tokens = max_tokens

        input_cost = (estimated_input_tokens / 1000) * self.cost_per_1k_input_tokens
        output_cost = (estimated_output_tokens / 1000) * self.cost_per_1k_output_tokens

        return input_cost + output_cost

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text with resilience patterns.

        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text

        Raises:
            CircuitBreakerError: If circuit breaker is OPEN
            CostBudgetExceededError: If request would exceed budget
            Exception: Any exception from underlying provider

        Examples:
            >>> resilient = ResilientProvider(provider, cost_budget_usd=10.0)
            >>> response = resilient.generate("Explain Python")
        """
        # Check budget before making request
        estimated_cost = self._estimate_cost(prompt, max_tokens)
        self._check_budget(estimated_cost)

        # Track with metrics if available
        if self.metrics_aggregator:
            with self.metrics_aggregator.track_request(
                self.provider_name, self.model_name
            ) as tracker:
                response = self._generate_with_breaker(prompt, max_tokens)

                # Record estimated cost (actual cost tracking would need provider-specific logic)
                if estimated_cost > 0:
                    tracker.record_cost(estimated_cost)
                    with self._cost_lock:
                        self._total_cost += estimated_cost

                return response
        else:
            # No metrics, just use circuit breaker if available
            response = self._generate_with_breaker(prompt, max_tokens)

            # Track cost even without metrics aggregator
            if estimated_cost > 0:
                with self._cost_lock:
                    self._total_cost += estimated_cost

            return response

    def _generate_with_breaker(self, prompt: str, max_tokens: int) -> str:
        """Generate with circuit breaker protection.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens

        Returns:
            Generated response
        """
        if self.circuit_breaker:
            # Protected by circuit breaker
            result: str = self.circuit_breaker.call(
                self.provider.generate, prompt, max_tokens=max_tokens
            )
            return result
        else:
            # No circuit breaker, call directly
            return self.provider.generate(prompt, max_tokens=max_tokens)

    def count_tokens(self, text: str) -> int:
        """Count tokens (pass-through to provider).

        Args:
            text: Text to count tokens for

        Returns:
            Token count

        Examples:
            >>> count = resilient.count_tokens("Hello world")
        """
        result: int = self.provider.count_tokens(text)
        return result

    @property
    def remaining_budget(self) -> float | None:
        """Get remaining cost budget.

        Returns:
            Remaining budget in USD, or None if no budget set

        Examples:
            >>> if resilient.remaining_budget and resilient.remaining_budget < 1.0:
            ...     print("Low budget warning!")
        """
        if self.cost_budget_usd is None:
            return None
        with self._cost_lock:
            return max(0.0, self.cost_budget_usd - self._total_cost)

    @property
    def total_cost(self) -> float:
        """Get total cost incurred.

        Returns:
            Total cost in USD

        Examples:
            >>> print(f"Total spent: ${resilient.total_cost:.2f}")
        """
        with self._cost_lock:
            return self._total_cost

    def reset_cost_tracking(self) -> None:
        """Reset cost tracking to zero.

        Examples:
            >>> resilient.reset_cost_tracking()  # Start fresh cost tracking
        """
        with self._cost_lock:
            self._total_cost = 0.0
        logger.info("Cost tracking reset")

    def __repr__(self) -> str:
        """String representation.

        Returns:
            Human-readable string

        Examples:
            >>> print(resilient)
            ResilientProvider(provider=claude-cli, model=claude-sonnet-4-5, budget=$10.00)
        """
        budget_str = f"${self.cost_budget_usd:.2f}" if self.cost_budget_usd else "unlimited"
        return (
            f"ResilientProvider(provider={self.provider_name}, "
            f"model={self.model_name}, budget={budget_str})"
        )
