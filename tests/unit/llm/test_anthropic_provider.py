"""Tests for Anthropic API provider.

This module tests the Anthropic provider implementation including:
- Provider protocol conformance
- Token counting with Anthropic's API
- Cost calculation (including cache costs)
- Retry logic with mocked failures
- Error handling for various failure modes
"""

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

from review_bot_automator.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
)
from review_bot_automator.llm.providers.anthropic_api import AnthropicAPIProvider
from review_bot_automator.llm.providers.base import LLMProvider


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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_init_sets_max_retries_to_zero(self, mock_anthropic_class: Mock) -> None:
        """Test that client is created with max_retries=0."""
        AnthropicAPIProvider(api_key="sk-ant-test")
        mock_anthropic_class.assert_called_once_with(
            api_key="sk-ant-test", timeout=60, max_retries=0
        )


class TestAnthropicProviderTokenCounting:
    """Test token counting using Anthropic's API."""

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_count_tokens_none_raises(self, mock_anthropic_class: Mock) -> None:
        """Test that None text raises ValueError."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        with pytest.raises(ValueError, match="Text cannot be None"):
            provider.count_tokens(None)  # type: ignore

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    def test_calculate_cost_sonnet_4_5_long_context(self) -> None:
        """Test that long-context pricing is applied when combined tokens > 200K."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")

        # Set up token counts that exceed 200K combined (input + cache_write + cache_read)
        provider.total_input_tokens = 150_000
        provider.total_cache_write_tokens = 40_000
        provider.total_cache_read_tokens = 20_000
        provider.total_output_tokens = 5_000

        # Combined: 150K + 40K + 20K = 210K > 200K threshold
        # Should use long-context pricing:
        # Input: $6/1M, Output: $22.50/1M, Cache write: $7.50/1M, Cache read: $0.60/1M
        expected_cost = (
            (150_000 / 1_000_000) * 6.00  # input_long
            + (5_000 / 1_000_000) * 22.50  # output_long
            + (40_000 / 1_000_000) * 7.50  # cache_write_long
            + (20_000 / 1_000_000) * 0.60  # cache_read_long
        )
        assert provider.get_total_cost() == pytest.approx(expected_cost)

    def test_calculate_cost_sonnet_4_5_standard_context(self) -> None:
        """Test that standard pricing is used when combined tokens <= 200K."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")

        # Set up token counts below 200K threshold
        provider.total_input_tokens = 100_000
        provider.total_cache_write_tokens = 50_000
        provider.total_cache_read_tokens = 40_000
        provider.total_output_tokens = 5_000

        # Combined: 100K + 50K + 40K = 190K <= 200K threshold
        # Should use standard pricing:
        # Input: $3/1M, Output: $15/1M, Cache write: $3.75/1M, Cache read: $0.30/1M
        expected_cost = (
            (100_000 / 1_000_000) * 3.00  # input
            + (5_000 / 1_000_000) * 15.00  # output
            + (50_000 / 1_000_000) * 3.75  # cache_write
            + (40_000 / 1_000_000) * 0.30  # cache_read
        )
        assert provider.get_total_cost() == pytest.approx(expected_cost)

    def test_calculate_cost_sonnet_4_5_exactly_200k(self) -> None:
        """Test boundary condition: exactly 200K tokens uses standard pricing."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5")

        # Exactly at 200K threshold
        provider.total_input_tokens = 150_000
        provider.total_cache_write_tokens = 30_000
        provider.total_cache_read_tokens = 20_000
        provider.total_output_tokens = 5_000

        # Combined: 150K + 30K + 20K = 200K (not > 200K)
        # Should use standard pricing
        expected_cost = (
            (150_000 / 1_000_000) * 3.00  # input
            + (5_000 / 1_000_000) * 15.00  # output
            + (30_000 / 1_000_000) * 3.75  # cache_write
            + (20_000 / 1_000_000) * 0.30  # cache_read
        )
        assert provider.get_total_cost() == pytest.approx(expected_cost)

    def test_calculate_cost_long_context_only_for_sonnet_4_5(self) -> None:
        """Test that long-context detection only applies to claude-sonnet-4-5."""
        # Opus should not trigger long-context pricing even with >200K tokens
        provider = AnthropicAPIProvider(api_key="sk-ant-test", model="claude-opus-4-1")
        provider.total_input_tokens = 150_000
        provider.total_cache_write_tokens = 40_000
        provider.total_cache_read_tokens = 20_000
        provider.total_output_tokens = 5_000

        # Combined > 200K but model is not sonnet-4-5, so use standard Opus pricing
        # Opus-4: $15/1M input, $75/1M output, $18.75/1M cache_write, $1.50/1M cache_read
        expected_cost = (
            (150_000 / 1_000_000) * 15.00
            + (5_000 / 1_000_000) * 75.00
            + (40_000 / 1_000_000) * 18.75
            + (20_000 / 1_000_000) * 1.50
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_empty_prompt_raises(self, mock_anthropic_class: Mock) -> None:
        """Test that empty prompt raises ValueError."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            provider.generate("")

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_invalid_max_tokens_raises(self, mock_anthropic_class: Mock) -> None:
        """Test that invalid max_tokens raises ValueError."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider.generate("Test prompt", max_tokens=0)

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_splits_prompt_with_context_marker(self, mock_anthropic_class: Mock) -> None:
        """Test that prompts with context marker are split into cached + uncached blocks."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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

        # Prompt with context marker should be split
        prompt_with_marker = (
            "Instructions here\n\n## Context Information\n\nFile: test.py\nLine: 42"
        )
        provider.generate(prompt_with_marker)

        # Verify 2 content blocks were sent
        call_args = mock_client.messages.create.call_args
        content_blocks = call_args[1]["messages"][0]["content"]
        assert len(content_blocks) == 2

        # Block 1: Cached prefix (before marker)
        assert content_blocks[0]["type"] == "text"
        assert "Instructions here" in content_blocks[0]["text"]
        assert "## Context Information" not in content_blocks[0]["text"]
        assert "cache_control" in content_blocks[0]
        assert content_blocks[0]["cache_control"]["type"] == "ephemeral"

        # Block 2: Uncached dynamic content (marker onward)
        assert content_blocks[1]["type"] == "text"
        assert "## Context Information" in content_blocks[1]["text"]
        assert "File: test.py" in content_blocks[1]["text"]
        assert "cache_control" not in content_blocks[1]

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_no_split_without_context_marker(self, mock_anthropic_class: Mock) -> None:
        """Test that prompts without context marker are sent as single cached block."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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

        # Simple prompt without marker
        provider.generate("Simple prompt without split marker")

        # Verify single content block was sent
        call_args = mock_client.messages.create.call_args
        content_blocks = call_args[1]["messages"][0]["content"]
        assert len(content_blocks) == 1
        assert content_blocks[0]["type"] == "text"
        assert "cache_control" in content_blocks[0]

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_handles_empty_prefix_gracefully(self, mock_anthropic_class: Mock) -> None:
        """Test that prompts starting with context marker don't create empty cached blocks."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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

        # Prompt starting with marker (empty prefix)
        prompt_starting_with_marker = "## Context Information\n\nFile: test.py\nLine: 42"
        provider.generate(prompt_starting_with_marker)

        # Verify only 1 block sent (no empty cached block)
        call_args = mock_client.messages.create.call_args
        content_blocks = call_args[1]["messages"][0]["content"]
        assert len(content_blocks) == 1

        # The single block should be the dynamic content (uncached)
        assert content_blocks[0]["type"] == "text"
        assert "## Context Information" in content_blocks[0]["text"]
        assert "cache_control" not in content_blocks[0]


class TestAnthropicProviderRetryLogic:
    """Test retry logic for transient failures."""

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
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


class TestAnthropicProviderEffortParameter:
    """Tests for effort parameter support (Claude Opus 4.5)."""

    def test_init_with_effort_none_by_default(self) -> None:
        """Test that effort is None by default."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        assert provider.effort is None

    def test_init_with_effort_parameter(self) -> None:
        """Test that effort parameter is stored correctly."""
        provider = AnthropicAPIProvider(
            api_key="sk-ant-test", model="claude-opus-4-5", effort="high"
        )
        assert provider.effort == "high"

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_without_effort_uses_base_beta_header(
        self, mock_anthropic_class: Mock
    ) -> None:
        """Test that only prompt-caching header is used when effort is None."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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

        provider = AnthropicAPIProvider(api_key="sk-ant-test", effort=None)
        provider.generate("Test prompt")

        # Verify only prompt-caching header is sent
        call_args = mock_client.messages.create.call_args
        assert call_args[1]["extra_headers"] == {"anthropic-beta": "prompt-caching-2024-07-31"}
        # Verify no extra_body for effort
        assert "extra_body" not in call_args[1]

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_with_effort_includes_effort_beta_header(
        self, mock_anthropic_class: Mock
    ) -> None:
        """Test that effort beta header is included when effort is set."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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

        provider = AnthropicAPIProvider(
            api_key="sk-ant-test", model="claude-opus-4-5", effort="high"
        )
        provider.generate("Test prompt")

        # Verify both beta headers are included
        call_args = mock_client.messages.create.call_args
        beta_header = call_args[1]["extra_headers"]["anthropic-beta"]
        assert "prompt-caching-2024-07-31" in beta_header
        assert "effort-2025-11-24" in beta_header

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_with_effort_includes_output_config(self, mock_anthropic_class: Mock) -> None:
        """Test that output_config with effort is passed via extra_body."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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

        provider = AnthropicAPIProvider(
            api_key="sk-ant-test", model="claude-opus-4-5", effort="high"
        )
        provider.generate("Test prompt")

        # Verify extra_body contains output_config with effort
        call_args = mock_client.messages.create.call_args
        assert "extra_body" in call_args[1]
        assert call_args[1]["extra_body"] == {"output_config": {"effort": "high"}}

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_with_effort_low(self, mock_anthropic_class: Mock) -> None:
        """Test that effort='low' is passed correctly."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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

        provider = AnthropicAPIProvider(
            api_key="sk-ant-test", model="claude-opus-4-5", effort="low"
        )
        provider.generate("Test prompt")

        call_args = mock_client.messages.create.call_args
        assert call_args[1]["extra_body"] == {"output_config": {"effort": "low"}}

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_with_effort_medium(self, mock_anthropic_class: Mock) -> None:
        """Test that effort='medium' is passed correctly."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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

        provider = AnthropicAPIProvider(
            api_key="sk-ant-test", model="claude-opus-4-5", effort="medium"
        )
        provider.generate("Test prompt")

        call_args = mock_client.messages.create.call_args
        assert call_args[1]["extra_body"] == {"output_config": {"effort": "medium"}}

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_generate_with_effort_none_disables_effort(self, mock_anthropic_class: Mock) -> None:
        """Test that effort='none' disables effort (does not send to API)."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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

        provider = AnthropicAPIProvider(
            api_key="sk-ant-test", model="claude-opus-4-5", effort="none"
        )
        provider.generate("Test prompt")

        # effort="none" means disabled - should NOT send extra_body to API
        # Only "low"/"medium"/"high" are valid API values
        call_args = mock_client.messages.create.call_args
        assert "extra_body" not in call_args[1]
        # Beta header should also NOT include effort beta
        assert call_args[1]["extra_headers"] == {"anthropic-beta": "prompt-caching-2024-07-31"}

    def test_init_with_effort_on_non_opus_model_raises(self) -> None:
        """Test that effort parameter on non-Opus model raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError, match="only supported for Claude Opus 4.5"):
            AnthropicAPIProvider(api_key="sk-ant-test", model="claude-sonnet-4-5", effort="high")

    def test_init_with_effort_on_haiku_raises(self) -> None:
        """Test that effort parameter on Haiku model raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError, match="only supported for Claude Opus 4.5"):
            AnthropicAPIProvider(api_key="sk-ant-test", model="claude-haiku-4-5", effort="low")

    def test_init_with_invalid_effort_level_raises(self) -> None:
        """Test that invalid effort level raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError, match="Invalid effort level"):
            AnthropicAPIProvider(api_key="sk-ant-test", model="claude-opus-4-5", effort="invalid")


class TestAnthropicProviderLatencyTracking:
    """Tests for latency tracking methods."""

    def test_get_last_request_latency_initial_none(self) -> None:
        """Returns None before any requests are made."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        assert provider.get_last_request_latency() is None

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_get_last_request_latency_after_request(self, mock_anthropic_class: Mock) -> None:
        """Returns latency value after a successful request."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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
        provider.generate("Test prompt")

        latency = provider.get_last_request_latency()
        assert latency is not None
        assert latency >= 0

    def test_get_all_latencies_initial_empty(self) -> None:
        """Returns empty list before any requests are made."""
        provider = AnthropicAPIProvider(api_key="sk-ant-test")
        assert provider.get_all_latencies() == []

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_get_all_latencies_accumulates(self, mock_anthropic_class: Mock) -> None:
        """Returns list of all request latencies after multiple requests."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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
        provider.generate("Test prompt 1")
        provider.generate("Test prompt 2")

        latencies = provider.get_all_latencies()
        assert len(latencies) == 2
        assert all(lat >= 0 for lat in latencies)

    @patch("review_bot_automator.llm.providers.anthropic_api.Anthropic")
    def test_reset_latency_tracking(self, mock_anthropic_class: Mock) -> None:
        """Clears latencies and resets last_request_latency to None."""
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

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
        provider.generate("Test prompt")

        # Verify latency was recorded
        assert provider.get_last_request_latency() is not None
        assert len(provider.get_all_latencies()) == 1

        # Reset and verify cleared
        provider.reset_latency_tracking()
        assert provider.get_last_request_latency() is None
        assert provider.get_all_latencies() == []
