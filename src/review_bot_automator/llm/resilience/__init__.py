# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Resilience patterns for LLM providers.

This package provides resilience patterns to handle transient failures and protect
against cascading failures when interacting with LLM services.

Available modules:
- circuit_breaker.py (Phase 5 - Issue #222): Circuit breaker pattern implementation
- resilient_provider.py (Phase 5 - Issue #222): Resilient LLM provider wrapper
"""

from review_bot_automator.llm.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from review_bot_automator.llm.resilience.resilient_provider import ResilientLLMProvider

__all__: list[str] = [
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
    "ResilientLLMProvider",
]
