"""
CodeRabbit Conflict Resolver

An intelligent, automated conflict resolution system for GitHub PR comments.
"""

__version__ = "0.1.0"
__author__ = "VirtualAgentics"
__email__ = "contact@virtualagentics.com"

from .core.resolver import ConflictResolver
from .config.presets import PresetConfig

__all__ = ["ConflictResolver", "PresetConfig"]
