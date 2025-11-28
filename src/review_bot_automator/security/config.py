# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Security configuration for the Review Bot Automator.

This module provides centralized security configuration with three preset
profiles: conservative, balanced, and permissive. All security settings are
immutable to prevent accidental modification at runtime.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityConfig:
    """Centralized security configuration with immutable settings.

    Provides three preset profiles via class methods:
    - conservative(): Maximum security with strict settings
    - balanced(): Recommended default with good balance
    - permissive(): Relaxed settings for development/CI

    All settings are immutable (frozen dataclass) to prevent runtime modification.
    Collections use frozenset for complete immutability.

    Example:
        >>> # Use default balanced profile
        >>> config = SecurityConfig.balanced()
        >>> config.max_file_size
        10485760

        >>> # Use conservative profile for production
        >>> prod_config = SecurityConfig.conservative()
        >>> prod_config.block_on_secrets_found
        True

        >>> # Custom configuration
        >>> custom = SecurityConfig(max_file_size=15 * 1024 * 1024)
        >>> custom.max_file_size
        15728640
    """

    # Input Validation Settings
    max_file_size: int = 10 * 1024 * 1024  # 10MB default
    allowed_extensions: frozenset[str] = frozenset(
        {".py", ".ts", ".js", ".json", ".yaml", ".yml", ".toml"}
    )
    enable_path_validation: bool = True
    enable_content_sanitization: bool = True

    # Secret Scanning Settings
    enable_secret_scanning: bool = True
    scan_on_file_read: bool = True
    block_on_secrets_found: bool = False  # Warning only by default

    # File Operations Settings
    enable_atomic_writes: bool = True
    enable_backups: bool = True
    max_backup_count: int = 5

    # GitHub API Settings
    github_api_timeout: int = 30  # seconds
    github_max_retries: int = 3

    # Logging Settings
    enable_audit_logging: bool = True
    log_sensitive_data: bool = False  # Never log secrets/tokens by default

    def __post_init__(self) -> None:
        """Validate configuration values after initialization.

        Validates numeric fields are positive integers and collections are valid.
        Raises ValueError with clear messages for any invalid values.

        Raises:
            ValueError: If any configuration value is invalid.
        """
        # Validate positive integer fields
        if not isinstance(self.max_file_size, int) or self.max_file_size <= 0:
            raise ValueError(f"max_file_size must be a positive integer, got {self.max_file_size}")

        if not isinstance(self.github_api_timeout, int) or self.github_api_timeout <= 0:
            raise ValueError(
                f"github_api_timeout must be a positive integer, got {self.github_api_timeout}"
            )

        if not isinstance(self.github_max_retries, int) or self.github_max_retries <= 0:
            raise ValueError(
                f"github_max_retries must be a positive integer, got {self.github_max_retries}"
            )

        # Validate max_backup_count (can be 0 or positive)
        if not isinstance(self.max_backup_count, int) or self.max_backup_count < 0:
            raise ValueError(
                f"max_backup_count must be a non-negative integer, got {self.max_backup_count}"
            )

        # Validate allowed_extensions collection
        if not isinstance(self.allowed_extensions, frozenset):
            raise ValueError(
                f"allowed_extensions must be a frozenset, got {type(self.allowed_extensions)}"
            )

        if len(self.allowed_extensions) == 0:
            raise ValueError("allowed_extensions cannot be empty")

        # Validate all extensions are strings
        for ext in self.allowed_extensions:
            if not isinstance(ext, str):
                raise ValueError(
                    f"All extensions in allowed_extensions must be strings, got {type(ext)}: {ext}"
                )

    @classmethod
    def conservative(cls) -> "SecurityConfig":
        """Conservative security profile with strict settings.

        Use this profile for production environments where security is paramount.
        Features:
        - Smaller max file size (5MB)
        - Blocks on secret detection (prevents unsafe operations)
        - Maximum backup retention
        - Shorter API timeouts

        Returns:
            SecurityConfig: Conservative configuration instance.

        Example:
            >>> config = SecurityConfig.conservative()
            >>> config.max_file_size
            5242880
            >>> config.block_on_secrets_found
            True
        """
        return cls(
            max_file_size=5 * 1024 * 1024,  # 5MB
            block_on_secrets_found=True,
            max_backup_count=10,
            github_api_timeout=20,
        )

    @classmethod
    def balanced(cls) -> "SecurityConfig":
        """Balanced security profile (recommended default).

        Use this profile for general-purpose usage with good security
        and usability balance. This is the recommended default for most users.
        Features:
        - Moderate file size limit (10MB)
        - Secret scanning with warnings (non-blocking)
        - Standard backup retention
        - Reasonable API timeouts

        Returns:
            SecurityConfig: Balanced configuration instance (default settings).

        Example:
            >>> config = SecurityConfig.balanced()
            >>> config.max_file_size
            10485760
            >>> config.block_on_secrets_found
            False
        """
        return cls()  # Use default values

    @classmethod
    def permissive(cls) -> "SecurityConfig":
        """Permissive security profile for development/CI environments.

        Use this profile for development, testing, or CI/CD environments
        where stricter security may interfere with workflows.
        Features:
        - Larger file size limit (20MB)
        - Secret scanning disabled
        - Fewer backups (faster operations)
        - Longer API timeouts

        Returns:
            SecurityConfig: Permissive configuration instance.

        Example:
            >>> config = SecurityConfig.permissive()
            >>> config.max_file_size
            20971520
            >>> config.enable_secret_scanning
            False
        """
        return cls(
            max_file_size=20 * 1024 * 1024,  # 20MB
            enable_secret_scanning=False,
            block_on_secrets_found=False,
            max_backup_count=3,
            github_api_timeout=60,
        )
