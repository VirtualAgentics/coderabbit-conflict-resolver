# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Runtime configuration management with environment variable and file support.

This module provides the RuntimeConfig system for managing application configuration
from multiple sources: defaults, config files (YAML/TOML), environment variables,
and CLI flags. Configuration precedence: CLI flags > env vars > config file > defaults.
"""

import logging
import os
import sys
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any

from review_bot_automator.config.exceptions import ConfigError

logger = logging.getLogger(__name__)

# Available configuration presets
PRESET_NAMES = {"conservative", "balanced", "aggressive", "semantic", "llm-enabled"}


class ApplicationMode(str, Enum):
    """Application execution modes for conflict resolution.

    Attributes:
        ALL: Apply both conflicting and non-conflicting changes.
        CONFLICTS_ONLY: Apply only changes that have conflicts (after resolution).
        NON_CONFLICTS_ONLY: Apply only non-conflicting changes.
        DRY_RUN: Analyze conflicts without applying any changes.
    """

    ALL = "all"
    CONFLICTS_ONLY = "conflicts-only"
    NON_CONFLICTS_ONLY = "non-conflicts-only"
    DRY_RUN = "dry-run"

    def __str__(self) -> str:
        """Return string representation of mode."""
        return self.value


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Runtime configuration for Review Bot Automator.

    This immutable configuration dataclass manages application settings from multiple
    sources with proper precedence. All fields are validated during initialization.

    Attributes:
        mode: Application execution mode (all, conflicts-only, non-conflicts-only, dry-run).
        enable_rollback: Enable automatic rollback on failure using git stash.
        validate_before_apply: Validate changes before applying them.
        parallel_processing: Enable parallel processing of changes.
        max_workers: Maximum number of worker threads for parallel processing.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to log file. If None, logs to stdout only.
        llm_enabled: Enable LLM-based parsing (default: False for backward compatibility).
        llm_provider: LLM provider to use
            ("claude-cli", "openai", "anthropic", "codex-cli", "ollama").
        llm_model: Model identifier (e.g., "claude-sonnet-4-5", "gpt-4").
        llm_api_key: API key for the provider (if required).
        llm_fallback_to_regex: Fall back to regex parsing if LLM fails (default: True).
        llm_cache_enabled: Cache LLM responses to reduce cost (default: True).
        llm_max_tokens: Maximum tokens per LLM request (default: 2000).
        llm_cost_budget: Maximum cost per run in USD (None = unlimited).
        llm_parallel_parsing: Enable parallel comment parsing for large PRs (default: False).
        llm_parallel_max_workers: Maximum worker threads for parallel parsing (default: 4).
        llm_rate_limit: Maximum requests per second for parallel parsing (default: 10.0).
        llm_effort: LLM effort level for speed/cost vs accuracy tradeoff (None, low, medium, high).

    Example:
        >>> config = RuntimeConfig.from_env()
        >>> config = config.merge_with_cli(mode=ApplicationMode.DRY_RUN, parallel_processing=True)
        >>> print(f"Mode: {config.mode}, Parallel: {config.parallel_processing}")
        Mode: dry-run, Parallel: True
    """

    mode: ApplicationMode
    enable_rollback: bool
    validate_before_apply: bool
    parallel_processing: bool
    max_workers: int
    log_level: str
    log_file: str | None
    llm_enabled: bool = False
    llm_provider: str = "claude-cli"
    llm_model: str = "claude-sonnet-4-5"
    llm_api_key: str | None = None
    llm_fallback_to_regex: bool = True
    llm_cache_enabled: bool = True
    llm_max_tokens: int = 2000
    llm_confidence_threshold: float = 0.5
    llm_cost_budget: float | None = None
    llm_parallel_parsing: bool = False
    llm_parallel_max_workers: int = 4
    llm_rate_limit: float = 10.0
    llm_effort: str | None = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization.

        Raises:
            ConfigError: If any configuration value is invalid.
        """
        # Validate log level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level not in valid_levels:
            raise ConfigError(f"Invalid log level: {self.log_level}. Must be one of {valid_levels}")

        # Validate max_workers
        if self.max_workers < 1:
            raise ConfigError(f"max_workers must be >= 1, got {self.max_workers}")
        if self.max_workers > 32:
            raise ConfigError(
                f"max_workers should be <= 32 for optimal performance, "
                f"got {self.max_workers}. Consider <= 16 for best results."
            )

        # Validate mode is ApplicationMode enum
        if not isinstance(self.mode, ApplicationMode):
            raise ConfigError(f"mode must be ApplicationMode enum, got {type(self.mode).__name__}")

        # Validate LLM configuration
        # Import here to avoid circular import
        # (runtime_config -> llm.constants -> llm.config -> runtime_config)
        from review_bot_automator.llm.constants import VALID_LLM_PROVIDERS

        if self.llm_provider not in VALID_LLM_PROVIDERS:
            raise ConfigError(
                f"llm_provider must be one of {VALID_LLM_PROVIDERS}, got '{self.llm_provider}'"
            )

        if self.llm_max_tokens <= 0:
            raise ConfigError(f"llm_max_tokens must be positive, got {self.llm_max_tokens}")

        if not 0.0 <= self.llm_confidence_threshold <= 1.0:
            raise ConfigError(
                "llm_confidence_threshold must be between 0.0 and 1.0 "
                f"(got {self.llm_confidence_threshold})"
            )

        if self.llm_cost_budget is not None and self.llm_cost_budget <= 0:
            raise ConfigError(f"llm_cost_budget must be positive, got {self.llm_cost_budget}")

        if self.llm_parallel_max_workers < 1:
            raise ConfigError(
                f"llm_parallel_max_workers must be >= 1, got {self.llm_parallel_max_workers}"
            )

        if self.llm_parallel_max_workers > 32:
            raise ConfigError(
                f"llm_parallel_max_workers should be <= 32 for optimal performance, "
                f"got {self.llm_parallel_max_workers}. Consider <= 16 for best results."
            )

        if self.llm_rate_limit < 0.1:
            raise ConfigError(f"llm_rate_limit must be >= 0.1, got {self.llm_rate_limit}")

        # Validate llm_effort (OpenAI accepts 'none', Anthropic doesn't)
        valid_efforts = {None, "none", "low", "medium", "high"}
        if self.llm_effort is not None and self.llm_effort.lower() not in valid_efforts:
            raise ConfigError(
                f"llm_effort must be one of {{'none', 'low', 'medium', 'high'}}, "
                f"got '{self.llm_effort}'"
            )

        # Validate that API-based providers have an API key if enabled
        if (
            self.llm_enabled
            and self.llm_provider in {"openai", "anthropic"}
            and not self.llm_api_key
        ):
            raise ConfigError(
                f"LLM enabled with provider '{self.llm_provider}' but no API key provided. "
                f"Set CR_LLM_API_KEY environment variable."
            )

    @classmethod
    def from_defaults(cls) -> "RuntimeConfig":
        """Create configuration with default values.

        Returns:
            RuntimeConfig with safe default values.

        Example:
            >>> config = RuntimeConfig.from_defaults()
            >>> assert config.mode == ApplicationMode.ALL
            >>> assert config.enable_rollback is True
        """
        return cls(
            mode=ApplicationMode.ALL,
            enable_rollback=True,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=4,
            log_level="INFO",
            log_file=None,
            llm_enabled=False,
            llm_provider="claude-cli",
            llm_model="claude-sonnet-4-5",
            llm_api_key=None,
            llm_fallback_to_regex=True,
            llm_cache_enabled=True,
            llm_max_tokens=2000,
            llm_confidence_threshold=0.5,
            llm_cost_budget=None,
            llm_parallel_parsing=False,
            llm_parallel_max_workers=4,
            llm_rate_limit=10.0,
            llm_effort=None,
        )

    @classmethod
    def from_conservative(cls) -> "RuntimeConfig":
        """Create conservative configuration for maximum safety.

        Conservative settings prioritize safety and correctness over performance.
        Ideal for production environments or critical changes.

        Returns:
            RuntimeConfig with conservative settings.

        Example:
            >>> config = RuntimeConfig.from_conservative()
            >>> assert config.enable_rollback is True
            >>> assert config.validate_before_apply is True
            >>> assert config.parallel_processing is False
        """
        return cls(
            mode=ApplicationMode.ALL,
            enable_rollback=True,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=2,
            log_level="INFO",
            log_file=None,
        )

    @classmethod
    def from_balanced(cls) -> "RuntimeConfig":
        """Create balanced configuration (same as defaults).

        Balanced settings provide a good mix of safety and performance.
        This is the recommended configuration for most use cases.

        Returns:
            RuntimeConfig with balanced settings.

        Example:
            >>> config = RuntimeConfig.from_balanced()
            >>> assert config.mode == ApplicationMode.ALL
            >>> assert config.enable_rollback is True
        """
        return cls.from_defaults()

    @classmethod
    def from_aggressive(cls) -> "RuntimeConfig":
        """Create aggressive configuration for maximum performance.

        Aggressive settings prioritize performance over safety checks.
        Use only in trusted environments with good testing coverage.

        Returns:
            RuntimeConfig with aggressive settings.

        Example:
            >>> config = RuntimeConfig.from_aggressive()
            >>> assert config.parallel_processing is True
            >>> assert config.max_workers == 16
        """
        return cls(
            mode=ApplicationMode.ALL,
            enable_rollback=False,
            validate_before_apply=False,
            parallel_processing=True,
            max_workers=16,
            log_level="WARNING",
            log_file=None,
        )

    @classmethod
    def from_semantic(cls) -> "RuntimeConfig":
        """Create semantic configuration for semantic-preserving changes.

        Semantic settings are tuned for changes that preserve code semantics.
        Enables validation and moderate parallelism for careful processing.

        Returns:
            RuntimeConfig with semantic settings.

        Example:
            >>> config = RuntimeConfig.from_semantic()
            >>> assert config.validate_before_apply is True
            >>> assert config.parallel_processing is True
            >>> assert config.max_workers == 8
        """
        return cls(
            mode=ApplicationMode.ALL,
            enable_rollback=True,
            validate_before_apply=True,
            parallel_processing=True,
            max_workers=8,
            log_level="INFO",
            log_file=None,
        )

    @classmethod
    def from_llm_enabled(cls) -> "RuntimeConfig":
        """Create configuration with LLM features enabled.

        LLM-enabled settings activate AI-powered parsing for higher coverage.
        Uses balanced settings for other configuration options.

        Returns:
            RuntimeConfig with LLM enabled and balanced defaults.

        Example:
            >>> config = RuntimeConfig.from_llm_enabled()
            >>> assert config.llm_enabled is True
            >>> assert config.llm_provider == "claude-cli"
            >>> assert config.enable_rollback is True
        """
        return cls(
            mode=ApplicationMode.ALL,
            enable_rollback=True,
            validate_before_apply=True,
            parallel_processing=False,
            max_workers=4,
            log_level="INFO",
            log_file=None,
            llm_enabled=True,
            llm_provider="claude-cli",
            llm_model="claude-sonnet-4-5",
            llm_api_key=None,
            llm_fallback_to_regex=True,
            llm_cache_enabled=True,
            llm_max_tokens=2000,
            llm_cost_budget=None,
            llm_parallel_parsing=False,
            llm_parallel_max_workers=4,
            llm_rate_limit=10.0,
            llm_effort=None,
        )

    @classmethod
    def from_preset(cls, preset_name: str, api_key: str | None = None) -> "RuntimeConfig":
        """Create configuration from an LLM preset.

        Loads an LLM preset and merges it with default RuntimeConfig settings.
        This provides zero-config setup for LLM providers.

        Args:
            preset_name: Name of the preset (e.g., "codex-cli-free", "ollama-local").
            api_key: Optional API key override for API-based providers.

        Returns:
            RuntimeConfig with LLM settings from preset and defaults for other settings.

        Raises:
            ValueError: If preset name is invalid.
            ConfigError: If preset configuration is invalid.

        Example:
            >>> config = RuntimeConfig.from_preset("codex-cli-free")
            >>> assert config.llm_enabled is True
            >>> assert config.llm_provider == "codex-cli"

            >>> config = RuntimeConfig.from_preset("openai-api-mini", api_key="sk-...")
            >>> assert config.llm_enabled is True
            >>> assert config.llm_api_key == "sk-..."
        """
        # Import here to avoid circular imports
        from review_bot_automator.llm.presets import LLMPresetConfig

        # Load preset config
        try:
            llm_config = LLMPresetConfig.load_preset(preset_name, api_key=api_key)
        except ValueError as e:
            raise ConfigError(str(e)) from e

        # Start with balanced defaults
        defaults = cls.from_defaults()

        # Merge LLM config from preset with runtime defaults
        return cls(
            mode=defaults.mode,
            enable_rollback=defaults.enable_rollback,
            validate_before_apply=defaults.validate_before_apply,
            parallel_processing=defaults.parallel_processing,
            max_workers=defaults.max_workers,
            log_level=defaults.log_level,
            log_file=defaults.log_file,
            llm_enabled=llm_config.enabled,
            llm_provider=llm_config.provider,
            llm_model=llm_config.model,
            llm_api_key=llm_config.api_key,
            llm_fallback_to_regex=llm_config.fallback_to_regex,
            llm_cache_enabled=llm_config.cache_enabled,
            llm_max_tokens=llm_config.max_tokens,
            llm_cost_budget=llm_config.cost_budget,
            llm_parallel_parsing=defaults.llm_parallel_parsing,
            llm_parallel_max_workers=defaults.llm_parallel_max_workers,
            llm_rate_limit=defaults.llm_rate_limit,
            llm_effort=llm_config.effort,
        )

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        """Create configuration from environment variables.

        Loads configuration from environment variables with CR_ prefix:
        - CR_MODE: Application mode (default: "all")
        - CR_ENABLE_ROLLBACK: Enable rollback (default: "true")
        - CR_VALIDATE: Enable validation (default: "true")
        - CR_PARALLEL: Enable parallel processing (default: "false")
        - CR_MAX_WORKERS: Max worker threads (default: "4")
        - CR_LOG_LEVEL: Logging level (default: "INFO")
        - CR_LOG_FILE: Log file path (default: None)
        - CR_LLM_ENABLED: Enable LLM parsing (default: "false")
        - CR_LLM_PROVIDER: LLM provider (default: "claude-cli")
        - CR_LLM_MODEL: LLM model (default: "claude-sonnet-4-5")
        - CR_LLM_API_KEY: API key for provider (default: None)
        - CR_LLM_FALLBACK_TO_REGEX: Fallback to regex (default: "true")
        - CR_LLM_CACHE_ENABLED: Enable response caching (default: "true")
        - CR_LLM_MAX_TOKENS: Max tokens per request (default: "2000")
        - CR_LLM_CONFIDENCE_THRESHOLD: Minimum LLM confidence (default: "0.5")
        - CR_LLM_COST_BUDGET: Max cost per run in USD (default: None)
        - CR_LLM_PARALLEL_PARSING: Enable parallel LLM comment parsing (default: "false")
        - CR_LLM_PARALLEL_WORKERS: Max worker threads for LLM parsing (default: "4")
        - CR_LLM_RATE_LIMIT: Max LLM requests per second (default: "10.0")
        - CR_LLM_EFFORT: LLM effort level (default: None, options: none/low/medium/high)

        Returns:
            RuntimeConfig loaded from environment variables.

        Raises:
            ConfigError: If environment variable has invalid value.

        Example:
            >>> os.environ["CR_MODE"] = "dry-run"
            >>> os.environ["CR_PARALLEL"] = "true"
            >>> config = RuntimeConfig.from_env()
            >>> assert config.mode == ApplicationMode.DRY_RUN
            >>> assert config.parallel_processing is True
        """
        # Start with defaults
        defaults = cls.from_defaults()

        # Parse mode
        mode_str = os.getenv("CR_MODE", defaults.mode.value).lower()
        try:
            mode = ApplicationMode(mode_str)
        except ValueError as e:
            valid_modes = [m.value for m in ApplicationMode]
            raise ConfigError(f"Invalid CR_MODE='{mode_str}'. Must be one of {valid_modes}") from e

        # Parse boolean values
        def parse_bool(env_var: str, default: bool) -> bool:
            """Parse boolean environment variable."""
            value = os.getenv(env_var, str(default)).lower()
            if value in ("true", "1", "yes", "on"):
                return True
            if value in ("false", "0", "no", "off"):
                return False
            raise ConfigError(
                f"Invalid {env_var}='{value}'. Must be true/false, 1/0, yes/no, or on/off"
            )

        # Parse integer values
        def parse_int(env_var: str, default: int, min_value: int = 1) -> int:
            """Parse integer environment variable."""
            value_str = os.getenv(env_var, str(default))
            try:
                value = int(value_str)
                if value < min_value:
                    raise ConfigError(f"{env_var}={value} must be >= {min_value}")
                return value
            except ValueError as e:
                raise ConfigError(f"Invalid {env_var}='{value_str}'. Must be an integer") from e

        # Parse optional float for cost budget
        def parse_float_optional(env_var: str) -> float | None:
            """Parse optional float environment variable."""
            value_str = os.getenv(env_var)
            if not value_str:
                return None
            try:
                return float(value_str)
            except ValueError as e:
                raise ConfigError(f"Invalid {env_var}='{value_str}'. Must be a number") from e

        # Parse required float (with default)
        def parse_float(
            env_var: str, default: float, min_value: float = 0.0, max_value: float | None = None
        ) -> float:
            """Parse required float environment variable."""
            value_str = os.getenv(env_var, str(default))
            try:
                value = float(value_str)
                if value < min_value:
                    raise ConfigError(f"{env_var}={value} must be >= {min_value}")
                if max_value is not None and value > max_value:
                    raise ConfigError(f"{env_var}={value} must be <= {max_value}")
                return value
            except ValueError as e:
                raise ConfigError(f"Invalid {env_var}='{value_str}'. Must be a number") from e

        # Load all configuration
        return cls(
            mode=mode,
            enable_rollback=parse_bool("CR_ENABLE_ROLLBACK", defaults.enable_rollback),
            validate_before_apply=parse_bool("CR_VALIDATE", defaults.validate_before_apply),
            parallel_processing=parse_bool("CR_PARALLEL", defaults.parallel_processing),
            max_workers=parse_int("CR_MAX_WORKERS", defaults.max_workers, min_value=1),
            log_level=os.getenv("CR_LOG_LEVEL", defaults.log_level).upper(),
            log_file=os.getenv("CR_LOG_FILE") or defaults.log_file,
            llm_enabled=parse_bool("CR_LLM_ENABLED", defaults.llm_enabled),
            llm_provider=os.getenv("CR_LLM_PROVIDER", defaults.llm_provider),
            llm_model=os.getenv("CR_LLM_MODEL", defaults.llm_model),
            llm_api_key=os.getenv("CR_LLM_API_KEY") or defaults.llm_api_key,
            llm_fallback_to_regex=parse_bool(
                "CR_LLM_FALLBACK_TO_REGEX", defaults.llm_fallback_to_regex
            ),
            llm_cache_enabled=parse_bool("CR_LLM_CACHE_ENABLED", defaults.llm_cache_enabled),
            llm_max_tokens=parse_int("CR_LLM_MAX_TOKENS", defaults.llm_max_tokens, min_value=1),
            llm_confidence_threshold=parse_float(
                "CR_LLM_CONFIDENCE_THRESHOLD",
                defaults.llm_confidence_threshold,
                min_value=0.0,
                max_value=1.0,
            ),
            llm_cost_budget=parse_float_optional("CR_LLM_COST_BUDGET"),
            llm_parallel_parsing=parse_bool(
                "CR_LLM_PARALLEL_PARSING", defaults.llm_parallel_parsing
            ),
            llm_parallel_max_workers=parse_int(
                "CR_LLM_PARALLEL_WORKERS", defaults.llm_parallel_max_workers, min_value=1
            ),
            llm_rate_limit=parse_float("CR_LLM_RATE_LIMIT", defaults.llm_rate_limit, min_value=0.1),
            llm_effort=os.getenv("CR_LLM_EFFORT", "").lower() or defaults.llm_effort,
        )

    @classmethod
    def from_file(cls, config_path: Path) -> "RuntimeConfig":
        """Load configuration from YAML or TOML file.

        Supports both YAML (.yaml, .yml) and TOML (.toml) formats.
        File paths are validated for security (no traversal attacks).

        Args:
            config_path: Path to configuration file (YAML or TOML).

        Returns:
            RuntimeConfig loaded from file.

        Raises:
            ConfigError: If file doesn't exist, has invalid format, or contains invalid values.

        Example:
            >>> config = RuntimeConfig.from_file(Path("config.yaml"))
            >>> config = RuntimeConfig.from_file(Path("/etc/myapp/config.toml"))
        """
        # Import here to avoid circular imports and make dependencies optional

        # Basic path validation for config files (allow absolute paths)
        # Convert to Path and resolve to canonical path
        try:
            config_path = Path(config_path).resolve()
        except (OSError, ValueError) as e:
            raise ConfigError(f"Invalid config file path: {e}") from e

        if not config_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")

        if not config_path.is_file():
            raise ConfigError(f"Config path is not a file: {config_path}")

        # Determine file format and load
        suffix = config_path.suffix.lower()

        if suffix in (".yaml", ".yml"):
            return cls._load_from_yaml(config_path)
        elif suffix == ".toml":
            return cls._load_from_toml(config_path)
        else:
            raise ConfigError(
                f"Unsupported config file format: {suffix}. Must be .yaml, .yml, or .toml"
            )

    @classmethod
    def _load_from_yaml(cls, config_path: Path) -> "RuntimeConfig":
        """Load configuration from YAML file.

        Args:
            config_path: Path to YAML file.

        Returns:
            RuntimeConfig loaded from YAML.

        Raises:
            ConfigError: If YAML is malformed or contains invalid values.
        """
        try:
            import yaml
        except ImportError as e:
            raise ConfigError("PyYAML not installed. Install with: pip install pyyaml") from e

        try:
            with config_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {config_path}: {e}") from e
        except OSError as e:
            raise ConfigError(f"Failed to read {config_path}: {e}") from e

        if not isinstance(data, dict):
            raise ConfigError(f"Config file must contain a mapping/dict, got {type(data).__name__}")

        return cls._from_dict(data, config_path)

    @classmethod
    def _load_from_toml(cls, config_path: Path) -> "RuntimeConfig":
        """Load configuration from TOML file.

        Args:
            config_path: Path to TOML file.

        Returns:
            RuntimeConfig loaded from TOML.

        Raises:
            ConfigError: If TOML is malformed or contains invalid values.
        """
        # Python 3.11+ has tomllib built-in, otherwise use tomli
        if sys.version_info >= (3, 11):  # noqa: UP036
            import tomllib
        else:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError as e:
                raise ConfigError("tomli not installed. Install with: pip install tomli") from e

        try:
            with config_path.open("rb") as f:
                data = tomllib.load(f)
        except Exception as e:  # tomllib can raise various exceptions
            raise ConfigError(f"Invalid TOML in {config_path}: {e}") from e

        return cls._from_dict(data, config_path)

    @staticmethod
    def _is_env_var_placeholder(value: str) -> bool:
        """Check if a string value is an environment variable placeholder.

        Args:
            value: String to check.

        Returns:
            True if value is a placeholder like ${VAR_NAME}, False otherwise.

        Example:
            >>> RuntimeConfig._is_env_var_placeholder("${API_KEY}")
            True
            >>> RuntimeConfig._is_env_var_placeholder("sk-actual-key-123")
            False
        """
        import re

        # Check if string contains ${VAR} pattern
        return bool(re.search(r"\$\{[A-Z_][A-Z0-9_]*\}", value))

    @classmethod
    def _interpolate_env_vars(cls, value: Any) -> Any:  # noqa: ANN401
        """Interpolate environment variables in configuration values.

        Supports ${VAR_NAME} syntax for environment variable substitution.
        Non-string values are returned unchanged.

        Args:
            value: Configuration value (string, dict, list, or primitive).

        Returns:
            Value with environment variables interpolated.

        Example:
            >>> os.environ["MY_KEY"] = "secret123"
            >>> cls._interpolate_env_vars("api_key: ${MY_KEY}")
            'api_key: secret123'
        """
        if isinstance(value, str):
            # Replace ${VAR} with environment variable value
            import re

            def replace_env_var(match: re.Match[str]) -> str:
                var_name = match.group(1)
                env_value = os.getenv(var_name)
                if env_value is None:
                    logger.warning(
                        f"Environment variable '{var_name}' not found, keeping placeholder"
                    )
                    return match.group(0)  # Keep original ${VAR}
                return env_value

            return re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", replace_env_var, value)
        elif isinstance(value, dict):
            return {k: cls._interpolate_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls._interpolate_env_vars(item) for item in value]
        else:
            return value

    @classmethod
    def _from_dict(cls, data: dict[str, Any], source: Path) -> "RuntimeConfig":
        """Create RuntimeConfig from dictionary (internal helper).

        Args:
            data: Dictionary with configuration values.
            source: Source file path (for error messages).

        Returns:
            RuntimeConfig from dictionary.

        Raises:
            ConfigError: If dictionary contains invalid values.
        """
        # Start with defaults
        defaults = cls.from_defaults()

        # Interpolate environment variables in all string values
        data = cls._interpolate_env_vars(data)

        # Parse mode
        mode_value = data.get("mode", defaults.mode.value)
        try:
            mode = ApplicationMode(mode_value)
        except ValueError as e:
            valid_modes = [m.value for m in ApplicationMode]
            raise ConfigError(
                f"Invalid mode '{mode_value}' in {source}. Must be one of {valid_modes}"
            ) from e

        # Parse rollback settings
        rollback = data.get("rollback", {})
        if isinstance(rollback, dict):
            enable_rollback = rollback.get("enabled", defaults.enable_rollback)
        elif isinstance(rollback, bool):
            enable_rollback = rollback
        else:
            raise ConfigError(f"Invalid rollback type in {source}: {type(rollback).__name__}")

        # Parse validation settings
        validation = data.get("validation", {})
        if isinstance(validation, dict):
            validate_before_apply = validation.get("enabled", defaults.validate_before_apply)
        elif isinstance(validation, bool):
            validate_before_apply = validation
        else:
            raise ConfigError(f"Invalid validation type in {source}: {type(validation).__name__}")

        # Parse parallel processing settings
        parallel = data.get("parallel", {})
        if isinstance(parallel, dict):
            parallel_processing = parallel.get("enabled", defaults.parallel_processing)
            max_workers = parallel.get("max_workers", defaults.max_workers)
        elif isinstance(parallel, bool):
            parallel_processing = parallel
            max_workers = defaults.max_workers
        else:
            raise ConfigError(f"Invalid parallel type in {source}: {type(parallel).__name__}")

        # Parse logging settings
        logging_config = data.get("logging", {})
        if isinstance(logging_config, dict):
            log_level = logging_config.get("level", defaults.log_level)
            log_file = logging_config.get("file", defaults.log_file)
        else:
            log_level = defaults.log_level
            log_file = defaults.log_file

        # Parse LLM settings
        llm_config = data.get("llm", {})
        if isinstance(llm_config, dict):
            llm_enabled = llm_config.get("enabled", defaults.llm_enabled)
            llm_provider = llm_config.get("provider", defaults.llm_provider)
            llm_model = llm_config.get("model", defaults.llm_model)
            llm_api_key = llm_config.get("api_key", defaults.llm_api_key)
            llm_fallback_to_regex = llm_config.get(
                "fallback_to_regex", defaults.llm_fallback_to_regex
            )
            llm_cache_enabled = llm_config.get("cache_enabled", defaults.llm_cache_enabled)
            llm_max_tokens = llm_config.get("max_tokens", defaults.llm_max_tokens)
            llm_confidence_threshold = llm_config.get(
                "confidence_threshold", defaults.llm_confidence_threshold
            )
            llm_cost_budget = llm_config.get("cost_budget", defaults.llm_cost_budget)
            llm_parallel_parsing = llm_config.get("parallel_parsing", defaults.llm_parallel_parsing)
            llm_parallel_max_workers = llm_config.get(
                "parallel_max_workers", defaults.llm_parallel_max_workers
            )
            llm_rate_limit = llm_config.get("rate_limit", defaults.llm_rate_limit)
            llm_effort = llm_config.get("effort", defaults.llm_effort)

            # SECURITY: Reject API keys in configuration files
            # API keys must only be provided via environment variables or CLI flags
            if llm_api_key and not cls._is_env_var_placeholder(llm_api_key):
                provider_upper = llm_provider.upper()
                raise ConfigError(
                    f"SECURITY: API keys must NOT be stored in configuration files ({source}). "
                    f"Use environment variables: CR_LLM_API_KEY or ${{{provider_upper}_API_KEY}}. "
                    f"Example: api_key: ${{ANTHROPIC_API_KEY}}"
                )
        else:
            llm_enabled = defaults.llm_enabled
            llm_provider = defaults.llm_provider
            llm_model = defaults.llm_model
            llm_api_key = defaults.llm_api_key
            llm_fallback_to_regex = defaults.llm_fallback_to_regex
            llm_cache_enabled = defaults.llm_cache_enabled
            llm_max_tokens = defaults.llm_max_tokens
            llm_cost_budget = defaults.llm_cost_budget
            llm_parallel_parsing = defaults.llm_parallel_parsing
            llm_parallel_max_workers = defaults.llm_parallel_max_workers
            llm_rate_limit = defaults.llm_rate_limit
            llm_effort = defaults.llm_effort

        # Validate and convert numeric LLM parallel config values
        try:
            parallel_workers = int(llm_parallel_max_workers)
            rate_limit = float(llm_rate_limit)
            confidence_threshold = float(llm_confidence_threshold)
        except (TypeError, ValueError) as e:
            raise ConfigError(f"Invalid LLM parallel config in {source}: {e}") from e

        return cls(
            mode=mode,
            enable_rollback=bool(enable_rollback),
            validate_before_apply=bool(validate_before_apply),
            parallel_processing=bool(parallel_processing),
            max_workers=int(max_workers),
            log_level=str(log_level).upper(),
            log_file=str(log_file) if log_file else None,
            llm_enabled=bool(llm_enabled),
            llm_provider=str(llm_provider),
            llm_model=str(llm_model),
            llm_api_key=str(llm_api_key) if llm_api_key else None,
            llm_fallback_to_regex=bool(llm_fallback_to_regex),
            llm_cache_enabled=bool(llm_cache_enabled),
            llm_max_tokens=int(llm_max_tokens),
            llm_confidence_threshold=float(confidence_threshold),
            llm_cost_budget=float(llm_cost_budget) if llm_cost_budget else None,
            llm_parallel_parsing=bool(llm_parallel_parsing),
            llm_parallel_max_workers=parallel_workers,
            llm_rate_limit=rate_limit,
            llm_effort=str(llm_effort).lower() if llm_effort else None,
        )

    def merge_with_cli(self, **overrides: Any) -> "RuntimeConfig":  # noqa: ANN401
        """Create new config with CLI flag overrides.

        CLI flags take precedence over environment variables and config files.
        Only non-None values are applied.

        Args:
            **overrides: Keyword arguments matching RuntimeConfig fields.
                        None values are ignored (no override).

        Returns:
            New RuntimeConfig with overrides applied.

        Raises:
            ConfigError: If override value is invalid.

        Example:
            >>> config = RuntimeConfig.from_env()
            >>> config = config.merge_with_cli(
            ...     mode=ApplicationMode.DRY_RUN,
            ...     enable_rollback=False,
            ...     parallel_processing=True
            ... )
        """
        # Filter out None values (no override)
        filtered_overrides = {k: v for k, v in overrides.items() if v is not None}

        # Handle mode string to enum conversion
        if "mode" in filtered_overrides and isinstance(filtered_overrides["mode"], str):
            try:
                filtered_overrides["mode"] = ApplicationMode(filtered_overrides["mode"])
            except ValueError as e:
                valid_modes = [m.value for m in ApplicationMode]
                raise ConfigError(
                    f"Invalid mode '{filtered_overrides['mode']}'. Must be one of {valid_modes}"
                ) from e

        # Create new config with overrides
        try:
            return replace(self, **filtered_overrides)
        except Exception as e:
            raise ConfigError(f"Failed to apply CLI overrides: {e}") from e

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration.

        Example:
            >>> config = RuntimeConfig.from_defaults()
            >>> data = config.to_dict()
            >>> assert data["mode"] == "all"
            >>> assert data["enable_rollback"] is True
        """
        return {
            "mode": self.mode.value,
            "enable_rollback": self.enable_rollback,
            "validate_before_apply": self.validate_before_apply,
            "parallel_processing": self.parallel_processing,
            "max_workers": self.max_workers,
            "log_level": self.log_level,
            "log_file": self.log_file,
            "llm_enabled": self.llm_enabled,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_api_key": self.llm_api_key,
            "llm_fallback_to_regex": self.llm_fallback_to_regex,
            "llm_cache_enabled": self.llm_cache_enabled,
            "llm_max_tokens": self.llm_max_tokens,
            "llm_confidence_threshold": self.llm_confidence_threshold,
            "llm_cost_budget": self.llm_cost_budget,
            "llm_parallel_parsing": self.llm_parallel_parsing,
            "llm_parallel_max_workers": self.llm_parallel_max_workers,
            "llm_rate_limit": self.llm_rate_limit,
            "llm_effort": self.llm_effort,
        }
