"""Shared helpers for LLM integration tests."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable

import pytest

from pr_conflict_resolver.llm.exceptions import LLMAuthenticationError, LLMRateLimitError


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


def _error_text(exc: BaseException) -> str:
    """Collect error text including chained causes for matching."""
    cause = getattr(exc, "__cause__", None)
    cause_text = f" {cause}" if cause else ""
    return f"{exc}{cause_text}".lower()


def _is_auth_error(exc: BaseException) -> bool:
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
            "401",
        )
    )


def _is_budget_error(exc: BaseException) -> bool:
    """Detect rate limit or exhausted budget errors."""
    if isinstance(exc, (LLMRateLimitError,)):
        return True

    status_code = getattr(exc, "status_code", None)
    response_status = getattr(getattr(exc, "response", None), "status_code", None)
    if status_code in (429, 402) or response_status in (429, 402):
        return True

    text = _error_text(exc)
    if any(
        token in text
        for token in (
            "rate limit",
            "quota",
            "billing",
            "insufficient",
            "limit exceeded",
            "429",
        )
    ):
        return True

    response = getattr(exc, "response", None)
    status_code = getattr(exc, "status_code", None) or getattr(response, "status_code", None)
    return status_code == 429


def handle_provider_exception(exc: BaseException, provider_name: str) -> None:
    """Skip integration tests for auth/quota failures, otherwise re-raise."""
    if _is_auth_error(exc):
        pytest.skip(f"{provider_name} credentials invalid or expired")
    if _is_budget_error(exc):
        pytest.skip(f"{provider_name} rate limit or budget exhausted")
    raise exc


def guarded_call[T](provider_name: str, func: Callable[[], T]) -> T:
    """Run a provider call and skip integration tests on auth/quota failures."""
    try:
        return func()
    except BaseException as exc:
        handle_provider_exception(exc, provider_name)
        raise
