"""Constants for LLM integration.

This module defines shared constants used across the LLM integration components.
"""

# Valid LLM provider identifiers
VALID_LLM_PROVIDERS: frozenset[str] = frozenset(
    {
        "claude-cli",  # Claude via CLI (no API key required)
        "openai",  # OpenAI API (requires API key)
        "anthropic",  # Anthropic API (requires API key)
        "codex-cli",  # Codex via CLI (no API key required)
        "ollama",  # Ollama local models (no API key required)
    }
)

# Maximum number of parallel workers for LLM operations
# Used for parallel parsing, caching, and other concurrent operations
MAX_WORKERS = 64
