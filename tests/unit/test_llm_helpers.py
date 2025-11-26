"""Unit tests for LLM integration helper heuristics."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from review_bot_automator.llm.exceptions import (
    LLMAuthenticationError,
    LLMRateLimitError,
)
from tests.integration.llm._helpers import (
    _is_auth_error,
    _is_budget_error,
    guarded_call,
    handle_provider_exception,
    require_cli,
    require_env_var,
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


def test_is_auth_error_by_message_only() -> None:
    """Auth text matches should trigger even without types or status codes."""
    exc = Exception("authentication failed for user")
    assert _is_auth_error(exc)


def test_is_auth_error_combined_signals() -> None:
    """Type or status or message combinations trigger auth detection."""
    typed = LLMAuthenticationError("auth failed")
    typed.status_code = 500  # type: ignore[attr-defined]
    assert _is_auth_error(typed)

    status_only = Exception("temporary issue")
    status_only.status_code = 401  # type: ignore[attr-defined]
    assert _is_auth_error(status_only)

    response_status = Exception("forbidden response")
    response_status.response = SimpleNamespace(status_code=403)  # type: ignore[attr-defined]
    assert _is_auth_error(response_status)


def test_is_auth_error_chained_exceptions() -> None:
    """Chained cause/context containing auth cues should trigger detection."""
    inner = Exception("authentication failed")
    outer = Exception("outer wrapper")
    outer.__cause__ = inner
    assert _is_auth_error(outer)

    context_exc = Exception("outer wrapper")
    context_exc.__context__ = Exception("forbidden")
    assert _is_auth_error(context_exc)


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


def test_is_budget_error_by_message_only() -> None:
    """Budget text matches should trigger even without types or status codes."""
    exc = Exception("rate limit exceeded on request")
    assert _is_budget_error(exc)


def test_is_budget_error_chained_exceptions() -> None:
    """Chained cause/context containing budget cues should trigger detection."""
    inner = Exception("quota exceeded")
    outer = Exception("outer")
    outer.__cause__ = inner
    assert _is_budget_error(outer)

    context_exc = Exception("outer")
    context_exc.__context__ = Exception("rate limit hit")
    assert _is_budget_error(context_exc)


def test_is_budget_error_combined_status_signals() -> None:
    """Status codes on exc or response should trigger budget detection."""
    status_only = Exception("ok")
    status_only.status_code = 429  # type: ignore[attr-defined]
    assert _is_budget_error(status_only)

    resp_status_only = Exception("ok")
    resp_status_only.response = SimpleNamespace(status_code=402)  # type: ignore[attr-defined]
    assert _is_budget_error(resp_status_only)


def test_is_auth_error_negative_case() -> None:
    """Non-auth errors should not be detected."""
    assert not _is_auth_error(RuntimeError("random failure"))


def test_is_budget_error_negative_case() -> None:
    """Non-budget errors should not be detected."""
    assert not _is_budget_error(Exception("unrelated message"))


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


def test_guarded_call_re_raises_unhandled() -> None:
    """guarded_call should propagate unexpected exceptions."""

    def raise_runtime() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        guarded_call("TestProvider", raise_runtime)


def test_guarded_call_skips_auth_and_budget() -> None:
    """guarded_call should skip on auth/budget exceptions."""

    def raise_auth() -> None:
        raise LLMAuthenticationError("auth")

    def raise_rate() -> None:
        raise LLMRateLimitError("rate limit")

    with pytest.raises(pytest.skip.Exception):
        guarded_call("TestProvider", raise_auth)
    with pytest.raises(pytest.skip.Exception):
        guarded_call("TestProvider", raise_rate)


def test_require_env_var_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return env value when present."""
    monkeypatch.setenv("TEST_KEY", "value")
    assert require_env_var("TEST_KEY", "Test") == "value"


def test_require_env_var_missing_or_empty_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip when env missing or empty."""
    monkeypatch.delenv("MISSING_KEY", raising=False)
    with pytest.raises(pytest.skip.Exception):
        require_env_var("MISSING_KEY", "Test")

    monkeypatch.setenv("EMPTY_KEY", "")
    with pytest.raises(pytest.skip.Exception):
        require_env_var("EMPTY_KEY", "Test")


def test_require_cli_skips_when_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip when CLI binary is unavailable."""
    monkeypatch.setenv("PATH", "")  # ensure lookup fails
    with pytest.raises(pytest.skip.Exception):
        require_cli("nonexistent-binary", "Test CLI")


def test_require_cli_present() -> None:
    """Do not skip when a known binary exists."""
    require_cli("python", "Python CLI")
