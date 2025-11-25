"""Tests for ResilientLLMProvider class.

Phase 5 - Issue #222: Circuit Breaker Pattern Implementation
"""

import threading

import pytest

from pr_conflict_resolver.llm.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from pr_conflict_resolver.llm.resilience.resilient_provider import ResilientLLMProvider


# Dummy provider class for testing (avoid MagicMock class name issues)
class DummyProvider:
    """Minimal LLMProvider implementation for testing."""

    def __init__(self, model: str = "test-model") -> None:
        self.model = model
        self._generate_response: str = "test response"
        self._generate_error: Exception | None = None
        self._call_count = 0
        self._total_cost = 0.0
        self._return_none: bool = False
        self._lock = threading.Lock()

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        with self._lock:
            self._call_count += 1
        if self._generate_error:
            raise self._generate_error
        if self._return_none:
            return ""  # Return empty string instead of None for type safety
        return self._generate_response

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def get_total_cost(self) -> float:
        return self._total_cost

    def reset_usage_tracking(self) -> None:
        self._total_cost = 0.0


class TestResilientLLMProviderInit:
    """Tests for ResilientLLMProvider initialization."""

    def test_basic_init(self) -> None:
        """Basic initialization works."""
        provider = DummyProvider()
        resilient = ResilientLLMProvider(provider)

        assert resilient.provider is provider
        assert resilient.model == "test-model"
        assert resilient.circuit_state == CircuitState.CLOSED

    def test_custom_threshold(self) -> None:
        """Custom failure threshold is applied."""
        provider = DummyProvider()
        resilient = ResilientLLMProvider(provider, failure_threshold=3)

        assert resilient.circuit_breaker.failure_threshold == 3

    def test_custom_cooldown(self) -> None:
        """Custom cooldown is applied."""
        provider = DummyProvider()
        resilient = ResilientLLMProvider(provider, cooldown_seconds=30.0)

        assert resilient.circuit_breaker.cooldown_seconds == 30.0

    def test_custom_circuit_breaker(self) -> None:
        """Custom circuit breaker is used."""
        provider = DummyProvider()
        breaker = CircuitBreaker(failure_threshold=10)
        resilient = ResilientLLMProvider(provider, circuit_breaker=breaker)

        assert resilient.circuit_breaker is breaker

    def test_missing_model_attribute(self) -> None:
        """Missing model attribute raises AttributeError."""

        class NoModelProvider:
            def generate(self, prompt: str, max_tokens: int = 2000) -> str:
                return "response"

            def count_tokens(self, text: str) -> int:
                return 0

            def get_total_cost(self) -> float:
                return 0.0

        with pytest.raises(AttributeError, match="must have a 'model' attribute"):
            ResilientLLMProvider(NoModelProvider())

    def test_empty_model_attribute(self) -> None:
        """Empty model attribute raises AttributeError."""

        class EmptyModelProvider:
            model = ""

            def generate(self, prompt: str, max_tokens: int = 2000) -> str:
                return "response"

            def count_tokens(self, text: str) -> int:
                return 0

            def get_total_cost(self) -> float:
                return 0.0

        with pytest.raises(AttributeError, match="invalid 'model' attribute"):
            ResilientLLMProvider(EmptyModelProvider())

    def test_none_model_attribute(self) -> None:
        """None model attribute raises AttributeError."""

        class NoneModelProvider:
            model = None

            def generate(self, prompt: str, max_tokens: int = 2000) -> str:
                return "response"

            def count_tokens(self, text: str) -> int:
                return 0

            def get_total_cost(self) -> float:
                return 0.0

        with pytest.raises(AttributeError, match="invalid 'model' attribute"):
            ResilientLLMProvider(NoneModelProvider())


class TestResilientLLMProviderGenerate:
    """Tests for generate() method."""

    def test_successful_generate(self) -> None:
        """Successful generation returns response."""
        provider = DummyProvider()
        resilient = ResilientLLMProvider(provider)

        result = resilient.generate("test prompt")

        assert result == "test response"
        assert provider._call_count == 1

    def test_generate_passes_max_tokens(self) -> None:
        """max_tokens is passed to provider."""
        provider = DummyProvider()
        resilient = ResilientLLMProvider(provider)

        # We can verify this works without error
        result = resilient.generate("test prompt", max_tokens=1000)
        assert result == "test response"

    def test_generate_failure_increments_counter(self) -> None:
        """Failed generation increments failure counter."""
        provider = DummyProvider()
        provider._generate_error = RuntimeError("API error")
        resilient = ResilientLLMProvider(provider, failure_threshold=5)

        with pytest.raises(RuntimeError):
            resilient.generate("test prompt")

        assert resilient.failure_count == 1

    def test_circuit_opens_after_failures(self) -> None:
        """Circuit opens after threshold failures."""
        provider = DummyProvider()
        provider._generate_error = RuntimeError("API error")
        resilient = ResilientLLMProvider(provider, failure_threshold=3)

        for _ in range(3):
            with pytest.raises(RuntimeError):
                resilient.generate("test prompt")

        assert resilient.circuit_state == CircuitState.OPEN

    def test_open_circuit_raises_exception(self) -> None:
        """Open circuit raises CircuitBreakerOpen."""
        provider = DummyProvider()
        provider._generate_error = RuntimeError("API error")
        resilient = ResilientLLMProvider(provider, failure_threshold=1, cooldown_seconds=60.0)

        # Trip the circuit
        with pytest.raises(RuntimeError):
            resilient.generate("test prompt")

        # Further calls raise CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            resilient.generate("test prompt")

        # Provider should only be called once
        assert provider._call_count == 1

    def test_empty_response_returned(self) -> None:
        """Empty response from provider is returned."""
        provider = DummyProvider()
        provider._return_none = True
        resilient = ResilientLLMProvider(provider)

        result = resilient.generate("test prompt")
        assert result == ""


class TestResilientLLMProviderCountTokens:
    """Tests for count_tokens() method."""

    def test_count_tokens_delegates(self) -> None:
        """count_tokens delegates to provider."""
        provider = DummyProvider()
        resilient = ResilientLLMProvider(provider)

        result = resilient.count_tokens("hello world test")

        assert result == 3  # DummyProvider counts words

    def test_count_tokens_no_circuit_breaker(self) -> None:
        """count_tokens doesn't use circuit breaker."""
        provider = DummyProvider()
        resilient = ResilientLLMProvider(provider, failure_threshold=1)

        # Trip the circuit
        provider._generate_error = RuntimeError("error")
        with pytest.raises(RuntimeError):
            resilient.generate("test")

        assert resilient.circuit_state == CircuitState.OPEN

        # count_tokens still works
        result = resilient.count_tokens("hello world")
        assert result == 2


class TestResilientLLMProviderCost:
    """Tests for cost tracking methods."""

    def test_get_total_cost(self) -> None:
        """get_total_cost returns provider cost."""
        provider = DummyProvider()
        provider._total_cost = 0.05
        resilient = ResilientLLMProvider(provider)

        assert resilient.get_total_cost() == 0.05

    def test_reset_usage_tracking(self) -> None:
        """reset_usage_tracking resets provider cost."""
        provider = DummyProvider()
        provider._total_cost = 0.05
        resilient = ResilientLLMProvider(provider)

        resilient.reset_usage_tracking()

        assert provider._total_cost == 0.0

    def test_get_total_cost_missing_method(self) -> None:
        """get_total_cost returns 0.0 if method missing."""

        # Intentionally not implementing get_total_cost to test fallback behavior
        class MinimalProvider:
            model = "test"

            def generate(self, prompt: str, max_tokens: int = 2000) -> str:
                return "response"

            def count_tokens(self, text: str) -> int:
                return 0

        resilient = ResilientLLMProvider(MinimalProvider())  # type: ignore[arg-type]
        assert resilient.get_total_cost() == 0.0


class TestResilientLLMProviderCircuitControl:
    """Tests for circuit breaker control methods."""

    def test_reset_circuit_breaker(self) -> None:
        """reset_circuit_breaker resets to CLOSED."""
        provider = DummyProvider()
        provider._generate_error = RuntimeError("error")
        resilient = ResilientLLMProvider(provider, failure_threshold=1)

        # Trip the circuit
        with pytest.raises(RuntimeError):
            resilient.generate("test")

        assert resilient.circuit_state == CircuitState.OPEN

        # Reset
        resilient.reset_circuit_breaker()
        assert resilient.circuit_state == CircuitState.CLOSED  # type: ignore[comparison-overlap]

    def test_remaining_cooldown(self) -> None:
        """remaining_cooldown returns correct value."""
        provider = DummyProvider()
        provider._generate_error = RuntimeError("error")
        resilient = ResilientLLMProvider(provider, failure_threshold=1, cooldown_seconds=60.0)

        # Closed circuit has no cooldown
        assert resilient.remaining_cooldown == 0.0

        # Trip the circuit
        with pytest.raises(RuntimeError):
            resilient.generate("test")

        # Open circuit has remaining cooldown
        assert 59.0 <= resilient.remaining_cooldown <= 60.0

    def test_failure_count_property(self) -> None:
        """failure_count property reflects circuit state."""
        provider = DummyProvider()
        provider._generate_error = RuntimeError("error")
        resilient = ResilientLLMProvider(provider, failure_threshold=5)

        assert resilient.failure_count == 0

        with pytest.raises(RuntimeError):
            resilient.generate("test")

        assert resilient.failure_count == 1


class TestResilientLLMProviderThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_successful_calls(self) -> None:
        """Concurrent successful calls work correctly."""
        provider = DummyProvider()
        resilient = ResilientLLMProvider(provider)
        results: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            for _ in range(10):
                result = resilient.generate("test prompt")
                with lock:
                    results.append(result)

        threads = []
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 100
        assert all(r == "test response" for r in results)
        assert provider._call_count == 100

    def test_concurrent_failures_trip_circuit(self) -> None:
        """Concurrent failures eventually trip the circuit."""
        provider = DummyProvider()
        provider._generate_error = RuntimeError("error")
        resilient = ResilientLLMProvider(provider, failure_threshold=10, cooldown_seconds=60.0)

        runtime_errors: list[Exception] = []
        circuit_open_errors: list[Exception] = []
        lock = threading.Lock()

        def worker() -> None:
            for _ in range(5):
                try:
                    resilient.generate("test prompt")
                except RuntimeError as e:
                    with lock:
                        runtime_errors.append(e)
                except CircuitBreakerOpen as e:
                    with lock:
                        circuit_open_errors.append(e)

        threads = []
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Circuit should have opened at some point
        assert resilient.circuit_state == CircuitState.OPEN
        # Some calls should have been blocked by circuit breaker
        assert len(circuit_open_errors) > 0
