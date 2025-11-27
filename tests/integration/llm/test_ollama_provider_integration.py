"""Integration tests with a real local Ollama instance.

Set OLLAMA_MODEL_NAME (default: llama2:7b) and ensure the model is pulled before running.
"""

from __future__ import annotations

import os

import pytest
import requests

from review_bot_automator.llm.exceptions import LLMAPIError, LLMConfigurationError
from review_bot_automator.llm.providers.ollama import OllamaProvider

from ._helpers import guarded_call, handle_provider_exception

pytestmark = pytest.mark.integration

MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "llama2:7b")
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"


@pytest.fixture(scope="module")
def ollama_provider() -> OllamaProvider:
    """Create an Ollama provider instance or skip when unavailable."""
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=5)
        if response.status_code != 200:
            pytest.skip(f"Ollama healthy endpoint returned {response.status_code}")
    except Exception as exc:
        pytest.skip(f"Ollama not running at {OLLAMA_TAGS_URL}: {exc}")

    try:
        provider = OllamaProvider(model=MODEL_NAME, timeout=30)
    except (LLMAPIError, LLMConfigurationError) as exc:
        handle_provider_exception(exc, "Ollama")
    else:
        provider.reset_usage_tracking()
        return provider
    raise AssertionError("Ollama provider setup should not reach this point")


class TestOllamaProviderIntegration:
    """Integration tests that hit the real Ollama HTTP API."""

    def test_real_api_availability(self, ollama_provider: OllamaProvider) -> None:
        """Ensure the Ollama instance responds to basic availability checks."""
        tags_response = requests.get(OLLAMA_TAGS_URL, timeout=5)
        assert tags_response.status_code == 200
        assert tags_response.json().get("models") is not None

    def test_real_generation(self, ollama_provider: OllamaProvider) -> None:
        """Model generates a non-empty response."""
        prompt = "Respond with just the word 'success'"
        initial_input = ollama_provider.total_input_tokens
        initial_output = ollama_provider.total_output_tokens
        result = guarded_call("Ollama", lambda: ollama_provider.generate(prompt, max_tokens=50))

        assert result
        assert len(result) > 0
        assert ollama_provider.total_input_tokens > initial_input
        assert ollama_provider.total_output_tokens > initial_output

    def test_real_cost_tracking(self, ollama_provider: OllamaProvider) -> None:
        """Cost stays zero while token counters increase."""
        initial_input = ollama_provider.total_input_tokens
        initial_output = ollama_provider.total_output_tokens
        guarded_call("Ollama", lambda: ollama_provider.generate("Test prompt", max_tokens=50))

        assert ollama_provider.get_total_cost() == 0.0
        assert ollama_provider.total_input_tokens > initial_input
        assert ollama_provider.total_output_tokens > initial_output
