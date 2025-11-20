"""Cache optimization utilities for preloading and warming LLM response cache.

This module provides utilities for optimizing cache performance through:
- Cache warming: Preloading common prompts before heavy usage
- Batch preloading: Loading multiple prompts in parallel
- Cache analysis: Identifying frequently used prompts
- Cache optimization: Removing stale entries, consolidating similar prompts

Usage Examples:
    Warm cache with common prompts:
        >>> optimizer = CacheOptimizer(cache)
        >>> common_prompts = ["Fix bug in code", "Explain error"]
        >>> optimizer.warm_cache(provider, common_prompts)

    Analyze cache for optimization opportunities:
        >>> analysis = optimizer.analyze_cache()
        >>> print(f"Hit rate: {analysis.hit_rate}")
        >>> print(f"Stale entries: {analysis.stale_entries}")

    Batch preload prompts in parallel:
        >>> prompts = ["prompt1", "prompt2", "prompt3"]
        >>> optimizer.batch_preload(provider, prompts, max_workers=4)
"""

import logging
import time
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from pr_conflict_resolver.llm.cache.prompt_cache import PromptCache
from pr_conflict_resolver.llm.constants import MAX_WORKERS
from pr_conflict_resolver.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from pr_conflict_resolver.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheAnalysis:
    """Cache analysis results for optimization recommendations.

    Attributes:
        total_entries: Total number of cache entries
        total_size_bytes: Total cache size in bytes
        hit_rate: Cache hit rate (0.0 to 1.0)
        stale_entries: Number of entries older than 80% of TTL
        fragmentation_ratio: Ratio of cache size to max size (0.0 to 1.0), or None if not calculable
        recommendations: List of optimization recommendations

    Examples:
        >>> analysis = optimizer.analyze_cache()
        >>> if analysis.fragmentation_ratio is not None and analysis.fragmentation_ratio > 0.9:
        ...     print("Cache nearly full, consider increasing size or evicting")
        >>> for rec in analysis.recommendations:
        ...     print(f"- {rec}")
    """

    total_entries: int
    total_size_bytes: int
    hit_rate: float
    stale_entries: int
    fragmentation_ratio: float | None
    recommendations: list[str]


@dataclass(frozen=True)
class WarmingProgress:
    """Progress tracking for cache warming operations.

    Attributes:
        total: Total number of prompts to warm
        completed: Number of prompts successfully cached
        failed: Number of prompts that failed
        in_progress: Number of prompts currently being processed
        elapsed_seconds: Time elapsed since warming started

    Examples:
        >>> def progress_callback(progress: WarmingProgress) -> None:
        ...     pct = (progress.completed / progress.total) * 100
        ...     print(f"Warming cache: {pct:.1f}% complete")
    """

    total: int
    completed: int = 0
    failed: int = 0
    in_progress: int = 0
    elapsed_seconds: float = 0.0


class CacheOptimizer:
    """Optimizer for LLM response cache with warming and analysis.

    Provides utilities for preloading common prompts, analyzing cache health,
    and optimizing cache performance. Supports parallel cache warming for faster
    preloading of multiple prompts.

    Attributes:
        cache: The PromptCache instance to optimize

    Examples:
        Basic cache warming:
            >>> optimizer = CacheOptimizer(cache)
            >>> provider = create_provider("claude-cli")
            >>> prompts = ["Fix this bug", "Explain this code"]
            >>> optimizer.warm_cache(provider, prompts)

        Parallel batch preloading:
            >>> prompts = load_common_prompts()  # 100 prompts
            >>> optimizer.batch_preload(
            ...     provider,
            ...     prompts,
            ...     max_workers=8,
            ...     progress_callback=lambda p: print(f"{p.completed}/{p.total}")
            ... )

        Cache analysis and optimization:
            >>> analysis = optimizer.analyze_cache()
            >>> if analysis.stale_entries > 10:
            ...     optimizer.evict_stale_entries()
    """

    def __init__(self, cache: PromptCache) -> None:
        """Initialize cache optimizer.

        Args:
            cache: PromptCache instance to optimize

        Examples:
            >>> from pr_conflict_resolver.llm.cache.prompt_cache import PromptCache
            >>> cache = PromptCache()
            >>> optimizer = CacheOptimizer(cache)
        """
        self.cache = cache

    def warm_cache(
        self,
        provider: LLMProvider,
        prompts: list[str],
        provider_name: str,
        model_name: str,
        max_tokens: int = 2000,
        fail_fast: bool = False,
    ) -> int:
        """Warm cache by preloading common prompts sequentially.

        Generates responses for all prompts and caches them. Useful for preloading
        cache before heavy usage periods. For parallel warming, use batch_preload().

        Args:
            provider: LLM provider to generate responses
            prompts: List of prompts to preload
            provider_name: Provider name for cache keys (e.g., "claude-cli")
            model_name: Model name for cache keys (e.g., "claude-sonnet-4-5")
            max_tokens: Maximum tokens per request (default: 2000)
            fail_fast: If True, re-raise unexpected exceptions; if False (default),
                log exceptions with traceback and continue processing remaining prompts

        Returns:
            Number of prompts successfully cached

        Examples:
            >>> optimizer = CacheOptimizer(cache)
            >>> provider = create_provider("claude-cli")
            >>> common_prompts = ["Fix bug", "Explain code", "Add tests"]
            >>> cached_count = optimizer.warm_cache(
            ...     provider,
            ...     common_prompts,
            ...     "claude-cli",
            ...     "claude-sonnet-4-5"
            ... )
            >>> print(f"Cached {cached_count} prompts")

        Note:
            This method runs sequentially. For faster warming of many prompts,
            use batch_preload() with parallel workers.
        """
        cached = 0
        failed = 0
        start_time = time.time()

        logger.info(f"Warming cache with {len(prompts)} prompts...")

        for i, prompt in enumerate(prompts, 1):
            try:
                # Compute cache key
                cache_key = self.cache.compute_key(prompt, provider_name, model_name)

                # Skip if already cached
                if self.cache.get(cache_key) is not None:
                    logger.debug(f"Prompt {i}/{len(prompts)} already cached, skipping")
                    cached += 1
                    continue

                # Generate response and cache it
                response = provider.generate(prompt, max_tokens=max_tokens)

                # Store in cache
                metadata = {
                    "prompt": prompt,
                    "provider": provider_name,
                    "model": model_name,
                }
                self.cache.set(cache_key, response, metadata)

                cached += 1
                logger.debug(f"Cached prompt {i}/{len(prompts)}")

            except ValueError as e:
                # Invalid input parameters (empty strings, etc.)
                logger.error(f"Failed to cache prompt {i}/{len(prompts)} - invalid input: {e}")
                failed += 1
                continue
            except TypeError as e:
                # Type errors in method calls
                logger.error(f"Failed to cache prompt {i}/{len(prompts)} - type error: {e}")
                failed += 1
                continue
            except (LLMAuthenticationError, LLMRateLimitError) as e:
                # Auth and rate limit errors may indicate systemic issues
                logger.error(
                    f"Failed to cache prompt {i}/{len(prompts)} - provider error: {e}. "
                    "Consider pausing cache warming."
                )
                failed += 1
                continue
            except (LLMAPIError, LLMTimeoutError, LLMProviderError) as e:
                # Transient API errors - log and continue
                logger.warning(
                    f"Failed to cache prompt {i}/{len(prompts)} - transient provider error: {e}"
                )
                failed += 1
                continue
            except OSError as e:
                # File system errors during cache operations
                logger.error(f"Failed to cache prompt {i}/{len(prompts)} - file system error: {e}")
                failed += 1
                continue
            except Exception as e:
                # Unexpected errors - log with traceback and re-raise or continue based on fail_fast
                logger.exception(
                    f"Unexpected error caching prompt {i}/{len(prompts)}: {e}. "
                    "This may indicate a bug."
                )
                if fail_fast:
                    raise
                failed += 1
                continue

        elapsed = time.time() - start_time
        if failed > 0:
            logger.info(
                f"Cache warming complete: {cached}/{len(prompts)} prompts cached, "
                f"{failed} failed in {elapsed:.1f}s"
            )
        else:
            logger.info(
                f"Cache warming complete: {cached}/{len(prompts)} prompts cached "
                f"in {elapsed:.1f}s"
            )

        return cached

    def batch_preload(
        self,
        # Provider instance used to actually generate LLM responses
        provider: LLMProvider,
        prompts: list[str],
        # Provider/model identification for cache key generation
        # These strings should match the provider instance's actual provider/model
        provider_name: str,
        model_name: str,
        # LLM request parameters
        max_workers: int = 4,
        max_tokens: int = 2000,
        # Optional monitoring
        progress_callback: Callable[[WarmingProgress], None] | None = None,
    ) -> int:
        """Preload multiple prompts in parallel for faster cache warming.

        Uses ThreadPoolExecutor to generate and cache responses concurrently.
        Recommended for warming cache with large prompt sets (50+ prompts).

        Args:
            provider: LLM provider to generate responses
            prompts: List of prompts to preload
            provider_name: Provider name for cache keys (must match provider instance)
            model_name: Model name for cache keys (must match provider instance)
            max_workers: Maximum concurrent workers (default: 4, recommended: 4-8)
            max_tokens: Maximum tokens per request (default: 2000)
            progress_callback: Optional callback for progress updates

        Returns:
            Number of prompts successfully cached

        Raises:
            LLMAuthenticationError: Authentication failure - batch terminates immediately
            LLMRateLimitError: Rate limit exceeded - batch terminates immediately
            Note: Other transient errors (LLMTimeoutError, LLMAPIError) are logged
                  and skipped, allowing the batch to continue processing remaining prompts.
                  Callers should catch authentication and rate-limit errors if they want
                  to handle or retry batch termination.

        Examples:
            >>> def show_progress(p: WarmingProgress) -> None:
            ...     pct = (p.completed / p.total) * 100
            ...     print(f"Progress: {pct:.1f}% ({p.completed}/{p.total})")
            >>>
            >>> optimizer = CacheOptimizer(cache)
            >>> provider = create_provider("claude-cli")
            >>> prompts = load_common_prompts()  # 100 prompts
            >>> cached = optimizer.batch_preload(
            ...     provider,
            ...     prompts,
            ...     "claude-cli",
            ...     "claude-sonnet-4-5",
            ...     max_workers=8,
            ...     progress_callback=show_progress
            ... )

        Note:
            - Optimal max_workers: 4-8 for most LLM providers
            - Higher parallelism may trigger rate limits
            - Progress callback receives WarmingProgress updates
        """
        # Validate and clamp max_workers to reasonable bounds
        # Max value uses shared MAX_WORKERS constant from llm.constants
        if max_workers < 1:
            logger.warning(f"max_workers must be >= 1, clamping from {max_workers} to 1")
            max_workers = 1
        elif max_workers > MAX_WORKERS:
            logger.warning(
                f"max_workers must be <= {MAX_WORKERS}, "
                f"clamping from {max_workers} to {MAX_WORKERS}"
            )
            max_workers = MAX_WORKERS
        elif max_workers > 16:
            logger.warning(
                f"max_workers={max_workers} is high and may cause rate limiting. "
                f"Consider 8-16 for most providers unless benchmarked."
            )

        start_time = time.time()
        cached = 0
        failed = 0

        logger.info(f"Batch preloading {len(prompts)} prompts with {max_workers} workers...")

        # Filter out already-cached prompts
        uncached_prompts = []
        for prompt in prompts:
            try:
                cache_key = self.cache.compute_key(prompt, provider_name, model_name)
                if self.cache.get(cache_key) is None:
                    uncached_prompts.append(prompt)
                else:
                    cached += 1
            except ValueError as e:
                # Skip invalid prompts (empty, invalid format, etc.)
                logger.warning(f"Skipping invalid prompt during pre-filter: {e}")
                failed += 1
                continue

        if not uncached_prompts:
            logger.info(f"All {len(prompts)} prompts already cached")
            return cached

        logger.info(
            f"Found {len(uncached_prompts)} uncached prompts "
            f"({len(prompts) - len(uncached_prompts)} already cached)"
        )

        def _cache_single_prompt(prompt: str) -> bool:
            """Cache a single prompt. Returns True on success, False on failure."""
            try:
                cache_key = self.cache.compute_key(prompt, provider_name, model_name)
                response = provider.generate(prompt, max_tokens=max_tokens)
                metadata = {
                    "prompt": prompt,
                    "provider": provider_name,
                    "model": model_name,
                }
                self.cache.set(cache_key, response, metadata)
                return True
            except (LLMAuthenticationError, LLMRateLimitError) as e:
                # Auth and rate limit errors - re-raise to terminate early
                logger.error(f"Failed to cache prompt - {type(e).__name__}: {e}")
                raise
            except (LLMAPIError, LLMTimeoutError, LLMProviderError) as e:
                # Transient network/provider errors - log and return False
                logger.warning(f"Failed to cache prompt - transient {type(e).__name__}: {e}")
                return False
            except OSError as e:
                # File system errors - log and return False
                logger.error(f"Failed to cache prompt - file system error: {e}")
                return False
            except Exception as e:
                # Unexpected errors - log with traceback and return False
                logger.exception(f"Failed to cache prompt - unexpected {type(e).__name__}: {e}")
                return False

        # Process prompts in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_prompt = {
                executor.submit(_cache_single_prompt, prompt): prompt for prompt in uncached_prompts
            }

            # Process completions
            for i, future in enumerate(as_completed(future_to_prompt), 1):
                try:
                    success = future.result()
                    if success:
                        cached += 1
                    else:
                        failed += 1
                except (LLMAuthenticationError, LLMRateLimitError) as critical_error:
                    # Critical errors: cancel remaining futures and re-raise
                    logger.error(
                        f"Critical error during batch preload: "
                        f"{critical_error.__class__.__name__}: {critical_error}"
                    )
                    # Cancel any outstanding futures
                    for pending_future in future_to_prompt:
                        if not pending_future.done():
                            pending_future.cancel()
                    raise
                except Exception as e:
                    # Non-critical errors: log and continue processing other prompts
                    logger.exception(
                        f"Failed to cache prompt in batch: {e.__class__.__name__}: {e}"
                    )
                    failed += 1

                # Report progress
                if progress_callback:
                    elapsed = time.time() - start_time
                    progress = WarmingProgress(
                        total=len(prompts),
                        completed=cached,
                        failed=failed,
                        in_progress=len(uncached_prompts) - i,
                        elapsed_seconds=elapsed,
                    )
                    progress_callback(progress)

        elapsed = time.time() - start_time
        logger.info(
            f"Batch preloading complete: {cached}/{len(prompts)} cached, "
            f"{failed} failed in {elapsed:.1f}s"
        )

        return cached

    def analyze_cache(self) -> CacheAnalysis:
        """Analyze cache health and provide optimization recommendations.

        Examines cache statistics, identifies stale entries, and provides
        actionable recommendations for improving cache performance.

        Returns:
            CacheAnalysis with metrics and recommendations

        Examples:
            >>> optimizer = CacheOptimizer(cache)
            >>> analysis = optimizer.analyze_cache()
            >>> print(f"Cache health: {analysis.hit_rate * 100:.1f}% hit rate")
            >>> print(f"Fragmentation: {analysis.fragmentation_ratio * 100:.1f}%")
            >>> for rec in analysis.recommendations:
            ...     print(f"Recommendation: {rec}")

        Note:
            - Stale entries: entries older than 80% of TTL
            - Fragmentation: ratio of used to max cache size
            - Recommendations based on configurable thresholds
        """
        stats = self.cache.get_stats()
        recommendations: list[str] = []

        # Calculate stale entries (older than 80% of TTL)
        stale_threshold = self.cache.ttl_seconds * 0.8
        stale_entries = self._count_stale_entries(stale_threshold)

        # Calculate fragmentation ratio
        if self.cache.max_size_bytes is None or self.cache.max_size_bytes <= 0:
            logger.debug(
                "max_size_bytes is None or <= 0, cannot calculate fragmentation ratio. "
                f"max_size_bytes={self.cache.max_size_bytes}"
            )
            fragmentation = None
        else:
            fragmentation = stats.cache_size_bytes / self.cache.max_size_bytes

        # Generate recommendations based on thresholds
        if stats.hit_rate < 0.3 and stats.total_requests > 10:
            recommendations.append(
                "Low hit rate (<30%). Consider warming cache with common prompts."
            )

        if fragmentation is not None and fragmentation > 0.9:
            recommendations.append(
                "Cache nearly full (>90%). Consider increasing max_size_bytes or "
                "running eviction."
            )

        if stale_entries > stats.entry_count * 0.5:
            recommendations.append(
                f"Many stale entries ({stale_entries}/{stats.entry_count}). "
                "Consider running evict_stale_entries()."
            )

        if stats.entry_count == 0 and stats.total_requests > 0:
            recommendations.append("Cache is empty but has requests. Check if caching is enabled.")

        if not recommendations:
            recommendations.append("Cache is healthy. No optimization needed.")

        fragmentation_str = (
            f"{fragmentation * 100:.1f}% full" if fragmentation is not None else "N/A (no max size)"
        )
        logger.info(
            f"Cache analysis: {stats.entry_count} entries, "
            f"{stats.hit_rate * 100:.1f}% hit rate, "
            f"{fragmentation_str}"
        )

        return CacheAnalysis(
            total_entries=stats.entry_count,
            total_size_bytes=stats.cache_size_bytes,
            hit_rate=stats.hit_rate,
            stale_entries=stale_entries,
            fragmentation_ratio=fragmentation,
            recommendations=recommendations,
        )

    def evict_stale_entries(self, age_threshold_ratio: float = 0.8) -> int:
        """Evict cache entries older than threshold.

        Removes entries that are approaching TTL expiration to free up space
        and improve cache freshness.

        Args:
            age_threshold_ratio: Evict entries older than this ratio of TTL
                (default: 0.8 = 80% of TTL). For example, with TTL=7 days,
                evicts entries older than 5.6 days.

        Returns:
            Number of entries evicted

        Examples:
            >>> optimizer = CacheOptimizer(cache)
            >>> evicted = optimizer.evict_stale_entries(age_threshold_ratio=0.8)
            >>> print(f"Evicted {evicted} stale entries")

            >>> # More aggressive: evict entries older than 50% of TTL
            >>> evicted = optimizer.evict_stale_entries(age_threshold_ratio=0.5)

        Note:
            - Does not evict entries within TTL (not expired)
            - Useful for proactive cache cleanup
            - Stale threshold: TTL * age_threshold_ratio
        """
        if not (0.0 < age_threshold_ratio <= 1.0):
            raise ValueError(f"age_threshold_ratio must be in (0, 1], got {age_threshold_ratio}")

        age_threshold = self.cache.ttl_seconds * age_threshold_ratio
        evicted = 0

        logger.info(
            f"Evicting entries older than {age_threshold:.0f}s "
            f"({age_threshold_ratio * 100:.0f}% of TTL)"
        )

        # Scan all cache files using centralized iterator
        for cache_file, age in self._iter_cache_files_with_age():
            if age > age_threshold:
                try:
                    cache_file.unlink()
                    evicted += 1
                    logger.debug(f"Evicted stale entry {cache_file.stem[:8]}... (age={age:.0f}s)")
                except OSError as e:
                    logger.debug(
                        f"Failed to evict cache file {cache_file.name}: "
                        f"{e.__class__.__name__}: {e}. "
                        "File may have been deleted or is inaccessible, skipping."
                    )
                    continue  # File may have been deleted, skip it

        logger.info(f"Evicted {evicted} stale entries")
        return evicted

    def _iter_cache_files_with_age(self) -> "Generator[tuple[Path, float], None, None]":
        """Iterate cache files with their age in seconds (internal helper).

        Yields (cache_file, age_seconds) for each cache file, logging and skipping
        files that can't be accessed due to OSError.

        Yields:
            Tuple of (cache_file Path, age in seconds)
        """
        current_time = time.time()

        for cache_file in self.cache.cache_dir.glob("*.json"):
            try:
                mtime = cache_file.stat().st_mtime
                age = current_time - mtime
                yield (cache_file, age)
            except OSError as e:
                logger.debug(f"Failed to stat cache file {cache_file}: {e.__class__.__name__}: {e}")
                continue  # File may have been deleted or inaccessible, skip it

    def _count_stale_entries(self, age_threshold: float) -> int:
        """Count entries older than age threshold (internal helper).

        Args:
            age_threshold: Age threshold in seconds

        Returns:
            Number of stale entries
        """
        stale = 0

        for _cache_file, age in self._iter_cache_files_with_age():
            if age > age_threshold:
                stale += 1

        return stale
