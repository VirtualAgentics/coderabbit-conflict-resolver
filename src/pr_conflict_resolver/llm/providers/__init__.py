"""LLM provider implementations.

This package contains provider-specific implementations for different LLM services.

Available providers:
- anthropic_api.py (Phase 0 - Issue #127): Anthropic API integration

Future providers:
- claude_cli.py (Phase 1)
- openai_api.py (Phase 2)
- codex_cli.py (Phase 3)
- ollama.py (Phase 4)
"""

from pr_conflict_resolver.llm.providers.anthropic_api import AnthropicAPIProvider

__all__: list[str] = ["AnthropicAPIProvider"]
