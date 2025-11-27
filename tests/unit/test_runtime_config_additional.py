"""Additional tests for RuntimeConfig to achieve 80%+ coverage."""

import builtins
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from review_bot_automator.config.exceptions import ConfigError
from review_bot_automator.config.runtime_config import ApplicationMode, RuntimeConfig


class TestPresetFactoryMethods:
    """Test all preset factory methods are called and return correct configs."""

    def test_from_conservative(self) -> None:
        """Test from_conservative preset factory method."""
        config = RuntimeConfig.from_conservative()

        assert config.mode == ApplicationMode.ALL
        assert config.enable_rollback is True
        assert config.validate_before_apply is True
        assert config.parallel_processing is False
        assert config.max_workers == 2
        assert config.log_level == "INFO"

    def test_from_balanced(self) -> None:
        """Test from_balanced preset factory method."""
        config = RuntimeConfig.from_balanced()

        # from_balanced() calls from_defaults()
        assert config.mode == ApplicationMode.ALL
        assert config.enable_rollback is True
        assert config.validate_before_apply is True
        assert config.parallel_processing is False
        assert config.max_workers == 4

    def test_from_aggressive(self) -> None:
        """Test from_aggressive preset factory method."""
        config = RuntimeConfig.from_aggressive()

        assert config.mode == ApplicationMode.ALL
        assert config.enable_rollback is False
        assert config.validate_before_apply is False
        assert config.parallel_processing is True
        assert config.max_workers == 16
        assert config.log_level == "WARNING"

    def test_from_semantic(self) -> None:
        """Test from_semantic preset factory method."""
        config = RuntimeConfig.from_semantic()

        assert config.mode == ApplicationMode.ALL
        assert config.enable_rollback is True
        assert config.validate_before_apply is True
        assert config.parallel_processing is True
        assert config.max_workers == 8
        assert config.log_level == "INFO"


class TestPostInitValidation:
    """Test __post_init__ validation catches invalid configurations."""

    def test_invalid_mode_type_raises(self) -> None:
        """Test __post_init__ raises ConfigError for invalid mode type."""
        with pytest.raises(ConfigError, match="mode must be ApplicationMode enum"):
            RuntimeConfig(
                mode="invalid",  # type: ignore[arg-type]
                enable_rollback=True,
                validate_before_apply=True,
                parallel_processing=False,
                max_workers=4,
                log_level="INFO",
                log_file=None,
            )


class TestFromFileValidation:
    """Test from_file validation and error handling."""

    def test_from_file_invalid_path_raises(self) -> None:
        """Test from_file raises ConfigError for invalid path."""
        # Path with null byte (invalid on most systems)
        with pytest.raises(ConfigError, match="Invalid config file path"):
            RuntimeConfig.from_file(Path("/tmp/test\x00config.yaml"))

    def test_from_file_nonexistent_raises(self, tmp_path: Path) -> None:
        """Test from_file raises ConfigError when file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.yaml"
        with pytest.raises(ConfigError, match="Config file not found"):
            RuntimeConfig.from_file(nonexistent)

    def test_from_file_directory_raises(self, tmp_path: Path) -> None:
        """Test from_file raises ConfigError when path is a directory."""
        # tmp_path is a directory
        with pytest.raises(ConfigError, match="Config path is not a file"):
            RuntimeConfig.from_file(tmp_path)


class TestYAMLLoadingErrors:
    """Test YAML file loading error paths."""

    def test_yaml_import_error(self, tmp_path: Path) -> None:
        """Test from_file raises ConfigError when PyYAML not installed."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("mode: all\n")

        # Mock yaml import to raise ModuleNotFoundError using import hook
        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "yaml":
                raise ModuleNotFoundError("No module named 'yaml'")
            return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

        with (
            patch("builtins.__import__", new=fake_import),
            pytest.raises(ConfigError, match="PyYAML not installed"),
        ):
            RuntimeConfig.from_file(config_file)

    def test_yaml_malformed_raises(self, tmp_path: Path) -> None:
        """Test from_file raises ConfigError for malformed YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("mode: [\ninvalid yaml")

        with pytest.raises(ConfigError, match="Invalid YAML"):
            RuntimeConfig.from_file(config_file)

    def test_yaml_not_dict_raises(self, tmp_path: Path) -> None:
        """Test from_file raises ConfigError when YAML is not a dict."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("- item1\n- item2\n")  # YAML list, not dict

        with pytest.raises(ConfigError, match="Config file must contain a mapping/dict"):
            RuntimeConfig.from_file(config_file)


class TestTOMLLoadingErrors:
    """Test TOML file loading error paths."""

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="Test tomli fallback (Python < 3.11)")
    def test_toml_import_error_python310(self, tmp_path: Path) -> None:
        """Test from_file raises ConfigError when tomli not installed (Python 3.10)."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('mode = "all"\n')

        # Mock tomli import to raise ModuleNotFoundError using import hook
        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "tomli":
                raise ModuleNotFoundError("No module named 'tomli'")
            return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

        with (
            patch("builtins.__import__", new=fake_import),
            pytest.raises(ConfigError, match="tomli not installed"),
        ):
            RuntimeConfig.from_file(config_file)

    def test_toml_malformed_raises(self, tmp_path: Path) -> None:
        """Test from_file raises ConfigError for malformed TOML."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("mode = [invalid toml")

        with pytest.raises(ConfigError, match="Invalid TOML"):
            RuntimeConfig.from_file(config_file)


class TestFromDictParsing:
    """Test _from_dict parsing of different configuration formats."""

    def test_from_dict_rollback_as_dict(self, tmp_path: Path) -> None:
        """Test _from_dict handles rollback as dict."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
rollback:
  enabled: false
"""
        )

        config = RuntimeConfig.from_file(config_file)
        assert config.enable_rollback is False

    def test_from_dict_rollback_as_bool(self, tmp_path: Path) -> None:
        """Test _from_dict handles rollback as bool."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
rollback: false
"""
        )

        config = RuntimeConfig.from_file(config_file)
        assert config.enable_rollback is False

    def test_from_dict_rollback_invalid_type(self, tmp_path: Path) -> None:
        """Test _from_dict raises for invalid rollback type."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
rollback: "invalid"
"""
        )

        with pytest.raises(ConfigError, match="Invalid rollback type"):
            RuntimeConfig.from_file(config_file)

    def test_from_dict_validation_as_dict(self, tmp_path: Path) -> None:
        """Test _from_dict handles validation as dict."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
validation:
  enabled: false
"""
        )

        config = RuntimeConfig.from_file(config_file)
        assert config.validate_before_apply is False

    def test_from_dict_validation_as_bool(self, tmp_path: Path) -> None:
        """Test _from_dict handles validation as bool."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
validation: false
"""
        )

        config = RuntimeConfig.from_file(config_file)
        assert config.validate_before_apply is False

    def test_from_dict_validation_invalid_type(self, tmp_path: Path) -> None:
        """Test _from_dict raises for invalid validation type."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
validation: "invalid"
"""
        )

        with pytest.raises(ConfigError, match="Invalid validation type"):
            RuntimeConfig.from_file(config_file)

    def test_from_dict_parallel_as_dict(self, tmp_path: Path) -> None:
        """Test _from_dict handles parallel as dict."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
parallel:
  enabled: true
  max_workers: 8
"""
        )

        config = RuntimeConfig.from_file(config_file)
        assert config.parallel_processing is True
        assert config.max_workers == 8

    def test_from_dict_parallel_as_bool(self, tmp_path: Path) -> None:
        """Test _from_dict handles parallel as bool."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
parallel: true
"""
        )

        config = RuntimeConfig.from_file(config_file)
        assert config.parallel_processing is True

    def test_from_dict_parallel_invalid_type(self, tmp_path: Path) -> None:
        """Test _from_dict raises for invalid parallel type."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
parallel: "invalid"
"""
        )

        with pytest.raises(ConfigError, match="Invalid parallel type"):
            RuntimeConfig.from_file(config_file)

    def test_from_dict_logging_as_dict(self, tmp_path: Path) -> None:
        """Test _from_dict handles logging as dict."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
mode: all
logging:
  level: WARNING
  file: /tmp/test.log
"""
        )

        config = RuntimeConfig.from_file(config_file)
        assert config.log_level == "WARNING"
        assert config.log_file == "/tmp/test.log"

    def test_from_dict_logging_missing_uses_defaults(self, tmp_path: Path) -> None:
        """Test _from_dict uses defaults when logging is missing."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("mode: all\n")

        config = RuntimeConfig.from_file(config_file)
        assert config.log_level == "INFO"  # Default
        assert config.log_file is None  # Default


class TestMergeWithCLI:
    """Test merge_with_cli error handling."""

    def test_merge_with_cli_invalid_field_raises(self) -> None:
        """Test merge_with_cli raises ConfigError for invalid field."""
        config = RuntimeConfig.from_defaults()

        # Trying to merge with invalid field should raise
        with pytest.raises(ConfigError, match="Failed to apply CLI overrides"):
            config.merge_with_cli(invalid_field="test")
