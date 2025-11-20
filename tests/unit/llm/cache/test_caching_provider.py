"""Tests for CachingProvider wrapper.

This module tests the transparent caching wrapper that adds response caching
to any LLM provider without modifying provider code.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pr_conflict_resolver.llm.cache.prompt_cache import DeleteStatus, PromptCache
from pr_conflict_resolver.llm.providers.caching_provider import CachingProvider


def create_mock_provider(
    class_name: str = "TestProvider", model: str = "test"
) -> Any:  # noqa: ANN401
    """Create a mock provider with proper class name configuration.

    Args:
        class_name: The __class__.__name__ value for the mock
        model: The model attribute value

    Returns:
        Configured MagicMock instance with correct __class__.__name__

    Note:
        Dynamically creates a class with the specified name, then instantiates
        a MagicMock using that class to ensure __class__.__name__ is properly set
        without mutating the MagicMock class itself.
    """
    # Dynamically create a MagicMock subclass with the desired name
    # This ensures each mock has its own class with the correct __name__
    MockProviderClass = type(class_name, (MagicMock,), {})
    mock = MockProviderClass()
    mock.model = model
    return mock


class TestCachingProviderInitialization:
    """Test CachingProvider initialization and configuration."""

    def test_init_with_provider_only(self) -> None:
        """Test initialization with provider only (creates default cache)."""
        mock_provider = create_mock_provider("ClaudeCLIProvider", "claude-sonnet-4-5")

        cached = CachingProvider(mock_provider)

        assert cached.provider == mock_provider
        assert cached.cache is not None
        assert cached.enabled is True
        assert cached.provider_name == "claude-cli"
        assert cached.model_name == "claude-sonnet-4-5"

    def test_init_with_custom_cache(self) -> None:
        """Test initialization with custom PromptCache instance."""
        mock_provider = create_mock_provider("OpenAIAPIProvider", "gpt-4")
        custom_cache = PromptCache()

        cached = CachingProvider(mock_provider, cache=custom_cache)

        assert cached.cache is custom_cache

    def test_init_with_caching_disabled(self) -> None:
        """Test initialization with caching disabled."""
        mock_provider = create_mock_provider("AnthropicAPIProvider")

        cached = CachingProvider(mock_provider, enabled=False)

        assert cached.enabled is False

    def test_init_with_custom_names(self) -> None:
        """Test initialization with custom provider and model names."""
        mock_provider = MagicMock()

        cached = CachingProvider(
            mock_provider,
            provider_name="custom-provider",
            model_name="custom-model",
        )

        assert cached.provider_name == "custom-provider"
        assert cached.model_name == "custom-model"


class TestCachingProviderNameDetection:
    """Test auto-detection of provider and model names."""

    def test_detect_claude_cli_provider(self) -> None:
        """Test detection of Claude CLI provider name."""
        mock_provider = create_mock_provider("ClaudeCLIProvider", "claude-sonnet-4-5")

        cached = CachingProvider(mock_provider)

        assert cached.provider_name == "claude-cli"

    def test_detect_codex_cli_provider(self) -> None:
        """Test detection of Codex CLI provider name."""
        mock_provider = create_mock_provider("CodexCLIProvider")
        mock_provider.model = "codex-latest"

        cached = CachingProvider(mock_provider)

        assert cached.provider_name == "codex-cli"

    def test_detect_openai_provider(self) -> None:
        """Test detection of OpenAI provider name."""
        mock_provider = create_mock_provider("OpenAIAPIProvider", "gpt-4")

        cached = CachingProvider(mock_provider)

        assert cached.provider_name == "openai"

    def test_detect_anthropic_provider(self) -> None:
        """Test detection of Anthropic provider name."""
        mock_provider = create_mock_provider("AnthropicAPIProvider")
        mock_provider.model = "claude-3-opus"

        cached = CachingProvider(mock_provider)

        assert cached.provider_name == "anthropic"

    def test_detect_ollama_provider(self) -> None:
        """Test detection of Ollama provider name."""
        mock_provider = create_mock_provider("OllamaProvider")
        mock_provider.model = "llama3.3:70b"

        cached = CachingProvider(mock_provider)

        assert cached.provider_name == "ollama"

    def test_detect_unknown_provider_uses_class_name(self) -> None:
        """Test that unknown provider falls back to class name."""
        mock_provider = create_mock_provider("CustomLLMProvider")
        mock_provider.model = "custom-model"

        cached = CachingProvider(mock_provider)

        assert cached.provider_name == "customllmprovider"

    def test_detect_model_from_provider_attribute(self) -> None:
        """Test model name detection from provider.model attribute."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test-model-v2"

        cached = CachingProvider(mock_provider)

        assert cached.model_name == "test-model-v2"

    def test_detect_model_fallback_unknown(self) -> None:
        """Test model name fallback when provider has no model attribute."""
        mock_provider = create_mock_provider()
        del mock_provider.model  # Remove model attribute

        cached = CachingProvider(mock_provider)

        assert cached.model_name == "unknown"


class TestCachingProviderGenerate:
    """Test generate() method with caching logic."""

    def test_generate_cache_disabled_calls_provider(self) -> None:
        """Test that disabled cache passes through to provider."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "Response from provider"

        cached = CachingProvider(mock_provider, enabled=False)
        result = cached.generate("Test prompt", max_tokens=100)

        mock_provider.generate.assert_called_once_with("Test prompt", max_tokens=100)
        assert result == "Response from provider"

    def test_generate_cache_miss_calls_provider_and_caches(self) -> None:
        """Test cache miss: calls provider and stores response."""
        mock_provider = create_mock_provider("ClaudeCLIProvider", "claude-sonnet-4-5")
        mock_provider.generate.return_value = "Fresh response"

        mock_cache = MagicMock(spec=PromptCache)
        mock_cache.get.return_value = None  # Cache miss

        cached = CachingProvider(mock_provider, cache=mock_cache)
        result = cached.generate("Test prompt", max_tokens=2000)

        # Should call provider
        mock_provider.generate.assert_called_once_with("Test prompt", max_tokens=2000)

        # Should cache the response
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][1] == "Fresh response"  # response argument
        assert "prompt" in call_args[0][2]  # metadata argument
        assert call_args[0][2]["prompt"] == "Test prompt"

        assert result == "Fresh response"

    def test_generate_cache_hit_skips_provider(self) -> None:
        """Test cache hit: returns cached response without calling provider."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test-model"

        mock_cache = MagicMock(spec=PromptCache)
        mock_cache.get.return_value = "Cached response"  # Cache hit

        cached = CachingProvider(mock_provider, cache=mock_cache)
        result = cached.generate("Test prompt")

        # Should NOT call provider
        mock_provider.generate.assert_not_called()

        # Should NOT cache again
        mock_cache.set.assert_not_called()

        assert result == "Cached response"

    def test_generate_cache_key_includes_provider_and_model(self) -> None:
        """Test that cache key computation includes provider and model."""
        mock_provider = create_mock_provider("ClaudeCLIProvider", "claude-sonnet-4-5")
        mock_provider.generate.return_value = "Response"

        mock_cache = MagicMock(spec=PromptCache)
        mock_cache.get.return_value = None
        mock_cache.compute_key.return_value = "computed_key_123"

        cached = CachingProvider(mock_provider, cache=mock_cache)
        cached.generate("Test prompt")

        # Verify compute_key was called with correct arguments
        mock_cache.compute_key.assert_called_once_with(
            "Test prompt", "claude-cli", "claude-sonnet-4-5"
        )

    def test_generate_with_different_max_tokens(self) -> None:
        """Test generate with custom max_tokens parameter."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.generate.return_value = "Response"

        mock_cache = MagicMock(spec=PromptCache)
        mock_cache.get.return_value = None

        cached = CachingProvider(mock_provider, cache=mock_cache)
        cached.generate("Test", max_tokens=500)

        mock_provider.generate.assert_called_once_with("Test", max_tokens=500)


class TestCachingProviderCountTokens:
    """Test count_tokens() pass-through method."""

    def test_count_tokens_passes_through_to_provider(self) -> None:
        """Test that count_tokens is passed through without caching."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.count_tokens.return_value = 42

        cached = CachingProvider(mock_provider)
        result = cached.count_tokens("Test text")

        mock_provider.count_tokens.assert_called_once_with("Test text")
        assert result == 42

    def test_count_tokens_not_cached(self) -> None:
        """Test that count_tokens does not use cache."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.count_tokens.return_value = 10

        mock_cache = MagicMock(spec=PromptCache)

        cached = CachingProvider(mock_provider, cache=mock_cache)
        cached.count_tokens("Test")

        # Cache should not be accessed at all
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()


class TestCachingProviderUtilities:
    """Test utility methods (stats, clear, invalidate, etc.)."""

    def test_get_cache_stats(self) -> None:
        """Test getting cache statistics."""
        from pr_conflict_resolver.llm.cache.prompt_cache import CacheStats

        mock_provider = create_mock_provider()

        mock_stats = CacheStats(
            hits=10,
            misses=5,
            total_requests=15,
            hit_rate=0.67,
            cache_size_bytes=1024,
            entry_count=10,
        )
        mock_cache = MagicMock(spec=PromptCache)
        mock_cache.get_stats.return_value = mock_stats

        cached = CachingProvider(mock_provider, cache=mock_cache)
        stats = cached.get_cache_stats()

        assert stats == mock_stats
        assert stats.hits == 10
        assert stats.misses == 5

    def test_clear_cache(self) -> None:
        """Test clearing cache."""
        mock_provider = create_mock_provider()

        mock_cache = MagicMock(spec=PromptCache)

        cached = CachingProvider(mock_provider, cache=mock_cache)
        cached.clear_cache()

        mock_cache.clear.assert_called_once()

    def test_invalidate_prompt_existing_entry(self, tmp_path: Path) -> None:
        """Test invalidating specific prompt (entry exists)."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"

        # Use real cache with temp directory
        cache = PromptCache(cache_dir=tmp_path)

        # Add an entry to cache
        key = cache.compute_key("Test prompt", "test", "test")
        cache.set(key, "Response", {"prompt": "Test prompt", "provider": "test", "model": "test"})

        cached = CachingProvider(
            mock_provider, cache=cache, provider_name="test", model_name="test"
        )

        # Invalidate the entry
        result = cached.invalidate_prompt("Test prompt")

        assert result == DeleteStatus.DELETED
        assert cache.get(key) is None  # Entry should be gone

    def test_invalidate_prompt_nonexistent_entry(self, tmp_path: Path) -> None:
        """Test invalidating prompt that doesn't exist in cache."""
        mock_provider = create_mock_provider()

        cache = PromptCache(cache_dir=tmp_path)
        cached = CachingProvider(mock_provider, cache=cache)

        result = cached.invalidate_prompt("Nonexistent prompt")

        assert result == DeleteStatus.NOT_FOUND

    def test_set_cache_enabled(self) -> None:
        """Test enabling/disabling cache at runtime."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test"
        mock_provider.generate.return_value = "Response"

        cached = CachingProvider(mock_provider, enabled=True)

        # Disable cache
        cached.set_cache_enabled(False)
        assert cached.enabled is False

        # Re-enable cache
        cached.set_cache_enabled(True)
        assert cached.enabled is True

    def test_repr(self) -> None:
        """Test string representation."""
        mock_provider = create_mock_provider("ClaudeCLIProvider", "claude-sonnet-4-5")

        cached = CachingProvider(mock_provider)
        repr_str = repr(cached)

        assert "CachingProvider" in repr_str
        assert "claude-cli" in repr_str
        assert "claude-sonnet-4-5" in repr_str
        assert "enabled=True" in repr_str


class TestCachingProviderIntegration:
    """Integration tests with real PromptCache."""

    def test_full_cache_workflow(self, tmp_path: Path) -> None:
        """Test complete cache workflow: miss, cache, hit."""
        mock_provider = create_mock_provider()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "Generated response"

        cache = PromptCache(cache_dir=tmp_path)
        cached = CachingProvider(
            mock_provider,
            cache=cache,
            provider_name="test",
            model_name="test-model",
        )

        # First call: cache miss
        result1 = cached.generate("Hello world")
        assert result1 == "Generated response"
        assert mock_provider.generate.call_count == 1

        # Second call: cache hit
        result2 = cached.generate("Hello world")
        assert result2 == "Generated response"
        assert mock_provider.generate.call_count == 1  # Should not increase

        # Different prompt: cache miss
        result3 = cached.generate("Different prompt")
        assert result3 == "Generated response"
        assert mock_provider.generate.call_count == 2

    def test_cache_shared_across_providers(self, tmp_path: Path) -> None:
        """Test that shared cache works across multiple provider instances."""
        mock_provider1 = create_mock_provider("Provider1", "model-a")
        mock_provider1.generate.return_value = "Response from provider 1"

        mock_provider2 = create_mock_provider("Provider2", "model-b")
        mock_provider2.generate.return_value = "Response from provider 2"

        # Shared cache
        shared_cache = PromptCache(cache_dir=tmp_path)

        cached1 = CachingProvider(
            mock_provider1,
            cache=shared_cache,
            provider_name="provider1",
            model_name="model-a",
        )
        cached2 = CachingProvider(
            mock_provider2,
            cache=shared_cache,
            provider_name="provider2",
            model_name="model-b",
        )

        # Each provider should cache independently
        cached1.generate("Prompt A")
        cached2.generate("Prompt B")

        assert mock_provider1.generate.call_count == 1
        assert mock_provider2.generate.call_count == 1

        # Cache hits for same prompts
        cached1.generate("Prompt A")
        cached2.generate("Prompt B")

        assert mock_provider1.generate.call_count == 1  # No increase
        assert mock_provider2.generate.call_count == 1  # No increase

    def test_cache_isolation_by_provider_and_model(self, tmp_path: Path) -> None:
        """Test that cache isolates by provider and model."""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "Response"

        cache = PromptCache(cache_dir=tmp_path)

        # Same provider, different models
        cached_model_a = CachingProvider(
            mock_provider,
            cache=cache,
            provider_name="test",
            model_name="model-a",
        )
        cached_model_b = CachingProvider(
            mock_provider,
            cache=cache,
            provider_name="test",
            model_name="model-b",
        )

        # Same prompt to different models
        cached_model_a.generate("Same prompt")
        cached_model_b.generate("Same prompt")

        # Should call provider twice (different cache keys)
        assert mock_provider.generate.call_count == 2
