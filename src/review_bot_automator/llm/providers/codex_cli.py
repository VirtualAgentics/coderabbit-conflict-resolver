# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Codex CLI provider implementation.

This module provides the Codex CLI integration for LLM text generation.
It includes:
- CLI availability checking on initialization
- Subprocess execution with timeout handling
- Character-based token estimation
- Cost tracking (always $0.00 - subscription covered)
- Comprehensive error handling

The provider uses subprocess to execute the Codex CLI and implements
the LLMProvider protocol for type safety and polymorphic usage.
"""

from typing import ClassVar

from review_bot_automator.llm.providers.cli_base import CLIProviderBase


class CodexCLIProvider(CLIProviderBase):
    """Codex CLI provider for LLM text generation.

    This provider implements the LLMProvider protocol and provides access to
    Codex models via the Codex CLI. It includes:
    - CLI availability checking on initialization
    - Subprocess execution with timeout handling
    - Character-based token estimation
    - Cost tracking (always $0.00 - subscription covered)
    - Comprehensive error handling

    The provider requires Codex CLI to be installed and authenticated.
    No API key is required (authenticated via CLI login).

    Examples:
        >>> provider = CodexCLIProvider(model="codex-latest")
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

    CLI_COMMAND: ClassVar[str] = "codex"
    DEFAULT_MODEL: ClassVar[str] = "codex-latest"

    def _get_provider_name(self) -> str:
        """Get provider name for error messages.

        Returns:
            str: Provider name "Codex"
        """
        return "Codex"

    def _get_provider_id(self) -> str:
        """Get provider identifier for error details.

        Returns:
            str: Provider identifier "codex-cli"
        """
        return "codex-cli"

    def _get_install_url(self) -> str:
        """Get installation URL for error messages.

        Returns:
            str: Installation URL "https://codex.ai/cli"
        """
        return "https://codex.ai/cli"

    def _get_auth_command(self) -> str:
        """Get authentication command for error messages.

        Returns:
            str: Authentication command "codex auth"
        """
        return "codex auth"

    def _get_cli_command(self) -> list[str]:
        """Get Codex CLI command for non-interactive execution.

        Returns the full CLI command with the "exec" subcommand for non-interactive
        mode, which allows the CLI to run without requiring a TTY. This enables
        the provider to work in CI/CD environments and automated testing.

        Returns:
            list[str]: ["codex", "exec"] for non-interactive execution
        """
        return ["codex", "exec"]
