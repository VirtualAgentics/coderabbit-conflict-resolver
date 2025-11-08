"""Claude CLI provider implementation.

This module provides the Claude CLI integration for LLM text generation.
It includes:
- CLI availability checking on initialization
- Subprocess execution with timeout handling
- Character-based token estimation
- Cost tracking (always $0.00 - subscription covered)
- Comprehensive error handling

The provider uses subprocess to execute the Claude CLI and implements
the LLMProvider protocol for type safety and polymorphic usage.
"""

import logging
import shutil
import subprocess  # nosec B404  # Required for CLI execution with validated inputs
from typing import ClassVar

from pr_conflict_resolver.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
)

logger = logging.getLogger(__name__)


class ClaudeCLIProvider:
    """Claude CLI provider for LLM text generation.

    This provider implements the LLMProvider protocol and provides access to
    Claude models via the Claude CLI. It includes:
    - CLI availability checking on initialization
    - Subprocess execution with timeout handling
    - Character-based token estimation
    - Cost tracking (always $0.00 - subscription covered)
    - Comprehensive error handling

    The provider requires Claude CLI to be installed and authenticated.
    No API key is required (authenticated via CLI login).

    Examples:
        >>> provider = ClaudeCLIProvider(model="claude-sonnet-4-5")
        >>> response = provider.generate("Extract changes from this comment")
        >>> tokens = provider.count_tokens("Some text")
        >>> cost = provider.get_total_cost()  # Always returns 0.0

    Attributes:
        model: Model identifier (may be ignored - CLI controls model)
        timeout: Request timeout in seconds (default: 60)
        total_input_tokens: Cumulative input tokens across all requests (estimated)
        total_output_tokens: Cumulative output tokens across all requests (estimated)

    Note:
        Token counts are estimated using character-based approximation (chars // 4)
        since CLI doesn't expose tokenization. Cost is always $0.00 as subscription
        covers usage.
    """

    DEFAULT_MODEL: ClassVar[str] = "claude-sonnet-4-5"
    DEFAULT_TIMEOUT: ClassVar[int] = 60
    CLI_COMMAND: ClassVar[str] = "claude"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize Claude CLI provider.

        Args:
            model: Model identifier (default: claude-sonnet-4-5, may be ignored by CLI)
            timeout: Request timeout in seconds (default: 60)

        Raises:
            LLMConfigurationError: If Claude CLI is not installed
        """
        self.model = model
        self.timeout = timeout

        # Token usage tracking (estimated via character count)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Verify CLI is available
        self._check_cli_available()

        logger.info(f"Initialized Claude CLI provider: model={model}, timeout={timeout}s")

    def _check_cli_available(self) -> None:
        """Check if Claude CLI is installed and available.

        Raises:
            LLMConfigurationError: If CLI is not found with installation instructions
        """
        cli_path = shutil.which(self.CLI_COMMAND)
        if not cli_path:
            raise LLMConfigurationError(
                "Claude CLI not found. Install it from: https://claude.ai/cli",
                details={"provider": "claude-cli", "cli_command": self.CLI_COMMAND},
            )

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text completion using Claude CLI.

        This method executes the Claude CLI with the provided prompt and returns
        the generated text. It handles timeouts, exit codes, and authentication
        errors appropriately.

        Args:
            prompt: Input prompt for generation
            max_tokens: Maximum tokens to generate (may be ignored by CLI)

        Returns:
            Generated text from Claude CLI

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

        logger.debug(
            f"Sending request to Claude CLI: prompt_length={len(prompt)}, max_tokens={max_tokens}"
        )

        try:
            result = subprocess.run(  # nosec B603, B607  # noqa: S603  # Claude CLI command with validated args
                [self.CLI_COMMAND],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )

            # Handle non-zero exit codes
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"

                # Check for authentication errors
                if result.returncode == 1 and "authentication" in error_msg.lower():
                    raise LLMAuthenticationError(
                        "Claude CLI authentication failed. Run 'claude auth' to authenticate.",
                        details={
                            "provider": "claude-cli",
                            "exit_code": result.returncode,
                            "stderr": error_msg,
                        },
                    ) from None

                raise LLMAPIError(
                    f"Claude CLI failed with exit code {result.returncode}: {error_msg}",
                    details={
                        "provider": "claude-cli",
                        "exit_code": result.returncode,
                        "stderr": error_msg,
                    },
                )

            # Parse response
            response = result.stdout.strip() if result.stdout else ""

            if not response:
                raise LLMAPIError(
                    "Claude CLI returned empty response",
                    details={"provider": "claude-cli", "prompt_length": len(prompt)},
                )

            # Track token usage (estimated)
            estimated_input_tokens = self.count_tokens(prompt)
            estimated_output_tokens = self.count_tokens(response)
            self.total_input_tokens += estimated_input_tokens
            self.total_output_tokens += estimated_output_tokens

            logger.debug(
                f"Claude CLI response received: response_length={len(response)}, "
                f"estimated_tokens={estimated_output_tokens}"
            )

            return response

        except subprocess.TimeoutExpired as e:
            logger.error(f"Claude CLI request timed out after {self.timeout}s")
            raise LLMAPIError(
                f"Claude CLI request timed out after {self.timeout}s",
                details={"provider": "claude-cli", "timeout": self.timeout},
            ) from e
        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"Claude CLI subprocess error: {e}")
            raise LLMAPIError(
                f"Claude CLI subprocess execution failed: {e}",
                details={"provider": "claude-cli", "error": str(e)},
            ) from e

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using character-based estimation.

        Since Claude CLI doesn't expose a tokenization API, this method uses
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

        Claude CLI uses subscription-based pricing, so there's no marginal
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
        logger.debug("Reset Claude CLI usage tracking")
