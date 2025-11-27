"""Integration tests with the real Codex CLI."""

from __future__ import annotations

import pytest

from review_bot_automator.llm.exceptions import LLMAPIError, LLMConfigurationError
from review_bot_automator.llm.providers.codex_cli import CodexCLIProvider

from ._helpers import guarded_call, handle_provider_exception, require_cli

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def codex_cli_provider() -> CodexCLIProvider:
    """Create a Codex CLI provider instance or skip when unavailable."""
    require_cli("codex", "Codex CLI")
    try:
        provider = CodexCLIProvider()
    except (LLMAPIError, LLMConfigurationError) as exc:
        handle_provider_exception(exc, "Codex CLI")
    else:
        provider.reset_usage_tracking()
        return provider
    raise AssertionError("Codex CLI provider setup should not reach this point")


class TestCodexCLIProviderIntegration:
    """Integration tests that hit the real Codex CLI."""

    def test_real_cli_execution(self, codex_cli_provider: CodexCLIProvider) -> None:
        """CLI returns a response."""
        response = guarded_call("Codex CLI", lambda: codex_cli_provider.generate("Say hello"))
        assert isinstance(response, str)
        assert len(response) > 0

    def test_real_token_counting(self, codex_cli_provider: CodexCLIProvider) -> None:
        """CLI estimates token counts."""
        count = guarded_call("Codex CLI", lambda: codex_cli_provider.count_tokens("Hello world"))
        assert count > 0

    def test_real_cost_tracking(self, codex_cli_provider: CodexCLIProvider) -> None:
        """CLI cost tracking remains zero while tokens increase."""
        guarded_call("Codex CLI", lambda: codex_cli_provider.generate("Test prompt"))
        assert codex_cli_provider.get_total_cost() == 0.0
        assert codex_cli_provider.total_input_tokens > 0
        assert codex_cli_provider.total_output_tokens > 0
