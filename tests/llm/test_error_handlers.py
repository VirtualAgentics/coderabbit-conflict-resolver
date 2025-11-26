"""Tests for LLM error handling utilities.

This module tests the error handler for user-friendly error messages,
provider-specific guidance, and security (API key sanitization).
"""

from review_bot_automator.llm.error_handlers import LLMErrorHandler
from review_bot_automator.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class TestAPIKeySanitization:
    """Tests for API key redaction in error messages (SECURITY CRITICAL)."""

    def test_sanitize_anthropic_api_key(self) -> None:
        """Test Anthropic API key is redacted."""
        message = "Authentication failed with key sk-ant-api03-abc123def456"
        sanitized = LLMErrorHandler.sanitize_error_message(message)

        assert "sk-ant-" not in sanitized
        assert "abc123def456" not in sanitized
        assert "[REDACTED_API_KEY]" in sanitized

    def test_sanitize_openai_api_key(self) -> None:
        """Test OpenAI API key is redacted."""
        message = "Invalid API key: sk-proj-abc123def456ghi789jkl012mno345"
        sanitized = LLMErrorHandler.sanitize_error_message(message)

        assert "sk-proj-" not in sanitized
        assert "abc123" not in sanitized
        assert "[REDACTED_API_KEY]" in sanitized

    def test_sanitize_generic_api_key_pattern(self) -> None:
        """Test generic 'api_key=' pattern is redacted."""
        message = "Error: api_key=secret_key_12345"
        sanitized = LLMErrorHandler.sanitize_error_message(message)

        assert "secret_key_12345" not in sanitized
        assert "[REDACTED_API_KEY]" in sanitized

    def test_sanitize_token_pattern(self) -> None:
        """Test 'token=' pattern is redacted."""
        message = "Auth failed: token='bearer_token_xyz789'"
        sanitized = LLMErrorHandler.sanitize_error_message(message)

        assert "bearer_token_xyz789" not in sanitized
        assert "[REDACTED_API_KEY]" in sanitized

    def test_sanitize_multiple_keys_in_message(self) -> None:
        """Test multiple API keys in one message are all redacted."""
        message = "Tried sk-ant-key1 but got error, " "then tried sk-proj-key2 which also failed"
        sanitized = LLMErrorHandler.sanitize_error_message(message)

        assert "key1" not in sanitized
        assert "key2" not in sanitized
        assert sanitized.count("[REDACTED_API_KEY]") == 2

    def test_sanitize_no_keys_in_message(self) -> None:
        """Test message without keys is unchanged."""
        message = "Connection timeout after 30 seconds"
        sanitized = LLMErrorHandler.sanitize_error_message(message)

        assert sanitized == message


class TestSetupLinks:
    """Tests for provider setup documentation links."""

    def test_get_setup_link_anthropic(self) -> None:
        """Test Anthropic setup link."""
        link = LLMErrorHandler.get_setup_link("anthropic")
        assert link == "https://console.anthropic.com/"

    def test_get_setup_link_openai(self) -> None:
        """Test OpenAI setup link."""
        link = LLMErrorHandler.get_setup_link("openai")
        assert link == "https://platform.openai.com/api-keys"

    def test_get_setup_link_ollama(self) -> None:
        """Test Ollama setup link."""
        link = LLMErrorHandler.get_setup_link("ollama")
        assert link == "https://github.com/ollama/ollama#quickstart"

    def test_get_setup_link_claude_cli(self) -> None:
        """Test Claude CLI setup link."""
        link = LLMErrorHandler.get_setup_link("claude-cli")
        assert link == "https://claude.ai/settings/subscriptions"

    def test_get_setup_link_codex_cli(self) -> None:
        """Test Codex CLI setup link."""
        link = LLMErrorHandler.get_setup_link("codex-cli")
        assert link == "https://github.com/features/copilot"

    def test_get_setup_link_unknown_provider(self) -> None:
        """Test unknown provider returns default docs link."""
        link = LLMErrorHandler.get_setup_link("unknown")
        assert "review-bot-automator" in link


class TestAuthErrorFormatting:
    """Tests for authentication error formatting."""

    def test_format_auth_error_anthropic(self) -> None:
        """Test Anthropic auth error message."""
        message = LLMErrorHandler.format_auth_error("anthropic")

        assert "Anthropic" in message
        assert "CR_LLM_API_KEY" in message
        assert "sk-ant-" in message
        assert "console.anthropic.com" in message
        assert "❌" in message

    def test_format_auth_error_openai(self) -> None:
        """Test OpenAI auth error message."""
        message = LLMErrorHandler.format_auth_error("openai")

        assert "OpenAI" in message
        assert "CR_LLM_API_KEY" in message
        assert "sk-" in message
        assert "platform.openai.com" in message

    def test_format_auth_error_ollama(self) -> None:
        """Test Ollama connection error message."""
        message = LLMErrorHandler.format_auth_error("ollama")

        assert "Ollama" in message
        assert "ollama serve" in message
        assert "localhost:11434" in message
        assert "ollama pull" in message

    def test_format_auth_error_claude_cli(self) -> None:
        """Test Claude CLI error message."""
        message = LLMErrorHandler.format_auth_error("claude-cli")

        assert "Claude-cli" in message
        assert "which claude-cli" in message
        assert "subscription" in message.lower()

    def test_format_auth_error_codex_cli(self) -> None:
        """Test Codex CLI error message."""
        message = LLMErrorHandler.format_auth_error("codex-cli")

        assert "Codex-cli" in message
        assert "which codex-cli" in message
        assert "github.com/features/copilot" in message


class TestConfigErrorFormatting:
    """Tests for configuration error formatting."""

    def test_format_config_error_provider(self) -> None:
        """Test provider config error message."""
        message = LLMErrorHandler.format_config_error("provider", "invalid-provider")

        assert "provider" in message
        assert "invalid-provider" in message
        assert "anthropic" in message
        assert "openai" in message
        assert "ollama" in message

    def test_format_config_error_model(self) -> None:
        """Test model config error message."""
        message = LLMErrorHandler.format_config_error("model", "invalid-model")

        assert "model" in message
        assert "invalid-model" in message
        assert "claude-haiku" in message
        assert "gpt-4o" in message

    def test_format_config_error_max_tokens(self) -> None:
        """Test max_tokens config error message."""
        message = LLMErrorHandler.format_config_error("max_tokens", -1)

        assert "max_tokens" in message
        assert "-1" in message
        assert "positive integer" in message

    def test_format_config_error_temperature(self) -> None:
        """Test temperature config error message."""
        message = LLMErrorHandler.format_config_error("temperature", 1.5)

        assert "temperature" in message
        assert "1.5" in message
        assert "0.0 and 1.0" in message

    def test_format_config_error_confidence_threshold(self) -> None:
        """Test confidence_threshold config error message."""
        message = LLMErrorHandler.format_config_error("confidence_threshold", -0.1)

        assert "confidence_threshold" in message
        assert "-0.1" in message or "0.1" in message
        assert "0.0 and 1.0" in message

    def test_format_config_error_api_key_sanitized(self) -> None:
        """Test API key in config error value is sanitized."""
        message = LLMErrorHandler.format_config_error("api_key", "sk-ant-secret123")

        assert "sk-ant-secret123" not in message
        assert "[REDACTED_API_KEY]" in message


class TestModelErrorFormatting:
    """Tests for model not available error formatting."""

    def test_format_model_error_ollama(self) -> None:
        """Test Ollama model error message."""
        message = LLMErrorHandler.format_model_error("ollama", "nonexistent-model")

        assert "Ollama" in message
        assert "nonexistent-model" in message
        assert "ollama pull" in message
        assert "ollama list" in message
        assert "llama3.3:70b" in message

    def test_format_model_error_anthropic(self) -> None:
        """Test Anthropic model error message."""
        message = LLMErrorHandler.format_model_error("anthropic", "invalid-model")

        assert "Anthropic" in message
        assert "invalid-model" in message
        assert "claude-haiku-4-5" in message
        assert "claude-sonnet-4-5" in message
        assert "claude-opus-4-5" in message

    def test_format_model_error_openai(self) -> None:
        """Test OpenAI model error message."""
        message = LLMErrorHandler.format_model_error("openai", "invalid-model")

        assert "OpenAI" in message
        assert "invalid-model" in message
        assert "gpt-5-mini" in message
        assert "gpt-5-nano" in message
        assert "gpt-4o-mini" in message

    def test_format_model_error_api_key_sanitized(self) -> None:
        """Test API key in model name is sanitized."""
        message = LLMErrorHandler.format_model_error("ollama", "sk-ant-secret")

        assert "sk-ant-secret" not in message
        assert "[REDACTED_API_KEY]" in message


class TestProviderErrorFormatting:
    """Tests for provider-specific error formatting."""

    def test_format_provider_error_auth(self) -> None:
        """Test formatting of authentication error."""
        error = LLMAuthenticationError("Invalid API key")
        message = LLMErrorHandler.format_provider_error("anthropic", error)

        assert "Anthropic" in message
        assert "Authentication" in message
        assert "CR_LLM_API_KEY" in message

    def test_format_provider_error_rate_limit(self) -> None:
        """Test formatting of rate limit error."""
        error = LLMRateLimitError("Rate limit exceeded")
        message = LLMErrorHandler.format_provider_error("openai", error)

        assert "OpenAI" in message
        assert "Rate Limit" in message
        assert "wait" in message.lower()
        assert "caching" in message.lower()  # Suggests using cache

    def test_format_provider_error_timeout(self) -> None:
        """Test formatting of timeout error."""
        error = LLMTimeoutError("Request timed out after 30s")
        message = LLMErrorHandler.format_provider_error("anthropic", error)

        assert "Anthropic" in message
        assert "Timeout" in message
        assert "connection" in message.lower()

    def test_format_provider_error_api_error(self) -> None:
        """Test formatting of generic API error."""
        error = LLMAPIError("Service unavailable")
        message = LLMErrorHandler.format_provider_error("openai", error)

        assert "OpenAI" in message or "Openai" in message
        assert "API Error" in message
        assert "Service unavailable" in message

    def test_format_provider_error_config_error(self) -> None:
        """Test formatting of configuration error."""
        error = LLMConfigurationError("Invalid model")
        message = LLMErrorHandler.format_provider_error("anthropic", error)

        assert "Anthropic" in message
        assert "Configuration Error" in message
        assert "Invalid model" in message

    def test_format_provider_error_generic_exception(self) -> None:
        """Test formatting of generic exception."""
        error = ValueError("Unexpected error")
        message = LLMErrorHandler.format_provider_error("ollama", error)

        assert "Ollama" in message
        assert "ValueError" in message
        assert "Unexpected error" in message

    def test_format_provider_error_sanitizes_api_key(self) -> None:
        """Test error message with API key is sanitized."""
        error = LLMAPIError("Auth failed with key sk-ant-secret123")
        message = LLMErrorHandler.format_provider_error("anthropic", error)

        assert "sk-ant-secret123" not in message
        assert "[REDACTED_API_KEY]" in message


class TestErrorMessageQuality:
    """Tests for error message quality and user experience."""

    def test_all_auth_errors_have_debug_hint(self) -> None:
        """Test all auth error messages suggest --log-level DEBUG."""
        providers = ["anthropic", "openai", "ollama", "claude-cli", "codex-cli"]

        for provider in providers:
            message = LLMErrorHandler.format_auth_error(provider)
            assert "--log-level DEBUG" in message, f"Missing DEBUG hint for {provider}"

    def test_all_config_errors_have_examples(self) -> None:
        """Test all config error messages have examples."""
        fields = ["provider", "model", "max_tokens", "temperature"]

        for field in fields:
            message = LLMErrorHandler.format_config_error(field, "invalid")
            # Should have either "Example:" or specific usage guidance
            assert (
                "Example:" in message or "example" in message.lower()
            ), f"Missing example for {field}"

    def test_all_model_errors_have_alternatives(self) -> None:
        """Test all model error messages suggest alternatives."""
        providers = ["anthropic", "openai", "ollama"]

        for provider in providers:
            message = LLMErrorHandler.format_model_error(provider, "invalid")
            # Should list alternative models
            assert any(
                model in message.lower() for model in ["claude", "gpt", "llama", "mistral"]
            ), f"Missing model alternatives for {provider}"

    def test_error_messages_use_emojis(self) -> None:
        """Test error messages use emojis for visual clarity."""
        error = LLMAPIError("Test error")
        message = LLMErrorHandler.format_provider_error("anthropic", error)

        # Should have at least one emoji
        assert any(
            char in message for char in ["❌", "⚠️", "⏱️", "💡"]
        ), "Error message missing visual indicator"
