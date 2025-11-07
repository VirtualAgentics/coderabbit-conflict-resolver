"""Tests for Anthropic API provider.

This module tests the Anthropic provider implementation including:
- Provider protocol conformance
- Token counting with Anthropic's API
- Cost calculation (including cache costs)
- Retry logic with mocked failures
- Error handling for various failure modes
- Integration tests with real API (optional, requires API key)
"""

import os
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

# Skip all tests if anthropic package is not installed
pytest.importorskip("anthropic")

from anthropic import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    RateLimitError,
)
from anthropic.types import TextBlock

from pr_conflict_resolver.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
)
from pr_conflict_resolver.llm.providers.anthropic_api import AnthropicAPIProvider
from pr_conflict_resolver.llm.providers.base import LLMProvider


def create_mock_anthropic_error(error_class: type, message: str) -> Any:  # noqa: ANN401
    """Helper to create Anthropic exceptions with required parameters."""
    if error_class in (AuthenticationError, RateLimitError):
        # These use response parameter
        mock_response = MagicMock()
        mock_response.status_code = 400
        return error_class(message, response=mock_response, body=None)
    elif error_class == APIConnectionError:
        # Uses request parameter (keyword-only message)
        mock_request = MagicMock()
        return error_class(message=message, request=mock_request)
    elif error_class == APIError:
        # Uses request parameter (keyword-only)
        mock_request = MagicMock()
        return error_class(message, request=mock_request, body=None)
    else:
        # Fallback for unknown error types
        return error_class(message)


class TestAnthropicProviderProtocol:
    """Test that AnthropicAPIProvider conforms to LLMProvider protocol."""

    def test_provider_implements_protocol(self) -> None:
        """Test that AnthropicAPIProvider implements LLMProvider protocol."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        assert isinstance(provider, LLMProvider)

    def test_provider_has_generate_method(self) -> None:
        """Test that provider has generate() method with correct signature."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        assert hasattr(provider, "generate")
        assert callable(provider.generate)

    def test_provider_has_count_tokens_method(self) -> None:
        """Test that provider has count_tokens() method with correct signature."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        assert hasattr(provider, "count_tokens")
        assert callable(provider.count_tokens)


class TestAnthropicProviderInitialization:
    """Test AnthropicAPIProvider initialization and configuration."""

    def test_init_with_valid_params(self) -> None:
        """Test initialization with valid parameters."""
        provider = AnthropicAPIProvider(
            api_key="sk-ant-test-key-12345",
            model="claude-opus-4-1",
            timeout=30,
        )
        assert provider.model == "claude-opus-4-1"
        assert provider.timeout == 30
        assert provider.total_input_tokens == 0
        assert provider.total_output_tokens == 0
        assert provider.total_cache_write_tokens == 0
        assert provider.total_cache_read_tokens == 0

    def test_init_with_empty_api_key_raises(self) -> None:
        """Test that empty API key raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError, match="API key cannot be empty"):
            AnthropicAPIProvider(api_key="", model="claude-sonnet-4-5")

    def test_init_with_default_model(self) -> None:
        """Test that default model is claude-sonnet-4-5 (best value)."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        assert provider.model == "claude-sonnet-4-5"

    def test_init_with_default_timeout(self) -> None:
        """Test that default timeout is 60 seconds."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        assert provider.timeout == 60

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_init_sets_max_retries_to_zero(self, mock_anthropic_class: Mock) -> None:
        """Test that client is created with max_retries=0."""
        AnthropicAPIProvider(api_key="sk-ant-test")
        mock_anthropic_class.assert_called_once_with(
            api_key="sk-ant-test", timeout=60, max_retries=0
        )


class TestAnthropicProviderTokenCounting:
    """Test token counting using Anthropic's API."""

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_count_tokens_simple_text(self, mock_anthropic_class: Mock) -> None:
        """Test counting tokens for simple text."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_count_response = MagicMock()
        mock_count_response.input_tokens = 10
        mock_client.messages.count_tokens.return_value = mock_count_response

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        count = provider.count_tokens("Hello, world!")

        assert count == 10
        mock_client.messages.count_tokens.assert_called_once()

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_count_tokens_empty_string(self, mock_anthropic_class: Mock) -> None:
        """Test counting tokens for empty string."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_count_response = MagicMock()
        mock_count_response.input_tokens = 0
        mock_client.messages.count_tokens.return_value = mock_count_response

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        count = provider.count_tokens("")

        assert count == 0

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_count_tokens_none_raises(self, mock_anthropic_class: Mock) -> None:
        """Test that None text raises ValueError."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        with pytest.raises(ValueError, match="Text cannot be None"):
            provider.count_tokens(None)  # type: ignore

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_count_tokens_fallback_on_error(
        self, mock_anthropic_class: Mock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test fallback estimation when API fails."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_client.messages.count_tokens.side_effect = Exception("API error")

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        # "Hello world" = 11 chars, should estimate ~2 tokens (11 // 4)
        count = provider.count_tokens("Hello world")

        assert count == 2  # len("Hello world") // 4
        assert "Error counting tokens" in caplog.text


class TestAnthropicProviderCostCalculation:
    """Test cost tracking and calculation."""

    def test_get_total_cost_initial_zero(self) -> None:
        """Test that initial total cost is zero."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        assert provider.get_total_cost() == 0.0

    def test_calculate_cost_opus_4(self) -> None:
        """Test cost calculation for Claude Opus 4."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-opus-4-1")
        provider.total_input_tokens = 1000
        provider.total_output_tokens = 500

        # Opus-4: $15/1M input, $75/1M output
        expected_cost = (1000 / 1_000_000) * 15.00 + (500 / 1_000_000) * 75.00
        assert provider.get_total_cost() == pytest.approx(expected_cost)

    def test_calculate_cost_sonnet_4_5(self) -> None:
        """Test cost calculation for Claude Sonnet 4.5."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        provider.total_input_tokens = 1000
        provider.total_output_tokens = 500

        # Sonnet-4-5: $3/1M input, $15/1M output
        expected_cost = (1000 / 1_000_000) * 3.00 + (500 / 1_000_000) * 15.00
        assert provider.get_total_cost() == pytest.approx(expected_cost)

    def test_calculate_cost_haiku_4(self) -> None:
        """Test cost calculation for Claude Haiku 4."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-haiku-4-5")
        provider.total_input_tokens = 1000
        provider.total_output_tokens = 500

        # Haiku-4: $1/1M input, $5/1M output
        expected_cost = (1000 / 1_000_000) * 1.00 + (500 / 1_000_000) * 5.00
        assert provider.get_total_cost() == pytest.approx(expected_cost)

    def test_calculate_cost_with_cache_write(self) -> None:
        """Test cost calculation including cache write tokens."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        provider.total_input_tokens = 1000
        provider.total_output_tokens = 500
        provider.total_cache_write_tokens = 200

        # Sonnet-4-5: $3/1M input, $15/1M output, $3.75/1M cache_write
        expected_cost = (
            (1000 / 1_000_000) * 3.00 + (500 / 1_000_000) * 15.00 + (200 / 1_000_000) * 3.75
        )
        assert provider.get_total_cost() == pytest.approx(expected_cost)

    def test_calculate_cost_with_cache_read(self) -> None:
        """Test cost calculation including cache read tokens."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        provider.total_input_tokens = 1000
        provider.total_output_tokens = 500
        provider.total_cache_read_tokens = 300

        # Sonnet-4-5: $3/1M input, $15/1M output, $0.30/1M cache_read
        expected_cost = (
            (1000 / 1_000_000) * 3.00 + (500 / 1_000_000) * 15.00 + (300 / 1_000_000) * 0.30
        )
        assert provider.get_total_cost() == pytest.approx(expected_cost)

    def test_calculate_cost_with_all_token_types(self) -> None:
        """Test cost calculation with input, output, cache write, and cache read."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")
        provider.total_input_tokens = 1000
        provider.total_output_tokens = 500
        provider.total_cache_write_tokens = 200
        provider.total_cache_read_tokens = 300

        # Sonnet-4-5: $3/1M input, $15/1M output, $3.75/1M cache_write, $0.30/1M cache_read
        expected_cost = (
            (1000 / 1_000_000) * 3.00
            + (500 / 1_000_000) * 15.00
            + (200 / 1_000_000) * 3.75
            + (300 / 1_000_000) * 0.30
        )
        assert provider.get_total_cost() == pytest.approx(expected_cost)

    def test_calculate_cost_unknown_model_returns_zero(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that unknown model returns zero cost with warning."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="unknown-model")
        provider.total_input_tokens = 1000
        provider.total_output_tokens = 500

        cost = provider.get_total_cost()
        assert cost == 0.0
        assert "Unknown model pricing" in caplog.text

    def test_reset_usage_tracking(self) -> None:
        """Test resetting usage counters including cache counters."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        provider.total_input_tokens = 1000
        provider.total_output_tokens = 500
        provider.total_cache_write_tokens = 200
        provider.total_cache_read_tokens = 300

        provider.reset_usage_tracking()

        assert provider.total_input_tokens == 0
        assert provider.total_output_tokens == 0
        assert provider.total_cache_write_tokens == 0
        assert provider.total_cache_read_tokens == 0


class TestAnthropicProviderGenerate:
    """Test text generation with mocked API."""

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_success(self, mock_anthropic_class: Mock) -> None:
        """Test successful generation."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Create a real TextBlock instance (not patched)
        mock_text_block = TextBlock(type="text", text='{"result": "success"}')

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        result = provider.generate("Test prompt")

        assert result == '{"result": "success"}'
        assert provider.total_input_tokens == 10
        assert provider.total_output_tokens == 5

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_empty_prompt_raises(self, mock_anthropic_class: Mock) -> None:
        """Test that empty prompt raises ValueError."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            provider.generate("")

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_invalid_max_tokens_raises(self, mock_anthropic_class: Mock) -> None:
        """Test that invalid max_tokens raises ValueError."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider.generate("Test prompt", max_tokens=0)

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_uses_zero_temperature(self, mock_anthropic_class: Mock) -> None:
        """Test that generation uses temperature=0 for determinism."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Create a real TextBlock instance (not patched)
        mock_text_block = TextBlock(type="text", text="response")

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        provider.generate("Test prompt")

        # Verify temperature=0.0 was used
        call_args = mock_client.messages.create.call_args
        assert call_args[1]["temperature"] == 0.0

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_empty_response_raises(self, mock_anthropic_class: Mock) -> None:
        """Test that empty response from API raises error."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = []
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=0,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        with pytest.raises(LLMAPIError, match="empty response"):
            provider.generate("Test prompt")

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_tracks_cache_tokens(self, mock_anthropic_class: Mock) -> None:
        """Test that cache tokens are tracked correctly."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Create a real TextBlock instance (not patched)
        mock_text_block = TextBlock(type="text", text="response")

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=100,
            cache_read_input_tokens=50,
        )
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        provider.generate("Test prompt")

        assert provider.total_cache_write_tokens == 100
        assert provider.total_cache_read_tokens == 50

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_sends_prompt_caching_header(self, mock_anthropic_class: Mock) -> None:
        """Test that prompt caching beta header is sent with API requests."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Create a real TextBlock instance (not patched)
        mock_text_block = TextBlock(type="text", text="response")

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        provider.generate("Test prompt")

        # Verify the prompt caching beta header was sent
        call_args = mock_client.messages.create.call_args
        assert call_args[1]["extra_headers"] == {"anthropic-beta": "prompt-caching-2024-07-31"}


class TestAnthropicProviderRetryLogic:
    """Test retry logic for transient failures."""

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_retries_on_rate_limit(self, mock_anthropic_class: Mock) -> None:
        """Test that generation retries on rate limit error."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Create a real TextBlock instance (not patched)
        mock_text_block = TextBlock(type="text", text="success")

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )

        # First call raises RateLimitError, second succeeds
        rate_limit_error = create_mock_anthropic_error(RateLimitError, "Rate limit")
        mock_client.messages.create.side_effect = [rate_limit_error, mock_response]

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        result = provider.generate("Test prompt")

        assert result == "success"
        assert mock_client.messages.create.call_count == 2

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_retries_on_connection_error(self, mock_anthropic_class: Mock) -> None:
        """Test that generation retries on connection error."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Create a real TextBlock instance (not patched)
        mock_text_block = TextBlock(type="text", text="success")

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=5,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )

        # First call raises APIConnectionError, second succeeds
        connection_error = create_mock_anthropic_error(APIConnectionError, "Connection failed")
        mock_client.messages.create.side_effect = [connection_error, mock_response]

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        result = provider.generate("Test prompt")

        assert result == "success"
        assert mock_client.messages.create.call_count == 2

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_no_retry_on_auth_error(self, mock_anthropic_class: Mock) -> None:
        """Test that generation does NOT retry on authentication error."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        auth_error = create_mock_anthropic_error(AuthenticationError, "Invalid API key")
        mock_client.messages.create.side_effect = auth_error

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        with pytest.raises(LLMAuthenticationError):
            provider.generate("Test prompt")

        # Should only try once (no retry on auth errors)
        assert mock_client.messages.create.call_count == 1

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_no_retry_on_api_error(self, mock_anthropic_class: Mock) -> None:
        """Test that generation does NOT retry on general API error."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        api_error = create_mock_anthropic_error(APIError, "Invalid request")
        mock_client.messages.create.side_effect = api_error

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        with pytest.raises(LLMAPIError):
            provider.generate("Test prompt")

        # Should only try once (no retry on API errors)
        assert mock_client.messages.create.call_count == 1

    @patch("pr_conflict_resolver.llm.providers.anthropic_api.Anthropic")
    def test_generate_exhausts_retries(self, mock_anthropic_class: Mock) -> None:
        """Test that generation raises LLMAPIError after 3 retry attempts."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # All attempts raise RateLimitError
        rate_limit_error = create_mock_anthropic_error(RateLimitError, "Rate limit exceeded")
        mock_client.messages.create.side_effect = rate_limit_error

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        # After exhausting retries, should convert to LLMAPIError
        with pytest.raises(LLMAPIError) as exc_info:
            provider.generate("Test prompt")

        # Verify exception message and chaining
        assert "failed after 3 retry attempts" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None  # Should have exception chaining

        # Should try 3 times
        assert mock_client.messages.create.call_count == 3


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping integration test",
)
class TestAnthropicProviderIntegration:
    """Integration tests with real Anthropic API."""

    def test_real_api_simple_generation(self) -> None:
        """Test real API call with simple prompt."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        provider = AnthropicAPIProvider(api_key=api_key, model="claude-haiku-4-5")  # type: ignore

        result = provider.generate("Say 'test' in JSON format", max_tokens=100)

        assert result
        assert isinstance(result, str)
        assert len(result) > 0

    def test_real_api_cost_tracking(self) -> None:
        """Test that real API calls track costs correctly."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        provider = AnthropicAPIProvider(api_key=api_key, model="claude-haiku-4-5")  # type: ignore

        provider.generate("Count to 5 in JSON", max_tokens=100)

        cost = provider.get_total_cost()
        assert cost > 0.0
        assert provider.total_input_tokens > 0
        assert provider.total_output_tokens > 0

    def test_real_api_token_counting(self) -> None:
        """Test token counting with real API."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        provider = AnthropicAPIProvider(api_key=api_key, model="claude-haiku-4-5")  # type: ignore

        count = provider.count_tokens("Hello, world!")
        assert count > 0
        assert isinstance(count, int)
