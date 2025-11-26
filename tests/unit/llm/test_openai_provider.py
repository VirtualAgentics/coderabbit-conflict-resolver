"""Tests for OpenAI API provider.

This module tests the OpenAI provider implementation including:
- Provider protocol conformance
- Token counting with tiktoken
- Cost calculation
- Retry logic with mocked failures
- Error handling for various failure modes
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

# Skip all tests if openai package is not installed
pytest.importorskip("openai")

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from review_bot_automator.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
)
from review_bot_automator.llm.providers.base import LLMProvider
from review_bot_automator.llm.providers.openai_api import OpenAIAPIProvider


class TestOpenAIProviderProtocol:
    """Test that OpenAIAPIProvider conforms to LLMProvider protocol."""

    def test_provider_implements_protocol(self) -> None:
        """Test that OpenAIAPIProvider implements LLMProvider protocol."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4o-mini")
        assert isinstance(provider, LLMProvider)

    def test_provider_has_generate_method(self) -> None:
        """Test that provider has generate() method with correct signature."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4o-mini")
        assert hasattr(provider, "generate")
        assert callable(provider.generate)

    def test_provider_has_count_tokens_method(self) -> None:
        """Test that provider has count_tokens() method with correct signature."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4o-mini")
        assert hasattr(provider, "count_tokens")
        assert callable(provider.count_tokens)


class TestOpenAIProviderInitialization:
    """Test OpenAIAPIProvider initialization and configuration."""

    def test_init_with_valid_params(self) -> None:
        """Test initialization with valid parameters."""
        provider = OpenAIAPIProvider(
            api_key="sk-test-key-12345",
            model="gpt-4",
            timeout=30,
        )
        assert provider.model == "gpt-4"
        assert provider.timeout == 30
        assert provider.total_input_tokens == 0
        assert provider.total_output_tokens == 0

    def test_init_with_empty_api_key_raises(self) -> None:
        """Test that empty API key raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError, match="API key cannot be empty"):
            OpenAIAPIProvider(api_key="", model="gpt-4")

    def test_init_with_unknown_model_uses_fallback_tokenizer(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that unknown model falls back to cl100k_base tokenizer."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="unknown-model-xyz")
        assert "Unknown model" in caplog.text
        assert "cl100k_base" in caplog.text
        assert provider.tokenizer is not None

    def test_init_with_default_model(self) -> None:
        """Test that default model is gpt-4o-mini (cost-effective)."""
        provider = OpenAIAPIProvider(api_key="sk-test")
        assert provider.model == "gpt-4o-mini"

    def test_init_with_default_timeout(self) -> None:
        """Test that default timeout is 60 seconds."""
        provider = OpenAIAPIProvider(api_key="sk-test")
        assert provider.timeout == 60


class TestOpenAIProviderTokenCounting:
    """Test token counting using tiktoken."""

    def test_count_tokens_simple_text(self) -> None:
        """Test counting tokens for simple text."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        text = "Hello world"
        count = provider.count_tokens(text)
        assert count > 0
        assert isinstance(count, int)

    def test_count_tokens_empty_string(self) -> None:
        """Test counting tokens for empty string."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        count = provider.count_tokens("")
        assert count == 0

    def test_count_tokens_code(self) -> None:
        """Test counting tokens for code snippet."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        code = """def hello():
    print("Hello world")
    return 42"""
        count = provider.count_tokens(code)
        assert count > 5  # Should tokenize to multiple tokens

    def test_count_tokens_none_raises(self) -> None:
        """Test that None text raises ValueError."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        with pytest.raises(ValueError, match="Text cannot be None"):
            provider.count_tokens(None)  # type: ignore[arg-type]

    def test_count_tokens_consistent(self) -> None:
        """Test that token counting is consistent for same text."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        text = "The quick brown fox jumps over the lazy dog"
        count1 = provider.count_tokens(text)
        count2 = provider.count_tokens(text)
        assert count1 == count2


class TestOpenAIProviderCostCalculation:
    """Test cost tracking and calculation."""

    def test_get_total_cost_initial_zero(self) -> None:
        """Test that initial total cost is zero."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        assert provider.get_total_cost() == 0.0

    def test_calculate_cost_gpt4(self) -> None:
        """Test cost calculation for GPT-4."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        # 1000 input tokens + 1000 output tokens
        # GPT-4: $30/1M input, $60/1M output
        # Expected: (1000/1M * 30) + (1000/1M * 60) = 0.03 + 0.06 = 0.09
        cost = provider._calculate_cost(1000, 1000)
        assert abs(cost - 0.09) < 0.001

    def test_calculate_cost_gpt4o_mini(self) -> None:
        """Test cost calculation for GPT-4o-mini."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4o-mini")
        # 1000 input tokens + 1000 output tokens
        # GPT-4o-mini: $0.15/1M input, $0.60/1M output
        # Expected: (1000/1M * 0.15) + (1000/1M * 0.60) = 0.00015 + 0.0006 = 0.00075
        cost = provider._calculate_cost(1000, 1000)
        assert abs(cost - 0.00075) < 0.000001

    def test_calculate_cost_unknown_model_returns_zero(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that unknown model returns zero cost with warning."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="unknown-model")
        cost = provider._calculate_cost(1000, 1000)
        assert cost == 0.0
        assert "Unknown model pricing" in caplog.text

    def test_reset_usage_tracking(self) -> None:
        """Test resetting usage counters."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        provider.total_input_tokens = 1000
        provider.total_output_tokens = 500
        provider.reset_usage_tracking()
        assert provider.total_input_tokens == 0
        assert provider.total_output_tokens == 0


class TestOpenAIProviderGenerate:
    """Test text generation with mocked API."""

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_success(self, mock_openai_class: Mock) -> None:
        """Test successful generation."""
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock the response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"result": "success"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        result = provider.generate("Test prompt", max_tokens=100)

        assert result == '{"result": "success"}'
        assert provider.total_input_tokens == 10
        assert provider.total_output_tokens == 5

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_empty_prompt_raises(self, mock_openai_class: Mock) -> None:
        """Test that empty prompt raises ValueError."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            provider.generate("", max_tokens=100)

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_invalid_max_tokens_raises(self, mock_openai_class: Mock) -> None:
        """Test that invalid max_tokens raises ValueError."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider.generate("Test prompt", max_tokens=0)

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_uses_json_mode(self, mock_openai_class: Mock) -> None:
        """Test that generation uses JSON mode for structured output."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"test": "data"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        provider.generate("Test prompt")

        # Verify JSON mode was requested
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_uses_zero_temperature(self, mock_openai_class: Mock) -> None:
        """Test that generation uses temperature=0 for determinism."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"test": "data"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        provider.generate("Test prompt")

        # Verify temperature=0
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.0

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_empty_response_raises(self, mock_openai_class: Mock) -> None:
        """Test that empty response from API raises error."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=""))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=0)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        with pytest.raises(LLMAPIError, match="empty response"):
            provider.generate("Test prompt")


class TestOpenAIProviderRetryLogic:
    """Test retry logic for transient failures."""

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_retries_on_timeout(self, mock_openai_class: Mock) -> None:
        """Test that generation retries on API timeout."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # First call times out, second succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"result": "success"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

        # Create mock request for the error
        mock_request = MagicMock()

        mock_client.chat.completions.create.side_effect = [
            APITimeoutError(request=mock_request),
            mock_response,
        ]

        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        result = provider.generate("Test prompt")

        assert result == '{"result": "success"}'
        assert mock_client.chat.completions.create.call_count == 2

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_retries_on_rate_limit(self, mock_openai_class: Mock) -> None:
        """Test that generation retries on rate limit error."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"result": "success"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

        # Create a mock response object for the error
        mock_error_response = MagicMock()
        mock_error_response.request = MagicMock()

        mock_client.chat.completions.create.side_effect = [
            RateLimitError("Rate limited", response=mock_error_response, body=None),
            mock_response,
        ]

        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        result = provider.generate("Test prompt")

        assert result == '{"result": "success"}'
        assert mock_client.chat.completions.create.call_count == 2

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_retries_on_connection_error(self, mock_openai_class: Mock) -> None:
        """Test that generation retries on connection error."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"result": "success"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

        # Create mock request for the error
        mock_request = MagicMock()

        mock_client.chat.completions.create.side_effect = [
            APIConnectionError(message="Connection failed", request=mock_request),
            mock_response,
        ]

        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        result = provider.generate("Test prompt")

        assert result == '{"result": "success"}'
        assert mock_client.chat.completions.create.call_count == 2

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_no_retry_on_auth_error(self, mock_openai_class: Mock) -> None:
        """Test that generation does NOT retry on authentication error."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Create a mock response object for the error
        mock_error_response = MagicMock()
        mock_error_response.request = MagicMock()

        mock_client.chat.completions.create.side_effect = AuthenticationError(
            "Invalid API key", response=mock_error_response, body=None
        )

        provider = OpenAIAPIProvider(api_key="sk-test", model="gpt-4")
        with pytest.raises(LLMAuthenticationError, match="authentication failed"):
            provider.generate("Test prompt")

        # Should only try once (no retries)
        assert mock_client.chat.completions.create.call_count == 1


class TestOpenAIProviderEffortParameter:
    """Tests for reasoning_effort parameter support."""

    def test_init_with_effort_none_by_default(self) -> None:
        """Test that effort is None by default."""
        provider = OpenAIAPIProvider(api_key="sk-test")
        assert provider.effort is None

    def test_init_with_effort_parameter(self) -> None:
        """Test that effort parameter is stored correctly on o1 model."""
        provider = OpenAIAPIProvider(api_key="sk-test", model="o1", effort="high")
        assert provider.effort == "high"

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_without_effort_omits_reasoning_effort(self, mock_openai_class: Mock) -> None:
        """Test that reasoning_effort is NOT included when effort is None."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"test": "data"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test", effort=None)
        provider.generate("Test prompt")

        # Verify reasoning_effort was NOT included
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "reasoning_effort" not in call_kwargs

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_with_effort_includes_reasoning_effort(self, mock_openai_class: Mock) -> None:
        """Test that reasoning_effort IS included when effort is set."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"test": "data"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test", model="o1", effort="high")
        provider.generate("Test prompt")

        # Verify reasoning_effort was included with correct value (o1 models only)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_with_effort_low(self, mock_openai_class: Mock) -> None:
        """Test that reasoning_effort='low' is passed correctly."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"test": "data"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test", model="o1-mini", effort="low")
        provider.generate("Test prompt")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "low"

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_with_effort_medium(self, mock_openai_class: Mock) -> None:
        """Test that reasoning_effort='medium' is passed correctly."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"test": "data"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test", model="o1-preview", effort="medium")
        provider.generate("Test prompt")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "medium"

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_generate_with_effort_none_disables_effort(self, mock_openai_class: Mock) -> None:
        """Test that effort='none' disables reasoning_effort (does not send to API)."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"test": "data"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test", model="o1", effort="none")
        provider.generate("Test prompt")

        # effort="none" means disabled - should NOT send reasoning_effort to API
        # Only "low"/"medium"/"high" are valid API values
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "reasoning_effort" not in call_kwargs

    def test_init_with_effort_on_non_o1_model_raises(self) -> None:
        """Test that effort parameter on non-o1 model raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError, match="only supported for o1 models"):
            OpenAIAPIProvider(api_key="sk-test", model="gpt-4o-mini", effort="high")

    def test_init_with_effort_on_gpt5_raises(self) -> None:
        """Test that effort parameter on GPT-5 model raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError, match="only supported for o1 models"):
            OpenAIAPIProvider(api_key="sk-test", model="gpt-5", effort="low")

    def test_init_with_invalid_effort_level_raises(self) -> None:
        """Test that invalid effort level raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError, match="Invalid effort level"):
            OpenAIAPIProvider(api_key="sk-test", model="o1", effort="invalid")


class TestOpenAIProviderLatencyTracking:
    """Tests for latency tracking methods."""

    def test_get_last_request_latency_initial_none(self) -> None:
        """Returns None before any requests are made."""
        provider = OpenAIAPIProvider(api_key="sk-test")
        assert provider.get_last_request_latency() is None

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_get_last_request_latency_after_request(self, mock_openai_class: Mock) -> None:
        """Returns latency value after a successful request."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"result": "ok"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test")
        provider.generate("Test prompt")

        latency = provider.get_last_request_latency()
        assert latency is not None
        assert latency >= 0

    def test_get_all_latencies_initial_empty(self) -> None:
        """Returns empty list before any requests are made."""
        provider = OpenAIAPIProvider(api_key="sk-test")
        assert provider.get_all_latencies() == []

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_get_all_latencies_accumulates(self, mock_openai_class: Mock) -> None:
        """Returns list of all request latencies after multiple requests."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"result": "ok"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test")
        provider.generate("Test prompt 1")
        provider.generate("Test prompt 2")

        latencies = provider.get_all_latencies()
        assert len(latencies) == 2
        assert all(lat >= 0 for lat in latencies)

    @patch("review_bot_automator.llm.providers.openai_api.OpenAI")
    def test_reset_latency_tracking(self, mock_openai_class: Mock) -> None:
        """Clears latencies and resets last_request_latency to None."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"result": "ok"}'))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIAPIProvider(api_key="sk-test")
        provider.generate("Test prompt")

        # Verify latency was recorded
        assert provider.get_last_request_latency() is not None
        assert len(provider.get_all_latencies()) == 1

        # Reset and verify cleared
        provider.reset_latency_tracking()
        assert provider.get_last_request_latency() is None
        assert provider.get_all_latencies() == []
