"""Tests for LLM provider factory and selection logic.

This module tests the factory functions for creating and validating LLM providers.
Covers all 5 providers with comprehensive mocking to avoid real API calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from pr_conflict_resolver.llm.config import LLMConfig
from pr_conflict_resolver.llm.exceptions import LLMAPIError, LLMConfigurationError
from pr_conflict_resolver.llm.factory import (
    _PROVIDERS_REQUIRING_API_KEY,
    PROVIDER_REGISTRY,
    create_provider,
    create_provider_from_config,
    validate_provider,
)


class TestProviderRegistry:
    """Test PROVIDER_REGISTRY constant and related sets."""

    def test_registry_contains_all_providers(self) -> None:
        """Test that registry contains all 5 expected providers."""
        expected_providers = {"openai", "anthropic", "claude-cli", "codex-cli", "ollama"}
        assert set(PROVIDER_REGISTRY.keys()) == expected_providers

    def test_providers_requiring_api_key(self) -> None:
        """Test that API key requirement set is correct."""
        assert frozenset({"openai", "anthropic"}) == _PROVIDERS_REQUIRING_API_KEY

    def test_registry_classes_are_not_none(self) -> None:
        """Test that all registry values are provider classes."""
        for _provider_name, provider_class in PROVIDER_REGISTRY.items():
            assert provider_class is not None
            assert callable(provider_class)


class TestCreateProvider:
    """Test create_provider() function."""

    def test_create_openai_provider(self) -> None:
        """Test creating OpenAI provider with valid API key."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"openai": mock_provider_class}):
            result = create_provider("openai", model="gpt-4", api_key="test-key")

        mock_provider_class.assert_called_once_with(
            api_key="test-key",
            model="gpt-4",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_anthropic_provider(self) -> None:
        """Test creating Anthropic provider with valid API key."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"anthropic": mock_provider_class}):
            result = create_provider("anthropic", model="claude-sonnet-4", api_key="sk-ant-test")

        mock_provider_class.assert_called_once_with(
            api_key="sk-ant-test",
            model="claude-sonnet-4",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_claude_cli_provider(self) -> None:
        """Test creating Claude CLI provider without API key."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"claude-cli": mock_provider_class}):
            result = create_provider("claude-cli", model="claude-sonnet-4-5")

        mock_provider_class.assert_called_once_with(
            model="claude-sonnet-4-5",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_codex_cli_provider(self) -> None:
        """Test creating Codex CLI provider without API key."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"codex-cli": mock_provider_class}):
            result = create_provider("codex-cli", model="codex-latest")

        mock_provider_class.assert_called_once_with(
            model="codex-latest",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_ollama_provider(self) -> None:
        """Test creating Ollama provider without API key."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"ollama": mock_provider_class}):
            result = create_provider("ollama", model="llama3.3:70b")

        mock_provider_class.assert_called_once_with(
            model="llama3.3:70b",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_with_custom_timeout(self) -> None:
        """Test creating provider with custom timeout."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"anthropic": mock_provider_class}):
            result = create_provider("anthropic", api_key="test", timeout=120)

        mock_provider_class.assert_called_once_with(
            api_key="test",
            timeout=120,
        )
        assert result == mock_instance

    def test_create_with_provider_specific_kwargs(self) -> None:
        """Test creating provider with provider-specific kwargs."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"ollama": mock_provider_class}):
            result = create_provider("ollama", model="llama3", base_url="http://localhost:11434")

        mock_provider_class.assert_called_once_with(
            model="llama3",
            timeout=60,
            base_url="http://localhost:11434",
        )
        assert result == mock_instance

    def test_create_with_default_model(self) -> None:
        """Test creating provider without explicit model (uses provider default)."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"claude-cli": mock_provider_class}):
            result = create_provider("claude-cli")

        mock_provider_class.assert_called_once_with(timeout=60)
        assert result == mock_instance

    def test_create_with_explicit_model(self) -> None:
        """Test creating provider with explicit model."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"openai": mock_provider_class}):
            result = create_provider("openai", model="gpt-4-turbo", api_key="test")

        mock_provider_class.assert_called_once_with(
            api_key="test",
            model="gpt-4-turbo",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_passes_through_kwargs(self) -> None:
        """Test that extra kwargs are passed through to provider."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"ollama": mock_provider_class}):
            result = create_provider("ollama", custom_param="value", another_param=123)

        mock_provider_class.assert_called_once_with(
            timeout=60,
            custom_param="value",
            another_param=123,
        )
        assert result == mock_instance


class TestCreateProviderValidation:
    """Test validation logic in create_provider()."""

    def test_invalid_provider_name_raises(self) -> None:
        """Test that invalid provider name raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            create_provider("invalid-provider")

        assert "Invalid provider 'invalid-provider'" in str(exc_info.value)
        assert "Valid providers" in str(exc_info.value)

    def test_openai_requires_api_key(self) -> None:
        """Test that OpenAI provider requires API key."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            create_provider("openai")

        assert "API key required for 'openai' provider" in str(exc_info.value)
        assert "CR_LLM_API_KEY" in str(exc_info.value)

    def test_anthropic_requires_api_key(self) -> None:
        """Test that Anthropic provider requires API key."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            create_provider("anthropic")

        assert "API key required for 'anthropic' provider" in str(exc_info.value)
        assert "CR_LLM_API_KEY" in str(exc_info.value)

    def test_cli_providers_no_api_key_required(self) -> None:
        """Test that CLI providers don't require API key."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"claude-cli": mock_provider_class}):
            # Should not raise
            result = create_provider("claude-cli")
            assert result == mock_instance

    def test_ollama_no_api_key_required(self) -> None:
        """Test that Ollama provider doesn't require API key."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        with patch.dict(PROVIDER_REGISTRY, {"ollama": mock_provider_class}):
            # Should not raise
            result = create_provider("ollama")
            assert result == mock_instance

    def test_empty_api_key_raises(self) -> None:
        """Test that empty API key raises LLMConfigurationError."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            create_provider("openai", api_key="   ")

        assert "API key cannot be empty" in str(exc_info.value)

    def test_invalid_timeout_raises(self) -> None:
        """Test that invalid timeout raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_provider("claude-cli", timeout=0)

        assert "timeout must be positive" in str(exc_info.value)

    def test_negative_timeout_raises(self) -> None:
        """Test that negative timeout raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_provider("claude-cli", timeout=-10)

        assert "timeout must be positive" in str(exc_info.value)

    def test_helpful_error_messages(self) -> None:
        """Test that error messages include helpful troubleshooting info."""
        with pytest.raises(LLMConfigurationError) as exc_info:
            create_provider("anthropic")

        error_msg = str(exc_info.value)
        assert "anthropic" in error_msg
        assert "CR_LLM_API_KEY" in error_msg


class TestValidateProvider:
    """Test validate_provider() health check function."""

    def test_validate_provider_success(self) -> None:
        """Test successful provider validation."""
        mock_provider = MagicMock()
        mock_provider.count_tokens.return_value = 1

        result = validate_provider(mock_provider)

        assert result is True
        mock_provider.count_tokens.assert_called_once_with("test")

    def test_validate_provider_failure(self) -> None:
        """Test provider validation failure raises error."""
        mock_provider = MagicMock()
        mock_provider.count_tokens.side_effect = LLMAPIError("Connection failed")

        with pytest.raises(LLMAPIError) as exc_info:
            validate_provider(mock_provider)

        assert "Connection failed" in str(exc_info.value)

    def test_validate_provider_generic_exception(self) -> None:
        """Test that generic exceptions are wrapped in LLMAPIError."""
        mock_provider = MagicMock()
        mock_provider.count_tokens.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(LLMAPIError) as exc_info:
            validate_provider(mock_provider)

        assert "Provider health check failed" in str(exc_info.value)
        assert "Unexpected error" in str(exc_info.value)

    def test_validate_with_custom_timeout(self) -> None:
        """Test validation with custom timeout parameter."""
        mock_provider = MagicMock()
        mock_provider.count_tokens.return_value = 1

        # timeout parameter doesn't affect token counting, but should be accepted
        result = validate_provider(mock_provider, timeout=10)

        assert result is True
        mock_provider.count_tokens.assert_called_once()

    def test_validate_handles_configuration_error(self) -> None:
        """Test that configuration errors are re-raised as-is."""
        mock_provider = MagicMock()
        mock_provider.count_tokens.side_effect = LLMConfigurationError("Not configured")

        with pytest.raises(LLMConfigurationError) as exc_info:
            validate_provider(mock_provider)

        assert "Not configured" in str(exc_info.value)

    def test_validate_returns_boolean(self) -> None:
        """Test that validate_provider returns True on success."""
        mock_provider = MagicMock()
        mock_provider.count_tokens.return_value = 42

        result = validate_provider(mock_provider)

        assert isinstance(result, bool)
        assert result is True


class TestCreateProviderFromConfig:
    """Test create_provider_from_config() helper."""

    def test_create_from_config_anthropic(self) -> None:
        """Test creating Anthropic provider from config."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        config = LLMConfig(
            enabled=True,
            provider="anthropic",
            model="claude-sonnet-4",
            api_key="sk-ant-test",
        )

        with patch.dict(PROVIDER_REGISTRY, {"anthropic": mock_provider_class}):
            result = create_provider_from_config(config)

        mock_provider_class.assert_called_once_with(
            api_key="sk-ant-test",
            model="claude-sonnet-4",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_from_config_openai(self) -> None:
        """Test creating OpenAI provider from config."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        config = LLMConfig(
            enabled=True,
            provider="openai",
            model="gpt-4",
            api_key="sk-test-123",
        )

        with patch.dict(PROVIDER_REGISTRY, {"openai": mock_provider_class}):
            result = create_provider_from_config(config)

        mock_provider_class.assert_called_once_with(
            api_key="sk-test-123",
            model="gpt-4",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_from_config_claude_cli(self) -> None:
        """Test creating Claude CLI provider from config."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        config = LLMConfig(
            enabled=True,
            provider="claude-cli",
            model="claude-sonnet-4-5",
        )

        with patch.dict(PROVIDER_REGISTRY, {"claude-cli": mock_provider_class}):
            result = create_provider_from_config(config)

        mock_provider_class.assert_called_once_with(
            model="claude-sonnet-4-5",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_from_config_codex_cli(self) -> None:
        """Test creating Codex CLI provider from config."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        config = LLMConfig(
            enabled=True,
            provider="codex-cli",
            model="codex-latest",
        )

        with patch.dict(PROVIDER_REGISTRY, {"codex-cli": mock_provider_class}):
            result = create_provider_from_config(config)

        mock_provider_class.assert_called_once_with(
            model="codex-latest",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_from_config_ollama(self) -> None:
        """Test creating Ollama provider from config."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        config = LLMConfig(
            enabled=True,
            provider="ollama",
            model="llama3.3:70b",
        )

        with patch.dict(PROVIDER_REGISTRY, {"ollama": mock_provider_class}):
            result = create_provider_from_config(config)

        mock_provider_class.assert_called_once_with(
            model="llama3.3:70b",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_from_config_uses_config_values(self) -> None:
        """Test that config values are correctly extracted."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        config = LLMConfig(
            enabled=False,  # Shouldn't affect provider creation
            provider="claude-cli",
            model="custom-model",
            api_key=None,  # CLI doesn't need API key
        )

        with patch.dict(PROVIDER_REGISTRY, {"claude-cli": mock_provider_class}):
            result = create_provider_from_config(config)

        mock_provider_class.assert_called_once_with(
            model="custom-model",
            timeout=60,
        )
        assert result == mock_instance

    def test_create_from_config_with_api_key(self) -> None:
        """Test config with API key is passed through."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        config = LLMConfig(
            enabled=True,
            provider="anthropic",
            model="claude-3",
            api_key="test-key-123",
        )

        with patch.dict(PROVIDER_REGISTRY, {"anthropic": mock_provider_class}):
            result = create_provider_from_config(config)

        mock_provider_class.assert_called_once()
        call_kwargs = mock_provider_class.call_args[1]
        assert call_kwargs["api_key"] == "test-key-123"
        assert result == mock_instance

    def test_create_from_config_without_api_key(self) -> None:
        """Test config without API key for CLI providers."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        config = LLMConfig(
            enabled=True,
            provider="claude-cli",
            model="claude-sonnet-4-5",
            api_key=None,
        )

        with patch.dict(PROVIDER_REGISTRY, {"claude-cli": mock_provider_class}):
            result = create_provider_from_config(config)

        mock_provider_class.assert_called_once()
        call_kwargs = mock_provider_class.call_args[1]
        assert "api_key" not in call_kwargs
        assert result == mock_instance

    def test_create_from_config_passes_timeout(self) -> None:
        """Test that default timeout is passed to provider."""
        mock_provider_class = MagicMock()
        mock_instance = MagicMock()
        mock_provider_class.return_value = mock_instance

        config = LLMConfig(
            enabled=True,
            provider="anthropic",
            model="claude-3",
            api_key="test",
        )

        with patch.dict(PROVIDER_REGISTRY, {"anthropic": mock_provider_class}):
            result = create_provider_from_config(config)

        mock_provider_class.assert_called_once()
        call_kwargs = mock_provider_class.call_args[1]
        assert call_kwargs["timeout"] == 60
        assert result == mock_instance

    def test_create_from_config_error_handling(self) -> None:
        """Test that config validation errors are propagated."""
        # Config with invalid provider should raise during config validation
        with pytest.raises(ValueError):
            config = LLMConfig(
                enabled=True,
                provider="invalid-provider",  # Will fail LLMConfig validation
            )
            create_provider_from_config(config)
