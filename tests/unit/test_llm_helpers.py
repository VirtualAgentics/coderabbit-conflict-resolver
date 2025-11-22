"""Unit tests for LLM integration helper heuristics."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pr_conflict_resolver.llm.exceptions import (
    LLMAuthenticationError,
    LLMRateLimitError,
)
from tests.integration.llm._helpers import (
    _is_auth_error,
    _is_budget_error,
    handle_provider_exception,
)


def test_is_auth_error_by_type() -> None:
    """Authentication error type triggers auth detection."""

    auth_exc = LLMAuthenticationError("invalid api key")
    assert _is_auth_error(auth_exc)


def test_is_auth_error_by_status_code() -> None:
    """HTTP 401/403 status codes trigger auth detection."""
    exc = Exception("unauthorized")
    exc.status_code = 401  # type: ignore[attr-defined]
    assert _is_auth_error(exc)

    resp_exc = Exception("forbidden")
    resp_exc.response = SimpleNamespace(status_code=403)  # type: ignore[attr-defined]
    assert _is_auth_error(resp_exc)


def test_is_budget_error_by_type() -> None:
    """Rate limit error type triggers budget detection."""

    rate_exc = LLMRateLimitError("rate limit exceeded")
    assert _is_budget_error(rate_exc)


def test_is_budget_error_by_status_code() -> None:
    """HTTP 429/402 status codes trigger budget detection."""
    exc = Exception("rate limit")
    exc.status_code = 429  # type: ignore[attr-defined]
    assert _is_budget_error(exc)

    resp_exc = Exception("quota")
    resp_exc.response = SimpleNamespace(status_code=402)  # type: ignore[attr-defined]
    assert _is_budget_error(resp_exc)


def test_handle_provider_exception_skips_on_auth_or_budget() -> None:
    """handle_provider_exception should skip appropriately."""
    auth_exc = Exception("invalid api key")
    auth_exc.status_code = 401  # type: ignore[attr-defined]
    with pytest.raises(pytest.skip.Exception):
        handle_provider_exception(auth_exc, "TestProvider")

    rate_exc = Exception("rate limit exceeded")
    rate_exc.status_code = 429  # type: ignore[attr-defined]
    with pytest.raises(pytest.skip.Exception):
        handle_provider_exception(rate_exc, "TestProvider")


def test_handle_provider_exception_reraises_other_errors() -> None:
    """Non-auth/budget errors are re-raised."""
    other_exc = RuntimeError("unexpected failure")
    with pytest.raises(RuntimeError):
        handle_provider_exception(other_exc, "TestProvider")
