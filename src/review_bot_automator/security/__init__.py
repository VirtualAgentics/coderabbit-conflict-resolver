# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Security module for the Review Bot Automator.

This module provides security controls including:
- Input validation and sanitization (InputValidator)
- Secure file handling with atomic operations (SecureFileHandler)
- Secret detection and prevention (SecretScanner)
- Centralized security configuration (SecurityConfig)
"""

from review_bot_automator.security.config import SecurityConfig
from review_bot_automator.security.input_validator import InputValidator
from review_bot_automator.security.secret_scanner import SecretFinding, SecretScanner
from review_bot_automator.security.secure_file_handler import SecureFileHandler

__all__ = [
    "InputValidator",
    "SecretFinding",
    "SecretScanner",
    "SecureFileHandler",
    "SecurityConfig",
]
