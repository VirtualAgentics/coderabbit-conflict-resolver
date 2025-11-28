# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Configuration loading utilities for CLI commands.

This module provides shared configuration loading logic for CLI commands.
"""

import logging
import os
from pathlib import Path
from typing import Any

from rich.console import Console

from review_bot_automator.config.runtime_config import PRESET_NAMES, RuntimeConfig

logger = logging.getLogger(__name__)
console = Console()


def load_runtime_config(
    config: str | None,
    llm_preset: str | None,
    llm_api_key: str | None,
    cli_overrides: dict[str, Any],
    env_var_map: dict[str, str],
) -> tuple[RuntimeConfig, str | None]:
    """Load runtime configuration with proper precedence.

    Configuration precedence (highest to lowest):
    1. CLI flags (provided in cli_overrides)
    2. Environment variables (mapped via env_var_map)
    3. Configuration file or preset (config parameter)
    4. LLM preset (llm_preset parameter)
    5. Default values

    Args:
        config: Configuration preset name or path to configuration file (YAML/TOML).
        llm_preset: LLM configuration preset name for zero-config setup.
        llm_api_key: API key for API-based providers (used with llm_preset).
        cli_overrides: Dictionary of CLI flag overrides to apply.
        env_var_map: Mapping of RuntimeConfig field names to environment variable names.

    Returns:
        Tuple of (RuntimeConfig instance, preset_name or None).
        The preset_name is the configuration preset name if one was loaded, None otherwise.

    Raises:
        ValueError: If preset method not found or invalid configuration.

    Example:
        runtime_config, preset_name = load_runtime_config(
            config="balanced",
            llm_preset=None,
            llm_api_key=None,
            cli_overrides={"llm_enabled": True, "log_level": "DEBUG"},
            env_var_map={"llm_provider": "CR_LLM_PROVIDER"},
        )
    """
    # Step 1: Load base configuration (config preset, config file, LLM preset, or defaults)
    preset_name = None  # Track which config preset was loaded (if any)

    if config:
        # Check if config is a preset name or file path
        if config.lower() in PRESET_NAMES:
            # Load configuration preset
            preset_name = config.lower()
            # Replace hyphens with underscores for method name
            method_suffix = preset_name.replace("-", "_")
            method_name = f"from_{method_suffix}"

            # Check if the preset method exists before calling
            if not hasattr(RuntimeConfig, method_name):
                raise ValueError(
                    f"Preset method '{method_name}' not found. "
                    f"Valid presets: {', '.join(PRESET_NAMES)}"
                )

            preset_method = getattr(RuntimeConfig, method_name)
            runtime_config = preset_method()
            console.print(f"[dim]Loaded configuration preset: {config}[/dim]")
        else:
            # Load from configuration file
            config_path = Path(config)
            runtime_config = RuntimeConfig.from_file(config_path)
            console.print(f"[dim]Loaded configuration from: {config}[/dim]")
    elif llm_preset:
        # Load from LLM preset (lower priority than config file/preset)
        runtime_config = RuntimeConfig.from_preset(llm_preset.lower(), api_key=llm_api_key)
        console.print(f"[dim]Loaded LLM preset: {llm_preset.lower()}[/dim]")
    else:
        # Use defaults when no config file/preset/llm-preset specified
        runtime_config = RuntimeConfig.from_defaults()

    # Step 2: Apply environment variable overrides
    env_config = RuntimeConfig.from_env()
    env_overrides = {
        field_name: getattr(env_config, field_name)
        for field_name, env_var in env_var_map.items()
        if env_var in os.environ
    }

    if env_overrides:
        runtime_config = runtime_config.merge_with_cli(**env_overrides)
        console.print(f"[dim]Applied {len(env_overrides)} environment variable override(s)[/dim]")

    # Step 3: Apply CLI overrides
    runtime_config = runtime_config.merge_with_cli(**cli_overrides)

    return runtime_config, preset_name
