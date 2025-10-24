"""
CodeRabbit Conflict Resolver

An intelligent, automated conflict resolution system for GitHub PR comments.
"""

__version__ = "0.1.0"
__author__ = "VirtualAgentics"
__email__ = "contact@virtualagentics.com"

from .core.resolver import ConflictResolver, Change, Conflict, Resolution, ResolutionResult
from .config.presets import PresetConfig
from .analysis.conflict_detector import ConflictDetector
from .handlers.json_handler import JsonHandler
from .handlers.yaml_handler import YamlHandler
from .handlers.toml_handler import TomlHandler
from .integrations.github import GitHubCommentExtractor
from .strategies.priority_strategy import PriorityStrategy

__all__ = [
    "ConflictResolver",
    "Change",
    "Conflict", 
    "Resolution",
    "ResolutionResult",
    "PresetConfig",
    "ConflictDetector",
    "JsonHandler",
    "YamlHandler", 
    "TomlHandler",
    "GitHubCommentExtractor",
    "PriorityStrategy"
]
