# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Configuration management and presets.

This module provides configuration management through:
- RuntimeConfig: Runtime configuration from env vars, files, and CLI flags
- ApplicationMode: Enum for application execution modes
- PresetConfig: Predefined configuration presets
- ConfigError: Exception for configuration errors
"""

from review_bot_automator.config.exceptions import ConfigError
from review_bot_automator.config.runtime_config import ApplicationMode, RuntimeConfig

__all__ = ["ApplicationMode", "ConfigError", "RuntimeConfig"]
