# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Prompt caching module for LLM cost reduction.

This module provides file-based caching for LLM responses with TTL expiration
and LRU eviction to achieve 50-90% cost reduction through cache hits.
"""

from review_bot_automator.llm.cache.prompt_cache import (
    CacheEntry,
    CacheStats,
    PromptCache,
)

__all__: list[str] = ["CacheEntry", "CacheStats", "PromptCache"]
