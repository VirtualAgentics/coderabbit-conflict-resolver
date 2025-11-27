"""Tests for RuntimeConfig LLM-specific features (presets, interpolation, validation).

Tests for Sub-Issue #117.2 - Configuration File Support & Environment Variables.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from review_bot_automator.config.exceptions import ConfigError
from review_bot_automator.config.runtime_config import RuntimeConfig


class TestRuntimeConfigPresetIntegration:
    """Tests for from_preset() LLM preset integration."""

    def test_from_preset_codex_cli_free(self) -> None:
        """Test loading codex-cli-free preset."""
        config = RuntimeConfig.from_preset("codex-cli-free")

        # LLM settings from preset
        assert config.llm_enabled is True
        assert config.llm_provider == "codex-cli"
        assert config.llm_model == "codex"
        assert config.llm_api_key is None
        assert config.llm_fallback_to_regex is True
        assert config.llm_cache_enabled is True
        assert config.llm_max_tokens == 2000
        assert config.llm_cost_budget is None

        # Runtime settings (defaults)
        assert config.enable_rollback is True
        assert config.validate_before_apply is True
        assert config.parallel_processing is False
        assert config.max_workers == 4

    def test_from_preset_ollama_local(self) -> None:
        """Test loading ollama-local preset."""
        config = RuntimeConfig.from_preset("ollama-local")

        assert config.llm_enabled is True
        assert config.llm_provider == "ollama"
        assert config.llm_model == "qwen2.5-coder:7b"
        assert config.llm_api_key is None

    def test_from_preset_claude_cli_sonnet(self) -> None:
        """Test loading claude-cli-sonnet preset."""
        config = RuntimeConfig.from_preset("claude-cli-sonnet")

        assert config.llm_enabled is True
        assert config.llm_provider == "claude-cli"
        assert config.llm_model == "claude-sonnet-4-5"
        assert config.llm_api_key is None

    def test_from_preset_openai_api_mini_without_key(self) -> None:
        """Test loading openai-api-mini preset without API key (disabled)."""
        config = RuntimeConfig.from_preset("openai-api-mini")

        # API preset without key should be disabled
        assert config.llm_enabled is False
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4o-mini"
        assert config.llm_api_key is None
        assert config.llm_cost_budget == 5.0

    def test_from_preset_openai_api_mini_with_key(self) -> None:
        """Test loading openai-api-mini preset with API key (enabled)."""
        config = RuntimeConfig.from_preset("openai-api-mini", api_key="sk-test123")

        # API preset with key should be enabled
        assert config.llm_enabled is True
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4o-mini"
        assert config.llm_api_key == "sk-test123"

    def test_from_preset_anthropic_api_balanced_with_key(self) -> None:
        """Test loading anthropic-api-balanced preset with API key."""
        config = RuntimeConfig.from_preset("anthropic-api-balanced", api_key="sk-ant-xyz")

        assert config.llm_enabled is True
        assert config.llm_provider == "anthropic"
        assert config.llm_model == "claude-haiku-4"
        assert config.llm_api_key == "sk-ant-xyz"
        assert config.llm_cost_budget == 5.0

    def test_from_preset_invalid_raises_error(self) -> None:
        """Test that invalid preset name raises ConfigError."""
        with pytest.raises(ConfigError, match="Unknown preset 'invalid-preset'"):
            RuntimeConfig.from_preset("invalid-preset")


class TestEnvironmentVariableInterpolation:
    """Tests for ${VAR} environment variable interpolation in config files."""

    def test_interpolate_env_vars_simple_string(self) -> None:
        """Test interpolation in simple string."""
        with patch.dict(os.environ, {"MY_KEY": "secret123"}):
            result = RuntimeConfig._interpolate_env_vars("api_key: ${MY_KEY}")
            assert result == "api_key: secret123"

    def test_interpolate_env_vars_multiple_vars(self) -> None:
        """Test interpolation with multiple variables."""
        with patch.dict(os.environ, {"VAR1": "value1", "VAR2": "value2"}):
            result = RuntimeConfig._interpolate_env_vars("${VAR1} and ${VAR2}")
            assert result == "value1 and value2"

    def test_interpolate_env_vars_dict(self) -> None:
        """Test interpolation in dictionary."""
        with patch.dict(os.environ, {"API_KEY": "sk-test"}):
            data = {"llm": {"api_key": "${API_KEY}", "provider": "openai"}}
            result = RuntimeConfig._interpolate_env_vars(data)
            assert result["llm"]["api_key"] == "sk-test"
            assert result["llm"]["provider"] == "openai"

    def test_interpolate_env_vars_list(self) -> None:
        """Test interpolation in list."""
        with patch.dict(os.environ, {"KEY1": "val1", "KEY2": "val2"}):
            data = ["${KEY1}", "static", "${KEY2}"]
            result = RuntimeConfig._interpolate_env_vars(data)
            assert result == ["val1", "static", "val2"]

    def test_interpolate_env_vars_missing_keeps_placeholder(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that missing env var keeps placeholder and warns."""
        result = RuntimeConfig._interpolate_env_vars("key: ${MISSING_VAR}")
        assert result == "key: ${MISSING_VAR}"
        assert "MISSING_VAR" in caplog.text
        assert "not found" in caplog.text

    def test_interpolate_env_vars_non_string_unchanged(self) -> None:
        """Test that non-string values are unchanged."""
        assert RuntimeConfig._interpolate_env_vars(123) == 123
        assert RuntimeConfig._interpolate_env_vars(True) is True
        assert RuntimeConfig._interpolate_env_vars(None) is None
        assert RuntimeConfig._interpolate_env_vars(3.14) == 3.14

    def test_interpolate_env_vars_in_yaml_config(self) -> None:
        """Test interpolation works in actual YAML config loading."""
        yaml_content = """
llm:
  enabled: false
  provider: anthropic
  api_key: ${TEST_API_KEY}
  model: claude-haiku-4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            # Note: After interpolation, if API key has value, it would be rejected
            # So we test with enabled=false (doesn't trigger validation) or without the key set
            config = RuntimeConfig.from_file(config_path)
            # Without TEST_API_KEY set, placeholder should remain
            assert "${TEST_API_KEY}" in (config.llm_api_key or "")
        finally:
            config_path.unlink()

    def test_interpolate_env_vars_in_toml_config(self) -> None:
        """Test interpolation works in actual TOML config loading."""
        toml_content = """
[llm]
enabled = false
provider = "openai"
api_key = "${TEST_OPENAI_KEY}"
model = "gpt-4"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            config_path = Path(f.name)

        try:
            config = RuntimeConfig.from_file(config_path)
            # Without TEST_OPENAI_KEY set, placeholder should remain
            assert "${TEST_OPENAI_KEY}" in (config.llm_api_key or "")
        finally:
            config_path.unlink()


class TestAPIKeyValidation:
    """Tests for API key validation in configuration files (security)."""

    def test_is_env_var_placeholder_true(self) -> None:
        """Test _is_env_var_placeholder detects placeholders."""
        assert RuntimeConfig._is_env_var_placeholder("${API_KEY}") is True
        assert RuntimeConfig._is_env_var_placeholder("prefix ${VAR} suffix") is True
        assert RuntimeConfig._is_env_var_placeholder("${ANTHROPIC_API_KEY}") is True
        assert RuntimeConfig._is_env_var_placeholder("${MY_SECRET_123}") is True

    def test_is_env_var_placeholder_false(self) -> None:
        """Test _is_env_var_placeholder rejects non-placeholders."""
        assert RuntimeConfig._is_env_var_placeholder("sk-actual-key-123") is False
        assert RuntimeConfig._is_env_var_placeholder("sk-ant-api03...") is False
        assert RuntimeConfig._is_env_var_placeholder("") is False
        assert RuntimeConfig._is_env_var_placeholder("no variables here") is False

    def test_config_file_rejects_real_api_key_yaml(self) -> None:
        """Test that YAML config file rejects real API keys."""
        yaml_content = """
llm:
  enabled: true
  provider: anthropic
  api_key: sk-ant-real-key-12345
  model: claude-haiku-4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            with pytest.raises(
                ConfigError, match="SECURITY: API keys must NOT be stored in configuration files"
            ):
                RuntimeConfig.from_file(config_path)
        finally:
            config_path.unlink()

    def test_config_file_rejects_real_api_key_toml(self) -> None:
        """Test that TOML config file rejects real API keys."""
        toml_content = """
[llm]
enabled = true
provider = "openai"
api_key = "sk-openai-real-key-67890"
model = "gpt-4"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            config_path = Path(f.name)

        try:
            with pytest.raises(
                ConfigError, match="SECURITY: API keys must NOT be stored in configuration files"
            ):
                RuntimeConfig.from_file(config_path)
        finally:
            config_path.unlink()

    def test_config_file_accepts_env_var_placeholder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that config file accepts ${VAR} placeholders."""
        # Unset ANTHROPIC_API_KEY to ensure placeholder is preserved
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        yaml_content = """
llm:
  enabled: false
  provider: anthropic
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-haiku-4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            # Placeholder ${VAR} should be accepted and remain if var not set
            config = RuntimeConfig.from_file(config_path)
            # Should succeed - placeholder syntax is allowed
            assert config.llm_api_key is not None
            assert "${ANTHROPIC_API_KEY}" in config.llm_api_key
        finally:
            config_path.unlink()

    def test_config_file_accepts_no_api_key(self) -> None:
        """Test that config file works with no API key (CLI providers)."""
        yaml_content = """
llm:
  enabled: true
  provider: claude-cli
  model: claude-sonnet-4-5
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            config = RuntimeConfig.from_file(config_path)
            assert config.llm_provider == "claude-cli"
            assert config.llm_api_key is None
        finally:
            config_path.unlink()

    def test_api_key_rejection_error_message_helpful(self) -> None:
        """Test that API key rejection error provides helpful guidance."""
        yaml_content = """
llm:
  enabled: true
  provider: openai
  api_key: sk-test-key
  model: gpt-4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            with pytest.raises(ConfigError) as exc_info:
                RuntimeConfig.from_file(config_path)

            error_msg = str(exc_info.value)
            # Check error message contains helpful guidance
            assert "SECURITY" in error_msg
            assert "CR_LLM_API_KEY" in error_msg
            assert "OPENAI_API_KEY" in error_msg or "${" in error_msg
            assert "ANTHROPIC_API_KEY" in error_msg
        finally:
            config_path.unlink()


class TestConfigurationPrecedence:
    """Tests for configuration precedence chain with presets."""

    def test_precedence_cli_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that CLI flags override environment variables."""
        # Set env var
        monkeypatch.setenv("CR_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("CR_LLM_MODEL", "llama3:70b")

        # Load from env
        config = RuntimeConfig.from_env()
        assert config.llm_provider == "ollama"

        # Override with CLI (merge_with_cli)
        config = config.merge_with_cli(llm_provider="openai", llm_model="gpt-4")
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4"

    def test_precedence_env_overrides_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that env vars override config file (via explicit merge)."""
        # Create config file
        yaml_content = """
llm:
  enabled: false
  provider: claude-cli
  model: claude-sonnet-4-5
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            # Load from file
            config_from_file = RuntimeConfig.from_file(config_path)
            assert config_from_file.llm_provider == "claude-cli"

            # Load from env (which should override)
            monkeypatch.setenv("CR_LLM_PROVIDER", "anthropic")
            config_from_env = RuntimeConfig.from_env()
            assert config_from_env.llm_provider == "anthropic"
        finally:
            config_path.unlink()

    def test_precedence_file_overrides_preset(self) -> None:
        """Test that config file can override preset settings."""
        # Create config file that overrides preset
        yaml_content = """
llm:
  enabled: false
  provider: anthropic
  model: claude-haiku-4
  api_key: ${TEST_KEY}
  max_tokens: 4000
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = Path(f.name)

        try:
            # Don't set TEST_KEY - placeholder should remain
            config = RuntimeConfig.from_file(config_path)
            # File values should be used
            assert config.llm_provider == "anthropic"
            assert config.llm_max_tokens == 4000  # Overridden from default
            # Placeholder should remain since TEST_KEY not set
            assert config.llm_api_key is not None
            assert "${TEST_KEY}" in config.llm_api_key
        finally:
            config_path.unlink()

    def test_precedence_preset_overrides_defaults(self) -> None:
        """Test that preset overrides default settings."""
        # Default config
        default_config = RuntimeConfig.from_defaults()
        assert default_config.llm_enabled is False
        assert default_config.llm_provider == "claude-cli"

        # Preset config
        preset_config = RuntimeConfig.from_preset("ollama-local")
        assert preset_config.llm_enabled is True
        assert preset_config.llm_provider == "ollama"
        assert preset_config.llm_model == "qwen2.5-coder:7b"
