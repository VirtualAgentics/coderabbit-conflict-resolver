# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Circuit breaker pattern for LLM provider resilience.

This module implements the circuit breaker pattern to protect against cascading
failures when LLM providers experience issues. The circuit breaker monitors
failures and temporarily blocks requests when a failure threshold is exceeded.

Phase 5 - Issue #222: Circuit Breaker Pattern Implementation
"""

import logging
import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """States for the circuit breaker.

    The circuit breaker follows a state machine pattern:
    - CLOSED: Normal operation, requests flow through
    - OPEN: Circuit tripped, requests blocked immediately
    - HALF_OPEN: Testing recovery, limited requests allowed

    State transitions:
        CLOSED -> OPEN: When failure_threshold consecutive failures occur
        OPEN -> HALF_OPEN: After cooldown_seconds elapsed
        HALF_OPEN -> CLOSED: On successful request
        HALF_OPEN -> OPEN: On failed request
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open.

    This exception indicates that the circuit breaker has tripped due to
    repeated failures and is blocking requests to allow the provider time
    to recover.

    Attributes:
        message: Description of why the circuit is open
        remaining_cooldown: Seconds until circuit attempts recovery

    Examples:
        >>> try:
        ...     result = breaker.call(provider.generate, prompt)
        ... except CircuitBreakerOpen as e:
        ...     print(f"Provider unavailable, retry in {e.remaining_cooldown:.1f}s")
    """

    def __init__(self, message: str, remaining_cooldown: float = 0.0) -> None:
        """Initialize CircuitBreakerOpen exception.

        Args:
            message: Description of the circuit breaker state
            remaining_cooldown: Seconds remaining until recovery attempt
        """
        super().__init__(message)
        self.message: str = message
        self.remaining_cooldown: float = remaining_cooldown


class CircuitBreaker:
    """Circuit breaker for protecting LLM provider calls.

    Implements the circuit breaker pattern to detect failures and prevent
    cascading failures by temporarily blocking requests when a provider
    is experiencing issues.

    The circuit breaker tracks consecutive failures and transitions between
    three states:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Requests blocked, waiting for cooldown period
    - HALF_OPEN: Testing recovery with a single request

    Thread-safe for concurrent usage across multiple threads.

    Examples:
        Basic usage:
        >>> breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=30.0)
        >>> try:
        ...     result = breaker.call(provider.generate, "Parse this code")
        ... except CircuitBreakerOpen:
        ...     print("Provider is temporarily unavailable")

        With custom exception types:
        >>> breaker = CircuitBreaker(
        ...     failure_threshold=5,
        ...     cooldown_seconds=60.0,
        ...     excluded_exceptions=(ValueError,)  # Don't trip on ValueError
        ... )

    Attributes:
        failure_threshold: Number of consecutive failures to trip circuit
        cooldown_seconds: Seconds to wait before attempting recovery
        state: Current circuit state
        failure_count: Current consecutive failure count
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
        excluded_exceptions: tuple[type[Exception], ...] = (),
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of consecutive failures before opening
                circuit. Must be at least 1. Default: 5
            cooldown_seconds: Seconds to wait in OPEN state before attempting
                recovery. Must be positive. Default: 60.0
            excluded_exceptions: Exception types that should not count as
                failures (e.g., validation errors). Default: ()

        Raises:
            ValueError: If failure_threshold < 1 or cooldown_seconds <= 0
        """
        if failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {failure_threshold}")
        if cooldown_seconds <= 0:
            raise ValueError(f"cooldown_seconds must be > 0, got {cooldown_seconds}")

        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._excluded_exceptions = excluded_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._lock = threading.Lock()
        self._half_open_in_flight: bool = False

        logger.debug(
            f"CircuitBreaker initialized: threshold={failure_threshold}, "
            f"cooldown={cooldown_seconds}s"
        )

    @property
    def failure_threshold(self) -> int:
        """Number of consecutive failures before circuit opens."""
        return self._failure_threshold

    @property
    def cooldown_seconds(self) -> float:
        """Seconds to wait before recovery attempt."""
        return self._cooldown_seconds

    @property
    def state(self) -> CircuitState:
        """Current circuit breaker state."""
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def failure_count(self) -> int:
        """Current consecutive failure count."""
        with self._lock:
            return self._failure_count

    def _check_state_transition(self) -> None:
        """Check and perform state transition if needed.

        Called internally to transition from OPEN to HALF_OPEN
        when cooldown period has elapsed. Must be called with lock held.
        """
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._cooldown_seconds:
                logger.info("Circuit breaker transitioning to HALF_OPEN for recovery")
                self._state = CircuitState.HALF_OPEN

    def _record_success(self) -> None:
        """Record a successful call. Must be called with lock held."""
        self._failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker recovered, transitioning to CLOSED")
            self._state = CircuitState.CLOSED

    def _record_failure(self) -> None:
        """Record a failed call. Must be called with lock held."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning("Recovery attempt failed, circuit breaker reopening")
            self._state = CircuitState.OPEN
        elif self._failure_count >= self._failure_threshold:
            logger.warning(
                f"Circuit breaker opening after {self._failure_count} consecutive failures"
            )
            self._state = CircuitState.OPEN

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:  # noqa: ANN401
        """Execute a function through the circuit breaker.

        Checks circuit state before calling the function. If the circuit is
        open, raises CircuitBreakerOpen immediately without calling the function.
        If half-open or closed, executes the function and updates state based
        on success or failure.

        Args:
            func: Function to execute
            *args: Positional arguments to pass to func
            **kwargs: Keyword arguments to pass to func

        Returns:
            The return value of func

        Raises:
            CircuitBreakerOpen: If circuit is open and cooldown hasn't elapsed
            Exception: Any exception raised by func (after recording failure)

        Examples:
            >>> breaker = CircuitBreaker()
            >>> result = breaker.call(provider.generate, "prompt", max_tokens=1000)
        """
        with self._lock:
            self._check_state_transition()

            # Block if OPEN, or if HALF_OPEN with a probe already in flight
            if self._state == CircuitState.OPEN or (
                self._state == CircuitState.HALF_OPEN and self._half_open_in_flight
            ):
                remaining = 0.0
                if self._last_failure_time is not None:
                    elapsed = time.monotonic() - self._last_failure_time
                    remaining = max(0.0, self._cooldown_seconds - elapsed)
                raise CircuitBreakerOpen(
                    f"Circuit breaker is open, retry in {remaining:.1f}s",
                    remaining_cooldown=remaining,
                )

            # Track if this is the single probe call in HALF_OPEN state
            is_half_open_probe = self._state == CircuitState.HALF_OPEN
            if is_half_open_probe:
                self._half_open_in_flight = True

        # Execute outside lock to allow concurrent calls in CLOSED state
        # Use try/finally to ensure _half_open_in_flight is always cleared,
        # even if a BaseException (e.g., KeyboardInterrupt) escapes
        try:
            result = func(*args, **kwargs)
            with self._lock:
                self._record_success()
            return result
        except Exception as e:
            # Check if exception should be excluded from failure tracking
            if isinstance(e, self._excluded_exceptions):
                raise
            with self._lock:
                self._record_failure()
            raise
        finally:
            if is_half_open_probe:
                with self._lock:
                    self._half_open_in_flight = False

    def reset(self) -> None:
        """Reset circuit breaker to initial closed state.

        Clears failure count and resets state to CLOSED. Useful for
        testing or manual recovery.

        Examples:
            >>> breaker.reset()
            >>> assert breaker.state == CircuitState.CLOSED
        """
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_in_flight = False
            logger.info("Circuit breaker reset to CLOSED")

    def get_remaining_cooldown(self) -> float:
        """Get remaining cooldown time in seconds.

        Returns:
            Seconds remaining until circuit attempts recovery, or 0.0 if
            circuit is not in OPEN state.

        Examples:
            >>> if breaker.state == CircuitState.OPEN:
            ...     print(f"Retry in {breaker.get_remaining_cooldown():.1f}s")
        """
        with self._lock:
            if self._state != CircuitState.OPEN or self._last_failure_time is None:
                return 0.0
            elapsed = time.monotonic() - self._last_failure_time
            return max(0.0, self._cooldown_seconds - elapsed)
