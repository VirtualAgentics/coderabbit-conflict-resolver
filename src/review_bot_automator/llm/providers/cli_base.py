# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Base class for CLI-based LLM providers.

This module provides a shared base class for CLI-based LLM providers (Claude CLI,
Codex CLI) to eliminate code duplication and ensure consistent behavior.
"""

import logging
import shutil
import subprocess  # nosec B404  # Required for CLI execution with validated inputs
from abc import ABC, abstractmethod
from typing import ClassVar

from review_bot_automator.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
)

logger = logging.getLogger(__name__)


class CLIProviderBase(ABC):
    """Base class for CLI-based LLM providers.

    This base class implements common functionality for CLI-based providers:
    - CLI availability checking on initialization
    - Subprocess execution with timeout handling
    - Character-based token estimation
    - Cost tracking (always $0.00 - subscription covered)
    - Comprehensive error handling

    Subclasses must define:
    - CLI_COMMAND: The CLI command name (e.g., "claude", "codex")
    - DEFAULT_MODEL: Default model identifier
    - _get_provider_name(): Return provider name for error messages
    - _get_provider_id(): Return provider identifier for error details
    - _get_install_url(): Return installation URL for error messages
    - _get_auth_command(): Return authentication command for error messages
    - _get_cli_command(): Return CLI command with args for non-interactive execution

    Examples:
        >>> class MyCLIProvider(CLIProviderBase):
        ...     CLI_COMMAND = "mycli"
        ...     DEFAULT_MODEL = "my-model"
        ...     def _get_provider_name(self) -> str:
        ...         return "My CLI"
        ...     def _get_provider_id(self) -> str:
        ...         return "my-cli"
        ...     def _get_install_url(self) -> str:
        ...         return "https://mycli.com/install"
        ...     def _get_auth_command(self) -> str:
        ...         return "mycli auth"
        ...     def _get_cli_command(self) -> list[str]:
        ...         return ["mycli", "--non-interactive"]
    """

    DEFAULT_TIMEOUT: ClassVar[int] = 60

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Get provider name for error messages.

        Returns:
            str: Provider name (e.g., "Claude", "Codex")
        """

    @abstractmethod
    def _get_provider_id(self) -> str:
        """Get provider identifier for error details.

        Returns:
            str: Provider identifier (e.g., "claude-cli", "codex-cli")
        """

    @abstractmethod
    def _get_install_url(self) -> str:
        """Get installation URL for error messages.

        Returns:
            str: Installation URL (e.g., "https://claude.ai/cli")
        """

    @abstractmethod
    def _get_auth_command(self) -> str:
        """Get authentication command for error messages.

        Returns:
            str: Authentication command (e.g., "claude auth", "codex auth")
        """

    @abstractmethod
    def _get_cli_command(self) -> list[str]:
        """Get CLI command with arguments for non-interactive execution.

        This method returns the full CLI command as a list of strings, including
        any flags needed for non-interactive mode (e.g., ["codex", "exec"] or
        ["claude", "--print"]).

        Returns:
            list[str]: Command and arguments for non-interactive CLI execution
        """

    def __init__(
        self,
        model: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize CLI provider.

        Args:
            model: Model identifier (default: DEFAULT_MODEL, may be ignored by CLI)
            timeout: Request timeout in seconds (default: 60)

        Raises:
            LLMConfigurationError: If CLI is not installed
        """
        # Access class variables from subclass
        default_model = getattr(self.__class__, "DEFAULT_MODEL", "")
        self.model = model or default_model
        self.timeout = timeout

        # Token usage tracking (estimated via character count)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Verify CLI is available
        self._check_cli_available()

        provider_name = self._get_provider_name()
        logger.info(f"Initialized {provider_name} provider: model={self.model}, timeout={timeout}s")

    def _check_cli_available(self) -> None:
        """Check if CLI is installed and available.

        Raises:
            LLMConfigurationError: If CLI is not found with installation instructions
        """
        cli_command = getattr(self.__class__, "CLI_COMMAND", "")
        cli_path = shutil.which(cli_command)
        if not cli_path:
            provider_name = self._get_provider_name()
            install_url = self._get_install_url()
            raise LLMConfigurationError(
                f"{provider_name} CLI not found. Install it from: {install_url}",
                details={
                    "provider": self._get_provider_id(),
                    "cli_command": cli_command,
                },
            )

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text completion using CLI.

        This method executes the CLI with the provided prompt and returns
        the generated text. It handles timeouts, exit codes, and authentication
        errors appropriately.

        Args:
            prompt: Input prompt for generation
            max_tokens: Maximum tokens to generate (may be ignored by CLI)

        Returns:
            Generated text from CLI

        Raises:
            ValueError: If prompt is empty or max_tokens is invalid
            LLMAPIError: If CLI execution fails or times out
            LLMAuthenticationError: If CLI authentication fails
            LLMConfigurationError: If CLI is not installed
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens}")

        provider_name = self._get_provider_name()
        logger.debug(
            f"Sending request to {provider_name} CLI: prompt_length={len(prompt)}, "
            f"max_tokens={max_tokens}"
        )

        try:
            cli_command = self._get_cli_command()
            result = (
                subprocess.run(  # nosec B603, B607  # noqa: S603  # CLI command with validated args
                    cli_command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                )
            )

            # Handle non-zero exit codes
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"

                # Check for authentication errors
                if result.returncode == 1 and "authentication" in error_msg.lower():
                    auth_cmd = self._get_auth_command()
                    raise LLMAuthenticationError(
                        f"{provider_name} CLI authentication failed. "
                        f"Run '{auth_cmd}' to authenticate.",
                        details={
                            "provider": self._get_provider_id(),
                            "exit_code": result.returncode,
                            "stderr": error_msg,
                        },
                    ) from None

                raise LLMAPIError(
                    f"{provider_name} CLI failed with exit code {result.returncode}: "
                    f"{error_msg}",
                    details={
                        "provider": self._get_provider_id(),
                        "exit_code": result.returncode,
                        "stderr": error_msg,
                    },
                )

            # Parse response
            response = result.stdout.strip() if result.stdout else ""

            if not response:
                raise LLMAPIError(
                    f"{provider_name} CLI returned empty response",
                    details={
                        "provider": self._get_provider_id(),
                        "prompt_length": len(prompt),
                    },
                )

            # Track token usage (estimated)
            estimated_input_tokens = self.count_tokens(prompt)
            estimated_output_tokens = self.count_tokens(response)
            self.total_input_tokens += estimated_input_tokens
            self.total_output_tokens += estimated_output_tokens

            logger.debug(
                f"{provider_name} CLI response received: response_length={len(response)}, "
                f"estimated_tokens={estimated_output_tokens}"
            )

            return response

        except subprocess.TimeoutExpired as e:
            logger.error(f"{provider_name} CLI request timed out after {self.timeout}s")
            raise LLMAPIError(
                f"{provider_name} CLI request timed out after {self.timeout}s",
                details={
                    "provider": self._get_provider_id(),
                    "timeout": self.timeout,
                },
            ) from e
        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"{provider_name} CLI subprocess error: {e}")
            raise LLMAPIError(
                f"{provider_name} CLI subprocess execution failed: {e}",
                details={
                    "provider": self._get_provider_id(),
                    "error": str(e),
                },
            ) from e

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using character-based estimation.

        Since CLI doesn't expose a tokenization API, this method uses
        a character-based approximation (chars // 4) which is consistent with
        the average token length for most text.

        Args:
            text: Text to tokenize and count

        Returns:
            Estimated number of tokens (chars // 4)

        Raises:
            ValueError: If text is None
        """
        if text is None:
            raise ValueError("Text cannot be None")

        if not text:
            return 0

        # Character-based estimation: ~4 chars per token average
        return len(text) // 4

    def get_total_cost(self) -> float:
        """Get total cost in USD for all requests.

        CLI providers use subscription-based pricing, so there's no marginal
        cost per request. This method always returns $0.00.

        Returns:
            Total cost in USD (always 0.0 for subscription-based CLI)
        """
        return 0.0

    def reset_usage_tracking(self) -> None:
        """Reset token usage tracking counters.

        This method resets the cumulative token counters to zero. Useful
        for testing or when tracking usage across different sessions.
        """
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        logger.debug(f"Reset {self._get_provider_name()} CLI usage tracking")
