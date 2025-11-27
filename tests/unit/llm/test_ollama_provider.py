"""Tests for Ollama API provider.

This module tests the Ollama provider implementation including:
- Provider protocol conformance
- Ollama and model availability checking
- Token counting via character estimation
- Cost calculation (always $0.00)
- Retry logic with mocked failures
- Error handling for various failure modes
Mocking Strategy:
    Unit test classes use the 'patch_session_for_module_mocks' fixture to enable
    backward-compatible mocking. This allows tests to use @patch("requests.get/post")
    decorators while the implementation uses requests.Session() for connection pooling.

    Example:
        @pytest.mark.usefixtures("patch_session_for_module_mocks")
        class TestOllamaProviderInitialization:
            @patch("review_bot_automator.llm.providers.ollama.requests.get")
            def test_init_with_valid_params(self, mock_get: Mock) -> None:
                # Test code that mocks requests.get
"""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
import requests
from requests.adapters import HTTPAdapter

from review_bot_automator.llm.exceptions import (
    LLMAPIError,
    LLMConfigurationError,
)
from review_bot_automator.llm.providers.base import LLMProvider
from review_bot_automator.llm.providers.ollama import OllamaProvider


# Fixture to patch Session's methods to forward to module-level patched functions
# This allows existing tests that patch requests.get/post to work with session-based implementation
@pytest.fixture
def patch_session_for_module_mocks() -> Generator[None, None, None]:
    """Patch Session methods to delegate to module-level mocked functions.

    This fixture enables backward compatibility with existing tests that patch
    requests.get/post at the module level. Since OllamaProvider now uses
    requests.Session(), we intercept Session's __init__ and replace its get/post
    methods to delegate to module-level functions that can be mocked by tests.

    This approach preserves session state while allowing existing test mocks to work.

    Usage:
        @pytest.mark.usefixtures("patch_session_for_module_mocks")
        class TestOllamaProviderInitialization:
            # Tests that use @patch("requests.get/post") decorators

    Note:
        Integration tests should NOT use this fixture as they work with real requests.

    Yields:
        None
    """
    original_session_init = requests.Session.__init__

    def patched_session_init(self: requests.Session) -> None:
        original_session_init(self)

        # Replace with module-level functions that can be mocked by tests
        # These delegate to requests.get/post which tests can mock
        # Using assignments instead of lambda to avoid suppression warnings
        def session_get(*args: object, **kwargs: object) -> object:
            return requests.get(*args, **kwargs)  # type: ignore[arg-type]  # noqa: S113

        def session_post(*args: object, **kwargs: object) -> object:
            return requests.post(*args, **kwargs)  # type: ignore[arg-type]  # noqa: S113

        self.get = session_get  # type: ignore[method-assign,assignment]
        self.post = session_post  # type: ignore[method-assign,assignment]

    with patch.object(requests.Session, "__init__", patched_session_init):
        yield


@pytest.mark.usefixtures("patch_session_for_module_mocks")
class TestOllamaProviderProtocol:
    """Test that OllamaProvider conforms to LLMProvider protocol."""

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_provider_implements_protocol(self, mock_get: Mock) -> None:
        """Test that OllamaProvider implements LLMProvider protocol."""
        # Mock Ollama availability and model list
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert isinstance(provider, LLMProvider)

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_provider_has_generate_method(self, mock_get: Mock) -> None:
        """Test that provider has generate() method with correct signature."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert hasattr(provider, "generate")
        assert callable(provider.generate)

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_provider_has_count_tokens_method(self, mock_get: Mock) -> None:
        """Test that provider has count_tokens() method with correct signature."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert hasattr(provider, "count_tokens")
        assert callable(provider.count_tokens)

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_provider_has_get_total_cost_method(self, mock_get: Mock) -> None:
        """Test that provider has get_total_cost() method."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert hasattr(provider, "get_total_cost")
        assert callable(provider.get_total_cost)

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_provider_has_reset_usage_tracking_method(self, mock_get: Mock) -> None:
        """Test that provider has reset_usage_tracking() method."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(model="llama3.3:70b")
        assert hasattr(provider, "reset_usage_tracking")
        assert callable(provider.reset_usage_tracking)


@pytest.mark.usefixtures("patch_session_for_module_mocks")
class TestOllamaProviderInitialization:
    """Test OllamaProvider initialization and configuration."""

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_with_default_model(self, mock_get: Mock) -> None:
        """Test that default model is llama3.3:70b."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.model == "llama3.3:70b"

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_with_default_timeout(self, mock_get: Mock) -> None:
        """Test that default timeout is 120 seconds (for slow local inference)."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.timeout == 120

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_with_default_base_url(self, mock_get: Mock) -> None:
        """Test that default base_url is http://localhost:11434."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.base_url == "http://localhost:11434"

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_strips_trailing_slash_from_base_url(self, mock_get: Mock) -> None:
        """Test that trailing slash is stripped from base_url."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider(base_url="http://localhost:11434/")
        assert provider.base_url == "http://localhost:11434"

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_checks_ollama_availability(self, mock_get: Mock) -> None:
        """Test that initialization checks Ollama availability."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        # Should not raise
        OllamaProvider()

        # Verify GET requests were made to both /api/ps (GPU detection) and /api/tags (model check)
        assert mock_get.called
        assert mock_get.call_count >= 2
        call_urls = [call[0][0] for call in mock_get.call_args_list]
        assert any("/api/ps" in url for url in call_urls), "GPU detection call to /api/ps expected"
        assert any(
            "/api/tags" in url for url in call_urls
        ), "Model check call to /api/tags expected"

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_checks_model_availability(self, mock_get: Mock) -> None:
        """Test that initialization checks model availability."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [{"name": "llama3.3:70b"}, {"name": "mistral:latest"}]
        }

        # Should not raise for available model
        provider = OllamaProvider(model="mistral:latest")
        assert provider.model == "mistral:latest"

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_raises_on_ollama_not_running(self, mock_get: Mock) -> None:
        """Test that ConnectionError is raised when Ollama is not running."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(LLMAPIError, match="Ollama is not running"):
            OllamaProvider()

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_raises_on_model_not_found(self, mock_get: Mock) -> None:
        """Test that LLMConfigurationError is raised when model is not found."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        with pytest.raises(LLMConfigurationError, match="Model 'nonexistent' not found"):
            OllamaProvider(model="nonexistent")

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_error_includes_install_command(self, mock_get: Mock) -> None:
        """Test that model not found error includes ollama pull command."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        with pytest.raises(LLMConfigurationError, match="ollama pull nonexistent"):
            OllamaProvider(model="nonexistent")


@pytest.mark.usefixtures("patch_session_for_module_mocks")
class TestOllamaProviderModelChecks:
    """Test Ollama and model availability checking methods."""

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_check_ollama_available_success(self, mock_get: Mock) -> None:
        """Test _check_ollama_available() succeeds when Ollama is running."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        # Should not raise
        provider = OllamaProvider(model="llama3.3:70b")
        provider._check_ollama_available()

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_check_ollama_available_connection_error(self, mock_get: Mock) -> None:
        """Test _check_ollama_available() raises on connection error."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(LLMAPIError, match="Ollama is not running"):
            OllamaProvider()

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_check_ollama_available_timeout(self, mock_get: Mock) -> None:
        """Test _check_ollama_available() raises on timeout."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        with pytest.raises(LLMAPIError, match="Ollama did not respond within 5 seconds"):
            OllamaProvider()

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_list_available_models_empty(self, mock_get: Mock) -> None:
        """Test _list_available_models() handles empty model list."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": []}

        with pytest.raises(LLMConfigurationError, match="not found"):
            OllamaProvider(model="llama3.3:70b")

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_check_model_available_success(self, mock_get: Mock) -> None:
        """Test _check_model_available() succeeds when model exists."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        # Should not raise
        provider = OllamaProvider(model="llama3.3:70b")
        provider._check_model_available()

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_check_model_available_not_found(self, mock_get: Mock) -> None:
        """Test _check_model_available() raises when model not found."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        with pytest.raises(LLMConfigurationError, match="Model 'nonexistent' not found"):
            OllamaProvider(model="nonexistent")

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
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


@pytest.mark.usefixtures("patch_session_for_module_mocks")
class TestOllamaProviderTokenCounting:
    """Test token counting via character estimation."""

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_count_tokens_simple_text(self, mock_get: Mock) -> None:
        """Test count_tokens() with simple text."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        # "Hello world" = 11 chars, 11 // 4 = 2 tokens (estimated)
        tokens = provider.count_tokens("Hello world")
        assert tokens == 2

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_count_tokens_empty_string(self, mock_get: Mock) -> None:
        """Test count_tokens() returns 0 for empty string."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.count_tokens("") == 0

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_count_tokens_long_text(self, mock_get: Mock) -> None:
        """Test count_tokens() with longer text."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        # 400 chars = 100 tokens (estimated)
        text = "x" * 400
        tokens = provider.count_tokens(text)
        assert tokens == 100

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_count_tokens_with_none_raises(self, mock_get: Mock) -> None:
        """Test count_tokens() raises ValueError for None input."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        with pytest.raises(ValueError, match="Text cannot be None"):
            provider.count_tokens(None)  # type: ignore[arg-type]

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_count_tokens_character_estimation(self, mock_get: Mock) -> None:
        """Test that token counting uses ~4 chars per token estimation."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        # Verify the 4:1 ratio
        assert provider.count_tokens("1234") == 1
        assert provider.count_tokens("12345678") == 2
        assert provider.count_tokens("x" * 40) == 10

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_count_tokens_unicode(self, mock_get: Mock) -> None:
        """Test count_tokens() handles unicode characters."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        # Unicode chars count as single characters
        text = "Hello 世界"  # 8 chars = 2 tokens
        tokens = provider.count_tokens(text)
        assert tokens == 2


@pytest.mark.usefixtures("patch_session_for_module_mocks")
class TestOllamaProviderCostCalculation:
    """Test cost tracking and calculation."""

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_get_total_cost_returns_zero(self, mock_get: Mock) -> None:
        """Test get_total_cost() always returns 0.0 for local models."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()
        assert provider.get_total_cost() == 0.0

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
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


@pytest.mark.usefixtures("patch_session_for_module_mocks")
class TestOllamaProviderGenerate:
    """Test text generation with mocked Ollama API."""

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    def test_generate_empty_prompt_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that empty prompt raises ValueError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            provider.generate("")

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    def test_generate_invalid_max_tokens_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that invalid max_tokens raises ValueError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        provider = OllamaProvider()

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider.generate("test", max_tokens=0)

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider.generate("test", max_tokens=-10)

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    def test_generate_http_404_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that HTTP 404 raises LLMAPIError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 404
        mock_post.return_value.text = "Model not found"

        provider = OllamaProvider()

        with pytest.raises(LLMAPIError, match="status 404"):
            provider.generate("test")

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    def test_generate_http_500_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that HTTP 500 raises LLMAPIError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 500
        mock_post.return_value.text = "Internal server error"

        provider = OllamaProvider()

        with pytest.raises(LLMAPIError, match="status 500"):
            provider.generate("test")

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    def test_generate_empty_response_raises(self, mock_post: Mock, mock_get: Mock) -> None:
        """Test that empty response raises LLMAPIError."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"models": [{"name": "llama3.3:70b"}]}

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"response": ""}

        provider = OllamaProvider()

        with pytest.raises(LLMAPIError, match="empty response"):
            provider.generate("test")

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
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

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    @patch("review_bot_automator.llm.providers.ollama.requests.post")
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


@pytest.mark.usefixtures("patch_session_for_module_mocks")
class TestOllamaProviderSessionManagement:
    """Test HTTP session management and connection pooling."""

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_creates_session(self, mock_get: Mock) -> None:
        """Test that __init__ creates a requests.Session instance."""
        # Mock successful Ollama availability check
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_response

        provider = OllamaProvider()

        # Verify session was created
        assert hasattr(provider, "session")
        assert isinstance(provider.session, requests.Session)

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_init_configures_http_adapter(self, mock_get: Mock) -> None:
        """Test that __init__ configures HTTPAdapter with connection pooling."""
        # Mock successful checks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_response

        provider = OllamaProvider()

        # Verify adapters are mounted for http:// and https://
        assert "http://" in provider.session.adapters
        assert "https://" in provider.session.adapters

        # Verify HTTPAdapter configuration
        http_adapter = provider.session.adapters["http://"]
        assert isinstance(http_adapter, HTTPAdapter)

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_uses_session_for_get_requests(self, mock_get: Mock) -> None:
        """Test that availability checks use session.get() instead of requests.get()."""
        # Mock successful checks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_response

        OllamaProvider()

        # Verify requests.get was called (via session delegation)
        assert mock_get.call_count >= 2  # At least 2 calls (availability + model list)

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_uses_session_for_post_requests(self, mock_get: Mock, mock_post: Mock) -> None:
        """Test that generate() uses session.post() instead of requests.post()."""
        # Mock initialization checks
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_get_response

        # Mock successful generation
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"response": "Test response"}
        mock_post.return_value = mock_post_response

        provider = OllamaProvider()
        result = provider.generate("Test prompt")

        # Verify requests.post was called (via session delegation)
        assert mock_post.call_count == 1
        assert result == "Test response"

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_close_method_closes_session(self, mock_get: Mock) -> None:
        """Test that close() method closes the HTTP session."""
        # Mock successful checks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_response

        provider = OllamaProvider()

        # Mock session.close() to verify it gets called
        with patch.object(provider.session, "close") as mock_close:
            provider.close()
            mock_close.assert_called_once()

    def test_close_method_safe_without_session(self) -> None:
        """Test that close() is safe to call even if session doesn't exist."""
        provider = object.__new__(OllamaProvider)

        # Should not raise an exception
        provider.close()

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_context_manager_enters_correctly(self, mock_get: Mock) -> None:
        """Test that __enter__ returns the provider instance."""
        # Mock successful checks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_response

        provider = OllamaProvider()
        result = provider.__enter__()

        # Verify __enter__ returns self
        assert result is provider

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_context_manager_closes_session_on_exit(self, mock_get: Mock) -> None:
        """Test that __exit__ closes the session."""
        # Mock successful checks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_response

        provider = OllamaProvider()

        # Mock session.close() to verify it gets called on context exit
        mock_session_close = Mock()
        provider.session.close = mock_session_close  # type: ignore[method-assign]

        with provider:
            assert provider.session is not None

        # Verify close() was called on context exit
        mock_session_close.assert_called_once()

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_session_reuses_connections(self, mock_get: Mock, mock_post: Mock) -> None:
        """Test that multiple requests reuse the same session connection."""
        # Mock initialization checks
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_get_response

        # Mock successful generation
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"response": "Test response"}
        mock_post.return_value = mock_post_response

        provider = OllamaProvider()

        # Make multiple generate calls
        provider.generate("test prompt 1", max_tokens=100)
        provider.generate("test prompt 2", max_tokens=100)
        provider.generate("test prompt 3", max_tokens=100)

        # Verify all three POST requests were made through session delegation
        assert mock_post.call_count == 3

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_context_manager_closes_on_exception(self, mock_get: Mock) -> None:
        """Test that __exit__ closes session even when exception occurs."""
        # Mock successful checks
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_response

        provider = OllamaProvider()

        # Mock session.close() to verify it gets called on exception exit
        mock_session_close = Mock()
        provider.session.close = mock_session_close  # type: ignore[method-assign]

        try:
            with provider:
                assert provider.session is not None
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify close() was called on context exit even with exception
        mock_session_close.assert_called_once()


@pytest.mark.usefixtures("patch_session_for_module_mocks")
class TestOllamaProviderAutoDownload:
    """Test auto-download functionality for models."""

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_auto_download_enabled_downloads_missing_model(
        self, mock_get: Mock, mock_post: Mock
    ) -> None:
        """Test that auto_download=True downloads missing models and verifies availability."""
        # Mock Ollama is available and model checks
        mock_get_response = Mock()
        mock_get_response.status_code = 200

        # Mock three GET calls:
        # 1. Ollama availability check (doesn't call .json(), just checks status)
        # 2. Model availability check (calls .json(), returns empty - model not available)
        # 3. Post-download verification (calls .json(), returns model - now available)
        mock_get_response.json.side_effect = [
            {"models": []},  # Model not available initially (.json() call #1)
            # Model available after download (.json() call #2)
            {"models": [{"name": "qwen2.5-coder:7b"}]},
        ]
        mock_get.return_value = mock_get_response

        # Mock successful download
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.iter_lines.return_value = iter(
            [b'{"status":"pulling"}', b'{"status":"success"}']
        )
        mock_post.return_value = mock_post_response

        # Initialize with auto_download=True
        _provider = OllamaProvider(model="qwen2.5-coder:7b", auto_download=True)

        # Verify download was attempted
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "api/pull" in call_args[0][0]
        assert call_args[1]["json"] == {"name": "qwen2.5-coder:7b"}

        # Verify we made 4 GET calls:
        # GPU detection, availability, initial check, post-download verification
        assert mock_get.call_count == 4

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_auto_download_disabled_raises_error_for_missing_model(self, mock_get: Mock) -> None:
        """Test that auto_download=False raises error for missing models."""
        # Mock Ollama is available but model is not
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "other-model:7b"}]}
        mock_get.return_value = mock_get_response

        # Initialize with auto_download=False (default)
        with pytest.raises(LLMConfigurationError) as exc_info:
            OllamaProvider(model="qwen2.5-coder:7b", auto_download=False)

        assert "qwen2.5-coder:7b" in str(exc_info.value)
        assert "ollama pull" in str(exc_info.value)

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_download_model_streams_response(self, mock_get: Mock, mock_post: Mock) -> None:
        """Test that _download_model consumes streaming response."""
        # Mock Ollama is available
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "qwen2.5-coder:7b"}]}
        mock_get.return_value = mock_get_response

        provider = OllamaProvider(model="qwen2.5-coder:7b")

        # Mock streaming download
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        stream_lines = [
            b'{"status":"pulling manifest"}',
            b'{"status":"downloading","completed":50,"total":100}',
            b'{"status":"downloading","completed":100,"total":100}',
            b'{"status":"success"}',
        ]
        mock_post_response.iter_lines.return_value = iter(stream_lines)
        mock_post.return_value = mock_post_response

        # Download model
        result = provider._download_model("test-model:7b")

        assert result is True
        mock_post.assert_called_once()
        assert mock_post_response.iter_lines.called

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_download_model_handles_failure(self, mock_get: Mock, mock_post: Mock) -> None:
        """Test that _download_model handles download failures."""
        # Mock Ollama is available
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "qwen2.5-coder:7b"}]}
        mock_get.return_value = mock_get_response

        provider = OllamaProvider(model="qwen2.5-coder:7b")

        # Mock failed download
        mock_post_response = Mock()
        mock_post_response.status_code = 404
        mock_post_response.text = "Model not found"
        mock_post.return_value = mock_post_response

        # Download should raise error
        with pytest.raises(LLMAPIError) as exc_info:
            provider._download_model("nonexistent-model:7b")

        assert "nonexistent-model:7b" in str(exc_info.value)
        assert "404" in str(exc_info.value)

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_download_model_timeout_error(self, mock_get: Mock, mock_post: Mock) -> None:
        """Test that _download_model handles timeout errors."""
        # Mock Ollama is available
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "qwen2.5-coder:7b"}]}
        mock_get.return_value = mock_get_response

        provider = OllamaProvider(model="qwen2.5-coder:7b")

        # Mock timeout during download
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        # Download should raise error with helpful message
        with pytest.raises(LLMAPIError) as exc_info:
            provider._download_model("large-model:70b")

        assert "timed out" in str(exc_info.value).lower()
        assert "large-model:70b" in str(exc_info.value)

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_auto_download_failure_raises_configuration_error(
        self, mock_get: Mock, mock_post: Mock
    ) -> None:
        """Test that auto-download failure raises LLMConfigurationError with helpful message."""
        # Mock Ollama is available
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": []}  # Model not available
        mock_get.return_value = mock_get_response

        # Mock failed download
        mock_post_response = Mock()
        mock_post_response.status_code = 404
        mock_post_response.text = "Model not found in registry"
        mock_post.return_value = mock_post_response

        # Initialize with auto_download=True - should fail and provide manual instructions
        with pytest.raises(LLMConfigurationError) as exc_info:
            OllamaProvider(model="invalid-model:7b", auto_download=True)

        error_msg = str(exc_info.value)
        assert "invalid-model:7b" in error_msg
        assert "auto-download failed" in error_msg.lower()
        assert "ollama pull" in error_msg

    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_auto_download_parameter_default_is_false(self, mock_get: Mock) -> None:
        """Test that auto_download defaults to False."""
        # Mock Ollama is available with model
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "test-model:7b"}]}
        mock_get.return_value = mock_get_response

        provider = OllamaProvider(model="test-model:7b")

        assert provider.auto_download is False

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_get_model_info_returns_model_details(self, mock_get: Mock, mock_post: Mock) -> None:
        """Test that _get_model_info returns model information."""
        # Mock Ollama is available
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "test-model:7b"}]}
        mock_get.return_value = mock_get_response

        provider = OllamaProvider(model="test-model:7b")

        # Mock model info response
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        model_info = {
            "modelfile": "FROM llama3.3:70b",
            "parameters": "num_ctx 2048",
            "template": "...",
        }
        mock_post_response.json.return_value = model_info
        mock_post.return_value = mock_post_response

        # Get model info
        info = provider._get_model_info("test-model:7b")

        assert info == model_info
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "api/show" in call_args[0][0]

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_get_model_info_returns_none_for_nonexistent_model(
        self, mock_get: Mock, mock_post: Mock
    ) -> None:
        """Test that _get_model_info returns None for non-existent models."""
        # Mock Ollama is available
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "test-model:7b"}]}
        mock_get.return_value = mock_get_response

        provider = OllamaProvider(model="test-model:7b")

        # Mock 404 response for non-existent model
        mock_post_response = Mock()
        mock_post_response.status_code = 404
        mock_post.return_value = mock_post_response

        # Get model info should return None
        info = provider._get_model_info("nonexistent-model:7b")

        assert info is None

    def test_list_recommended_models_returns_list(self) -> None:
        """Test that list_recommended_models returns a list of recommendations."""
        recommendations = OllamaProvider.list_recommended_models()

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # Verify structure of each recommendation
        for model in recommendations:
            assert "name" in model
            assert "size" in model
            assert "speed" in model
            assert "quality" in model
            assert "description" in model

    def test_list_recommended_models_includes_default_model(self) -> None:
        """Test that list_recommended_models includes the default preset model."""
        recommendations = OllamaProvider.list_recommended_models()

        # qwen2.5-coder:7b should be in recommendations
        model_names = [m["name"] for m in recommendations]
        assert "qwen2.5-coder:7b" in model_names

        # Find the qwen2.5-coder:7b entry
        qwen_model = next(m for m in recommendations if m["name"] == "qwen2.5-coder:7b")
        assert (
            "default" in qwen_model["description"].lower()
            or "best balance" in qwen_model["description"].lower()
        )

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_auto_download_with_closed_provider_raises_error(
        self, mock_get: Mock, mock_post: Mock
    ) -> None:
        """Test that auto-download with closed provider raises error."""
        # Mock Ollama is available
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "test-model:7b"}]}
        mock_get.return_value = mock_get_response

        provider = OllamaProvider(model="test-model:7b")
        provider.close()

        # Attempt to download model with closed provider
        with pytest.raises(LLMAPIError) as exc_info:
            provider._download_model("another-model:7b")

        assert "closed" in str(exc_info.value).lower()


@pytest.mark.usefixtures("patch_session_for_module_mocks")
class TestOllamaProviderLatencyTracking:
    """Tests for latency tracking methods."""

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_get_last_request_latency_initial_none(self, mock_get: Mock, mock_post: Mock) -> None:
        """Returns None before any requests are made."""
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_get_response

        provider = OllamaProvider(model="llama3.3:70b")
        assert provider.get_last_request_latency() is None

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_get_last_request_latency_after_request(self, mock_get: Mock, mock_post: Mock) -> None:
        """Returns latency value after a successful request."""
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_get_response

        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"response": '{"result": "ok"}'}
        mock_post.return_value = mock_post_response

        provider = OllamaProvider(model="llama3.3:70b")
        provider.generate("Test prompt")

        latency = provider.get_last_request_latency()
        assert latency is not None
        assert latency >= 0

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_get_all_latencies_initial_empty(self, mock_get: Mock, mock_post: Mock) -> None:
        """Returns empty list before any requests are made."""
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_get_response

        provider = OllamaProvider(model="llama3.3:70b")
        assert provider.get_all_latencies() == []

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_get_all_latencies_accumulates(self, mock_get: Mock, mock_post: Mock) -> None:
        """Returns list of all request latencies after multiple requests."""
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_get_response

        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"response": '{"result": "ok"}'}
        mock_post.return_value = mock_post_response

        provider = OllamaProvider(model="llama3.3:70b")
        provider.generate("Test prompt 1")
        provider.generate("Test prompt 2")

        latencies = provider.get_all_latencies()
        assert len(latencies) == 2
        assert all(lat >= 0 for lat in latencies)

    @patch("review_bot_automator.llm.providers.ollama.requests.post")
    @patch("review_bot_automator.llm.providers.ollama.requests.get")
    def test_reset_latency_tracking(self, mock_get: Mock, mock_post: Mock) -> None:
        """Clears latencies and resets last_request_latency to None."""
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {"models": [{"name": "llama3.3:70b"}]}
        mock_get.return_value = mock_get_response

        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"response": '{"result": "ok"}'}
        mock_post.return_value = mock_post_response

        provider = OllamaProvider(model="llama3.3:70b")
        provider.generate("Test prompt")

        # Verify latency was recorded
        assert provider.get_last_request_latency() is not None
        assert len(provider.get_all_latencies()) == 1

        # Reset and verify cleared
        provider.reset_latency_tracking()
        assert provider.get_last_request_latency() is None
        assert provider.get_all_latencies() == []
