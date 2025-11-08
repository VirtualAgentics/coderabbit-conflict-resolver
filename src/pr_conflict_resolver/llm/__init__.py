"""LLM integration for CodeRabbit comment parsing.

This package provides LLM-based parsing capabilities to increase coverage
from 20% (regex-only) to 95%+ (LLM-enhanced).

Phase 0: Foundation - data structures and configuration only.
"""

from pr_conflict_resolver.llm.base import ParsedChange
from pr_conflict_resolver.llm.cache import CacheStats, PromptCache
from pr_conflict_resolver.llm.config import LLMConfig
from pr_conflict_resolver.llm.constants import VALID_LLM_PROVIDERS

__all__: list[str] = [
    "VALID_LLM_PROVIDERS",
    "CacheStats",
    "LLMConfig",
    "ParsedChange",
    "PromptCache",
]
