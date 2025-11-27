"""Configuration exceptions for PR Conflict Resolver.

This module contains exception classes used across the configuration system,
separated to avoid circular import dependencies.
"""


class ConfigError(Exception):
    """Exception raised for configuration errors."""
