"""LLM integration for CodeRabbit comment parsing.

This package provides LLM-based parsing capabilities to increase coverage
from 20% (regex-only) to 95%+ (LLM-enhanced).

Phase 0: Foundation - data structures and configuration only.
"""

from pr_conflict_resolver.llm.base import ParsedChange
from pr_conflict_resolver.llm.config import LLMConfig

__all__: list[str] = ["LLMConfig", "ParsedChange"]
