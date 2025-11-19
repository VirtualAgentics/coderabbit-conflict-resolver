"""Circuit breaker pattern for LLM provider resilience.

This module implements the circuit breaker pattern to prevent cascading failures
when LLM providers are experiencing issues. The circuit breaker monitors failures
and automatically "opens" (stops sending requests) when failure rates exceed
thresholds, allowing the provider time to recover.

Circuit States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Provider is failing, requests are rejected immediately
    - HALF_OPEN: Testing if provider has recovered

Usage Examples:
    Wrap a provider with circuit breaker:
        >>> breaker = CircuitBreaker(
        ...     failure_threshold=5,
        ...     recovery_timeout=60,
        ...     success_threshold=2
        ... )
        >>> provider = CircuitBreakerProvider(base_provider, breaker)
        >>> response = provider.generate("prompt")  # Protected by circuit breaker

    Check circuit state:
        >>> if breaker.state == CircuitState.OPEN:
        ...     print("Provider is down, using fallback")

    Manual circuit control:
        >>> breaker.reset()  # Force circuit closed
        >>> breaker.trip()   # Force circuit open
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any

from pr_conflict_resolver.llm.exceptions import LLMAPIError

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states.

    Attributes:
        CLOSED: Normal operation, requests pass through
        OPEN: Circuit is open, requests fail immediately (provider is down)
        HALF_OPEN: Testing recovery, limited requests allowed
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior.

    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery (OPEN -> HALF_OPEN)
        success_threshold: Number of consecutive successes to close circuit from HALF_OPEN
        expected_exception_types: Exception types that trigger circuit breaker
        excluded_exception_types: Exception types that don't count as failures

    Examples:
        >>> config = CircuitBreakerConfig(
        ...     failure_threshold=5,
        ...     recovery_timeout=60,
        ...     success_threshold=2
        ... )
    """

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 2
    expected_exception_types: tuple[type[Exception], ...] = (Exception,)
    excluded_exception_types: tuple[type[Exception], ...] = ()


@dataclass(frozen=True)
class CircuitBreakerStats:
    """Circuit breaker statistics and metrics.

    Attributes:
        state: Current circuit state
        failure_count: Number of consecutive failures
        success_count: Number of consecutive successes (in HALF_OPEN)
        total_requests: Total requests attempted
        total_failures: Total failures (all time)
        total_successes: Total successes (all time)
        total_rejected: Total requests rejected (circuit OPEN)
        last_failure_time: Timestamp of last failure (None if never failed)
        opened_at: Timestamp when circuit opened (None if not open)

    Examples:
        >>> stats = breaker.get_stats()
        >>> print(f"State: {stats.state.value}")
        >>> print(f"Failure rate: {stats.total_failures / stats.total_requests * 100:.1f}%")
    """

    state: CircuitState
    failure_count: int
    success_count: int
    total_requests: int
    total_failures: int
    total_successes: int
    total_rejected: int
    last_failure_time: float | None
    opened_at: float | None


class CircuitBreakerError(LLMAPIError):
    """Exception raised when circuit breaker is OPEN.

    Raised when attempting to call a provider while the circuit is open,
    indicating the provider is currently unavailable.
    """


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    Implements the circuit breaker pattern with three states: CLOSED (normal),
    OPEN (failing), and HALF_OPEN (testing recovery). Automatically opens when
    failures exceed threshold and attempts recovery after timeout.

    Thread-safe implementation suitable for concurrent usage.

    Attributes:
        config: CircuitBreakerConfig with behavior settings
        state: Current circuit state (CLOSED, OPEN, HALF_OPEN)

    Examples:
        Basic usage:
            >>> breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
            >>> try:
            ...     with breaker.protect():
            ...         result = some_risky_operation()
            ... except CircuitBreakerError:
            ...     result = fallback_operation()

        As a decorator:
            >>> @breaker.protected
            ... def call_api():
            ...     return api.request()

        Manual state management:
            >>> breaker.trip()  # Force open
            >>> breaker.reset()  # Force closed
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
        expected_exception_types: tuple[type[Exception], ...] | None = None,
        excluded_exception_types: tuple[type[Exception], ...] | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Consecutive failures before opening (default: 5)
            recovery_timeout: Seconds before attempting recovery (default: 60)
            success_threshold: Consecutive successes to close from HALF_OPEN (default: 2)
            expected_exception_types: Exceptions that trigger breaker (default: Exception)
            excluded_exception_types: Exceptions to ignore (default: none)

        Examples:
            >>> breaker = CircuitBreaker(
            ...     failure_threshold=3,
            ...     recovery_timeout=30,
            ...     success_threshold=1
            ... )
        """
        if failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {failure_threshold}")
        if recovery_timeout <= 0:
            raise ValueError(f"recovery_timeout must be > 0, got {recovery_timeout}")
        if success_threshold < 1:
            raise ValueError(f"success_threshold must be >= 1, got {success_threshold}")

        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
            expected_exception_types=expected_exception_types or (Exception,),
            excluded_exception_types=excluded_exception_types or (),
        )

        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._opened_at: float | None = None

        # Statistics
        self._total_requests = 0
        self._total_failures = 0
        self._total_successes = 0
        self._total_rejected = 0

        # Thread safety
        self._lock = threading.Lock()

        logger.debug(
            f"Initialized CircuitBreaker: failure_threshold={failure_threshold}, "
            f"recovery_timeout={recovery_timeout}s, success_threshold={success_threshold}"
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state.

        Returns:
            Current CircuitState (CLOSED, OPEN, or HALF_OPEN)

        Examples:
            >>> if breaker.state == CircuitState.OPEN:
            ...     print("Circuit is open, provider is down")
        """
        with self._lock:
            return self._state

    def call(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """Execute function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func() if successful

        Raises:
            CircuitBreakerError: If circuit is OPEN
            Exception: Any exception raised by func (and circuit may open)

        Examples:
            >>> result = breaker.call(api.request, "endpoint", timeout=30)
        """
        with self._lock:
            self._total_requests += 1

            # Check if we should attempt recovery
            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit breaker entering HALF_OPEN state for recovery test")
                else:
                    self._total_rejected += 1
                    # Defensive check: if OPEN but no opened_at, log and repair
                    if self._opened_at is None:
                        logger.error(
                            "Circuit breaker in OPEN state but _opened_at is None. "
                            "This indicates an inconsistent state. "
                            "Repairing by setting opened_at to now."
                        )
                        self._opened_at = time.monotonic()
                    elapsed = time.monotonic() - self._opened_at
                    raise CircuitBreakerError(
                        f"Circuit breaker is OPEN (provider unavailable). "
                        f"Opened {elapsed:.1f}s ago, will retry in "
                        f"{self.config.recovery_timeout - elapsed:.1f}s.",
                        details={
                            "state": "open",
                            "failure_count": self._failure_count,
                            "opened_at": self._opened_at,
                        },
                    )

        # Execute the function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            # Check if this exception should trigger the breaker
            if self._should_count_exception(e):
                self._on_failure()
            raise

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery.

        Returns:
            True if recovery should be attempted, False otherwise
        """
        if self._opened_at is None:
            return False
        elapsed = time.monotonic() - self._opened_at
        return elapsed >= self.config.recovery_timeout

    def _should_count_exception(self, exception: Exception) -> bool:
        """Check if exception should count toward circuit breaker.

        Args:
            exception: The exception that was raised

        Returns:
            True if exception should count as failure, False otherwise
        """
        # Excluded exceptions don't count
        if isinstance(exception, self.config.excluded_exception_types):
            return False

        # Only count expected exception types
        return isinstance(exception, self.config.expected_exception_types)

    def _on_success(self) -> None:
        """Handle successful operation (acquires internal lock)."""
        with self._lock:
            self._total_successes += 1
            self._failure_count = 0

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.debug(
                    f"Circuit breaker HALF_OPEN success {self._success_count}/"
                    f"{self.config.success_threshold}"
                )

                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._success_count = 0
                    self._opened_at = None
                    logger.info("Circuit breaker CLOSED (recovery successful)")

    def _on_failure(self) -> None:
        """Handle failed operation (internal)."""
        with self._lock:
            self._total_failures += 1
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery, back to OPEN
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                self._success_count = 0
                logger.warning(
                    f"Circuit breaker failed during recovery, reopening "
                    f"(failures: {self._failure_count})"
                )

            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = time.monotonic()
                    logger.error(
                        f"Circuit breaker OPEN after {self._failure_count} consecutive failures"
                    )

    def trip(self) -> None:
        """Manually trip (open) the circuit breaker.

        Examples:
            >>> breaker.trip()  # Force circuit open for maintenance
        """
        with self._lock:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            logger.info("Circuit breaker manually tripped (OPEN)")

    def reset(self) -> None:
        """Manually reset (close) the circuit breaker.

        Examples:
            >>> breaker.reset()  # Force circuit closed after fixing issues
        """
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._opened_at = None
            logger.info("Circuit breaker manually reset (CLOSED)")

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics.

        Returns:
            CircuitBreakerStats with current state and metrics

        Examples:
            >>> stats = breaker.get_stats()
            >>> print(f"State: {stats.state.value}")
            >>> print(f"Failures: {stats.total_failures}/{stats.total_requests}")
            >>> if stats.state == CircuitState.OPEN:
            ...     print(f"Open for {time.monotonic() - stats.opened_at:.1f}s")
        """
        with self._lock:
            return CircuitBreakerStats(
                state=self._state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                total_requests=self._total_requests,
                total_failures=self._total_failures,
                total_successes=self._total_successes,
                total_rejected=self._total_rejected,
                last_failure_time=self._last_failure_time,
                opened_at=self._opened_at,
            )

    def protected(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to protect a function with circuit breaker.

        Args:
            func: Function to protect

        Returns:
            Wrapped function with circuit breaker protection

        Examples:
            >>> @breaker.protected
            ... def risky_operation():
            ...     return api.call()
            >>>
            >>> result = risky_operation()  # Protected by circuit breaker
        """

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            return self.call(func, *args, **kwargs)

        return wrapper

    def __repr__(self) -> str:
        """String representation of circuit breaker.

        Returns:
            Human-readable string with state and config

        Examples:
            >>> print(breaker)
            CircuitBreaker(state=CLOSED, failures=0/5, recovery=60s)
        """
        with self._lock:
            return (
                f"CircuitBreaker(state={self._state.value}, "
                f"failures={self._failure_count}/{self.config.failure_threshold}, "
                f"recovery={self.config.recovery_timeout}s)"
            )
