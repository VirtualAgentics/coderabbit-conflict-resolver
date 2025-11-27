"""Integration tests with the real OpenAI API."""

from __future__ import annotations

import json

import pytest

from review_bot_automator.llm.providers.openai_api import OpenAIAPIProvider

from ._helpers import guarded_call, require_env_var

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def openai_provider() -> OpenAIAPIProvider:
    """Create a real OpenAI provider instance or skip when unavailable."""
    api_key = require_env_var("OPENAI_API_KEY", "OpenAI")
    provider = OpenAIAPIProvider(api_key=api_key, model="gpt-4o-mini")

    # Sanity check credentials/budget with a minimal call, then reset counters.
    # Note: OpenAI requires the word "json" in the prompt when using json_object response_format
    guarded_call(
        "OpenAI",
        lambda: provider.generate('Return this JSON exactly: {"status": "ok"}', max_tokens=20),
    )
    provider.reset_usage_tracking()
    return provider


class TestOpenAIProviderIntegration:
    """Integration tests that hit the real OpenAI API."""

    def test_real_api_simple_generation(self, openai_provider: OpenAIAPIProvider) -> None:
        """LLM returns JSON and tracks tokens."""
        # Note: OpenAI requires the word "json" in the prompt when using json_object response_format
        prompt = 'Return this JSON object: {"test": "success"}'

        result = guarded_call("OpenAI", lambda: openai_provider.generate(prompt, max_tokens=50))

        start = result.find("{")
        end = result.rfind("}")
        json_blob = result[start : end + 1] if start != -1 and end != -1 and end > start else result

        parsed = json.loads(json_blob)
        assert isinstance(parsed, dict)
        assert openai_provider.total_input_tokens > 0
        assert openai_provider.total_output_tokens > 0

    def test_real_api_cost_tracking(self, openai_provider: OpenAIAPIProvider) -> None:
        """Cost tracking increments after a live call."""
        # Note: OpenAI requires the word "json" in the prompt when using json_object response_format
        guarded_call(
            "OpenAI",
            lambda: openai_provider.generate(
                'Return a JSON object with: {"test": "data"}', max_tokens=50
            ),
        )

        cost = openai_provider.get_total_cost()
        assert cost > 0.0
        assert cost < 0.05  # Should be inexpensive for small prompt
