"""Security module for the Review Bot Automator.

This module provides security controls including:
- Input validation and sanitization (InputValidator)
- Secure file handling with atomic operations (SecureFileHandler)
- Secret detection and prevention (SecretScanner)
- Centralized security configuration (SecurityConfig)
"""

from pr_conflict_resolver.security.config import SecurityConfig
from pr_conflict_resolver.security.input_validator import InputValidator
from pr_conflict_resolver.security.secret_scanner import SecretFinding, SecretScanner
from pr_conflict_resolver.security.secure_file_handler import SecureFileHandler

__all__ = [
    "InputValidator",
    "SecretFinding",
    "SecretScanner",
    "SecureFileHandler",
    "SecurityConfig",
]
