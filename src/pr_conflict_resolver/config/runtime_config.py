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


class ConfigError(Exception):
    """Exception raised for configuration errors."""


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Runtime configuration for the PR conflict resolver.

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
        llm_provider: LLM provider to use ("claude-cli", "openai", "anthropic", "ollama").
        llm_model: Model identifier (e.g., "claude-sonnet-4-5", "gpt-4").
        llm_api_key: API key for the provider (if required).
        llm_fallback_to_regex: Fall back to regex parsing if LLM fails (default: True).
        llm_cache_enabled: Cache LLM responses to reduce cost (default: True).
        llm_max_tokens: Maximum tokens per LLM request (default: 2000).
        llm_cost_budget: Maximum cost per run in USD (None = unlimited).

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
    llm_cost_budget: float | None = None

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
            logger.warning(
                f"max_workers={self.max_workers} is very high. "
                f"Consider using <= 16 for optimal performance."
            )

        # Validate mode is ApplicationMode enum
        if not isinstance(self.mode, ApplicationMode):
            raise ConfigError(f"mode must be ApplicationMode enum, got {type(self.mode).__name__}")

        # Validate LLM configuration
        valid_providers = {"claude-cli", "openai", "anthropic", "codex-cli", "ollama"}
        if self.llm_provider not in valid_providers:
            raise ConfigError(
                f"llm_provider must be one of {valid_providers}, got '{self.llm_provider}'"
            )

        if self.llm_max_tokens <= 0:
            raise ConfigError(f"llm_max_tokens must be positive, got {self.llm_max_tokens}")

        if self.llm_cost_budget is not None and self.llm_cost_budget <= 0:
            raise ConfigError(f"llm_cost_budget must be positive, got {self.llm_cost_budget}")

        # Warn if LLM is enabled with API-based providers without API key
        if (
            self.llm_enabled
            and self.llm_provider in {"openai", "anthropic"}
            and not self.llm_api_key
        ):
            logger.warning(
                f"LLM enabled with provider '{self.llm_provider}' but no API key provided. "
                f"Set CR_LLM_API_KEY environment variable or --llm-api-key CLI flag."
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
        - CR_LLM_COST_BUDGET: Max cost per run in USD (default: None)

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
            llm_cost_budget=parse_float_optional("CR_LLM_COST_BUDGET"),
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

        return cls(
            mode=mode,
            enable_rollback=bool(enable_rollback),
            validate_before_apply=bool(validate_before_apply),
            parallel_processing=bool(parallel_processing),
            max_workers=int(max_workers),
            log_level=str(log_level).upper(),
            log_file=str(log_file) if log_file else None,
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
        }
