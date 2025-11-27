"""Unit tests for RuntimeConfig in review_bot_automator.config.runtime_config."""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from review_bot_automator.config.exceptions import ConfigError
from review_bot_automator.config.runtime_config import ApplicationMode, RuntimeConfig


class TestApplicationMode:
    """Test ApplicationMode enum."""

    def test_all_mode_value(self) -> None:
        assert ApplicationMode.ALL.value == "all"
        assert str(ApplicationMode.ALL) == "all"

    def test_conflicts_only_mode_value(self) -> None:
        assert ApplicationMode.CONFLICTS_ONLY.value == "conflicts-only"
        assert str(ApplicationMode.CONFLICTS_ONLY) == "conflicts-only"

    def test_non_conflicts_only_mode_value(self) -> None:
        assert ApplicationMode.NON_CONFLICTS_ONLY.value == "non-conflicts-only"
        assert str(ApplicationMode.NON_CONFLICTS_ONLY) == "non-conflicts-only"

    def test_dry_run_mode_value(self) -> None:
        assert ApplicationMode.DRY_RUN.value == "dry-run"
        assert str(ApplicationMode.DRY_RUN) == "dry-run"

    def test_mode_from_string(self) -> None:
        assert ApplicationMode("all") == ApplicationMode.ALL
        assert ApplicationMode("conflicts-only") == ApplicationMode.CONFLICTS_ONLY
        assert ApplicationMode("non-conflicts-only") == ApplicationMode.NON_CONFLICTS_ONLY
        assert ApplicationMode("dry-run") == ApplicationMode.DRY_RUN

    def test_invalid_mode_raises_error(self) -> None:
        with pytest.raises(ValueError):
            ApplicationMode("invalid-mode")


class TestRuntimeConfigDefaults:
    """Test RuntimeConfig default values."""

    def test_from_defaults_mode(self) -> None:
        config = RuntimeConfig.from_defaults()
        assert config.mode == ApplicationMode.ALL

    def test_from_defaults_rollback(self) -> None:
        config = RuntimeConfig.from_defaults()
        assert config.enable_rollback is True

    def test_from_defaults_validation(self) -> None:
        config = RuntimeConfig.from_defaults()
        assert config.validate_before_apply is True

    def test_from_defaults_parallel(self) -> None:
        config = RuntimeConfig.from_defaults()
        assert config.parallel_processing is False

    def test_from_defaults_max_workers(self) -> None:
        config = RuntimeConfig.from_defaults()
        assert config.max_workers == 4

    def test_from_defaults_log_level(self) -> None:
        config = RuntimeConfig.from_defaults()
        assert config.log_level == "INFO"

    def test_from_defaults_log_file(self) -> None:
        config = RuntimeConfig.from_defaults()
        assert config.log_file is None

    def test_from_defaults_llm_confidence_threshold(self) -> None:
        config = RuntimeConfig.from_defaults()
        assert config.llm_confidence_threshold == 0.5


class TestRuntimeConfigFromEnv:
    """Test RuntimeConfig.from_env() with environment variables."""

    def test_from_env_default_when_no_vars(self) -> None:
        """When no env vars set, should return defaults."""
        with patch.dict(os.environ, {}, clear=False):
            # Clear any CR_ vars
            env_copy = {k: v for k, v in os.environ.items() if not k.startswith("CR_")}
            with patch.dict(os.environ, env_copy, clear=True):
                config = RuntimeConfig.from_env()
                assert config.mode == ApplicationMode.ALL
                assert config.enable_rollback is True
                assert config.validate_before_apply is True
                assert config.parallel_processing is False
                assert config.max_workers == 4
                assert config.log_level == "INFO"
                assert config.log_file is None

    def test_from_env_mode_dry_run(self) -> None:
        with patch.dict(os.environ, {"CR_MODE": "dry-run"}):
            config = RuntimeConfig.from_env()
            assert config.mode == ApplicationMode.DRY_RUN

    def test_from_env_mode_conflicts_only(self) -> None:
        with patch.dict(os.environ, {"CR_MODE": "conflicts-only"}):
            config = RuntimeConfig.from_env()
            assert config.mode == ApplicationMode.CONFLICTS_ONLY

    def test_from_env_mode_non_conflicts_only(self) -> None:
        with patch.dict(os.environ, {"CR_MODE": "non-conflicts-only"}):
            config = RuntimeConfig.from_env()
            assert config.mode == ApplicationMode.NON_CONFLICTS_ONLY

    def test_from_env_enable_rollback_false(self) -> None:
        with patch.dict(os.environ, {"CR_ENABLE_ROLLBACK": "false"}):
            config = RuntimeConfig.from_env()
            assert config.enable_rollback is False

    def test_from_env_enable_rollback_true_variants(self, subtests: pytest.Subtests) -> None:
        """Test various true values using subtests."""
        for value in ["true", "True", "1", "yes", "on"]:
            with (
                subtests.test(msg=f"Boolean true variant: {value}", value=value),
                patch.dict(os.environ, {"CR_ENABLE_ROLLBACK": value}),
            ):
                config = RuntimeConfig.from_env()
                assert config.enable_rollback is True

    def test_from_env_enable_rollback_false_variants(self, subtests: pytest.Subtests) -> None:
        """Test various false values using subtests."""
        for value in ["false", "False", "0", "no", "off"]:
            with (
                subtests.test(msg=f"Boolean false variant: {value}", value=value),
                patch.dict(os.environ, {"CR_ENABLE_ROLLBACK": value}),
            ):
                config = RuntimeConfig.from_env()
                assert config.enable_rollback is False

    def test_from_env_validate_false(self) -> None:
        with patch.dict(os.environ, {"CR_VALIDATE": "false"}):
            config = RuntimeConfig.from_env()
            assert config.validate_before_apply is False

    def test_from_env_parallel_true(self) -> None:
        with patch.dict(os.environ, {"CR_PARALLEL": "true"}):
            config = RuntimeConfig.from_env()
            assert config.parallel_processing is True

    def test_from_env_max_workers(self) -> None:
        with patch.dict(os.environ, {"CR_MAX_WORKERS": "8"}):
            config = RuntimeConfig.from_env()
            assert config.max_workers == 8

    def test_from_env_log_level(self) -> None:
        with patch.dict(os.environ, {"CR_LOG_LEVEL": "debug"}):
            config = RuntimeConfig.from_env()
            assert config.log_level == "DEBUG"

    def test_from_env_log_file(self) -> None:
        with patch.dict(os.environ, {"CR_LOG_FILE": "/tmp/test.log"}):
            config = RuntimeConfig.from_env()
            assert config.log_file == "/tmp/test.log"

    def test_from_env_invalid_mode_raises(self) -> None:
        with (
            patch.dict(os.environ, {"CR_MODE": "invalid"}),
            pytest.raises(ConfigError, match="Invalid CR_MODE"),
        ):
            RuntimeConfig.from_env()

    def test_from_env_invalid_boolean_raises(self) -> None:
        with (
            patch.dict(os.environ, {"CR_ENABLE_ROLLBACK": "maybe"}),
            pytest.raises(ConfigError, match="Invalid CR_ENABLE_ROLLBACK"),
        ):
            RuntimeConfig.from_env()

    def test_from_env_invalid_max_workers_raises(self) -> None:
        with (
            patch.dict(os.environ, {"CR_MAX_WORKERS": "invalid"}),
            pytest.raises(ConfigError, match="Invalid CR_MAX_WORKERS"),
        ):
            RuntimeConfig.from_env()

    def test_from_env_max_workers_zero_raises(self) -> None:
        with (
            patch.dict(os.environ, {"CR_MAX_WORKERS": "0"}),
            pytest.raises(ConfigError, match="must be >= 1"),
        ):
            RuntimeConfig.from_env()

    def test_from_env_llm_confidence_threshold(self) -> None:
        with patch.dict(os.environ, {"CR_LLM_CONFIDENCE_THRESHOLD": "0.75"}):
            config = RuntimeConfig.from_env()
            assert config.llm_confidence_threshold == 0.75

    def test_from_env_llm_confidence_threshold_too_low(self) -> None:
        with (
            patch.dict(os.environ, {"CR_LLM_CONFIDENCE_THRESHOLD": "-0.1"}),
            pytest.raises(ConfigError, match="CR_LLM_CONFIDENCE_THRESHOLD"),
        ):
            RuntimeConfig.from_env()

    def test_from_env_llm_confidence_threshold_too_high(self) -> None:
        with (
            patch.dict(os.environ, {"CR_LLM_CONFIDENCE_THRESHOLD": "1.5"}),
            pytest.raises(ConfigError, match="CR_LLM_CONFIDENCE_THRESHOLD"),
        ):
            RuntimeConfig.from_env()


class TestRuntimeConfigFromFile:
    """Test RuntimeConfig.from_file() with YAML/TOML files."""

    def test_from_file_yaml_basic(self) -> None:
        """Test loading basic YAML config."""
        yaml_content = """
mode: dry-run
rollback:
  enabled: false
validation:
  enabled: true
parallel:
  enabled: true
  max_workers: 8
logging:
  level: DEBUG
  file: /tmp/test.log
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                config = RuntimeConfig.from_file(Path(f.name))
                assert config.mode == ApplicationMode.DRY_RUN
                assert config.enable_rollback is False
                assert config.validate_before_apply is True
                assert config.parallel_processing is True
                assert config.max_workers == 8
                assert config.log_level == "DEBUG"
                assert config.log_file == "/tmp/test.log"
            finally:
                os.unlink(f.name)

    def test_from_file_toml_basic(self) -> None:
        """Test loading basic TOML config."""
        toml_content = """
mode = "conflicts-only"

[rollback]
enabled = true

[validation]
enabled = false

[parallel]
enabled = false
max_workers = 4

[logging]
level = "WARNING"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            try:
                config = RuntimeConfig.from_file(Path(f.name))
                assert config.mode == ApplicationMode.CONFLICTS_ONLY
                assert config.enable_rollback is True
                assert config.validate_before_apply is False
                assert config.parallel_processing is False
                assert config.max_workers == 4
                assert config.log_level == "WARNING"
            finally:
                os.unlink(f.name)

    def test_from_file_yaml_with_llm_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading YAML with LLM configuration section."""
        # Unset ANTHROPIC_API_KEY to ensure placeholder is preserved
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        yaml_content = """
mode: all
rollback:
  enabled: true
llm:
  enabled: false
  provider: anthropic
  model: claude-3-opus
  api_key: ${ANTHROPIC_API_KEY}
  fallback_to_regex: false
  cache_enabled: true
  max_tokens: 4000
  confidence_threshold: 0.65
  cost_budget: 50.0
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                config = RuntimeConfig.from_file(Path(f.name))
                # LLM fields
                assert config.llm_enabled is False
                assert config.llm_provider == "anthropic"
                assert config.llm_model == "claude-3-opus"
                assert config.llm_api_key is not None
                assert "${ANTHROPIC_API_KEY}" in config.llm_api_key
                assert config.llm_fallback_to_regex is False
                assert config.llm_cache_enabled is True
                assert config.llm_max_tokens == 4000
                assert config.llm_confidence_threshold == 0.65
                assert config.llm_cost_budget == 50.0
                # Non-LLM fields from YAML
                assert config.mode == ApplicationMode.ALL
                assert config.enable_rollback is True
            finally:
                os.unlink(f.name)

    def test_from_file_yaml_partial_config(self) -> None:
        """Test YAML with only some fields (rest should be defaults)."""
        yaml_content = """
mode: non-conflicts-only
parallel:
  enabled: true
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                config = RuntimeConfig.from_file(Path(f.name))
                assert config.mode == ApplicationMode.NON_CONFLICTS_ONLY
                assert config.parallel_processing is True
                # Defaults for non-specified fields
                assert config.enable_rollback is True
                assert config.validate_before_apply is True
                assert config.max_workers == 4
            finally:
                os.unlink(f.name)

    def test_from_file_nonexistent_raises(self) -> None:
        with pytest.raises(ConfigError, match="Config file not found"):
            RuntimeConfig.from_file(Path("/nonexistent/config.yaml"))

    def test_from_file_invalid_extension_raises(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test")
            f.flush()
            try:
                with pytest.raises(ConfigError, match="Unsupported config file format"):
                    RuntimeConfig.from_file(Path(f.name))
            finally:
                os.unlink(f.name)

    def test_from_file_invalid_yaml_raises(self) -> None:
        """Test malformed YAML raises ConfigError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [unclosed")
            f.flush()
            try:
                with pytest.raises(ConfigError, match="Invalid YAML"):
                    RuntimeConfig.from_file(Path(f.name))
            finally:
                os.unlink(f.name)

    def test_from_file_invalid_toml_raises(self) -> None:
        """Test malformed TOML raises ConfigError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[section\ninvalid toml")
            f.flush()
            try:
                with pytest.raises(ConfigError, match="Invalid TOML"):
                    RuntimeConfig.from_file(Path(f.name))
            finally:
                os.unlink(f.name)

    def test_from_file_invalid_mode_in_file_raises(self) -> None:
        """Test invalid mode in config file raises ConfigError."""
        yaml_content = "mode: invalid-mode"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                with pytest.raises(ConfigError, match="Invalid mode"):
                    RuntimeConfig.from_file(Path(f.name))
            finally:
                os.unlink(f.name)


class TestRuntimeConfigValidation:
    """Test RuntimeConfig validation in __post_init__."""

    def test_invalid_log_level_raises(self) -> None:
        with pytest.raises(ConfigError, match="Invalid log level"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=True,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INVALID",
                log_file=None,
            )

    def test_max_workers_less_than_one_raises(self) -> None:
        with pytest.raises(ConfigError, match="max_workers must be >= 1"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=True,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=0,
                log_level="INFO",
                log_file=None,
            )

    def test_max_workers_very_high_raises_error(self) -> None:
        """Test that max_workers > 32 raises ConfigError."""
        with pytest.raises(ConfigError, match="max_workers should be <= 32"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=True,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=64,
                log_level="INFO",
                log_file=None,
            )

    def test_llm_parallel_max_workers_too_high_raises_error(self) -> None:
        """Test that llm_parallel_max_workers > 32 raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_parallel_max_workers should be <= 32"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=True,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_parallel_max_workers=64,
            )

    def test_llm_parallel_max_workers_too_low_raises_error(self) -> None:
        """Test that llm_parallel_max_workers < 1 raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_parallel_max_workers must be >= 1"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=True,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_parallel_max_workers=0,
            )

    def test_llm_rate_limit_too_low_raises_error(self) -> None:
        """Test that llm_rate_limit < 0.1 raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_rate_limit must be >= 0.1"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=True,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_rate_limit=0.05,
            )

    def test_llm_confidence_threshold_too_low_raises_error(self) -> None:
        """Test that llm_confidence_threshold < 0 raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_confidence_threshold"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=True,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_confidence_threshold=-0.1,
            )

    def test_llm_confidence_threshold_too_high_raises_error(self) -> None:
        """Test that llm_confidence_threshold > 1 raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_confidence_threshold"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=True,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_confidence_threshold=1.2,
            )


class TestRuntimeConfigMergeWithCLI:
    """Test RuntimeConfig.merge_with_cli() for CLI overrides."""

    def test_merge_with_cli_mode_override(self) -> None:
        config = RuntimeConfig.from_defaults()
        merged = config.merge_with_cli(mode=ApplicationMode.DRY_RUN)
        assert merged.mode == ApplicationMode.DRY_RUN
        assert merged.enable_rollback is True  # Unchanged

    def test_merge_with_cli_mode_string_override(self) -> None:
        """Test that mode can be passed as string and is converted."""
        config = RuntimeConfig.from_defaults()
        merged = config.merge_with_cli(mode="dry-run")
        assert merged.mode == ApplicationMode.DRY_RUN

    def test_merge_with_cli_rollback_override(self) -> None:
        config = RuntimeConfig.from_defaults()
        merged = config.merge_with_cli(enable_rollback=False)
        assert merged.enable_rollback is False
        assert merged.mode == ApplicationMode.ALL  # Unchanged

    def test_merge_with_cli_multiple_overrides(self) -> None:
        config = RuntimeConfig.from_defaults()
        merged = config.merge_with_cli(
            mode=ApplicationMode.CONFLICTS_ONLY,
            parallel_processing=True,
            max_workers=16,
            log_level="DEBUG",
        )
        assert merged.mode == ApplicationMode.CONFLICTS_ONLY
        assert merged.parallel_processing is True
        assert merged.max_workers == 16
        assert merged.log_level == "DEBUG"
        # Unchanged
        assert merged.enable_rollback is True
        assert merged.validate_before_apply is True

    def test_merge_with_cli_confidence_threshold_override(self) -> None:
        config = RuntimeConfig.from_defaults()
        merged = config.merge_with_cli(llm_confidence_threshold=0.8)
        assert merged.llm_confidence_threshold == 0.8
        # Original config should remain unchanged
        assert config.llm_confidence_threshold == 0.5

    def test_merge_with_cli_none_values_ignored(self) -> None:
        """Test that None values don't override existing config."""
        config = RuntimeConfig(
            mode=ApplicationMode.CONFLICTS_ONLY,
            enable_rollback=False,
            validate_before_apply=False,
            parallel_processing=True,
            max_workers=8,
            log_level="DEBUG",
            log_file="/tmp/test.log",
        )
        merged = config.merge_with_cli(
            mode=None,
            enable_rollback=None,
            max_workers=None,
        )
        # All values should remain unchanged
        assert merged.mode == ApplicationMode.CONFLICTS_ONLY
        assert merged.enable_rollback is False
        assert merged.max_workers == 8

    def test_merge_with_cli_invalid_mode_string_raises(self) -> None:
        config = RuntimeConfig.from_defaults()
        with pytest.raises(ConfigError, match="Invalid mode"):
            config.merge_with_cli(mode="invalid-mode")

    def test_merge_with_cli_immutability(self) -> None:
        """Test that merge creates new config and doesn't modify original."""
        original = RuntimeConfig.from_defaults()
        merged = original.merge_with_cli(mode=ApplicationMode.DRY_RUN)
        # Original should be unchanged
        assert original.mode == ApplicationMode.ALL
        # Merged should have new value
        assert merged.mode == ApplicationMode.DRY_RUN


class TestRuntimeConfigToDict:
    """Test RuntimeConfig.to_dict() conversion."""

    def test_to_dict_structure(self) -> None:
        config = RuntimeConfig.from_defaults()
        data = config.to_dict()
        assert isinstance(data, dict)
        assert "mode" in data
        assert "enable_rollback" in data
        assert "validate_before_apply" in data
        assert "parallel_processing" in data
        assert "max_workers" in data
        assert "log_level" in data
        assert "log_file" in data
        # LLM fields
        assert "llm_enabled" in data
        assert "llm_provider" in data
        assert "llm_model" in data
        assert "llm_api_key" in data
        assert "llm_fallback_to_regex" in data
        assert "llm_cache_enabled" in data
        assert "llm_max_tokens" in data
        assert "llm_confidence_threshold" in data
        assert "llm_cost_budget" in data

    def test_to_dict_values(self) -> None:
        config = RuntimeConfig(
            mode=ApplicationMode.DRY_RUN,
            enable_rollback=False,
            validate_before_apply=True,
            parallel_processing=True,
            max_workers=8,
            log_level="DEBUG",
            log_file="/tmp/test.log",
            llm_enabled=True,
            llm_provider="anthropic",
            llm_model="claude-3-opus",
            llm_api_key="test-key-12345",
            llm_fallback_to_regex=False,
            llm_cache_enabled=False,
            llm_max_tokens=4000,
            llm_confidence_threshold=0.65,
            llm_cost_budget=50.0,
        )
        data = config.to_dict()
        assert data["mode"] == "dry-run"  # Enum converted to string
        assert data["enable_rollback"] is False
        assert data["validate_before_apply"] is True
        assert data["parallel_processing"] is True
        assert data["max_workers"] == 8
        assert data["log_level"] == "DEBUG"
        assert data["log_file"] == "/tmp/test.log"
        # LLM fields
        assert data["llm_enabled"] is True
        assert data["llm_provider"] == "anthropic"
        assert data["llm_model"] == "claude-3-opus"
        assert data["llm_api_key"] == "test-key-12345"
        assert data["llm_fallback_to_regex"] is False
        assert data["llm_cache_enabled"] is False
        assert data["llm_max_tokens"] == 4000
        assert data["llm_confidence_threshold"] == 0.65
        assert data["llm_cost_budget"] == 50.0

    def test_to_dict_none_log_file(self) -> None:
        config = RuntimeConfig.from_defaults()
        data = config.to_dict()
        assert data["log_file"] is None


class TestRuntimeConfigPrecedence:
    """Test configuration precedence: CLI > env vars > file > defaults."""

    def test_precedence_chain_full(self) -> None:
        """Test full precedence chain: file < env < CLI."""
        # Create config file
        yaml_content = """
mode: all
rollback:
  enabled: true
parallel:
  enabled: false
  max_workers: 4
logging:
  level: INFO
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            try:
                # Load from file
                config = RuntimeConfig.from_file(Path(f.name))
                assert config.mode == ApplicationMode.ALL
                assert config.max_workers == 4
                assert config.log_level == "INFO"

                # Apply CLI overrides
                config = config.merge_with_cli(
                    mode=ApplicationMode.DRY_RUN,
                    max_workers=16,
                )
                assert config.mode == ApplicationMode.DRY_RUN  # CLI wins
                assert config.max_workers == 16  # CLI wins
                assert config.log_level == "INFO"  # File value (no CLI override)
            finally:
                os.unlink(f.name)

    def test_precedence_env_over_defaults(self) -> None:
        """Test env vars override defaults."""
        with patch.dict(os.environ, {"CR_MODE": "dry-run", "CR_MAX_WORKERS": "8"}):
            config = RuntimeConfig.from_env()
            assert config.mode == ApplicationMode.DRY_RUN
            assert config.max_workers == 8


class TestConfigError:
    """Test ConfigError exception."""

    def test_config_error_is_exception(self) -> None:
        assert issubclass(ConfigError, Exception)

    def test_config_error_message(self) -> None:
        error = ConfigError("test message")
        assert str(error) == "test message"


class TestRuntimeConfigLLMFields:
    """Test RuntimeConfig LLM fields (Phase 0)."""

    def test_llm_defaults(self) -> None:
        """Test that LLM fields have safe defaults."""
        config = RuntimeConfig.from_defaults()

        assert config.llm_enabled is False
        assert config.llm_provider == "claude-cli"
        assert config.llm_model == "claude-sonnet-4-5"
        assert config.llm_api_key is None
        assert config.llm_fallback_to_regex is True
        assert config.llm_cache_enabled is True
        assert config.llm_max_tokens == 2000
        assert config.llm_cost_budget is None

    def test_llm_enabled_with_valid_provider(self) -> None:
        """Test RuntimeConfig with LLM enabled."""
        config = RuntimeConfig(
            mode=ApplicationMode.ALL,
            enable_rollback=False,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=4,
            log_level="INFO",
            log_file=None,
            llm_enabled=True,
            llm_provider="claude-cli",
        )

        assert config.llm_enabled is True
        assert config.llm_provider == "claude-cli"

    @pytest.mark.parametrize(
        "provider",
        ["openai", "anthropic", "claude-cli", "codex-cli", "ollama"],
    )
    def test_all_valid_llm_providers(self, provider: str) -> None:
        """Test that all valid LLM providers are accepted without error."""
        # API-based providers require an API key when enabled
        api_key = "test-key" if provider in {"openai", "anthropic"} else None

        config = RuntimeConfig(
            mode=ApplicationMode.ALL,
            enable_rollback=False,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=4,
            log_level="INFO",
            log_file=None,
            llm_enabled=True,
            llm_provider=provider,
            llm_api_key=api_key,
        )

        assert config.llm_enabled is True
        assert config.llm_provider == provider

    def test_invalid_llm_provider_raises_error(self) -> None:
        """Test that invalid LLM provider raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_provider must be one of"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=False,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_provider="invalid-provider",
            )

    def test_negative_llm_max_tokens_raises_error(self) -> None:
        """Test that negative llm_max_tokens raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_max_tokens must be positive"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=False,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_max_tokens=-100,
            )

    def test_zero_llm_max_tokens_raises_error(self) -> None:
        """Test that llm_max_tokens=0 raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_max_tokens must be positive"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=False,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_max_tokens=0,
            )

    def test_negative_llm_cost_budget_raises_error(self) -> None:
        """Test that negative llm_cost_budget raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_cost_budget must be positive"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=False,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_cost_budget=-50.0,
            )

    def test_zero_llm_cost_budget_raises_error(self) -> None:
        """Test that llm_cost_budget=0 raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_cost_budget must be positive"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=False,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_cost_budget=0.0,
            )

    def test_from_env_with_llm_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with LLM environment variables."""
        monkeypatch.setenv("CR_LLM_ENABLED", "true")
        monkeypatch.setenv("CR_LLM_PROVIDER", "openai")
        monkeypatch.setenv("CR_LLM_MODEL", "gpt-4")
        monkeypatch.setenv("CR_LLM_API_KEY", "sk-test-key")  # Required for openai
        monkeypatch.setenv("CR_LLM_MAX_TOKENS", "4000")
        monkeypatch.setenv("CR_LLM_COST_BUDGET", "25.50")

        config = RuntimeConfig.from_env()

        assert config.llm_enabled is True
        assert config.llm_provider == "openai"
        assert config.llm_model == "gpt-4"
        assert config.llm_api_key == "sk-test-key"
        assert config.llm_max_tokens == 4000
        assert config.llm_cost_budget == 25.50

    def test_from_env_invalid_llm_max_tokens_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid CR_LLM_MAX_TOKENS raises ConfigError."""
        monkeypatch.setenv("CR_LLM_MAX_TOKENS", "invalid")
        with pytest.raises(ConfigError, match="Invalid CR_LLM_MAX_TOKENS"):
            RuntimeConfig.from_env()

    def test_from_env_invalid_llm_cost_budget_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid CR_LLM_COST_BUDGET raises ConfigError."""
        monkeypatch.setenv("CR_LLM_COST_BUDGET", "not-a-number")
        with pytest.raises(ConfigError, match="Invalid CR_LLM_COST_BUDGET"):
            RuntimeConfig.from_env()

    def test_from_env_llm_parallel_parsing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with LLM parallel parsing environment variables."""
        monkeypatch.setenv("CR_LLM_PARALLEL_PARSING", "true")
        monkeypatch.setenv("CR_LLM_PARALLEL_WORKERS", "8")
        monkeypatch.setenv("CR_LLM_RATE_LIMIT", "20.0")

        config = RuntimeConfig.from_env()

        assert config.llm_parallel_parsing is True
        assert config.llm_parallel_max_workers == 8
        assert config.llm_rate_limit == 20.0

    def test_from_env_invalid_llm_parallel_workers_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that invalid CR_LLM_PARALLEL_WORKERS raises ConfigError."""
        monkeypatch.setenv("CR_LLM_PARALLEL_WORKERS", "invalid")
        with pytest.raises(ConfigError, match="Invalid CR_LLM_PARALLEL_WORKERS"):
            RuntimeConfig.from_env()

    def test_from_env_llm_parallel_workers_zero_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that CR_LLM_PARALLEL_WORKERS=0 raises ConfigError."""
        monkeypatch.setenv("CR_LLM_PARALLEL_WORKERS", "0")
        with pytest.raises(ConfigError, match="must be >= 1"):
            RuntimeConfig.from_env()

    def test_from_env_llm_parallel_workers_too_high_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that CR_LLM_PARALLEL_WORKERS > 32 raises ConfigError."""
        monkeypatch.setenv("CR_LLM_PARALLEL_WORKERS", "64")
        with pytest.raises(ConfigError, match="llm_parallel_max_workers should be <= 32"):
            RuntimeConfig.from_env()

    def test_from_env_invalid_llm_rate_limit_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid CR_LLM_RATE_LIMIT raises ConfigError."""
        monkeypatch.setenv("CR_LLM_RATE_LIMIT", "not-a-number")
        with pytest.raises(ConfigError, match="Invalid CR_LLM_RATE_LIMIT"):
            RuntimeConfig.from_env()

    def test_from_env_llm_rate_limit_too_low_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that CR_LLM_RATE_LIMIT < 0.1 raises ConfigError."""
        monkeypatch.setenv("CR_LLM_RATE_LIMIT", "0.05")
        with pytest.raises(ConfigError, match="CR_LLM_RATE_LIMIT=0.05 must be >= 0.1"):
            RuntimeConfig.from_env()


class TestRuntimeConfigFromFileErrorHandling:
    """Test error handling in RuntimeConfig.from_file for LLM parallel config."""

    def test_from_file_invalid_llm_parallel_workers_type(self, tmp_path: Path) -> None:
        """Test that invalid type for llm.parallel_max_workers raises ConfigError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
llm:
  enabled: true
  provider: claude-cli
  parallel_parsing: true
  parallel_max_workers: "not-a-number"
  rate_limit: 10.0
"""
        )

        with pytest.raises(ConfigError, match="Invalid LLM parallel config"):
            RuntimeConfig.from_file(config_file)

    def test_from_file_invalid_llm_rate_limit_type(self, tmp_path: Path) -> None:
        """Test that invalid type for llm.rate_limit raises ConfigError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
llm:
  enabled: true
  provider: claude-cli
  parallel_parsing: true
  parallel_max_workers: 4
  rate_limit: "invalid"
"""
        )

        with pytest.raises(ConfigError, match="Invalid LLM parallel config"):
            RuntimeConfig.from_file(config_file)

    def test_from_file_llm_parallel_workers_list_type(self, tmp_path: Path) -> None:
        """Test that list type for llm.parallel_max_workers raises ConfigError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
llm:
  enabled: true
  provider: claude-cli
  parallel_parsing: true
  parallel_max_workers: [4, 8]
  rate_limit: 10.0
"""
        )

        with pytest.raises(ConfigError, match="Invalid LLM parallel config"):
            RuntimeConfig.from_file(config_file)

    def test_from_file_llm_rate_limit_dict_type(self, tmp_path: Path) -> None:
        """Test that dict type for llm.rate_limit raises ConfigError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
llm:
  enabled: true
  provider: claude-cli
  parallel_parsing: true
  parallel_max_workers: 4
  rate_limit: {value: 10.0}
"""
        )

        with pytest.raises(ConfigError, match="Invalid LLM parallel config"):
            RuntimeConfig.from_file(config_file)

    def test_from_file_invalid_llm_confidence_threshold(self, tmp_path: Path) -> None:
        """Test that invalid confidence_threshold value raises ConfigError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
llm:
  enabled: true
  provider: claude-cli
  parallel_parsing: true
  parallel_max_workers: 4
  rate_limit: 10.0
  confidence_threshold: "high"
"""
        )

        with pytest.raises(ConfigError, match="Invalid LLM parallel config"):
            RuntimeConfig.from_file(config_file)

    def test_from_file_valid_llm_parallel_config(self, tmp_path: Path) -> None:
        """Test that valid LLM parallel config values are accepted."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
llm:
  enabled: true
  provider: claude-cli
  parallel_parsing: true
  parallel_max_workers: 8
  rate_limit: 20.5
"""
        )

        config = RuntimeConfig.from_file(config_file)

        assert config.llm_parallel_parsing is True
        assert config.llm_parallel_max_workers == 8
        assert config.llm_rate_limit == 20.5

    def test_merge_with_cli_llm_overrides(self) -> None:
        """Test merge_with_cli() with LLM overrides."""
        config = RuntimeConfig.from_defaults()
        merged = config.merge_with_cli(
            llm_enabled=True,
            llm_provider="anthropic",
            llm_model="claude-3-opus",
            llm_api_key="sk-ant-test",  # Required for anthropic
        )

        assert merged.llm_enabled is True
        assert merged.llm_provider == "anthropic"
        assert merged.llm_model == "claude-3-opus"

    def test_llm_enabled_without_api_key_raises_error(self) -> None:
        """Test that enabling LLM with API provider without key raises ConfigError."""
        with pytest.raises(ConfigError, match="no API key provided"):
            RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=False,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_enabled=True,
                llm_provider="openai",
                llm_api_key=None,
            )

    def test_llm_enabled_with_claude_cli_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that enabling LLM with claude-cli without key does not warn."""
        with caplog.at_level(logging.WARNING):
            config = RuntimeConfig(
                mode=ApplicationMode.ALL,
                enable_rollback=False,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
                llm_enabled=True,
                llm_provider="claude-cli",
                llm_api_key=None,
            )

        assert config.llm_enabled is True
        assert "no API key provided" not in caplog.text

    def test_llm_enabled_from_env_without_api_key_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that from_env() with LLM enabled and API provider without key raises ConfigError."""
        # Clear any existing API key env vars
        monkeypatch.delenv("CR_LLM_API_KEY", raising=False)

        # Set up environment for LLM with anthropic provider
        monkeypatch.setenv("CR_LLM_ENABLED", "true")
        monkeypatch.setenv("CR_LLM_PROVIDER", "anthropic")

        with pytest.raises(ConfigError, match="anthropic.*no API key provided"):
            RuntimeConfig.from_env()

    def test_from_llm_enabled_preset(self) -> None:
        """Test from_llm_enabled() returns LLM-enabled configuration."""
        config = RuntimeConfig.from_llm_enabled()

        # LLM fields
        assert config.llm_enabled is True
        assert config.llm_provider == "claude-cli"
        assert config.llm_model == "claude-sonnet-4-5"
        assert config.llm_api_key is None
        assert config.llm_fallback_to_regex is True
        assert config.llm_cache_enabled is True
        assert config.llm_max_tokens == 2000
        assert config.llm_cost_budget is None

        # Other fields should match balanced preset
        assert config.mode == ApplicationMode.ALL
        assert config.enable_rollback is True
        assert config.validate_before_apply is True
        assert config.parallel_processing is False
        assert config.max_workers == 4
        assert config.log_level == "INFO"
