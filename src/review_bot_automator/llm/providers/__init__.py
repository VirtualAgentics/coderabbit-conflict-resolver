# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""LLM provider implementations.

This package contains provider-specific implementations for different LLM services.

Available providers:
- anthropic_api.py (Phase 0 - Issue #127): Anthropic API integration
- claude_cli.py (Phase 2.2 - Issue #128): Claude CLI integration
- codex_cli.py (Phase 2.2 - Issue #128): Codex CLI integration
- ollama.py (Phase 2.3 - Issue #129): Ollama local LLM integration
- openai_api.py (Phase 2): OpenAI API integration
- caching_provider.py (Phase 5 - Issue #221): Transparent caching wrapper
"""

from review_bot_automator.llm.providers.anthropic_api import AnthropicAPIProvider
from review_bot_automator.llm.providers.caching_provider import CachingProvider
from review_bot_automator.llm.providers.claude_cli import ClaudeCLIProvider
from review_bot_automator.llm.providers.codex_cli import CodexCLIProvider
from review_bot_automator.llm.providers.ollama import OllamaProvider
from review_bot_automator.llm.providers.openai_api import OpenAIAPIProvider

__all__: list[str] = [
    "AnthropicAPIProvider",
    "CachingProvider",
    "ClaudeCLIProvider",
    "CodexCLIProvider",
    "OllamaProvider",
    "OpenAIAPIProvider",
]
