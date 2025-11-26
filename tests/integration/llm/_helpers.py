"""Shared helpers for LLM integration tests."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from typing import TypeVar

import pytest

from review_bot_automator.llm.exceptions import LLMAuthenticationError, LLMRateLimitError


def require_env_var(env_var: str, provider_name: str) -> str:
    """Return required env var or skip if missing."""
    value = os.getenv(env_var)
    if not value:
        pytest.skip(f"{env_var} not set - skipping {provider_name} integration tests")
    return value


def require_cli(binary: str, provider_name: str) -> None:
    """Skip tests if required CLI binary is not available."""
    if not shutil.which(binary):
        pytest.skip(f"{provider_name} CLI not installed ({binary})")


def _error_text(exc: Exception) -> str:
    """Collect error text including chained causes for matching."""
    cause = getattr(exc, "__cause__", None)
    context = getattr(exc, "__context__", None)
    parts = [str(exc)]
    if cause:
        parts.append(str(cause))
    if context:
        parts.append(str(context))
    return " ".join(parts).lower()


def _is_auth_error(exc: Exception) -> bool:
    """Detect authentication/authorization failures."""
    if isinstance(exc, LLMAuthenticationError):
        return True

    status_code = getattr(exc, "status_code", None)
    response_status = getattr(getattr(exc, "response", None), "status_code", None)
    if status_code in (401, 403) or response_status in (401, 403):
        return True

    text = _error_text(exc)
    return any(
        token in text
        for token in (
            "unauthorized",
            "authentication",
            "invalid api key",
            "expired",
            "forbidden",
            "permission denied",
            "access denied",
            "401",
        )
    )


def _is_budget_error(exc: Exception) -> bool:
    """Detect rate limit or exhausted budget errors."""
    if isinstance(exc, LLMRateLimitError):
        return True

    status_code = getattr(exc, "status_code", None)
    response_status = getattr(getattr(exc, "response", None), "status_code", None)
    if status_code in (429, 402) or response_status in (429, 402):
        return True

    text = _error_text(exc)
    return any(
        token in text
        for token in (
            "rate limit",
            "quota",
            "billing",
            "insufficient",
            "limit exceeded",
            "429",
        )
    )


def handle_provider_exception(exc: Exception, provider_name: str) -> None:
    """Skip integration tests for auth/quota failures, otherwise re-raise."""
    if _is_auth_error(exc):
        pytest.skip(f"{provider_name} credentials invalid or expired")
    if _is_budget_error(exc):
        pytest.skip(f"{provider_name} rate limit or budget exhausted")
    raise exc


T = TypeVar("T")


def guarded_call(  # noqa: UP047 - TypeVar style kept for Python 3.11 compatibility
    provider_name: str, func: Callable[[], T]
) -> T:
    """Run a provider call and skip integration tests on auth/quota failures."""
    try:
        return func()
    except Exception as exc:
        handle_provider_exception(exc, provider_name)
        # Defensive: handle_provider_exception never returns normally.
        raise AssertionError("handle_provider_exception should not return") from exc
