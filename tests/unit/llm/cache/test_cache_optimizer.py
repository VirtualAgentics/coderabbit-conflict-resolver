"""Tests for cache optimizer and warming utilities.

This module tests cache optimization, warming, batch preloading, and analysis.
"""

import logging
import os
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pr_conflict_resolver.llm.cache.cache_optimizer import (
    CacheAnalysis,
    CacheOptimizer,
    WarmingProgress,
)
from pr_conflict_resolver.llm.cache.prompt_cache import PromptCache
from pr_conflict_resolver.llm.exceptions import LLMProviderError


class TestCacheOptimizerInitialization:
    """Test CacheOptimizer initialization."""

    def test_init_with_cache(self, tmp_path: Path) -> None:
        """Test initialization with PromptCache."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        assert optimizer.cache is cache


class TestCacheOptimizerWarmCache:
    """Test warm_cache() sequential preloading."""

    def test_warm_cache_basic(self, tmp_path: Path) -> None:
        """Test basic cache warming with multiple prompts."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            "Response 1",
            "Response 2",
            "Response 3",
        ]

        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        cached_count = optimizer.warm_cache(
            mock_provider,
            prompts,
            provider_name="test",
            model_name="test-model",
        )

        assert cached_count == 3
        assert mock_provider.generate.call_count == 3

        # Verify all prompts are cached
        for prompt in prompts:
            key = cache.compute_key(prompt, "test", "test-model")
            assert cache.get(key) is not None

    def test_warm_cache_skips_existing_entries(self, tmp_path: Path) -> None:
        """Test that warm_cache skips already-cached prompts."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        # Pre-cache one prompt
        key = cache.compute_key("Prompt 1", "test", "test-model")
        cache.set(
            key,
            "Existing response",
            {"prompt": "Prompt 1", "provider": "test", "model": "test-model"},
        )

        mock_provider = MagicMock()
        mock_provider.generate.return_value = "New response"

        prompts = ["Prompt 1", "Prompt 2"]
        cached_count = optimizer.warm_cache(
            mock_provider,
            prompts,
            "test",
            "test-model",
        )

        # Should only call provider for Prompt 2
        assert mock_provider.generate.call_count == 1
        assert cached_count == 2  # Both are cached (1 pre-existing, 1 new)

    def test_warm_cache_handles_provider_errors(self, tmp_path: Path) -> None:
        """Test warm_cache handles provider errors gracefully."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        mock_provider = MagicMock()
        mock_provider.generate.side_effect = [
            "Response 1",
            LLMProviderError("Provider error"),
            "Response 3",
        ]

        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]
        cached_count = optimizer.warm_cache(
            mock_provider,
            prompts,
            "test",
            "test-model",
        )

        # Should cache 2 out of 3
        assert cached_count == 2
        assert mock_provider.generate.call_count == 3

    def test_warm_cache_with_custom_max_tokens(self, tmp_path: Path) -> None:
        """Test warm_cache with custom max_tokens."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        mock_provider = MagicMock()
        mock_provider.generate.return_value = "Response"

        optimizer.warm_cache(
            mock_provider,
            ["Test prompt"],
            "test",
            "test-model",
            max_tokens=500,
        )

        mock_provider.generate.assert_called_once_with("Test prompt", max_tokens=500)

    def test_warm_cache_fail_fast_on_critical_exception(self, tmp_path: Path) -> None:
        """Test warm_cache with fail_fast stops immediately on critical exceptions."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        mock_provider = MagicMock()
        # First call succeeds, second raises critical error
        mock_provider.generate.side_effect = [
            "Response 1",
            RuntimeError("Provider failed"),
        ]

        prompts = ["Prompt 1", "Prompt 2", "Prompt 3"]

        # Should propagate critical exception immediately with fail_fast=True
        with pytest.raises(RuntimeError):
            optimizer.warm_cache(
                mock_provider,
                prompts,
                "test",
                "test-model",
                fail_fast=True,
            )

        # Should have cached first prompt before critical error
        key1 = cache.compute_key("Prompt 1", "test", "test-model")
        assert cache.get(key1) is not None

        # Should not have processed third prompt
        key3 = cache.compute_key("Prompt 3", "test", "test-model")
        assert cache.get(key3) is None


class TestCacheOptimizerBatchPreload:
    """Test batch_preload() parallel preloading."""

    def test_batch_preload_basic(self, tmp_path: Path) -> None:
        """Test basic batch preloading with parallel workers."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        mock_provider = MagicMock()
        mock_provider.generate.return_value = "Response"

        prompts = [f"Prompt {i}" for i in range(10)]
        cached_count = optimizer.batch_preload(
            mock_provider,
            prompts,
            "test",
            "test-model",
            max_workers=4,
        )

        assert cached_count == 10
        assert mock_provider.generate.call_count == 10

        # Verify all cached
        for prompt in prompts:
            key = cache.compute_key(prompt, "test", "test-model")
            assert cache.get(key) is not None

    def test_batch_preload_skips_cached_prompts(self, tmp_path: Path) -> None:
        """Test batch_preload skips already-cached prompts."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        # Pre-cache half the prompts
        for i in range(5):
            prompt = f"Prompt {i}"
            key = cache.compute_key(prompt, "test", "test-model")
            cache.set(
                key,
                f"Cached response {i}",
                {"prompt": prompt, "provider": "test", "model": "test-model"},
            )

        mock_provider = MagicMock()
        mock_provider.generate.return_value = "New response"

        prompts = [f"Prompt {i}" for i in range(10)]
        cached_count = optimizer.batch_preload(
            mock_provider,
            prompts,
            "test",
            "test-model",
            max_workers=2,
        )

        # Should cache all 10 (5 pre-existing, 5 new)
        assert cached_count == 10
        # Should only generate for uncached prompts
        assert mock_provider.generate.call_count == 5

    def test_batch_preload_progress_callback(self, tmp_path: Path) -> None:
        """Test batch_preload calls progress callback."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        mock_provider = MagicMock()
        mock_provider.generate.return_value = "Response"

        progress_updates: list[WarmingProgress] = []

        def progress_callback(progress: WarmingProgress) -> None:
            progress_updates.append(progress)

        prompts = [f"Prompt {i}" for i in range(5)]
        optimizer.batch_preload(
            mock_provider,
            prompts,
            "test",
            "test-model",
            max_workers=2,
            progress_callback=progress_callback,
        )

        # Should receive progress updates
        assert len(progress_updates) == 5
        # Final update should show all completed
        assert progress_updates[-1].completed == 5
        assert progress_updates[-1].total == 5

    def test_batch_preload_handles_errors(self, tmp_path: Path) -> None:
        """Test batch_preload handles provider errors."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        call_count = 0

        def generate_with_errors(prompt: str, max_tokens: int = 2000) -> str:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("Provider error")
            return "Response"

        mock_provider = MagicMock()
        mock_provider.generate.side_effect = generate_with_errors

        prompts = [f"Prompt {i}" for i in range(6)]
        cached_count = optimizer.batch_preload(
            mock_provider,
            prompts,
            "test",
            "test-model",
            max_workers=2,
        )

        # Should cache 3 out of 6
        assert cached_count == 3

    def test_batch_preload_all_cached_returns_early(self, tmp_path: Path) -> None:
        """Test batch_preload returns early if all prompts cached."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        # Pre-cache all prompts
        prompts = [f"Prompt {i}" for i in range(5)]
        for prompt in prompts:
            key = cache.compute_key(prompt, "test", "test-model")
            cache.set(
                key,
                "Cached",
                {"prompt": prompt, "provider": "test", "model": "test-model"},
            )

        mock_provider = MagicMock()

        cached_count = optimizer.batch_preload(
            mock_provider,
            prompts,
            "test",
            "test-model",
        )

        assert cached_count == 5
        # Should not call provider at all
        mock_provider.generate.assert_not_called()

    def test_batch_preload_max_workers_validation(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test batch_preload validates and clamps max_workers parameter."""
        caplog.set_level(logging.WARNING)
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "Response"

        # Test max_workers=0 gets clamped to 1 with warning
        caplog.clear()
        cached = optimizer.batch_preload(
            mock_provider,
            ["Prompt 1"],
            "test",
            "test-model",
            max_workers=0,
        )
        assert cached == 1
        assert any(
            "max_workers must be >= 1, clamping from 0 to 1" in record.message
            for record in caplog.records
        )

        # Test max_workers=-1 gets clamped to 1 with warning
        caplog.clear()
        cached = optimizer.batch_preload(
            mock_provider,
            ["Prompt 2"],
            "test",
            "test-model",
            max_workers=-1,
        )
        assert cached == 1
        assert any(
            "max_workers must be >= 1, clamping from -1 to 1" in record.message
            for record in caplog.records
        )

        # Test max_workers=1 is valid and doesn't warn
        caplog.clear()
        cached = optimizer.batch_preload(
            mock_provider,
            ["Prompt 3"],
            "test",
            "test-model",
            max_workers=1,
        )
        assert cached == 1
        assert not any("max_workers" in record.message for record in caplog.records)


class TestCacheOptimizerAnalyzeCache:
    """Test analyze_cache() health check."""

    def test_analyze_cache_empty(self, tmp_path: Path) -> None:
        """Test analysis of empty cache."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        analysis = optimizer.analyze_cache()

        assert analysis.total_entries == 0
        assert analysis.total_size_bytes == 0
        assert analysis.hit_rate == 0.0
        assert analysis.stale_entries == 0
        assert analysis.fragmentation_ratio == 0.0
        assert len(analysis.recommendations) > 0

    def test_analyze_cache_healthy(self, tmp_path: Path) -> None:
        """Test analysis of healthy cache."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        # Add some entries
        for i in range(5):
            key = cache.compute_key(f"Prompt {i}", "test", "model")
            cache.set(
                key,
                f"Response {i}",
                {"prompt": f"Prompt {i}", "provider": "test", "model": "model"},
            )

        # Simulate some cache hits
        for i in range(5):
            key = cache.compute_key(f"Prompt {i}", "test", "model")
            _ = cache.get(key)

        analysis = optimizer.analyze_cache()

        assert analysis.total_entries == 5
        assert analysis.total_size_bytes > 0
        assert analysis.hit_rate > 0.0
        assert "healthy" in analysis.recommendations[0].lower()

    def test_analyze_cache_low_hit_rate_recommendation(self, tmp_path: Path) -> None:
        """Test recommendation for low hit rate."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        # Add entry
        key = cache.compute_key("Prompt", "test", "model")
        cache.set(
            key,
            "Response",
            {"prompt": "Prompt", "provider": "test", "model": "model"},
        )

        # Simulate many misses
        for i in range(20):
            _ = cache.get(f"nonexistent_key_{i}")

        analysis = optimizer.analyze_cache()

        # Should recommend warming cache
        assert any("low hit rate" in rec.lower() for rec in analysis.recommendations)

    @pytest.mark.slow  # Requires 1.5s sleep to test TTL expiration behavior
    def test_analyze_cache_detects_stale_entries(self, tmp_path: Path) -> None:
        """Test that analyze_cache detects and counts stale cache entries."""
        # Create cache with short TTL
        cache = PromptCache(cache_dir=tmp_path, ttl_seconds=1)
        optimizer = CacheOptimizer(cache)

        # Add entries
        for i in range(3):
            key = cache.compute_key(f"Prompt {i}", "test", "model")
            cache.set(
                key,
                f"Response {i}",
                {"prompt": f"Prompt {i}", "provider": "test", "model": "model"},
            )

        # Immediately analyze - no stale entries
        analysis_fresh = optimizer.analyze_cache()
        assert analysis_fresh.stale_entries == 0
        assert analysis_fresh.total_entries == 3

        # Wait for TTL to expire
        time.sleep(1.5)

        # Analyze again - all entries should be stale
        analysis_stale = optimizer.analyze_cache()
        assert analysis_stale.stale_entries == 3
        assert analysis_stale.total_entries == 3
        # Should recommend cleanup
        assert any("stale" in rec.lower() for rec in analysis_stale.recommendations)

    def test_analyze_cache_high_fragmentation_recommendation(self, tmp_path: Path) -> None:
        """Test recommendation for high fragmentation."""
        # Small cache size to trigger fragmentation
        cache = PromptCache(cache_dir=tmp_path, max_size_bytes=1000)
        optimizer = CacheOptimizer(cache)

        # Fill cache close to max
        for i in range(10):
            key = cache.compute_key(f"Prompt {i}" * 10, "test", "model")
            cache.set(
                key,
                f"Response {i}" * 20,  # Larger responses
                {"prompt": f"Prompt {i}" * 10, "provider": "test", "model": "model"},
            )

        analysis = optimizer.analyze_cache()

        # Should warn about fragmentation when ratio > 0.7 (cache is significantly full)
        assert analysis.fragmentation_ratio is not None
        assert analysis.fragmentation_ratio > 0.7
        # Verify there's at least one recommendation (exact text depends on threshold logic)
        assert len(analysis.recommendations) > 0


class TestCacheOptimizerEvictStaleEntries:
    """Test evict_stale_entries() cleanup."""

    def test_evict_stale_entries_basic(self, tmp_path: Path) -> None:
        """Test evicting stale entries based on age threshold."""
        cache = PromptCache(cache_dir=tmp_path, ttl_seconds=100)
        optimizer = CacheOptimizer(cache)

        # Add entries
        for i in range(5):
            key = cache.compute_key(f"Prompt {i}", "test", "model")
            cache.set(
                key,
                f"Response {i}",
                {"prompt": f"Prompt {i}", "provider": "test", "model": "model"},
            )

        # Make some files "old" by modifying their mtime
        cache_files = list(cache.cache_dir.glob("*.json"))
        old_time = time.time() - 85  # 85 seconds ago (85% of 100s TTL)

        for cache_file in cache_files[:3]:
            # Make first 3 files old
            Path(cache_file).touch()
            os.utime(cache_file, (old_time, old_time))

        # Evict entries older than 80% of TTL
        evicted = optimizer.evict_stale_entries(age_threshold_ratio=0.8)

        # Should evict the 3 old entries
        assert evicted == 3

        # Verify only 2 entries remain
        stats = cache.get_stats()
        assert stats.entry_count == 2

    def test_evict_stale_entries_validation(self, tmp_path: Path) -> None:
        """Test age_threshold_ratio validation."""
        cache = PromptCache(cache_dir=tmp_path)
        optimizer = CacheOptimizer(cache)

        with pytest.raises(ValueError, match="must be in \\(0, 1\\]"):
            optimizer.evict_stale_entries(age_threshold_ratio=1.5)

        with pytest.raises(ValueError, match="must be in \\(0, 1\\]"):
            optimizer.evict_stale_entries(age_threshold_ratio=0.0)

    def test_evict_stale_entries_no_stale(self, tmp_path: Path) -> None:
        """Test evicting when no entries are stale."""
        cache = PromptCache(cache_dir=tmp_path, ttl_seconds=1000)
        optimizer = CacheOptimizer(cache)

        # Add fresh entries
        for i in range(3):
            key = cache.compute_key(f"Prompt {i}", "test", "model")
            cache.set(
                key,
                f"Response {i}",
                {"prompt": f"Prompt {i}", "provider": "test", "model": "model"},
            )

        # Try to evict stale (threshold = 80% of 1000s = 800s)
        evicted = optimizer.evict_stale_entries(age_threshold_ratio=0.8)

        assert evicted == 0
        # All entries should remain
        stats = cache.get_stats()
        assert stats.entry_count == 3


class TestWarmingProgress:
    """Test WarmingProgress dataclass."""

    def test_warming_progress_creation(self) -> None:
        """Test WarmingProgress dataclass creation."""
        progress = WarmingProgress(
            total=100,
            completed=50,
            failed=5,
            in_progress=10,
            elapsed_seconds=30.5,
        )

        assert progress.total == 100
        assert progress.completed == 50
        assert progress.failed == 5
        assert progress.in_progress == 10
        assert progress.elapsed_seconds == 30.5

    def test_warming_progress_defaults(self) -> None:
        """Test WarmingProgress default values."""
        progress = WarmingProgress(total=100)

        assert progress.total == 100
        assert progress.completed == 0
        assert progress.failed == 0
        assert progress.in_progress == 0
        assert progress.elapsed_seconds == 0.0


class TestCacheAnalysis:
    """Test CacheAnalysis dataclass."""

    def test_cache_analysis_creation(self) -> None:
        """Test CacheAnalysis dataclass creation."""
        analysis = CacheAnalysis(
            total_entries=50,
            total_size_bytes=1024000,
            hit_rate=0.75,
            stale_entries=10,
            fragmentation_ratio=0.5,
            recommendations=["Recommendation 1", "Recommendation 2"],
        )

        assert analysis.total_entries == 50
        assert analysis.total_size_bytes == 1024000
        assert analysis.hit_rate == 0.75
        assert analysis.stale_entries == 10
        assert analysis.fragmentation_ratio == 0.5
        assert len(analysis.recommendations) == 2
