"""Tests for circuit breaker pattern implementation.

This module tests the circuit breaker for fault tolerance and cascading failure
prevention.
"""

import time
from unittest.mock import MagicMock

import pytest

from pr_conflict_resolver.llm.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
)


class TestCircuitBreakerInitialization:
    """Test CircuitBreaker initialization and configuration."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""
        breaker = CircuitBreaker()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.config.failure_threshold == 5
        assert breaker.config.recovery_timeout == 60.0
        assert breaker.config.success_threshold == 2

    def test_init_with_custom_values(self) -> None:
        """Test initialization with custom configuration."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=1,
        )

        assert breaker.config.failure_threshold == 3
        assert breaker.config.recovery_timeout == 30.0
        assert breaker.config.success_threshold == 1

    def test_init_validation_failure_threshold(self) -> None:
        """Test validation of failure_threshold."""
        with pytest.raises(ValueError, match="failure_threshold must be >= 1"):
            CircuitBreaker(failure_threshold=0)

    def test_init_validation_recovery_timeout(self) -> None:
        """Test validation of recovery_timeout."""
        with pytest.raises(ValueError, match="recovery_timeout must be > 0"):
            CircuitBreaker(recovery_timeout=0)

    def test_init_validation_success_threshold(self) -> None:
        """Test validation of success_threshold."""
        with pytest.raises(ValueError, match="success_threshold must be >= 1"):
            CircuitBreaker(success_threshold=0)


class TestCircuitBreakerClosedState:
    """Test circuit breaker behavior in CLOSED state."""

    def test_call_success_in_closed_state(self) -> None:
        """Test successful call in CLOSED state."""
        breaker = CircuitBreaker()
        mock_func = MagicMock(return_value="success")

        result = breaker.call(mock_func, "arg1", kwarg1="value1")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
        assert breaker.state == CircuitState.CLOSED

    def test_single_failure_stays_closed(self) -> None:
        """Test that single failure doesn't open circuit."""
        breaker = CircuitBreaker(failure_threshold=3)
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        with pytest.raises(RuntimeError):
            breaker.call(mock_func)

        assert breaker.state == CircuitState.CLOSED
        stats = breaker.get_stats()
        assert stats.failure_count == 1

    def test_multiple_failures_open_circuit(self) -> None:
        """Test that exceeding failure threshold opens circuit."""
        breaker = CircuitBreaker(failure_threshold=3)
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        # Trigger 3 failures
        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN
        stats = breaker.get_stats()
        assert stats.failure_count == 3

    def test_success_resets_failure_count(self) -> None:
        """Test that success resets failure count."""
        breaker = CircuitBreaker(failure_threshold=3)
        mock_func = MagicMock()

        # 2 failures
        mock_func.side_effect = RuntimeError("Error")
        for _ in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(mock_func)

        # 1 success
        mock_func.side_effect = None
        mock_func.return_value = "success"
        breaker.call(mock_func)

        stats = breaker.get_stats()
        assert stats.failure_count == 0
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerOpenState:
    """Test circuit breaker behavior in OPEN state."""

    def test_open_state_rejects_requests(self) -> None:
        """Test that OPEN state rejects requests immediately."""
        breaker = CircuitBreaker(failure_threshold=2)
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN

        # Next call should be rejected without calling func
        with pytest.raises(CircuitBreakerError):
            breaker.call(mock_func)

        # Function should not have been called the 3rd time
        assert mock_func.call_count == 2

    def test_open_state_tracks_rejected_requests(self) -> None:
        """Test that rejected requests are tracked."""
        breaker = CircuitBreaker(failure_threshold=1)
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        # Open circuit
        with pytest.raises(RuntimeError):
            breaker.call(mock_func)

        # Reject multiple requests
        for _ in range(3):
            with pytest.raises(CircuitBreakerError):
                breaker.call(mock_func)

        stats = breaker.get_stats()
        assert stats.total_rejected == 3

    def test_open_state_transitions_to_half_open(self) -> None:
        """Test transition from OPEN to HALF_OPEN after timeout."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        # Open circuit
        with pytest.raises(RuntimeError):
            breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Next call should transition to HALF_OPEN
        mock_func.side_effect = None
        mock_func.return_value = "success"
        result = breaker.call(mock_func)

        assert result == "success"
        # After one success with success_threshold=2, should still be HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN  # type: ignore[comparison-overlap]


class TestCircuitBreakerHalfOpenState:
    """Test circuit breaker behavior in HALF_OPEN state."""

    def test_half_open_success_closes_circuit(self) -> None:
        """Test that sufficient successes close circuit from HALF_OPEN."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=2,
        )
        mock_func = MagicMock()

        # Open circuit
        mock_func.side_effect = RuntimeError("Error")
        with pytest.raises(RuntimeError):
            breaker.call(mock_func)

        # Wait for recovery timeout
        time.sleep(0.15)

        # Successful recovery with 2 successes
        mock_func.side_effect = None
        mock_func.return_value = "success"

        breaker.call(mock_func)  # 1st success -> HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN

        breaker.call(mock_func)  # 2nd success -> CLOSED
        assert breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]

    def test_half_open_failure_reopens_circuit(self) -> None:
        """Test that failure in HALF_OPEN reopens circuit."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=2,
        )
        mock_func = MagicMock()

        # Open circuit
        mock_func.side_effect = RuntimeError("Error")
        with pytest.raises(RuntimeError):
            breaker.call(mock_func)

        # Wait for recovery timeout
        time.sleep(0.15)

        # Failed recovery attempt
        with pytest.raises(RuntimeError):
            breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN

    def test_half_open_success_count_reset(self) -> None:
        """Test that success count resets properly in HALF_OPEN."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=3,
        )
        mock_func = MagicMock()

        # Open circuit
        mock_func.side_effect = RuntimeError("Error")
        with pytest.raises(RuntimeError):
            breaker.call(mock_func)

        # Wait for recovery timeout
        time.sleep(0.15)

        # Two successes
        mock_func.side_effect = None
        mock_func.return_value = "success"
        breaker.call(mock_func)
        breaker.call(mock_func)

        stats = breaker.get_stats()
        assert stats.success_count == 2
        assert breaker.state == CircuitState.HALF_OPEN

        # Third success should close circuit
        breaker.call(mock_func)
        assert breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]
        stats = breaker.get_stats()  # type: ignore[unreachable]
        assert stats.success_count == 0  # Reset after closing  # type: ignore[unreachable]


class TestCircuitBreakerManualControl:
    """Test manual circuit control methods."""

    def test_manual_trip(self) -> None:
        """Test manually tripping (opening) circuit."""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitState.CLOSED

        breaker.trip()
        assert breaker.state == CircuitState.OPEN  # type: ignore[comparison-overlap]

    def test_manual_reset(self) -> None:
        """Test manually resetting (closing) circuit."""
        breaker = CircuitBreaker(failure_threshold=1)
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        # Open circuit
        with pytest.raises(RuntimeError):
            breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN

        # Reset
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED  # type: ignore[comparison-overlap]
        stats = breaker.get_stats()  # type: ignore[unreachable]
        assert stats.failure_count == 0


class TestCircuitBreakerStatistics:
    """Test circuit breaker statistics tracking."""

    def test_stats_tracks_total_requests(self) -> None:
        """Test that total requests are tracked."""
        breaker = CircuitBreaker()
        mock_func = MagicMock(return_value="success")

        for _ in range(5):
            breaker.call(mock_func)

        stats = breaker.get_stats()
        assert stats.total_requests == 5
        assert stats.total_successes == 5

    def test_stats_tracks_failures(self) -> None:
        """Test that failures are tracked."""
        breaker = CircuitBreaker(failure_threshold=10)
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        for _ in range(3):
            with pytest.raises(RuntimeError):
                breaker.call(mock_func)

        stats = breaker.get_stats()
        assert stats.total_failures == 3
        assert stats.failure_count == 3

    def test_stats_tracks_last_failure_time(self) -> None:
        """Test that last failure time is tracked."""
        breaker = CircuitBreaker()
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        before_time = time.monotonic()
        with pytest.raises(RuntimeError):
            breaker.call(mock_func)
        after_time = time.monotonic()

        stats = breaker.get_stats()
        assert stats.last_failure_time is not None
        assert before_time <= stats.last_failure_time <= after_time

    def test_stats_tracks_opened_at(self) -> None:
        """Test that opened_at timestamp is tracked."""
        breaker = CircuitBreaker(failure_threshold=1)
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        before_time = time.monotonic()
        with pytest.raises(RuntimeError):
            breaker.call(mock_func)
        after_time = time.monotonic()

        stats = breaker.get_stats()
        assert stats.state == CircuitState.OPEN
        assert stats.opened_at is not None
        assert before_time <= stats.opened_at <= after_time


class TestCircuitBreakerExceptionHandling:
    """Test exception handling and filtering."""

    def test_expected_exceptions_trigger_breaker(self) -> None:
        """Test that expected exceptions trigger circuit breaker."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            expected_exception_types=(RuntimeError, ValueError),
        )
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        for _ in range(2):
            with pytest.raises(RuntimeError):
                breaker.call(mock_func)

        assert breaker.state == CircuitState.OPEN

    def test_excluded_exceptions_dont_trigger_breaker(self) -> None:
        """Test that excluded exceptions don't trigger circuit breaker."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            excluded_exception_types=(ValueError,),
        )
        mock_func = MagicMock()

        # ValueError should not count
        mock_func.side_effect = ValueError("Not counted")
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call(mock_func)

        assert breaker.state == CircuitState.CLOSED
        stats = breaker.get_stats()
        assert stats.failure_count == 0

    def test_unexpected_exception_type_doesnt_count(self) -> None:
        """Test that unexpected exception types don't count as failures."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            expected_exception_types=(RuntimeError,),
        )
        mock_func = MagicMock(side_effect=ValueError("Not expected"))

        # ValueError is not in expected_exception_types
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call(mock_func)

        # Circuit should remain CLOSED
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerDecorator:
    """Test circuit breaker as decorator."""

    def test_decorator_protects_function(self) -> None:
        """Test using circuit breaker as decorator."""
        breaker = CircuitBreaker(failure_threshold=2)

        call_count = 0

        @breaker.protected
        def risky_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("Error")
            return "success"

        # First 2 calls fail
        for _ in range(2):
            with pytest.raises(RuntimeError):
                risky_function()

        # Circuit opens
        assert breaker.state == CircuitState.OPEN

        # Next call rejected
        with pytest.raises(CircuitBreakerError):
            risky_function()

        # Function should only have been called 2 times
        assert call_count == 2

    def test_decorator_with_arguments(self) -> None:
        """Test decorator with function arguments."""
        breaker = CircuitBreaker()

        @breaker.protected
        def add(a: int, b: int) -> int:
            return a + b

        result = add(2, 3)
        assert result == 5


class TestCircuitBreakerRepr:
    """Test string representation."""

    def test_repr_closed_state(self) -> None:
        """Test repr in CLOSED state."""
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
        repr_str = repr(breaker)

        assert "CircuitBreaker" in repr_str
        assert "CLOSED" in repr_str or "closed" in repr_str
        assert "5" in repr_str
        assert "30" in repr_str

    def test_repr_open_state(self) -> None:
        """Test repr in OPEN state."""
        breaker = CircuitBreaker(failure_threshold=1)
        mock_func = MagicMock(side_effect=RuntimeError("Error"))

        with pytest.raises(RuntimeError):
            breaker.call(mock_func)

        repr_str = repr(breaker)
        assert "OPEN" in repr_str or "open" in repr_str


class TestCircuitBreakerThreadSafety:
    """Test thread safety of circuit breaker."""

    def test_concurrent_calls(self) -> None:
        """Test that concurrent calls are thread-safe."""
        import threading

        breaker = CircuitBreaker(failure_threshold=10)
        mock_func = MagicMock(return_value="success")
        results = []

        def call_breaker() -> None:
            result = breaker.call(mock_func)
            results.append(result)

        # Launch 20 concurrent calls
        threads = [threading.Thread(target=call_breaker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All calls should succeed (no exceptions expected)
        assert len(results) == 20
        stats = breaker.get_stats()
        assert stats.total_requests == 20

    def test_concurrent_failures(self) -> None:
        """Test that concurrent failures are handled correctly and circuit opens."""
        import threading

        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        mock_func = MagicMock(side_effect=RuntimeError("Concurrent failure"))
        exceptions = []

        def call_breaker() -> None:
            try:
                breaker.call(mock_func)
            except Exception as e:
                exceptions.append(e)

        # Launch 10 concurrent calls that will all fail
        threads = [threading.Thread(target=call_breaker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All calls should fail
        assert len(exceptions) == 10
        stats = breaker.get_stats()
        assert stats.total_requests == 10

        # Circuit should be open due to exceeding failure threshold
        assert stats.state == CircuitState.OPEN
        assert stats.failure_count >= 5
