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
#
# Rationale for MAX_WORKERS=64:
# - Balances parallelism vs. resource consumption (thread overhead, API rate limits)
# - Typical usage: 4-8 workers for API providers, 2-4 for CLI providers
# - Upper bound prevents runaway worker creation from misconfiguration
# - Based on: ThreadPoolExecutor best practices + typical LLM API rate limits
# - Recommendation: Most users should use 4-16; higher values only for:
#   * Local models (Ollama) with powerful hardware
#   * Batch processing with generous API rate limits
#   * Benchmarked scenarios showing linear scaling
MAX_WORKERS: int = 64

# Maximum number of retry attempts when waiting for another thread's cache fetch
# Used in CachingProvider to prevent infinite wait loops in edge cases
MAX_CACHE_WAIT_RETRIES: int = 3

# Timeout in seconds for waiting on another thread's cache fetch
# Prevents deadlocks when waiting threads don't receive event signal
MAX_CACHE_WAIT_TIMEOUT: float = 30.0
