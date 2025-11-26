"""Integration tests with the real Claude CLI."""

from __future__ import annotations

import pytest

from review_bot_automator.llm.exceptions import LLMAPIError, LLMConfigurationError
from review_bot_automator.llm.providers.claude_cli import ClaudeCLIProvider

from ._helpers import guarded_call, handle_provider_exception, require_cli

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def claude_cli_provider() -> ClaudeCLIProvider:
    """Create a Claude CLI provider instance or skip when unavailable."""
    require_cli("claude", "Claude CLI")
    try:
        provider = ClaudeCLIProvider()
    except (LLMAPIError, LLMConfigurationError) as exc:
        handle_provider_exception(exc, "Claude CLI")
    else:
        provider.reset_usage_tracking()
        return provider
    # handle_provider_exception will skip for auth/quota/availability; reaching here
    # means neither skip path ran, so this defensive assertion should be unreachable.
    raise AssertionError("Claude CLI provider setup should not reach this point")


class TestClaudeCLIProviderIntegration:
    """Integration tests that hit the real Claude CLI."""

    def test_real_cli_execution(self, claude_cli_provider: ClaudeCLIProvider) -> None:
        """CLI returns a response."""
        response = guarded_call("Claude CLI", lambda: claude_cli_provider.generate("Say hello"))
        assert isinstance(response, str)
        assert len(response) > 0

    def test_real_token_counting(self, claude_cli_provider: ClaudeCLIProvider) -> None:
        """CLI estimates token counts."""
        count = guarded_call("Claude CLI", lambda: claude_cli_provider.count_tokens("Hello world"))
        assert count > 0

    def test_real_cost_tracking(self, claude_cli_provider: ClaudeCLIProvider) -> None:
        """CLI cost tracking remains zero while tokens increase."""
        initial_input = claude_cli_provider.total_input_tokens
        initial_output = claude_cli_provider.total_output_tokens

        guarded_call("Claude CLI", lambda: claude_cli_provider.generate("Test prompt"))

        assert claude_cli_provider.get_total_cost() == 0.0
        assert claude_cli_provider.total_input_tokens > initial_input
        assert claude_cli_provider.total_output_tokens > initial_output
