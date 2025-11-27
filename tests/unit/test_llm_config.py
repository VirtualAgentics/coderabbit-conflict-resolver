"""Unit tests for LLM configuration.

Tests the LLMConfig dataclass for Phase 0 (Foundation).
"""

import os

import pytest

from review_bot_automator.llm.config import LLMConfig


class TestLLMConfigDefaults:
    """Test LLMConfig default values."""

    def test_from_defaults(self) -> None:
        """Test LLMConfig.from_defaults() creates config with safe defaults."""
        config = LLMConfig.from_defaults()

        assert config.enabled is False
        assert config.provider == "claude-cli"
        assert config.model == "claude-sonnet-4-5"
        assert config.api_key is None
        assert config.fallback_to_regex is True
        assert config.cache_enabled is True
        assert config.max_tokens == 2000
        assert config.cost_budget is None

    def test_direct_instantiation_defaults(self) -> None:
        """Test LLMConfig() with no arguments uses defaults."""
        config = LLMConfig()

        assert config.enabled is False
        assert config.provider == "claude-cli"
        assert config.model == "claude-sonnet-4-5"


class TestLLMConfigValidation:
    """Test LLMConfig validation in __post_init__."""

    def test_invalid_provider_raises_error(self) -> None:
        """Test that invalid provider raises ValueError."""
        with pytest.raises(ValueError, match="provider must be one of"):
            LLMConfig(provider="invalid-provider")

    def test_negative_max_tokens_raises_error(self) -> None:
        """Test that negative max_tokens raises ValueError."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            LLMConfig(max_tokens=-100)

    def test_zero_max_tokens_raises_error(self) -> None:
        """Test that zero max_tokens raises ValueError."""
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            LLMConfig(max_tokens=0)

    def test_negative_cost_budget_raises_error(self) -> None:
        """Test that negative cost_budget raises ValueError."""
        with pytest.raises(ValueError, match="cost_budget must be positive"):
            LLMConfig(cost_budget=-10.0)

    def test_enabled_openai_without_api_key_raises_error(self) -> None:
        """Test that enabling OpenAI without API key raises ValueError."""
        with pytest.raises(ValueError, match="api_key is required"):
            LLMConfig(enabled=True, provider="openai", api_key=None)

    def test_enabled_anthropic_without_api_key_raises_error(self) -> None:
        """Test that enabling Anthropic without API key raises ValueError."""
        with pytest.raises(ValueError, match="api_key is required"):
            LLMConfig(enabled=True, provider="anthropic", api_key=None)

    def test_enabled_claude_cli_without_api_key_is_valid(self) -> None:
        """Test that enabling claude-cli without API key is valid (uses CLI auth)."""
        config = LLMConfig(enabled=True, provider="claude-cli", api_key=None)
        assert config.enabled is True
        assert config.api_key is None

    def test_enabled_ollama_without_api_key_is_valid(self) -> None:
        """Test that enabling ollama without API key is valid (local model)."""
        config = LLMConfig(enabled=True, provider="ollama", api_key=None)
        assert config.enabled is True
        assert config.api_key is None

    def test_retry_max_attempts_zero_raises_error(self) -> None:
        """Test that zero retry_max_attempts raises ValueError."""
        with pytest.raises(ValueError, match="retry_max_attempts must be >= 1"):
            LLMConfig(retry_max_attempts=0)

    def test_retry_max_attempts_negative_raises_error(self) -> None:
        """Test that negative retry_max_attempts raises ValueError."""
        with pytest.raises(ValueError, match="retry_max_attempts must be >= 1"):
            LLMConfig(retry_max_attempts=-1)

    def test_retry_base_delay_zero_raises_error(self) -> None:
        """Test that zero retry_base_delay raises ValueError."""
        with pytest.raises(ValueError, match="retry_base_delay must be > 0"):
            LLMConfig(retry_base_delay=0.0)

    def test_retry_base_delay_negative_raises_error(self) -> None:
        """Test that negative retry_base_delay raises ValueError."""
        with pytest.raises(ValueError, match="retry_base_delay must be > 0"):
            LLMConfig(retry_base_delay=-1.0)

    def test_valid_retry_config(self) -> None:
        """Test that valid retry configuration is accepted."""
        config = LLMConfig(
            retry_on_rate_limit=True,
            retry_max_attempts=5,
            retry_base_delay=3.0,
        )
        assert config.retry_on_rate_limit is True
        assert config.retry_max_attempts == 5
        assert config.retry_base_delay == 3.0


class TestLLMConfigFromEnv:
    """Test LLMConfig.from_env() environment variable loading."""

    def test_from_env_with_no_env_vars_uses_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() uses defaults when no env vars are set."""
        # Clear all CR_LLM_* env vars
        for key in list(os.environ.keys()):
            if key.startswith("CR_LLM_"):
                monkeypatch.delenv(key, raising=False)

        config = LLMConfig.from_env()

        assert config.enabled is False
        assert config.provider == "claude-cli"
        assert config.model == "claude-sonnet-4-5"

    def test_from_env_with_enabled_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_ENABLED=true."""
        monkeypatch.setenv("CR_LLM_ENABLED", "true")

        config = LLMConfig.from_env()

        assert config.enabled is True

    def test_from_env_with_enabled_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_ENABLED=false."""
        monkeypatch.setenv("CR_LLM_ENABLED", "false")

        config = LLMConfig.from_env()

        assert config.enabled is False

    def test_from_env_with_custom_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_PROVIDER=openai."""
        monkeypatch.setenv("CR_LLM_PROVIDER", "openai")

        config = LLMConfig.from_env()

        assert config.provider == "openai"

    def test_from_env_with_custom_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_MODEL=gpt-4."""
        monkeypatch.setenv("CR_LLM_MODEL", "gpt-4")

        config = LLMConfig.from_env()

        assert config.model == "gpt-4"

    def test_from_env_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_API_KEY."""
        monkeypatch.setenv("CR_LLM_API_KEY", "sk-test-key-12345")

        config = LLMConfig.from_env()

        assert config.api_key == "sk-test-key-12345"

    def test_from_env_with_fallback_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_FALLBACK_TO_REGEX=false."""
        monkeypatch.setenv("CR_LLM_FALLBACK_TO_REGEX", "false")

        config = LLMConfig.from_env()

        assert config.fallback_to_regex is False

    def test_from_env_with_cache_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_CACHE_ENABLED=false."""
        monkeypatch.setenv("CR_LLM_CACHE_ENABLED", "false")

        config = LLMConfig.from_env()

        assert config.cache_enabled is False

    def test_from_env_with_max_tokens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_MAX_TOKENS=4000."""
        monkeypatch.setenv("CR_LLM_MAX_TOKENS", "4000")

        config = LLMConfig.from_env()

        assert config.max_tokens == 4000

    def test_from_env_with_invalid_max_tokens_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env() with invalid CR_LLM_MAX_TOKENS raises ConfigError."""
        from review_bot_automator.config.exceptions import ConfigError

        monkeypatch.setenv("CR_LLM_MAX_TOKENS", "invalid")

        with pytest.raises(ConfigError, match="CR_LLM_MAX_TOKENS must be a valid integer"):
            LLMConfig.from_env()

    def test_from_env_with_cost_budget(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_COST_BUDGET=50.0."""
        monkeypatch.setenv("CR_LLM_COST_BUDGET", "50.0")

        config = LLMConfig.from_env()

        assert config.cost_budget == 50.0

    def test_from_env_with_invalid_cost_budget_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env() with invalid CR_LLM_COST_BUDGET raises ConfigError."""
        from review_bot_automator.config.exceptions import ConfigError

        monkeypatch.setenv("CR_LLM_COST_BUDGET", "invalid")

        with pytest.raises(ConfigError, match="CR_LLM_COST_BUDGET must be a valid float"):
            LLMConfig.from_env()

    def test_from_env_with_all_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with all environment variables set."""
        monkeypatch.setenv("CR_LLM_ENABLED", "true")
        monkeypatch.setenv("CR_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("CR_LLM_MODEL", "claude-3-opus")
        monkeypatch.setenv("CR_LLM_API_KEY", "sk-ant-test")
        monkeypatch.setenv("CR_LLM_FALLBACK_TO_REGEX", "false")
        monkeypatch.setenv("CR_LLM_CACHE_ENABLED", "false")
        monkeypatch.setenv("CR_LLM_MAX_TOKENS", "8000")
        monkeypatch.setenv("CR_LLM_COST_BUDGET", "100.0")

        config = LLMConfig.from_env()

        assert config.enabled is True
        assert config.provider == "anthropic"
        assert config.model == "claude-3-opus"
        assert config.api_key == "sk-ant-test"
        assert config.fallback_to_regex is False
        assert config.cache_enabled is False
        assert config.max_tokens == 8000
        assert config.cost_budget == 100.0

    def test_from_env_retry_on_rate_limit_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_RETRY_ON_RATE_LIMIT=true."""
        monkeypatch.setenv("CR_LLM_RETRY_ON_RATE_LIMIT", "true")
        config = LLMConfig.from_env()
        assert config.retry_on_rate_limit is True

    def test_from_env_retry_on_rate_limit_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_RETRY_ON_RATE_LIMIT=false."""
        monkeypatch.setenv("CR_LLM_RETRY_ON_RATE_LIMIT", "false")
        config = LLMConfig.from_env()
        assert config.retry_on_rate_limit is False

    def test_from_env_retry_max_attempts_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_RETRY_MAX_ATTEMPTS=5."""
        monkeypatch.setenv("CR_LLM_RETRY_MAX_ATTEMPTS", "5")
        config = LLMConfig.from_env()
        assert config.retry_max_attempts == 5

    def test_from_env_retry_max_attempts_invalid_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env() with invalid CR_LLM_RETRY_MAX_ATTEMPTS raises ConfigError."""
        from review_bot_automator.config.exceptions import ConfigError

        monkeypatch.setenv("CR_LLM_RETRY_MAX_ATTEMPTS", "invalid")
        with pytest.raises(ConfigError, match="CR_LLM_RETRY_MAX_ATTEMPTS must be a valid integer"):
            LLMConfig.from_env()

    def test_from_env_retry_base_delay_custom(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_RETRY_BASE_DELAY=5.0."""
        monkeypatch.setenv("CR_LLM_RETRY_BASE_DELAY", "5.0")
        config = LLMConfig.from_env()
        assert config.retry_base_delay == 5.0

    def test_from_env_retry_base_delay_invalid_raises_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env() with invalid CR_LLM_RETRY_BASE_DELAY raises ConfigError."""
        from review_bot_automator.config.exceptions import ConfigError

        monkeypatch.setenv("CR_LLM_RETRY_BASE_DELAY", "invalid")
        with pytest.raises(ConfigError, match="CR_LLM_RETRY_BASE_DELAY must be a valid float"):
            LLMConfig.from_env()


class TestLLMConfigEffort:
    """Test LLMConfig effort parameter validation and loading."""

    def test_effort_default_none(self) -> None:
        """Test that effort defaults to None."""
        config = LLMConfig()
        assert config.effort is None

    def test_effort_valid_values(self) -> None:
        """Test that all valid effort values are accepted."""
        for effort in ["none", "low", "medium", "high"]:
            config = LLMConfig(effort=effort)
            assert config.effort == effort

    def test_effort_case_insensitive_validation(self) -> None:
        """Test that effort validation is case insensitive and normalizes to lowercase."""
        for effort in ["LOW", "Medium", "HIGH", "None"]:
            # Should not raise and should normalize to lowercase
            config = LLMConfig(effort=effort)
            assert config.effort == effort.lower()

    def test_effort_invalid_value_raises_error(self) -> None:
        """Test that invalid effort values raise ValueError."""
        with pytest.raises(ValueError, match="effort must be one of"):
            LLMConfig(effort="invalid")

    def test_effort_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_EFFORT."""
        monkeypatch.setenv("CR_LLM_EFFORT", "high")
        config = LLMConfig.from_env()
        assert config.effort == "high"

    def test_effort_from_env_normalizes_to_lowercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() normalizes effort to lowercase."""
        monkeypatch.setenv("CR_LLM_EFFORT", "HIGH")
        config = LLMConfig.from_env()
        assert config.effort == "high"  # Should be normalized to lowercase

    def test_effort_from_env_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() with CR_LLM_EFFORT=none."""
        monkeypatch.setenv("CR_LLM_EFFORT", "none")
        config = LLMConfig.from_env()
        assert config.effort == "none"

    def test_effort_from_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() without CR_LLM_EFFORT returns None."""
        monkeypatch.delenv("CR_LLM_EFFORT", raising=False)
        config = LLMConfig.from_env()
        assert config.effort is None

    def test_effort_from_env_strips_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test from_env() strips whitespace from effort value."""
        monkeypatch.setenv("CR_LLM_EFFORT", "  HIGH  ")
        config = LLMConfig.from_env()
        assert config.effort == "high"

    def test_effort_from_env_whitespace_only_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test from_env() treats whitespace-only effort as None."""
        monkeypatch.setenv("CR_LLM_EFFORT", "   ")
        config = LLMConfig.from_env()
        assert config.effort is None


class TestLLMConfigImmutability:
    """Test that LLMConfig is immutable (frozen=True)."""

    def test_cannot_modify_enabled(self) -> None:
        """Test that enabled field cannot be modified."""
        config = LLMConfig()

        with pytest.raises((AttributeError, TypeError)):
            config.enabled = True  # type: ignore[misc]

    def test_cannot_modify_provider(self) -> None:
        """Test that provider field cannot be modified."""
        config = LLMConfig()

        with pytest.raises((AttributeError, TypeError)):
            config.provider = "openai"  # type: ignore[misc]


class TestLLMConfigAllProviders:
    """Test that all valid providers are accepted."""

    def test_claude_cli_provider(self) -> None:
        """Test claude-cli provider is valid."""
        config = LLMConfig(provider="claude-cli")
        assert config.provider == "claude-cli"

    def test_openai_provider(self) -> None:
        """Test openai provider is valid."""
        config = LLMConfig(provider="openai", api_key="sk-test")
        assert config.provider == "openai"

    def test_anthropic_provider(self) -> None:
        """Test anthropic provider is valid."""
        config = LLMConfig(provider="anthropic", api_key="sk-ant-test")
        assert config.provider == "anthropic"

    def test_codex_cli_provider(self) -> None:
        """Test codex-cli provider is valid."""
        config = LLMConfig(provider="codex-cli")
        assert config.provider == "codex-cli"

    def test_ollama_provider(self) -> None:
        """Test ollama provider is valid."""
        config = LLMConfig(provider="ollama")
        assert config.provider == "ollama"
