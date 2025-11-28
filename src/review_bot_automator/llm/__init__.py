# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""LLM integration for CodeRabbit comment parsing.

This package provides LLM-based parsing capabilities to increase coverage
from 20% (regex-only) to 95%+ (LLM-enhanced).

Phase 0: Foundation - data structures and configuration only.
"""

from review_bot_automator.llm.base import ParsedChange
from review_bot_automator.llm.cache import CacheStats, PromptCache
from review_bot_automator.llm.config import LLMConfig
from review_bot_automator.llm.constants import VALID_LLM_PROVIDERS
from review_bot_automator.llm.cost_tracker import CostStatus, CostTracker
from review_bot_automator.llm.error_handlers import LLMErrorHandler
from review_bot_automator.llm.exceptions import LLMCostExceededError
from review_bot_automator.llm.factory import (
    create_provider,
    create_provider_from_config,
    validate_provider,
)
from review_bot_automator.llm.metrics import LLMMetrics

__all__: list[str] = [
    "VALID_LLM_PROVIDERS",
    "CacheStats",
    "CostStatus",
    "CostTracker",
    "LLMConfig",
    "LLMCostExceededError",
    "LLMErrorHandler",
    "LLMMetrics",
    "ParsedChange",
    "PromptCache",
    "create_provider",
    "create_provider_from_config",
    "validate_provider",
]
