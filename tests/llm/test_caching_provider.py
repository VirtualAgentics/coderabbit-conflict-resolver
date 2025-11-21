"""Tests for CachingProvider wrapper.

This module tests the transparent caching functionality for LLM providers,
including cache hit/miss behavior, statistics tracking, and method delegation.

Phase 5 - Issue #221: Cache Integration with LLM Providers
"""

import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from pr_conflict_resolver.llm.cache.prompt_cache import PromptCache
from pr_conflict_resolver.llm.providers.caching_provider import CachingProvider


class TestCachingProviderCacheHit:
    """Tests for cache hit scenarios."""

    def test_cache_hit_returns_cached_response(self) -> None:
        """Test that cache hit returns the cached response without calling provider."""
        # Arrange
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = '{"changes": []}'

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            # First call - cache miss, should call provider
            response1 = cached.generate("test prompt")
            assert mock_provider.generate.call_count == 1
            assert response1 == '{"changes": []}'

            # Second call - cache hit, should NOT call provider
            response2 = cached.generate("test prompt")
            assert mock_provider.generate.call_count == 1  # Still 1, not 2
            assert response2 == '{"changes": []}'

    def test_cache_hit_does_not_call_provider(self) -> None:
        """Test provider.generate() is not called on cache hit."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "response"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            # Populate cache
            cached.generate("my prompt")

            # Reset mock to track only subsequent calls
            mock_provider.generate.reset_mock()

            # This should be a cache hit
            cached.generate("my prompt")

            mock_provider.generate.assert_not_called()

    def test_cache_hit_increments_hit_counter(self) -> None:
        """Test that cache hits are tracked in statistics."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "response"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            # First call - miss
            cached.generate("test")
            stats = cached.get_cache_stats()
            assert stats.misses == 1
            assert stats.hits == 0

            # Second call - hit
            cached.generate("test")
            stats = cached.get_cache_stats()
            assert stats.misses == 1
            assert stats.hits == 1
            assert stats.hit_rate == pytest.approx(0.5)


class TestCachingProviderCacheMiss:
    """Tests for cache miss scenarios."""

    def test_cache_miss_calls_provider(self) -> None:
        """Test that cache miss calls the wrapped provider."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "generated response"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            result = cached.generate("new prompt", max_tokens=1000)

            mock_provider.generate.assert_called_once_with("new prompt", 1000)
            assert result == "generated response"

    def test_cache_miss_stores_response(self) -> None:
        """Test that cache miss stores the response for future hits."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "stored response"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            # Generate response (miss)
            cached.generate("store this")

            # Verify it's in cache
            key = cache.compute_key("store this", cached.provider_name, "test-model")
            cached_value = cache.get(key)
            assert cached_value == "stored response"

    def test_cache_miss_increments_miss_counter(self) -> None:
        """Test that cache misses are tracked in statistics."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "response"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            # Three different prompts - all misses
            cached.generate("prompt 1")
            cached.generate("prompt 2")
            cached.generate("prompt 3")

            stats = cached.get_cache_stats()
            assert stats.misses == 3
            assert stats.hits == 0


class TestCachingProviderCacheKey:
    """Tests for cache key generation."""

    def test_same_prompt_same_key(self) -> None:
        """Test identical prompts generate identical cache keys."""
        mock_provider = Mock()
        mock_provider.model = "model-a"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            key1 = cache.compute_key("test", cached.provider_name, "model-a")
            key2 = cache.compute_key("test", cached.provider_name, "model-a")

            assert key1 == key2
            assert len(key1) == 64  # SHA256 hex

    def test_different_prompt_different_key(self) -> None:
        """Test different prompts generate different cache keys."""
        mock_provider = Mock()
        mock_provider.model = "model-a"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            key1 = cache.compute_key("prompt A", cached.provider_name, "model-a")
            key2 = cache.compute_key("prompt B", cached.provider_name, "model-a")

            assert key1 != key2

    def test_different_provider_different_key(self) -> None:
        """Test same prompt with different providers generates different keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key1 = cache.compute_key("test", "anthropic", "model")
            key2 = cache.compute_key("test", "openai", "model")

            assert key1 != key2

    def test_different_model_different_key(self) -> None:
        """Test same prompt with different models generates different keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key1 = cache.compute_key("test", "anthropic", "claude-sonnet-4")
            key2 = cache.compute_key("test", "anthropic", "claude-haiku-4")

            assert key1 != key2


class TestCachingProviderProxyMethods:
    """Tests for delegated methods."""

    def test_count_tokens_delegates(self) -> None:
        """Test count_tokens() delegates to wrapped provider."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.count_tokens.return_value = 42

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            result = cached.count_tokens("hello world")

            mock_provider.count_tokens.assert_called_once_with("hello world")
            assert result == 42

    def test_get_total_cost_delegates(self) -> None:
        """Test get_total_cost() delegates to wrapped provider."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.get_total_cost.return_value = 0.0025

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            result = cached.get_total_cost()

            mock_provider.get_total_cost.assert_called_once()
            assert result == 0.0025

    def test_get_total_cost_handles_missing_method(self) -> None:
        """Test get_total_cost() returns 0.0 if provider doesn't have method."""
        mock_provider = Mock(spec=[])  # No methods
        mock_provider.model = "test-model"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            result = cached.get_total_cost()
            assert result == 0.0

    def test_reset_usage_tracking_delegates(self) -> None:
        """Test reset_usage_tracking() delegates to wrapped provider."""
        mock_provider = Mock()
        mock_provider.model = "test-model"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            cached.reset_usage_tracking()

            mock_provider.reset_usage_tracking.assert_called_once()

    def test_reset_usage_tracking_handles_missing_method(self) -> None:
        """Test reset_usage_tracking() is no-op if provider doesn't have method."""
        mock_provider = Mock(spec=[])  # No methods
        mock_provider.model = "test-model"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            # Should not raise
            cached.reset_usage_tracking()


class TestCachingProviderStatistics:
    """Tests for cache statistics."""

    def test_get_cache_stats_returns_stats(self) -> None:
        """Test get_cache_stats() returns CacheStats object."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "response"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            # Generate some activity
            cached.generate("prompt 1")
            cached.generate("prompt 1")  # hit
            cached.generate("prompt 2")

            stats = cached.get_cache_stats()

            assert stats.hits == 1
            assert stats.misses == 2
            assert stats.total_requests == 3
            assert stats.entry_count == 2

    def test_clear_cache_resets_entries(self) -> None:
        """Test clear_cache() removes all entries."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "response"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            # Add some entries
            cached.generate("prompt 1")
            cached.generate("prompt 2")

            stats = cached.get_cache_stats()
            assert stats.entry_count == 2

            # Clear cache
            cached.clear_cache()

            stats = cached.get_cache_stats()
            assert stats.entry_count == 0


class TestCachingProviderThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_access_no_corruption(self) -> None:
        """Test concurrent cache access doesn't cause corruption."""
        mock_provider = Mock()
        mock_provider.model = "test-model"

        # Make generate() return different values based on input
        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            return f"response for {prompt}"

        mock_provider.generate.side_effect = mock_generate

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            # Track results with their prompts for consistency verification
            results_by_prompt: dict[str, list[str]] = {f"prompt-{i}": [] for i in range(5)}
            results_lock = threading.Lock()
            errors: list[Exception] = []

            def worker(prompt: str) -> None:
                try:
                    for _ in range(10):
                        result = cached.generate(prompt)
                        with results_lock:
                            results_by_prompt[prompt].append(result)
                except Exception as e:
                    errors.append(e)

            # Launch multiple threads with different prompts
            threads = []
            for i in range(5):
                t = threading.Thread(target=worker, args=(f"prompt-{i}",))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # No errors should have occurred
            assert len(errors) == 0

            # Verify total result count
            total_results = sum(len(r) for r in results_by_prompt.values())
            assert total_results == 50  # 5 threads * 10 iterations

            # Verify each prompt produced exactly 10 responses
            for prompt, responses in results_by_prompt.items():
                assert (
                    len(responses) == 10
                ), f"Expected 10 responses for {prompt}, got {len(responses)}"

            # Verify all responses for each prompt are identical (cache consistency)
            for prompt, responses in results_by_prompt.items():
                expected_response = f"response for {prompt}"
                assert all(
                    r == expected_response for r in responses
                ), f"Inconsistent responses for {prompt}: {set(responses)}"


class TestCachingProviderProviderName:
    """Tests for provider name extraction."""

    def test_provider_name_extraction_anthropic(self) -> None:
        """Test provider name is extracted correctly for Anthropic."""
        mock_provider = MagicMock()
        mock_provider.__class__.__name__ = "AnthropicAPIProvider"
        mock_provider.model = "claude-sonnet-4"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            assert cached.provider_name == "anthropic"

    def test_provider_name_extraction_openai(self) -> None:
        """Test provider name is extracted correctly for OpenAI."""
        mock_provider = MagicMock()
        mock_provider.__class__.__name__ = "OpenAIAPIProvider"
        mock_provider.model = "gpt-4"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            assert cached.provider_name == "openai"

    def test_provider_name_extraction_ollama(self) -> None:
        """Test provider name is extracted correctly for Ollama."""
        mock_provider = MagicMock()
        mock_provider.__class__.__name__ = "OllamaProvider"
        mock_provider.model = "llama3"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)

            assert cached.provider_name == "ollama"


class TestCachingProviderModelValidation:
    """Tests for model attribute validation."""

    def test_missing_model_attribute_raises(self) -> None:
        """Test that missing model attribute raises AttributeError."""
        mock_provider = Mock(spec=[])  # No attributes

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            with pytest.raises(AttributeError, match="must have a 'model' attribute"):
                CachingProvider(mock_provider, cache)

    def test_none_model_raises(self) -> None:
        """Test that None model raises AttributeError."""
        mock_provider = Mock()
        mock_provider.model = None

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            with pytest.raises(AttributeError, match="invalid 'model' attribute"):
                CachingProvider(mock_provider, cache)

    def test_empty_string_model_raises(self) -> None:
        """Test that empty string model raises AttributeError."""
        mock_provider = Mock()
        mock_provider.model = ""

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            with pytest.raises(AttributeError, match="invalid 'model' attribute"):
                CachingProvider(mock_provider, cache)

    def test_whitespace_only_model_raises(self) -> None:
        """Test that whitespace-only model raises AttributeError."""
        mock_provider = Mock()
        mock_provider.model = "   "

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            with pytest.raises(AttributeError, match="invalid 'model' attribute"):
                CachingProvider(mock_provider, cache)

    def test_non_string_model_raises(self) -> None:
        """Test that non-string model raises AttributeError."""
        mock_provider = Mock()
        mock_provider.model = 123  # Not a string

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            with pytest.raises(AttributeError, match="invalid 'model' attribute"):
                CachingProvider(mock_provider, cache)

    def test_valid_model_succeeds(self) -> None:
        """Test that valid model string is accepted."""
        mock_provider = Mock()
        mock_provider.model = "claude-sonnet-4"

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))
            cached = CachingProvider(mock_provider, cache)
            assert cached.model == "claude-sonnet-4"


class TestCachingProviderEviction:
    """Tests for cache eviction."""

    def test_evict_expired_removes_old_entries(self) -> None:
        """Test evict_expired() removes entries past TTL."""
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_provider.generate.return_value = "response"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Very short TTL for testing
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=1)
            cached = CachingProvider(mock_provider, cache)

            # Add entry
            cached.generate("test")
            assert cached.get_cache_stats().entry_count == 1

            # Wait for expiration
            import time

            time.sleep(1.1)

            # Evict expired
            evicted = cached.evict_expired()
            assert evicted == 1
            assert cached.get_cache_stats().entry_count == 0
