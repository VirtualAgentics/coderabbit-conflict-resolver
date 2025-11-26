"""Integration tests with the real Anthropic API."""

from __future__ import annotations

import os

import pytest

from review_bot_automator.llm.providers.anthropic_api import AnthropicAPIProvider

from ._helpers import guarded_call, require_env_var

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def anthropic_provider() -> AnthropicAPIProvider:
    """Create a real Anthropic provider instance or skip when unavailable."""
    api_key = require_env_var("ANTHROPIC_API_KEY", "Anthropic")
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")
    provider = AnthropicAPIProvider(api_key=api_key, model=model)

    # Sanity check credentials and budget with a cheap call.
    guarded_call("Anthropic", lambda: provider.count_tokens("ping"))
    provider.reset_usage_tracking()
    return provider


class TestAnthropicProviderIntegration:
    """Integration tests that hit the real Anthropic API."""

    def test_real_api_simple_generation(self, anthropic_provider: AnthropicAPIProvider) -> None:
        """LLM generates a minimal JSON payload."""
        result = guarded_call(
            "Anthropic",
            lambda: anthropic_provider.generate("Say 'test' in JSON format", max_tokens=100),
        )

        assert result
        assert isinstance(result, str)
        assert len(result) > 0

    def test_real_api_cost_tracking(self, anthropic_provider: AnthropicAPIProvider) -> None:
        """Cost tracking increments after a live call."""
        guarded_call(
            "Anthropic",
            lambda: anthropic_provider.generate("Count to 5 in JSON", max_tokens=100),
        )

        cost = anthropic_provider.get_total_cost()
        assert cost > 0.0
        assert anthropic_provider.total_input_tokens > 0
        assert anthropic_provider.total_output_tokens > 0

    def test_real_api_token_counting(self, anthropic_provider: AnthropicAPIProvider) -> None:
        """Token counting uses the real API endpoint."""
        count = guarded_call("Anthropic", lambda: anthropic_provider.count_tokens("Hello, world!"))
        assert count > 0
        assert isinstance(count, int)
