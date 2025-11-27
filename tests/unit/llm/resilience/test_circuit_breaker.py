"""Tests for CircuitBreaker class.

Phase 5 - Issue #222: Circuit Breaker Pattern Implementation
"""

import threading
import time
from unittest.mock import MagicMock

import pytest

from review_bot_automator.llm.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_state_values(self) -> None:
        """All expected states exist."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_state_count(self) -> None:
        """Exactly three states exist."""
        assert len(CircuitState) == 3


class TestCircuitBreakerOpen:
    """Tests for CircuitBreakerOpen exception."""

    def test_basic_exception(self) -> None:
        """Exception stores message correctly."""
        exc = CircuitBreakerOpen("test message")
        assert str(exc) == "test message"
        assert exc.remaining_cooldown == 0.0

    def test_with_remaining_cooldown(self) -> None:
        """Exception stores remaining cooldown."""
        exc = CircuitBreakerOpen("test", remaining_cooldown=30.5)
        assert exc.remaining_cooldown == 30.5

    def test_is_exception(self) -> None:
        """CircuitBreakerOpen is a proper exception."""
        with pytest.raises(CircuitBreakerOpen):
            raise CircuitBreakerOpen("test")


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_default_values(self) -> None:
        """Default values are applied correctly."""
        breaker = CircuitBreaker()
        assert breaker.failure_threshold == 5
        assert breaker.cooldown_seconds == 60.0
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_custom_threshold(self) -> None:
        """Custom failure threshold is applied."""
        breaker = CircuitBreaker(failure_threshold=3)
        assert breaker.failure_threshold == 3

    def test_custom_cooldown(self) -> None:
        """Custom cooldown is applied."""
        breaker = CircuitBreaker(cooldown_seconds=30.0)
        assert breaker.cooldown_seconds == 30.0

    def test_invalid_threshold_zero(self) -> None:
        """Zero threshold raises ValueError."""
        with pytest.raises(ValueError, match="failure_threshold must be >= 1"):
            CircuitBreaker(failure_threshold=0)

    def test_invalid_threshold_negative(self) -> None:
        """Negative threshold raises ValueError."""
        with pytest.raises(ValueError, match="failure_threshold must be >= 1"):
            CircuitBreaker(failure_threshold=-1)

    def test_invalid_cooldown_zero(self) -> None:
        """Zero cooldown raises ValueError."""
        with pytest.raises(ValueError, match="cooldown_seconds must be > 0"):
            CircuitBreaker(cooldown_seconds=0)

    def test_invalid_cooldown_negative(self) -> None:
        """Negative cooldown raises ValueError."""
        with pytest.raises(ValueError, match="cooldown_seconds must be > 0"):
            CircuitBreaker(cooldown_seconds=-1.0)


class TestCircuitBreakerCall:
    """Tests for CircuitBreaker.call() method."""

    def test_successful_call(self) -> None:
        """Successful call returns result."""
        breaker = CircuitBreaker()
        func = MagicMock(return_value="success")

        result = breaker.call(func, "arg1", kwarg1="value1")

        assert result == "success"
        func.assert_called_once_with("arg1", kwarg1="value1")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_failed_call_increments_counter(self) -> None:
        """Failed call increments failure counter."""
        breaker = CircuitBreaker(failure_threshold=5)
        func = MagicMock(side_effect=RuntimeError("test error"))

        with pytest.raises(RuntimeError):
            breaker.call(func)

        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self) -> None:
        """Successful call resets failure count."""
        breaker = CircuitBreaker(failure_threshold=5)
        failing_func = MagicMock(side_effect=RuntimeError("error"))
        success_func = MagicMock(return_value="success")

        # Accumulate some failures
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(failing_func)

        assert breaker.failure_count == 3

        # Success resets count
        breaker.call(success_func)
        assert breaker.failure_count == 0

    def test_circuit_opens_after_threshold(self) -> None:
        """Circuit opens after failure threshold reached."""
        breaker = CircuitBreaker(failure_threshold=3)
        func = MagicMock(side_effect=RuntimeError("error"))

        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3

    def test_open_circuit_raises_exception(self) -> None:
        """Open circuit raises CircuitBreakerOpen."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=60.0)
        func = MagicMock(side_effect=RuntimeError("error"))

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(func)

        # Circuit is now open
        assert breaker.state == CircuitState.OPEN

        # Further calls raise CircuitBreakerOpen without calling func
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            breaker.call(func)

        assert exc_info.value.remaining_cooldown > 0
        assert func.call_count == 1  # Only called once (first failure)


class TestCircuitBreakerHalfOpen:
    """Tests for HALF_OPEN state transitions."""

    def test_transition_to_half_open(self) -> None:
        """Circuit transitions to HALF_OPEN after cooldown."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.2)
        func = MagicMock(side_effect=RuntimeError("error"))

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(func)

        assert breaker.state == CircuitState.OPEN

        # Wait for cooldown (generous margin for CI environments)
        time.sleep(0.35)

        assert breaker.state == CircuitState.HALF_OPEN  # type: ignore[comparison-overlap]

    def test_half_open_success_closes_circuit(self) -> None:
        """Successful call in HALF_OPEN closes circuit."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.2)
        failing_func = MagicMock(side_effect=RuntimeError("error"))
        success_func = MagicMock(return_value="success")

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(failing_func)

        # Wait for HALF_OPEN (generous margin for CI environments)
        time.sleep(0.35)
        assert breaker.state == CircuitState.HALF_OPEN

        # Success closes circuit
        result = breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]

    def test_half_open_failure_reopens_circuit(self) -> None:
        """Failed call in HALF_OPEN reopens circuit."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.2)
        func = MagicMock(side_effect=RuntimeError("error"))

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(func)

        # Wait for HALF_OPEN (generous margin for CI environments)
        time.sleep(0.35)
        assert breaker.state == CircuitState.HALF_OPEN

        # Failure reopens circuit
        with pytest.raises(RuntimeError):
            breaker.call(func)

        assert breaker.state == CircuitState.OPEN  # type: ignore[comparison-overlap]

    def test_half_open_single_probe_only(self) -> None:
        """Only one probe call is allowed in HALF_OPEN state."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.2)
        failing_func = MagicMock(side_effect=RuntimeError("error"))

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(failing_func)

        # Wait for HALF_OPEN (generous margin for CI environments)
        time.sleep(0.35)
        assert breaker.state == CircuitState.HALF_OPEN

        # Create a slow function for the probe
        probe_started = threading.Event()
        probe_continue = threading.Event()

        def slow_probe() -> str:
            probe_started.set()
            probe_continue.wait(timeout=5.0)
            return "success"

        results: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def call_probe() -> None:
            try:
                result = breaker.call(slow_probe)
                with lock:
                    results.append(result)
            except CircuitBreakerOpen as e:
                with lock:
                    errors.append(e)

        # Start first probe (will block in slow_probe)
        t1 = threading.Thread(target=call_probe)
        t1.start()
        probe_started.wait(timeout=5.0)

        # Second call should be blocked while probe is in flight
        with pytest.raises(CircuitBreakerOpen):
            breaker.call(lambda: "blocked")

        # Let the probe complete
        probe_continue.set()
        t1.join(timeout=5.0)

        # First probe should have succeeded
        assert len(results) == 1
        assert results[0] == "success"
        assert breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]

    def test_half_open_probe_excluded_exception_clears_flag(self) -> None:
        """Excluded exception in HALF_OPEN probe clears flag and keeps HALF_OPEN."""
        breaker = CircuitBreaker(
            failure_threshold=1, cooldown_seconds=0.2, excluded_exceptions=(ValueError,)
        )
        failing_func = MagicMock(side_effect=RuntimeError("error"))

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(failing_func)

        # Wait for HALF_OPEN (generous margin for CI environments)
        time.sleep(0.35)
        assert breaker.state == CircuitState.HALF_OPEN

        # Probe raises excluded exception
        def raise_excluded() -> str:
            raise ValueError("excluded")

        probe_errors: list[Exception] = []
        lock = threading.Lock()

        def probe_with_excluded_exception() -> None:
            try:
                breaker.call(raise_excluded)
            except ValueError as e:
                with lock:
                    probe_errors.append(e)

        t = threading.Thread(target=probe_with_excluded_exception)
        t.start()
        t.join(timeout=5.0)

        # Excluded exception should have been raised
        assert len(probe_errors) == 1
        assert isinstance(probe_errors[0], ValueError)

        # Flag should be cleared (subsequent probe should be allowed)
        # State remains HALF_OPEN since excluded exceptions don't record failure
        assert breaker.state == CircuitState.HALF_OPEN

        # Verify flag is cleared by attempting another probe (should not raise CircuitBreakerOpen)
        success_result = breaker.call(lambda: "success")
        assert success_result == "success"
        assert breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]

    def test_half_open_probe_base_exception_clears_flag(self) -> None:
        """BaseException in HALF_OPEN probe clears flag via finally block."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.2)
        failing_func = MagicMock(side_effect=RuntimeError("error"))

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(failing_func)

        # Wait for HALF_OPEN (generous margin for CI environments)
        time.sleep(0.35)
        assert breaker.state == CircuitState.HALF_OPEN

        # Custom BaseException subclass for testing (avoids KeyboardInterrupt side effects)
        class TestBaseException(BaseException):
            pass

        def raise_base() -> str:
            raise TestBaseException("test")

        probe_errors: list[BaseException] = []
        lock = threading.Lock()

        def probe_with_base_exception() -> None:
            try:
                breaker.call(raise_base)
            except TestBaseException as e:
                with lock:
                    probe_errors.append(e)

        t = threading.Thread(target=probe_with_base_exception)
        t.start()
        t.join(timeout=5.0)

        # BaseException should have been raised
        assert len(probe_errors) == 1
        assert isinstance(probe_errors[0], TestBaseException)

        # Flag should be cleared via finally block
        # BaseException escapes the except Exception block, so _record_failure() is NOT called
        # The circuit remains in HALF_OPEN state (no failure recorded)
        assert breaker.state == CircuitState.HALF_OPEN

        # Verify flag is cleared by attempting another probe (should not raise CircuitBreakerOpen)
        success_result = breaker.call(lambda: "recovered")
        assert success_result == "recovered"
        assert breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]


class TestCircuitBreakerExcludedExceptions:
    """Tests for excluded exceptions."""

    def test_excluded_exception_not_counted(self) -> None:
        """Excluded exceptions don't increment failure count."""
        breaker = CircuitBreaker(failure_threshold=2, excluded_exceptions=(ValueError,))
        func = MagicMock(side_effect=ValueError("validation error"))

        with pytest.raises(ValueError):
            breaker.call(func)

        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_non_excluded_exception_counted(self) -> None:
        """Non-excluded exceptions increment failure count."""
        breaker = CircuitBreaker(failure_threshold=2, excluded_exceptions=(ValueError,))
        func = MagicMock(side_effect=RuntimeError("runtime error"))

        with pytest.raises(RuntimeError):
            breaker.call(func)

        assert breaker.failure_count == 1

    def test_multiple_excluded_exceptions(self) -> None:
        """Multiple excluded exception types work correctly."""
        breaker = CircuitBreaker(failure_threshold=2, excluded_exceptions=(ValueError, TypeError))

        for error in [ValueError("a"), TypeError("b")]:
            func = MagicMock(side_effect=error)
            with pytest.raises(type(error)):
                breaker.call(func)

        assert breaker.failure_count == 0


class TestCircuitBreakerReset:
    """Tests for reset() method."""

    def test_reset_clears_state(self) -> None:
        """Reset clears failure count and state."""
        breaker = CircuitBreaker(failure_threshold=1)
        func = MagicMock(side_effect=RuntimeError("error"))

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 1

        # Reset - mypy narrows state to Literal[OPEN] after the assert above,
        # so it thinks CLOSED comparison is impossible and subsequent code unreachable.
        # The state does change via reset(), this is a mypy type-narrowing limitation.
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]
        assert breaker.failure_count == 0  # type: ignore[unreachable]

    def test_reset_allows_new_calls(self) -> None:
        """Reset allows new calls immediately."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=60.0)
        failing_func = MagicMock(side_effect=RuntimeError("error"))
        success_func = MagicMock(return_value="success")

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(failing_func)

        # Reset and call
        breaker.reset()
        result = breaker.call(success_func)
        assert result == "success"


class TestCircuitBreakerRemainingCooldown:
    """Tests for get_remaining_cooldown() method."""

    def test_closed_circuit_no_cooldown(self) -> None:
        """Closed circuit returns zero cooldown."""
        breaker = CircuitBreaker()
        assert breaker.get_remaining_cooldown() == 0.0

    def test_open_circuit_returns_remaining(self) -> None:
        """Open circuit returns remaining cooldown."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=60.0)
        func = MagicMock(side_effect=RuntimeError("error"))

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(func)

        remaining = breaker.get_remaining_cooldown()
        # Use wide bounds to avoid flakiness on slow CI environments
        assert 55.0 <= remaining <= 60.0

    def test_cooldown_decreases_over_time(self) -> None:
        """Remaining cooldown decreases over time."""
        breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=1.0)
        func = MagicMock(side_effect=RuntimeError("error"))

        # Trip the circuit
        with pytest.raises(RuntimeError):
            breaker.call(func)

        initial = breaker.get_remaining_cooldown()
        time.sleep(0.2)
        later = breaker.get_remaining_cooldown()

        assert later < initial


class TestCircuitBreakerThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_calls(self) -> None:
        """Concurrent calls don't corrupt state."""
        breaker = CircuitBreaker(failure_threshold=10, cooldown_seconds=60.0)
        call_count = 0
        lock = threading.Lock()

        def increment() -> int:
            nonlocal call_count
            with lock:
                call_count += 1
            return call_count

        threads = []
        results: list[int] = []
        results_lock = threading.Lock()

        def worker() -> None:
            for _ in range(100):
                result = breaker.call(increment)
                with results_lock:
                    results.append(result)

        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert call_count == 1000
        assert len(results) == 1000
        assert breaker.failure_count == 0

    def test_concurrent_failures(self) -> None:
        """Concurrent failures don't corrupt failure count."""
        breaker = CircuitBreaker(failure_threshold=100, cooldown_seconds=60.0)
        errors: list[Exception] = []
        lock = threading.Lock()

        def failing_func() -> str:
            raise RuntimeError("error")

        def worker() -> None:
            for _ in range(10):
                try:
                    breaker.call(failing_func)
                except RuntimeError as e:
                    with lock:
                        errors.append(e)
                except CircuitBreakerOpen:
                    pass

        threads = []
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Verify failures were actually recorded
        assert len(errors) > 0, "Expected some RuntimeError exceptions to be captured"
        assert 1 <= breaker.failure_count <= 100
