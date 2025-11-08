"""Tests for Ollama API provider.

This module tests the Ollama provider implementation including:
- Provider protocol conformance
- Ollama and model availability checking
- Token counting via character estimation
- Cost calculation (always $0.00)
- Retry logic with mocked failures
- Error handling for various failure modes
- Integration tests with real Ollama API (optional, requires Ollama running)
"""

from unittest.mock import Mock, patch

import pytest
import requests

from pr_conflict_resolver.llm.exceptions import (
    LLMAPIError,
    LLMConfigurationError,
)
from pr_conflict_resolver.llm.providers.base import LLMProvider
from pr_conflict_resolver.llm.providers.ollama import OllamaProvider


class TestOllamaProviderProtocol:
    """Test that OllamaProvider conforms to LLMProvider protocol."""

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_provider_implements_protocol(self, mock_get: Mock) -> None:
        """Test that OllamaProvider implements LLMProvider protocol."""
        # Mock Ollama availability and model list
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert isinstance(provider, LLMProvider)

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_provider_has_generate_method(self, mock_get: Mock) -> None:
        """Test that provider has generate() method with correct signature."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert hasattr(provider, "generate")
        assert callable(provider.generate)

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_provider_has_count_tokens_method(self, mock_get: Mock) -> None:
        """Test that provider has count_tokens() method with correct signature."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert hasattr(provider, "count_tokens")
        assert callable(provider.count_tokens)

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_provider_has_get_total_cost_method(self, mock_get: Mock) -> None:
        """Test that provider has get_total_cost() method."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert hasattr(provider, "get_total_cost")
        assert callable(provider.get_total_cost)

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_provider_has_reset_usage_tracking_method(self, mock_get: Mock) -> None:
        """Test that provider has reset_usage_tracking() method."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert hasattr(provider, "reset_usage_tracking")
        assert callable(provider.reset_usage_tracking)


class TestOllamaProviderInitialization:
    """Test OllamaProvider initialization and configuration."""

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_with_valid_params(self, mock_get: Mock) -> None:
        """Test initialization with valid parameters."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "mistral:latest"}]}

        provider = OllamaProvider(
            model="mistral:latest",
            timeout=60,
            base_url="http://localhost:11434",
        )

        assert provider.model == "mistral:latest"
        assert provider.timeout == 60
        assert provider.base_url == "http://localhost:11434"
        assert provider.total_input_tokens == 0
        assert provider.total_output_tokens == 0

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_with_default_model(self, mock_get: Mock) -> None:
        """Test that default model is llama3.3:70b."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.model == "llama3.3:70b"

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_with_default_timeout(self, mock_get: Mock) -> None:
        """Test that default timeout is 120 seconds (for slow local inference)."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.timeout == 120

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_with_default_base_url(self, mock_get: Mock) -> None:
        """Test that default base_url is http://localhost:11434."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.base_url == "http://localhost:11434"

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_strips_trailing_slash_from_base_url(self, mock_get: Mock) -> None:
        """Test that trailing slash is stripped from base_url."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(base_url="http://localhost:11434/")
        assert provider.base_url == "http://localhost:11434"

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_checks_ollama_availability(self, mock_get: Mock) -> None:
        """Test that initialization checks Ollama availability."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        # Should not raise
        OllamaProvider()

        # Verify GET request was made to /api/tags
        assert mock_get.called
        assert "/api/tags" in mock_get.call_args[0][0]

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_checks_model_availability(self, mock_get: Mock) -> None:
        """Test that initialization checks model availability."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [{"name": "llama3.3:70b"}, {"name": "mistral:latest"}]
        }

        # Should not raise for available model
        provider = OllamaProvider(model="mistral:latest")
        assert provider.model == "mistral:latest"

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_raises_on_ollama_not_running(self, mock_get: Mock) -> None:
        """Test that ConnectionError is raised when Ollama is not running."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(LLMAPIError, match="Ollama is not running"):
            OllamaProvider()

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_raises_on_model_not_found(self, mock_get: Mock) -> None:
        """Test that LLMConfigurationError is raised when model is not found."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        with pytest.raises(LLMConfigurationError, match="Model 'nonexistent' not found"):
            OllamaProvider(model="nonexistent")

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_init_error_includes_install_command(self, mock_get: Mock) -> None:
        """Test that model not found error includes ollama pull command."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        with pytest.raises(LLMConfigurationError, match="ollama pull nonexistent"):
            OllamaProvider(model="nonexistent")


class TestOllamaProviderModelChecks:
    """Test Ollama and model availability checking methods."""

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_check_ollama_available_success(self, mock_get: Mock) -> None:
        """Test _check_ollama_available() succeeds when Ollama is running."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        # Should not raise
        provider = OllamaProvider(model="llama3.3:70b")
        provider._check_ollama_available()

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_check_ollama_available_connection_error(self, mock_get: Mock) -> None:
        """Test _check_ollama_available() raises on connection error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(LLMAPIError, match="Ollama is not running"):
            OllamaProvider()

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_check_ollama_available_timeout(self, mock_get: Mock) -> None:
        """Test _check_ollama_available() raises on timeout."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        with pytest.raises(LLMAPIError, match="Ollama did not respond within 5 seconds"):
            OllamaProvider()

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_list_available_models_success(self, mock_get: Mock) -> None:
        """Test _list_available_models() returns model names."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [
                {"name": "llama3.3:70b"},
                {"name": "mistral:latest"},
                {"name": "codellama:13b"},
            ]
        }

        provider = OllamaProvider(model="llama3.3:70b")
        models = provider._list_available_models()

        assert "llama3.3:70b" in models
        assert "mistral:latest" in models
        assert "codellama:13b" in models
        assert len(models) == 3

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_list_available_models_empty(self, mock_get: Mock) -> None:
        """Test _list_available_models() handles empty model list."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": []}

        with pytest.raises(LLMConfigurationError, match="not found"):
            OllamaProvider(model="llama3.3:70b")

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_check_model_available_success(self, mock_get: Mock) -> None:
        """Test _check_model_available() succeeds when model exists."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        # Should not raise
        provider = OllamaProvider(model="llama3.3:70b")
        provider._check_model_available()

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_check_model_available_not_found(self, mock_get: Mock) -> None:
        """Test _check_model_available() raises when model not found."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        with pytest.raises(LLMConfigurationError, match="Model 'nonexistent' not found"):
            OllamaProvider(model="nonexistent")

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_check_model_available_lists_available_models(self, mock_get: Mock) -> None:
        """Test that model not found error lists available models."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [{"name": "llama3.3:70b"}, {"name": "mistral:latest"}]
        }

        with pytest.raises(LLMConfigurationError) as exc_info:
            OllamaProvider(model="nonexistent")

        error_msg = str(exc_info.value)
        assert "Available models:" in error_msg
        assert "llama3.3:70b" in error_msg


class TestOllamaProviderTokenCounting:
    """Test token counting via character estimation."""

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_count_tokens_simple_text(self, mock_get: Mock) -> None:
        """Test count_tokens() with simple text."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        # "Hello world" = 11 chars, 11 // 4 = 2 tokens (estimated)
        tokens = provider.count_tokens("Hello world")
        assert tokens == 2

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_count_tokens_empty_string(self, mock_get: Mock) -> None:
        """Test count_tokens() returns 0 for empty string."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.count_tokens("") == 0

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_count_tokens_long_text(self, mock_get: Mock) -> None:
        """Test count_tokens() with longer text."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        # 400 chars = 100 tokens (estimated)
        text = "x" * 400
        tokens = provider.count_tokens(text)
        assert tokens == 100

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_count_tokens_with_none_raises(self, mock_get: Mock) -> None:
        """Test count_tokens() raises ValueError for None input."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        with pytest.raises(ValueError, match="Text cannot be None"):
            provider.count_tokens(None)  # type: ignore[arg-type]

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_count_tokens_character_estimation(self, mock_get: Mock) -> None:
        """Test that token counting uses ~4 chars per token estimation."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        # Verify the 4:1 ratio
        assert provider.count_tokens("1234") == 1
        assert provider.count_tokens("12345678") == 2
        assert provider.count_tokens("x" * 40) == 10

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_count_tokens_unicode(self, mock_get: Mock) -> None:
        """Test count_tokens() handles unicode characters."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        # Unicode chars count as single characters
        text = "Hello 世界"  # 8 chars = 2 tokens
        tokens = provider.count_tokens(text)
        assert tokens == 2


class TestOllamaProviderCostCalculation:
    """Test cost tracking and calculation."""

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_get_total_cost_returns_zero(self, mock_get: Mock) -> None:
        """Test get_total_cost() always returns 0.0 for local models."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.get_total_cost() == 0.0

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_get_total_cost_after_generation(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test get_total_cost() returns 0.0 even after API calls."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"response": "Generated text response"}

        provider = OllamaProvider()
        provider.generate("test prompt")

        # Cost should still be 0.0 even after generation
        assert provider.get_total_cost() == 0.0

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    def test_reset_usage_tracking(self, mock_get: Mock) -> None:
        """Test reset_usage_tracking() resets token counters."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        # Manually set some usage
        provider.total_input_tokens = 100
        provider.total_output_tokens = 200

        # Reset
        provider.reset_usage_tracking()

        assert provider.total_input_tokens == 0
        assert provider.total_output_tokens == 0


class TestOllamaProviderGenerate:
    """Test text generation with mocked Ollama API."""

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_success(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test successful generation."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"response": "This is a generated response"}

        provider = OllamaProvider()
        result = provider.generate("test prompt", max_tokens=100)

        assert result == "This is a generated response"
        assert mock_post.called

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_tracks_tokens(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that generate() tracks input and output tokens."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "response": "Generated response"  # 18 chars = 4 tokens
        }

        provider = OllamaProvider()
        provider.generate("test", max_tokens=100)  # 4 chars = 1 token

        assert provider.total_input_tokens == 1  # "test" = 4 chars // 4 = 1
        assert provider.total_output_tokens == 4  # 18 chars // 4 = 4

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_empty_prompt_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that empty prompt raises ValueError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            provider.generate("")

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_invalid_max_tokens_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that invalid max_tokens raises ValueError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider.generate("test", max_tokens=0)

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider.generate("test", max_tokens=-10)

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_http_404_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that HTTP 404 raises LLMAPIError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 404
        mock_post.return_value.text = "Model not found"

        provider = OllamaProvider()

        with pytest.raises(LLMAPIError, match="status 404"):
            provider.generate("test")

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_http_500_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that HTTP 500 raises LLMAPIError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Internal server error"

        provider = OllamaProvider()

        with pytest.raises(LLMAPIError, match="status 500"):
            provider.generate("test")

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_empty_response_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that empty response raises LLMAPIError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"response": ""}

        provider = OllamaProvider()

        with pytest.raises(LLMAPIError, match="empty response"):
            provider.generate("test")

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_uses_temperature_zero(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that generate() uses temperature=0 for deterministic output."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"response": "test"}

        provider = OllamaProvider()
        provider.generate("test")

        # Verify temperature=0 in request
        call_args = mock_post.call_args
        assert call_args[1]["json"]["options"]["temperature"] == 0.0

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_disables_streaming(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that generate() disables streaming."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"response": "test"}

        provider = OllamaProvider()
        provider.generate("test")

        # Verify stream=False in request
        call_args = mock_post.call_args
        assert call_args[1]["json"]["stream"] is False

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_sets_max_tokens(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that generate() passes max_tokens to API."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"response": "test"}

        provider = OllamaProvider()
        provider.generate("test", max_tokens=500)

        # Verify num_predict=500 in request options
        call_args = mock_post.call_args
        assert call_args[1]["json"]["options"]["num_predict"] == 500

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_timeout_retries(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that timeout triggers retry logic."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        # First call times out, second succeeds
        mock_post.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            Mock(status_code=200, json=lambda: {"response": "success"}),
        ]

        provider = OllamaProvider()
        result = provider.generate("test")

        assert result == "success"
        assert mock_post.call_count == 2

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_connection_error_retries(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that connection error triggers retry logic."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        # First call connection error, second succeeds
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            Mock(status_code=200, json=lambda: {"response": "success"}),
        ]

        provider = OllamaProvider()
        result = provider.generate("test")

        assert result == "success"
        assert mock_post.call_count == 2

    @patch("pr_conflict_resolver.llm.providers.ollama.requests.get")
    @patch("pr_conflict_resolver.llm.providers.ollama.requests.post")
    def test_generate_retry_exhaustion_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that retry exhaustion raises LLMAPIError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        # All attempts time out
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        provider = OllamaProvider()

        with pytest.raises(LLMAPIError, match="after 3 retry attempts"):
            provider.generate("test")

        # Should have tried 3 times
        assert mock_post.call_count == 3


@pytest.mark.integration
class TestOllamaProviderIntegration:
    """Integration tests with real Ollama API.

    These tests require:
    1. Ollama running locally: ollama serve
    2. Model available: ollama pull llama3.3:70b

    Tests are skipped if Ollama is not available.
    """

    def test_ollama_available(self) -> None:
        """Test connection to real Ollama instance."""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            assert response.status_code == 200
        except Exception:
            pytest.skip("Ollama not running at http://localhost:11434")

    def test_real_generation(self) -> None:
        """Test real generation with Ollama API."""
        try:
            provider = OllamaProvider(model="llama3.3:70b", timeout=30)
        except (LLMAPIError, LLMConfigurationError):
            pytest.skip("Ollama not available or model not found")

        prompt = "Respond with just the word 'success'"
        result = provider.generate(prompt, max_tokens=50)

        assert result
        assert len(result) > 0
        assert provider.total_input_tokens > 0
        assert provider.total_output_tokens > 0

    def test_real_cost_tracking(self) -> None:
        """Test cost tracking with real API calls."""
        try:
            provider = OllamaProvider(model="llama3.3:70b", timeout=30)
        except (LLMAPIError, LLMConfigurationError):
            pytest.skip("Ollama not available or model not found")

        provider.generate("Test prompt", max_tokens=50)

        # Cost should always be $0.00
        assert provider.get_total_cost() == 0.0
        # But tokens should be tracked
        assert provider.total_input_tokens > 0
        assert provider.total_output_tokens > 0
