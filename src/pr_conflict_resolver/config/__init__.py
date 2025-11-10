"""Configuration management and presets.

This module provides configuration management through:
- RuntimeConfig: Runtime configuration from env vars, files, and CLI flags
- ApplicationMode: Enum for application execution modes
- PresetConfig: Predefined configuration presets
- ConfigError: Exception for configuration errors
"""

from pr_conflict_resolver.config.exceptions import ConfigError
from pr_conflict_resolver.config.runtime_config import ApplicationMode, RuntimeConfig

__all__ = ["ApplicationMode", "ConfigError", "RuntimeConfig"]
