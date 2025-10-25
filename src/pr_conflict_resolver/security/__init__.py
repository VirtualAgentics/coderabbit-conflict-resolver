"""Security module for the CodeRabbit Conflict Resolver.

This module provides security controls including:
- Input validation and sanitization
- Secure file handling
- Secret detection
- Security configuration
"""

from .input_validator import InputValidator

__all__ = ["InputValidator"]
