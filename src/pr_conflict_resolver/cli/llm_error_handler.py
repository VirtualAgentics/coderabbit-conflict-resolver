"""LLM error handling utilities for CLI commands.

This module provides shared error handling for LLM operations across CLI commands.
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import click
from rich.console import Console

from pr_conflict_resolver.llm.error_handlers import LLMErrorHandler
from pr_conflict_resolver.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMCostExceededError,
    LLMError,
    LLMParsingError,
    LLMRateLimitError,
    LLMSecretDetectedError,
    LLMTimeoutError,
)

if TYPE_CHECKING:
    from pr_conflict_resolver.config.runtime_config import RuntimeConfig

logger = logging.getLogger(__name__)
console = Console()


@contextmanager
def handle_llm_errors(runtime_config: "RuntimeConfig") -> Generator[None, None, None]:
    """Context manager for handling LLM errors in CLI commands.

    Args:
        runtime_config: Runtime configuration containing LLM provider settings.

    Yields:
        None

    Raises:
        click.Abort: For fatal LLM errors that should terminate execution.

    Example:
        with handle_llm_errors(runtime_config):
            # LLM operations here
            result = resolver.resolve_pr_conflicts(...)
    """
    try:
        yield

    except LLMAuthenticationError as e:
        # Authentication errors - provide setup guidance
        provider = getattr(runtime_config, "llm_provider", None) or "unknown"
        error_msg = LLMErrorHandler.format_auth_error(provider)
        console.print(f"\n[red]{error_msg}[/red]")
        logger.error("LLM authentication failed: %s", e)
        raise click.Abort() from e

    except LLMRateLimitError as e:
        # Rate limit errors - suggest waiting or alternatives
        provider = getattr(runtime_config, "llm_provider", None) or "unknown"
        error_msg = LLMErrorHandler.format_provider_error(provider, e)
        console.print(f"\n[yellow]{error_msg}[/yellow]")
        logger.warning("LLM rate limit exceeded: %s", e)
        raise click.Abort() from e

    except LLMTimeoutError as e:
        # Timeout errors - suggest retry or faster model
        provider = getattr(runtime_config, "llm_provider", None) or "unknown"
        error_msg = LLMErrorHandler.format_provider_error(provider, e)
        console.print(f"\n[yellow]{error_msg}[/yellow]")
        logger.warning("LLM request timed out: %s", e)
        raise click.Abort() from e

    except LLMConfigurationError as e:
        # Configuration errors - provide actionable guidance
        provider = getattr(runtime_config, "llm_provider", None) or "unknown"
        error_msg = LLMErrorHandler.format_provider_error(provider, e)
        console.print(f"\n[red]{error_msg}[/red]")
        logger.error("LLM configuration error: %s", e)
        raise click.Abort() from e

    except LLMParsingError as e:
        # Parsing errors - may fall back to regex
        provider = getattr(runtime_config, "llm_provider", None) or "unknown"
        error_msg = LLMErrorHandler.format_provider_error(provider, e)
        console.print(f"\n[yellow]{error_msg}[/yellow]")
        logger.warning("LLM parsing error: %s", e)
        # Don't abort - may have fallen back to regex parsing
        # Suppress the exception to allow execution to continue

    except LLMCostExceededError as e:
        # Cost budget exceeded - allow graceful degradation to regex
        provider = getattr(runtime_config, "llm_provider", None) or "unknown"
        console.print(
            f"\n[yellow]⚠️ LLM cost budget exceeded: "
            f"${e.accumulated_cost:.4f} of ${e.budget:.4f}[/yellow]"
        )
        console.print("[dim]Falling back to regex parsing for remaining comments[/dim]")
        logger.warning("LLM cost budget exceeded for provider %s: %s", provider, e)
        # Don't abort - allow graceful degradation to regex parsing

    except LLMSecretDetectedError as e:
        # Security error - secrets detected in content, abort to prevent exfiltration
        secret_types = ", ".join(sorted(e.secret_types)) if e.secret_types else "unknown"
        console.print(
            f"\n[red]🔒 Security: Secret detected in PR comment ({secret_types}). "
            "Content blocked from external LLM API.[/red]"
        )
        console.print("[dim]Review the PR comment for sensitive data before retrying.[/dim]")
        logger.error(
            "Secret detected, blocked LLM request: types=%s, count=%d",
            secret_types,
            len(e.findings),
        )
        raise click.Abort() from e

    except LLMAPIError as e:
        # Generic API errors
        provider = getattr(runtime_config, "llm_provider", None) or "unknown"
        error_msg = LLMErrorHandler.format_provider_error(provider, e)
        console.print(f"\n[red]{error_msg}[/red]")
        logger.error("LLM API error: %s", e)
        raise click.Abort() from e

    except LLMError as e:
        # Catch-all for other LLM errors
        provider = getattr(runtime_config, "llm_provider", None) or "unknown"
        error_msg = LLMErrorHandler.format_provider_error(provider, e)
        console.print(f"\n[red]{error_msg}[/red]")
        logger.error("LLM error: %s", e)
        raise click.Abort() from e
