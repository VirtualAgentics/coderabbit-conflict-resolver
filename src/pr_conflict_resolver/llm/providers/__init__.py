"""LLM provider implementations.

This package contains provider-specific implementations for different LLM services.

Available providers:
- anthropic_api.py (Phase 0 - Issue #127): Anthropic API integration
- claude_cli.py (Phase 2.2 - Issue #128): Claude CLI integration
- codex_cli.py (Phase 2.2 - Issue #128): Codex CLI integration
- ollama.py (Phase 2.3 - Issue #129): Ollama local LLM integration
- openai_api.py (Phase 2): OpenAI API integration
"""

from pr_conflict_resolver.llm.providers.anthropic_api import AnthropicAPIProvider
from pr_conflict_resolver.llm.providers.claude_cli import ClaudeCLIProvider
from pr_conflict_resolver.llm.providers.codex_cli import CodexCLIProvider
from pr_conflict_resolver.llm.providers.ollama import OllamaProvider
from pr_conflict_resolver.llm.providers.openai_api import OpenAIAPIProvider

__all__: list[str] = [
    "AnthropicAPIProvider",
    "ClaudeCLIProvider",
    "CodexCLIProvider",
    "OllamaProvider",
    "OpenAIAPIProvider",
]
