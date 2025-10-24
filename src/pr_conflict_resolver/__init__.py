"""CodeRabbit Conflict Resolver.

An intelligent, automated conflict resolution system for GitHub PR comments.
"""

__version__ = "0.1.0"
__author__ = "VirtualAgentics"
__email__ = "contact@virtualagentics.com"

from .analysis.conflict_detector import ConflictDetector
from .config.presets import PresetConfig
from .core.models import Change, Conflict, FileType, Resolution, ResolutionResult
from .core.resolver import ConflictResolver
from .handlers.json_handler import JsonHandler
from .handlers.toml_handler import TomlHandler
from .handlers.yaml_handler import YamlHandler
from .integrations.github import GitHubCommentExtractor
from .strategies.priority_strategy import PriorityStrategy

__all__ = [
    "Change",
    "Conflict",
    "ConflictDetector",
    "ConflictResolver",
    "FileType",
    "GitHubCommentExtractor",
    "JsonHandler",
    "PresetConfig",
    "PriorityStrategy",
    "Resolution",
    "ResolutionResult",
    "TomlHandler",
    "YamlHandler",
]
