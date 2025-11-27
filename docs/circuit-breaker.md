# Circuit Breaker Pattern

The circuit breaker pattern protects against cascading failures when LLM providers experience issues. It monitors failures and temporarily blocks requests when a threshold is exceeded, giving the provider time to recover.

## Overview

The circuit breaker follows a state machine pattern with three states:

```text
    ┌─────────────────────────────────────────────────────────────┐
    │                                                             │
    │   CLOSED ──────────────> OPEN ──────────────> HALF_OPEN    │
    │     │                      │                      │         │
    │     │  (5 consecutive      │  (60s cooldown       │         │
    │     │   failures)          │   elapsed)           │         │
    │     │                      │                      │         │
    │     └──────────────────────┼──────────────────────┘         │
    │                            │                                │
    │                    (success) │ (failure)                    │
    │                            ↓                                │
    │                         CLOSED                              │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘
```

## States

### CLOSED (Normal Operation)

* All requests pass through to the LLM provider
* Failures are counted
* Circuit trips to OPEN after `failure_threshold` consecutive failures

### OPEN (Blocking Requests)

* All requests are blocked immediately
* Returns `CircuitBreakerOpen` exception without calling provider
* After `cooldown_seconds`, transitions to HALF_OPEN

### HALF_OPEN (Testing Recovery)

* Allows a single "probe" request through
* If probe succeeds: transitions to CLOSED
* If probe fails: transitions back to OPEN

## Configuration

Configure the circuit breaker via environment variables or config file:

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CR_LLM_CIRCUIT_BREAKER_ENABLED` | `true` | Enable/disable circuit breaker |
| `CR_LLM_CIRCUIT_BREAKER_THRESHOLD` | `5` | Consecutive failures to trip circuit |
| `CR_LLM_CIRCUIT_BREAKER_COOLDOWN` | `60.0` | Seconds before recovery attempt |

### Config File (YAML)

```yaml
llm:
  circuit_breaker_enabled: true
  circuit_breaker_threshold: 5
  circuit_breaker_cooldown: 60.0
```

### Config File (TOML)

```toml
[llm]
circuit_breaker_enabled = true
circuit_breaker_threshold = 5
circuit_breaker_cooldown = 60.0
```

## Handling CircuitBreakerOpen Errors

When the circuit is open, you'll see an error like:

```text
CircuitBreakerOpen: Circuit breaker is open, retry in 45.2s
```

### What to Do

1. **Wait for cooldown**: The error message includes remaining time
2. **Check provider status**: Verify the LLM provider is operational
3. **Review logs**: Check for the underlying failure cause
4. **Adjust threshold**: If too sensitive, increase `circuit_breaker_threshold`

### Programmatic Handling

```python
from review_bot_automator.llm.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)

breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=60.0)

try:
    result = breaker.call(provider.generate, prompt)
except CircuitBreakerOpen as e:
    print(f"Provider unavailable, retry in {e.remaining_cooldown:.1f}s")
    # Implement fallback or retry logic
```

## Tuning Recommendations

### High Availability (Lenient)

For applications where availability is critical and you can tolerate occasional failures:

```yaml
llm:
  circuit_breaker_threshold: 10  # More failures before tripping
  circuit_breaker_cooldown: 30.0  # Faster recovery attempts
```

### Cost Optimization (Strict)

For applications where cost matters and you want to fail fast on issues:

```yaml
llm:
  circuit_breaker_threshold: 3  # Trip quickly on failures
  circuit_breaker_cooldown: 120.0  # Longer wait between retries
```

### Default (Balanced)

The default configuration balances availability and protection:

```yaml
llm:
  circuit_breaker_threshold: 5
  circuit_breaker_cooldown: 60.0
```

## Integration with Retry

The circuit breaker works alongside the retry mechanism:

1. **Retry handles transient failures**: Rate limits, timeouts
2. **Circuit breaker handles persistent failures**: Provider outages, API errors

When retry exhausts attempts on repeated failures, the circuit breaker trips to prevent further attempts until cooldown.

## Thread Safety

The circuit breaker is fully thread-safe and can be shared across multiple threads during parallel comment parsing. All state transitions are atomic.

## Monitoring

Check circuit breaker state in logs:

```text
INFO: Circuit breaker transitioning to HALF_OPEN for recovery
WARNING: Circuit breaker opening after 5 consecutive failures
INFO: Circuit breaker recovered, transitioning to CLOSED
```

## Disabling the Circuit Breaker

If you need to disable the circuit breaker (not recommended for production):

```bash
export CR_LLM_CIRCUIT_BREAKER_ENABLED=false
```

Or in config:

```yaml
llm:
  circuit_breaker_enabled: false
```

## See Also

* [LLM Configuration](llm-configuration.md) - Full LLM configuration reference
* [Troubleshooting](troubleshooting.md) - Common issues and solutions
* [Performance Tuning](performance-tuning.md) - Optimizing LLM performance
