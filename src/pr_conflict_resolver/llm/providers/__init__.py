"""LLM provider implementations.

This package contains provider-specific implementations for different LLM services.

Available providers:
- anthropic_api.py (Phase 0 - Issue #127): Anthropic API integration
- ollama.py (Phase 2.3 - Issue #129): Ollama local LLM integration
- openai_api.py (Phase 2): OpenAI API integration

Future providers:
- claude_cli.py (Phase 1)
- codex_cli.py (Phase 3)
"""

from pr_conflict_resolver.llm.providers.anthropic_api import AnthropicAPIProvider
from pr_conflict_resolver.llm.providers.ollama import OllamaProvider

__all__: list[str] = ["AnthropicAPIProvider", "OllamaProvider"]
