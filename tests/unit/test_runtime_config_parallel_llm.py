"""Tests for parallel LLM parsing configuration in RuntimeConfig.

This module tests the parallel LLM parsing configuration fields including:
- New fields: parallel_llm_parsing and llm_max_workers
- Initialization with defaults and custom values
- Validation of llm_max_workers
- Environment variable loading
- Config file loading (YAML/TOML)
- CLI override merging
- Serialization with to_dict()
"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from pr_conflict_resolver.config.exceptions import ConfigError
from pr_conflict_resolver.config.runtime_config import RuntimeConfig


class TestRuntimeConfigParallelLLMFields:
    """Test new parallel LLM parsing fields in RuntimeConfig."""

    def test_defaults_have_parallel_fields(self) -> None:
        """Test that default config includes parallel LLM fields."""
        config = RuntimeConfig.from_defaults()
        assert hasattr(config, "parallel_llm_parsing")
        assert hasattr(config, "llm_max_workers")

    def test_default_values(self) -> None:
        """Test default values for parallel LLM fields."""
        config = RuntimeConfig.from_defaults()
        assert config.parallel_llm_parsing is False
        assert config.llm_max_workers == 4

    def test_custom_parallel_llm_parsing(self) -> None:
        """Test setting parallel_llm_parsing to True."""
        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(parallel_llm_parsing=True)
        assert config.parallel_llm_parsing is True

    def test_custom_llm_max_workers(self) -> None:
        """Test setting custom llm_max_workers."""
        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(llm_max_workers=8)
        assert config.llm_max_workers == 8


class TestRuntimeConfigLLMMaxWorkersValidation:
    """Test validation of llm_max_workers field."""

    def test_llm_max_workers_minimum_one(self) -> None:
        """Test that llm_max_workers >= 1."""
        with pytest.raises(ConfigError, match="llm_max_workers must be >= 1"):
            RuntimeConfig.from_defaults().merge_with_cli(llm_max_workers=0)

    def test_llm_max_workers_negative_raises(self) -> None:
        """Test that negative llm_max_workers raises ConfigError."""
        with pytest.raises(ConfigError, match="llm_max_workers must be >= 1"):
            RuntimeConfig.from_defaults().merge_with_cli(llm_max_workers=-1)

    def test_llm_max_workers_one_valid(self) -> None:
        """Test that llm_max_workers=1 is valid."""
        config = RuntimeConfig.from_defaults().merge_with_cli(llm_max_workers=1)
        assert config.llm_max_workers == 1

    def test_llm_max_workers_large_value_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that llm_max_workers > 32 logs warning."""
        import logging

        caplog.set_level(logging.WARNING)
        config = RuntimeConfig.from_defaults().merge_with_cli(llm_max_workers=64)
        assert config.llm_max_workers == 64
        # Check for warning in logs with specific content
        assert any(
            rec.levelname == "WARNING"
            and "llm_max_workers" in rec.getMessage()
            and "64" in rec.getMessage()
            for rec in caplog.records
        )


class TestRuntimeConfigParallelLLMEnvironmentVariables:
    """Test loading parallel LLM config from environment variables."""

    def test_env_parallel_llm_parsing_true(self) -> None:
        """Test CR_PARALLEL_LLM_PARSING=true."""
        with patch.dict(os.environ, {"CR_PARALLEL_LLM_PARSING": "true"}):
            config = RuntimeConfig.from_env()
            assert config.parallel_llm_parsing is True

    def test_env_parallel_llm_parsing_false(self) -> None:
        """Test CR_PARALLEL_LLM_PARSING=false."""
        with patch.dict(os.environ, {"CR_PARALLEL_LLM_PARSING": "false"}):
            config = RuntimeConfig.from_env()
            assert config.parallel_llm_parsing is False

    def test_env_parallel_llm_parsing_1(self) -> None:
        """Test CR_PARALLEL_LLM_PARSING=1 (truthy)."""
        with patch.dict(os.environ, {"CR_PARALLEL_LLM_PARSING": "1"}):
            config = RuntimeConfig.from_env()
            assert config.parallel_llm_parsing is True

    def test_env_parallel_llm_parsing_0(self) -> None:
        """Test CR_PARALLEL_LLM_PARSING=0 (falsy)."""
        with patch.dict(os.environ, {"CR_PARALLEL_LLM_PARSING": "0"}):
            config = RuntimeConfig.from_env()
            assert config.parallel_llm_parsing is False

    def test_env_llm_max_workers(self) -> None:
        """Test CR_LLM_MAX_WORKERS environment variable."""
        with patch.dict(os.environ, {"CR_LLM_MAX_WORKERS": "8"}):
            config = RuntimeConfig.from_env()
            assert config.llm_max_workers == 8

    def test_env_llm_max_workers_invalid_raises(self) -> None:
        """Test that invalid CR_LLM_MAX_WORKERS raises ConfigError."""
        with (
            patch.dict(os.environ, {"CR_LLM_MAX_WORKERS": "not-a-number"}),
            pytest.raises(ConfigError, match="Must be an integer"),
        ):
            RuntimeConfig.from_env()

    def test_env_llm_max_workers_zero_raises(self) -> None:
        """Test that CR_LLM_MAX_WORKERS=0 raises ConfigError."""
        with (
            patch.dict(os.environ, {"CR_LLM_MAX_WORKERS": "0"}),
            pytest.raises(ConfigError, match="must be >= 1"),
        ):
            RuntimeConfig.from_env()

    def test_env_both_parallel_fields(self) -> None:
        """Test setting both parallel fields via environment."""
        with patch.dict(
            os.environ,
            {
                "CR_PARALLEL_LLM_PARSING": "true",
                "CR_LLM_MAX_WORKERS": "16",
            },
        ):
            config = RuntimeConfig.from_env()
            assert config.parallel_llm_parsing is True
            assert config.llm_max_workers == 16


class TestRuntimeConfigParallelLLMFileLoading:
    """Test loading parallel LLM config from YAML/TOML files."""

    def test_yaml_parallel_llm_parsing(self) -> None:
        """Test loading parallel_llm_parsing from YAML."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
llm:
  enabled: true
  parallel_parsing: true
  max_workers: 8
"""
            )
            config = RuntimeConfig.from_file(config_file)
            assert config.parallel_llm_parsing is True
            assert config.llm_max_workers == 8

    def test_yaml_parallel_llm_parsing_false(self) -> None:
        """Test loading parallel_llm_parsing=false from YAML."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
llm:
  enabled: true
  parallel_parsing: false
  max_workers: 2
"""
            )
            config = RuntimeConfig.from_file(config_file)
            assert config.parallel_llm_parsing is False
            assert config.llm_max_workers == 2

    def test_yaml_defaults_when_not_specified(self) -> None:
        """Test that defaults are used when fields not in YAML."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
llm:
  enabled: true
  provider: claude-cli
"""
            )
            config = RuntimeConfig.from_file(config_file)
            # Should use defaults
            assert config.parallel_llm_parsing is False
            assert config.llm_max_workers == 4

    def test_toml_parallel_llm_parsing(self) -> None:
        """Test loading parallel_llm_parsing from TOML."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            config_file.write_text(
                """
[llm]
enabled = true
parallel_parsing = true
max_workers = 12
"""
            )
            config = RuntimeConfig.from_file(config_file)
            assert config.parallel_llm_parsing is True
            assert config.llm_max_workers == 12

    def test_toml_defaults_when_not_specified(self) -> None:
        """Test that defaults are used when fields not in TOML."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.toml"
            config_file.write_text(
                """
[llm]
enabled = true
provider = "claude-cli"
"""
            )
            config = RuntimeConfig.from_file(config_file)
            # Should use defaults
            assert config.parallel_llm_parsing is False
            assert config.llm_max_workers == 4


class TestRuntimeConfigParallelLLMCLIOverrides:
    """Test CLI overrides for parallel LLM config."""

    def test_cli_override_parallel_llm_parsing(self) -> None:
        """Test CLI override of parallel_llm_parsing."""
        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(parallel_llm_parsing=True)
        assert config.parallel_llm_parsing is True

    def test_cli_override_llm_max_workers(self) -> None:
        """Test CLI override of llm_max_workers."""
        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(llm_max_workers=16)
        assert config.llm_max_workers == 16

    def test_cli_override_both_parallel_fields(self) -> None:
        """Test CLI override of both parallel fields."""
        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(
            parallel_llm_parsing=True,
            llm_max_workers=8,
        )
        assert config.parallel_llm_parsing is True
        assert config.llm_max_workers == 8

    def test_cli_none_values_ignored(self) -> None:
        """Test that None values in CLI overrides are ignored."""
        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(
            parallel_llm_parsing=None,
            llm_max_workers=None,
        )
        # Should retain defaults
        assert config.parallel_llm_parsing is False
        assert config.llm_max_workers == 4


class TestRuntimeConfigParallelLLMPrecedence:
    """Test configuration precedence: CLI > env > file > defaults."""

    def test_cli_overrides_env(self) -> None:
        """Test that CLI overrides environment variables."""
        with patch.dict(os.environ, {"CR_PARALLEL_LLM_PARSING": "false"}):
            config = RuntimeConfig.from_env()
            config = config.merge_with_cli(parallel_llm_parsing=True)
            assert config.parallel_llm_parsing is True

    def test_cli_overrides_file(self) -> None:
        """Test that CLI overrides config file."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
llm:
  parallel_parsing: false
  max_workers: 2
"""
            )
            config = RuntimeConfig.from_file(config_file)
            config = config.merge_with_cli(
                parallel_llm_parsing=True,
                llm_max_workers=16,
            )
            assert config.parallel_llm_parsing is True
            assert config.llm_max_workers == 16

    def test_env_overrides_defaults(self) -> None:
        """Test that environment overrides defaults."""
        with patch.dict(
            os.environ,
            {
                "CR_PARALLEL_LLM_PARSING": "true",
                "CR_LLM_MAX_WORKERS": "8",
            },
        ):
            config = RuntimeConfig.from_env()
            assert config.parallel_llm_parsing is True
            assert config.llm_max_workers == 8


class TestRuntimeConfigParallelLLMSerialization:
    """Test serialization of parallel LLM config."""

    def test_to_dict_includes_parallel_fields(self) -> None:
        """Test that to_dict() includes parallel LLM fields."""
        config = RuntimeConfig.from_defaults()
        config_dict = config.to_dict()
        assert "parallel_llm_parsing" in config_dict
        assert "llm_max_workers" in config_dict

    def test_to_dict_values_correct(self) -> None:
        """Test that to_dict() returns correct values."""
        config = RuntimeConfig.from_defaults().merge_with_cli(
            parallel_llm_parsing=True,
            llm_max_workers=8,
        )
        config_dict = config.to_dict()
        assert config_dict["parallel_llm_parsing"] is True
        assert config_dict["llm_max_workers"] == 8


class TestRuntimeConfigParallelLLMIntegration:
    """Integration tests for parallel LLM configuration."""

    def test_full_config_with_parallel_enabled(self) -> None:
        """Test complete config with parallel LLM enabled."""
        config = RuntimeConfig.from_defaults()
        config = config.merge_with_cli(
            llm_enabled=True,
            llm_provider="claude-cli",  # Use CLI provider (doesn't need API key)
            llm_model="claude-sonnet-4-5",
            parallel_llm_parsing=True,
            llm_max_workers=8,
        )

        assert config.llm_enabled is True
        assert config.llm_provider == "claude-cli"
        assert config.llm_model == "claude-sonnet-4-5"
        assert config.parallel_llm_parsing is True
        assert config.llm_max_workers == 8

    def test_config_file_with_all_llm_settings(self) -> None:
        """Test config file with all LLM settings including parallel."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
llm:
  enabled: true
  provider: claude-cli
  model: claude-sonnet-4-5
  fallback_to_regex: true
  cache_enabled: true
  max_tokens: 3000
  parallel_parsing: true
  max_workers: 6
"""
            )
            config = RuntimeConfig.from_file(config_file)

            assert config.llm_enabled is True
            assert config.llm_provider == "claude-cli"
            assert config.llm_model == "claude-sonnet-4-5"
            assert config.llm_fallback_to_regex is True
            assert config.llm_cache_enabled is True
            assert config.llm_max_tokens == 3000
            assert config.parallel_llm_parsing is True
            assert config.llm_max_workers == 6

    def test_env_file_cli_precedence_chain(self) -> None:
        """Test precedence chain: defaults < env < CLI."""
        # Use non-default value (8) to prove env overrides default (4)
        with patch.dict(os.environ, {"CR_LLM_MAX_WORKERS": "8"}):
            config = RuntimeConfig.from_env()
            assert config.llm_max_workers == 8

        # Test CLI overrides env
        with patch.dict(
            os.environ, {"CR_LLM_MAX_WORKERS": "4", "CR_PARALLEL_LLM_PARSING": "false"}
        ):
            config = RuntimeConfig.from_env()
            config = config.merge_with_cli(
                parallel_llm_parsing=True,
                llm_max_workers=16,
            )
            assert config.parallel_llm_parsing is True
            assert config.llm_max_workers == 16

        # Test file values, then CLI override
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
llm:
  parallel_parsing: false
  max_workers: 2
"""
            )
            config = RuntimeConfig.from_file(config_file)
            assert config.parallel_llm_parsing is False
            assert config.llm_max_workers == 2

            # CLI overrides file
            config = config.merge_with_cli(
                parallel_llm_parsing=True,
                llm_max_workers=16,
            )
            assert config.parallel_llm_parsing is True
            assert config.llm_max_workers == 16
