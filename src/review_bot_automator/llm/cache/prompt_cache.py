# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""File-based prompt caching with TTL and LRU eviction.

This module implements a thread-safe file-based cache for LLM responses to achieve
significant cost reduction (50-90%) by avoiding redundant API calls for identical prompts.
"""

import contextlib
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Eviction target ratio: reduce cache to 90% of max size to minimize frequent evictions
_EVICTION_TARGET_RATIO = 0.9


@dataclass(frozen=True)
class CacheEntry:
    """Cache entry containing LLM response and metadata.

    Attributes:
        response: The LLM-generated response text
        timestamp: Unix timestamp when entry was created
        provider: LLM provider name (e.g., "anthropic", "openai")
        model: Model name (e.g., "claude-sonnet-4-5", "gpt-4o")
        prompt_hash: SHA256 hash of the original prompt text ONLY
                     (not the composite cache key which includes provider+model)

    Examples:
        >>> entry = CacheEntry(
        ...     response="Generated text",
        ...     timestamp=1699999999.99,
        ...     provider="anthropic",
        ...     model="claude-sonnet-4-5",
        ...     prompt_hash="abc123...",
        ... )
    """

    response: str
    timestamp: float
    provider: str
    model: str
    prompt_hash: str


@dataclass(frozen=True)
class CacheStats:
    """Cache statistics for monitoring hit rates and storage usage.

    Attributes:
        hits: Number of successful cache retrievals
        misses: Number of cache misses (key not found or expired)
        total_requests: Total number of get() operations
        hit_rate: Percentage of successful hits (hits / total_requests)
        cache_size_bytes: Total disk space used by cache files
        entry_count: Number of entries currently in cache

    Examples:
        >>> stats = CacheStats(
        ...     hits=85,
        ...     misses=15,
        ...     total_requests=100,
        ...     hit_rate=0.85,
        ...     cache_size_bytes=1024000,
        ...     entry_count=42,
        ... )
        >>> print(f"Hit rate: {stats.hit_rate * 100}%")
        Hit rate: 85.0%
    """

    hits: int
    misses: int
    total_requests: int
    hit_rate: float
    cache_size_bytes: int
    entry_count: int


class PromptCache:
    """Thread-safe file-based cache for LLM responses with TTL and LRU eviction.

    Provides transparent caching of LLM API responses to reduce costs by 50-90% through
    cache hits. Uses SHA256-based keys, JSON file storage with restricted permissions,
    and automatic eviction based on TTL (Time To Live) and LRU (Least Recently Used).

    The cache directory defaults to `~/.cache/review-bot-automator/llm/` with user-only
    permissions (0700). Individual cache files have 0600 permissions (user read/write only).

    Examples:
        Basic usage:
        >>> cache = PromptCache()
        >>> key = cache.compute_key("Fix this bug", "anthropic", "claude-sonnet-4-5")
        >>> cache.set(key, "Here's the fix...", {"provider": "anthropic"})
        >>> response = cache.get(key)
        >>> print(response)
        Here's the fix...

        Custom configuration:
        >>> cache = PromptCache(
        ...     cache_dir=Path("/tmp/my-cache"),
        ...     ttl_seconds=86400,  # 1 day
        ...     max_size_bytes=50 * 1024 * 1024,  # 50MB
        ... )

        Statistics:
        >>> stats = cache.get_stats()
        >>> print(f"Hit rate: {stats.hit_rate * 100:.1f}%")
        >>> print(f"Cache size: {stats.cache_size_bytes / 1024 / 1024:.1f}MB")

    Attributes:
        cache_dir: Directory path where cache files are stored
        ttl_seconds: Time-to-live for cache entries (default: 7 days)
        max_size_bytes: Maximum cache size before LRU eviction (default: 100MB)

    Note:
        - All operations are thread-safe using a lock
        - Expired entries are automatically deleted on get()
        - LRU eviction is triggered automatically when cache exceeds max_size_bytes
        - Cache is NOT integrated with providers in Phase 2.5 (deferred to Phase 5)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_seconds: int = 604800,  # 7 days
        max_size_bytes: int = 100 * 1024 * 1024,  # 100MB
    ) -> None:
        """Initialize prompt cache with directory and eviction settings.

        Args:
            cache_dir: Directory path for cache storage
                (default: ~/.cache/review-bot-automator/llm)
            ttl_seconds: Time-to-live for cache entries in seconds
                (default: 604800 = 7 days)
            max_size_bytes: Maximum cache size in bytes before LRU eviction
                (default: 104857600 = 100MB)

        Raises:
            ValueError: If ttl_seconds or max_size_bytes are non-positive
            OSError: If cache directory cannot be created

        Examples:
            >>> cache = PromptCache()  # Use defaults
            >>> cache = PromptCache(ttl_seconds=86400)  # 1 day TTL
            >>> cache = PromptCache(max_size_bytes=50 * 1024 * 1024)  # 50MB limit
        """
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds}")
        if max_size_bytes <= 0:
            raise ValueError(f"max_size_bytes must be positive, got {max_size_bytes}")

        # Set default cache directory if not provided
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "review-bot-automator" / "llm"

        self.cache_dir = cache_dir.resolve()
        self.ttl_seconds = ttl_seconds
        self.max_size_bytes = max_size_bytes

        # Thread safety
        self._lock = threading.Lock()

        # Statistics
        self._hits = 0
        self._misses = 0
        self._total_requests = 0

        # Create cache directory with restricted permissions
        self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Enforce 0700 permissions even if directory already existed
        current_mode = self.cache_dir.stat().st_mode & 0o777
        if current_mode != 0o700:
            try:
                os.chmod(self.cache_dir, 0o700)
            except OSError as exc:
                raise OSError(
                    f"Failed to enforce 0700 permissions on cache directory {self.cache_dir}"
                ) from exc

        logger.debug(
            f"Initialized cache at {self.cache_dir} "
            f"(TTL={ttl_seconds}s, max={max_size_bytes} bytes)"
        )

    def compute_key(self, prompt: str, provider: str, model: str) -> str:
        """Compute SHA256 cache key from prompt, provider, and model.

        The cache key is deterministic: identical inputs always produce the same key.
        This enables reliable cache hits across different sessions.

        Args:
            prompt: The prompt text sent to the LLM
            provider: LLM provider name (e.g., "anthropic", "openai")
            model: Model name (e.g., "claude-sonnet-4-5", "gpt-4o")

        Returns:
            64-character hexadecimal SHA256 hash

        Raises:
            ValueError: If any argument is empty or None

        Examples:
            >>> cache = PromptCache()
            >>> key1 = cache.compute_key("Fix bug", "anthropic", "claude-sonnet-4-5")
            >>> key2 = cache.compute_key("Fix bug", "anthropic", "claude-sonnet-4-5")
            >>> assert key1 == key2  # Deterministic
            >>> assert len(key1) == 64  # SHA256 hex length

        Note:
            Different prompts, providers, or models produce different keys.
            The prompt is never stored in plaintext for privacy.
        """
        if not prompt:
            raise ValueError("prompt cannot be empty")
        if not provider:
            raise ValueError("provider cannot be empty")
        if not model:
            raise ValueError("model cannot be empty")

        # Create deterministic hash using length-prefixing to prevent collisions
        # Each component is prefixed with its byte length (8 bytes, big-endian)
        # This ensures distinct inputs always produce distinct hashes
        hash_obj = hashlib.sha256()
        for part in (prompt, provider, model):
            encoded = part.encode("utf-8")
            hash_obj.update(len(encoded).to_bytes(8, "big", signed=False))
            hash_obj.update(encoded)
        return hash_obj.hexdigest()

    def get(self, key: str) -> str | None:
        """Retrieve cached response for the given key.

        Performs TTL check: if entry is expired, it is automatically deleted and None is returned.
        Updates cache statistics (hit/miss counters).

        Args:
            key: SHA256 cache key from compute_key()

        Returns:
            Cached response text if found and not expired, otherwise None

        Examples:
            >>> cache = PromptCache()
            >>> key = cache.compute_key("test", "anthropic", "claude-sonnet-4-5")
            >>> response = cache.get(key)  # Returns None if not cached
            >>> if response is None:
            ...     response = "Fresh LLM response"
            ...     cache.set(key, response, {})

        Note:
            This method is thread-safe. Corrupted cache files are automatically
            deleted and logged as misses.
        """
        with self._lock:
            return self._get_unlocked(key)

    def _get_unlocked(self, key: str) -> str | None:
        """Internal get implementation without locking (caller must hold lock).

        Args:
            key: SHA256 cache key

        Returns:
            Cached response or None if not found/expired/corrupted
        """
        self._total_requests += 1
        cache_file = self.cache_dir / f"{key}.json"

        if not cache_file.exists():
            self._misses += 1
            logger.debug(f"Cache miss: {key[:8]}... (file not found)")
            return None

        try:
            # Read and deserialize cache entry
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)

            # Check TTL
            entry_age = time.time() - data["timestamp"]
            if entry_age > self.ttl_seconds:
                # Expired: delete file
                cache_file.unlink(missing_ok=True)
                self._misses += 1
                logger.debug(f"Cache miss: {key[:8]}... (expired after {entry_age:.0f}s)")
                return None

            # Update access time for LRU
            cache_file.touch()

            # Cache hit
            self._hits += 1
            logger.debug(f"Cache hit: {key[:8]}... (age={entry_age:.0f}s)")
            response: str = data["response"]
            return response

        except (json.JSONDecodeError, KeyError) as e:
            # Corrupted file: delete and log
            cache_file.unlink(missing_ok=True)
            self._misses += 1
            logger.warning(f"Corrupted cache file {key[:8]}..., deleting: {e}")
            return None
        except Exception as e:
            # Unexpected error: delete corrupted file and return None
            cache_file.unlink(missing_ok=True)
            self._misses += 1
            logger.error(f"Unexpected error reading cache {key[:8]}..., deleting: {e}")
            return None

    def set(self, key: str, response: str, metadata: dict[str, str]) -> None:
        """Store response in cache with metadata.

        Automatically triggers LRU eviction if cache size exceeds max_size_bytes after storing.

        Args:
            key: SHA256 cache key from compute_key()
            response: LLM-generated response text to cache
            metadata: Must include "prompt", "provider", "model"
                - prompt: Original prompt text (for computing prompt_hash)
                - provider: LLM provider name
                - model: Model name

        Raises:
            ValueError: If key, response, or prompt is empty/missing

        Examples:
            >>> cache = PromptCache()
            >>> prompt = "Fix the bug in login.py"
            >>> key = cache.compute_key(prompt, "anthropic", "claude-sonnet-4-5")
            >>> cache.set(key, "LLM response here", {
            ...     "prompt": prompt,
            ...     "provider": "anthropic",
            ...     "model": "claude-sonnet-4-5",
            ... })

        Note:
            - Cache files are created with 0600 permissions (user read/write only)
            - Automatic LRU eviction occurs if cache exceeds max_size_bytes
            - Thread-safe operation
        """
        if not key:
            raise ValueError("key cannot be empty")
        if not response:
            raise ValueError("response cannot be empty")

        with self._lock:
            self._set_unlocked(key, response, metadata)

    def _set_unlocked(
        self,
        key: str,
        response: str,
        metadata: dict[str, str],
        *,
        skip_eviction: bool = False,
    ) -> None:
        """Internal set implementation without locking (caller must hold lock).

        Args:
            key: SHA256 cache key
            response: LLM response to cache
            metadata: Must include prompt, provider, and model
            skip_eviction: If True, skip cache size check and eviction (for bulk ops)
        """
        # Extract and validate prompt (required for prompt_hash)
        prompt = metadata.get("prompt")
        if not prompt:
            raise ValueError("metadata must include 'prompt' field")

        # Compute prompt_hash from prompt only (not the composite cache key)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        cache_file = self.cache_dir / f"{key}.json"
        tmp_file = cache_file.with_suffix(".json.tmp")

        # Create cache entry
        entry = {
            "response": response,
            "timestamp": time.time(),
            "provider": metadata.get("provider", "unknown"),
            "model": metadata.get("model", "unknown"),
            "prompt_hash": prompt_hash,
        }

        # Write to temp file with secure permissions, then atomically replace
        # This prevents partially-written/corrupted files if interrupted
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp_file, 0o600)
            os.replace(tmp_file, cache_file)
        except Exception:
            tmp_file.unlink(missing_ok=True)
            raise

        logger.debug(f"Cached response for key {key[:8]}...")

        # Check if eviction needed (skip during bulk operations for O(n) instead of O(n²))
        if not skip_eviction:
            cache_size = self._get_cache_size_unlocked()
            if cache_size > self.max_size_bytes:
                # Calculate target size (90% of max to reduce frequent evictions)
                target_size = int(self.max_size_bytes * _EVICTION_TARGET_RATIO)
                evicted = self._evict_lru_unlocked(target_size)
                logger.info(
                    f"Cache exceeded {self.max_size_bytes} bytes, evicted {evicted} entries"
                )

    def evict_expired(self) -> int:
        """Remove all expired cache entries based on TTL.

        Scans entire cache directory and deletes entries older than ttl_seconds.

        Returns:
            Number of entries evicted

        Examples:
            >>> cache = PromptCache(ttl_seconds=60)  # 1 minute TTL
            >>> # ... wait 61 seconds ...
            >>> evicted = cache.evict_expired()
            >>> print(f"Removed {evicted} expired entries")

        Note:
            This method is thread-safe and can be called periodically to clean up
            expired entries proactively.
        """
        with self._lock:
            return self._evict_expired_unlocked()

    def _evict_expired_unlocked(self) -> int:
        """Internal evict_expired implementation without locking.

        Returns:
            Number of entries evicted
        """
        evicted = 0
        current_time = time.time()

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)

                entry_age = current_time - data["timestamp"]
                if entry_age > self.ttl_seconds:
                    cache_file.unlink()
                    evicted += 1
                    logger.debug(
                        f"Evicted expired entry {cache_file.stem[:8]}... (age={entry_age:.0f}s)"
                    )

            except (json.JSONDecodeError, KeyError, Exception) as e:
                # Corrupted or unreadable: delete it
                cache_file.unlink(missing_ok=True)
                evicted += 1
                logger.debug(f"Evicted corrupted entry {cache_file.stem[:8]}...: {e}")

        if evicted > 0:
            logger.info(f"Evicted {evicted} expired entries (TTL={self.ttl_seconds}s)")

        return evicted

    def evict_lru(self, target_size: int) -> int:
        """Remove least recently used entries until cache size is below target.

        Sorts cache files by modification time (oldest first) and deletes until
        target size is reached.

        Args:
            target_size: Target cache size in bytes

        Returns:
            Number of entries evicted

        Examples:
            >>> cache = PromptCache()
            >>> stats = cache.get_stats()
            >>> if stats.cache_size_bytes > 80 * 1024 * 1024:  # 80MB
            ...     evicted = cache.evict_lru(50 * 1024 * 1024)  # Reduce to 50MB

        Note:
            Thread-safe operation. Files are sorted by mtime (modification time),
            with oldest files evicted first.
        """
        with self._lock:
            return self._evict_lru_unlocked(target_size)

    def _evict_lru_unlocked(self, target_size: int) -> int:
        """Internal evict_lru implementation without locking.

        Args:
            target_size: Target cache size in bytes

        Returns:
            Number of entries evicted
        """
        cache_size = self._get_cache_size_unlocked()
        if cache_size <= target_size:
            return 0

        # Get all cache files with their mtimes
        files_with_mtime = []
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                mtime = cache_file.stat().st_mtime
                size = cache_file.stat().st_size
                files_with_mtime.append((mtime, size, cache_file))
            except OSError:
                pass  # File may have been deleted, skip it

        # Sort by mtime (oldest first)
        files_with_mtime.sort(key=lambda x: x[0])

        # Evict oldest files until target size reached
        evicted = 0
        current_size = cache_size

        for _mtime, size, cache_file in files_with_mtime:
            if current_size <= target_size:
                break

            try:
                cache_file.unlink()
                current_size -= size
                evicted += 1
                logger.debug(f"Evicted LRU entry {cache_file.stem[:8]}... (size={size} bytes)")
            except OSError:
                pass  # File may have been deleted by another thread

        if evicted > 0:
            logger.info(
                f"Evicted {evicted} LRU entries (reduced from {cache_size} to {current_size} bytes)"
            )

        return evicted

    def get_stats(self) -> CacheStats:
        """Get current cache statistics.

        Returns:
            CacheStats with hits, misses, hit rate, size, and entry count

        Examples:
            >>> cache = PromptCache()
            >>> stats = cache.get_stats()
            >>> print(f"Hit rate: {stats.hit_rate * 100:.1f}%")
            >>> print(f"Entries: {stats.entry_count}")
            >>> print(f"Size: {stats.cache_size_bytes / 1024 / 1024:.1f}MB")

        Note:
            Returns immutable statistics snapshot. Thread-safe operation.
        """
        with self._lock:
            return self._get_stats_unlocked()

    def _get_stats_unlocked(self) -> CacheStats:
        """Internal get_stats implementation without locking.

        Returns:
            CacheStats dataclass with current statistics
        """
        cache_size = self._get_cache_size_unlocked()
        entry_count = sum(1 for _ in self.cache_dir.glob("*.json"))

        # Calculate hit rate
        hit_rate = self._hits / self._total_requests if self._total_requests > 0 else 0.0

        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            total_requests=self._total_requests,
            hit_rate=hit_rate,
            cache_size_bytes=cache_size,
            entry_count=entry_count,
        )

    def clear(self) -> None:
        """Remove all cache entries and reset statistics.

        Deletes all JSON files in cache directory and resets hit/miss counters.

        Examples:
            >>> cache = PromptCache()
            >>> cache.clear()  # Delete all cached entries
            >>> stats = cache.get_stats()
            >>> assert stats.entry_count == 0
            >>> assert stats.hits == 0

        Note:
            Thread-safe operation. Use with caution in production.
        """
        with self._lock:
            self._clear_unlocked()

    def _clear_unlocked(self) -> None:
        """Internal clear implementation without locking."""
        # Delete all cache files
        deleted = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                deleted += 1
            except OSError:
                pass  # File may have been deleted

        # Reset statistics
        self._hits = 0
        self._misses = 0
        self._total_requests = 0

        logger.info(f"Cleared cache: deleted {deleted} entries")

    def _get_cache_size_unlocked(self) -> int:
        """Calculate total size of all cache files in bytes (caller must hold lock).

        Returns:
            Total cache size in bytes
        """
        total_size = 0
        for cache_file in self.cache_dir.glob("*.json"):
            with contextlib.suppress(OSError):
                total_size += cache_file.stat().st_size
        return total_size

    @staticmethod
    def _validate_field(entry: dict[str, str], field: str) -> str | None:
        """Validate and return field value or None if invalid.

        Args:
            entry: Dictionary to extract field from
            field: Field name to validate

        Returns:
            Stripped string value if valid, None if missing/empty/whitespace-only
        """
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            return None
        return value

    def warm_cache(self, entries: list[dict[str, str]]) -> tuple[int, int]:
        """Pre-populate cache with pre-computed entries for cold start optimization.

        This method allows importing previously cached responses to avoid cold start
        latency. Useful for:
        - Restoring cache after container restart
        - Sharing cache across team members
        - Pre-populating test environments

        Args:
            entries: List of cache entry dictionaries. Each entry must contain:
                - prompt: Original prompt text
                - provider: LLM provider name (e.g., "anthropic", "openai")
                - model: Model name (e.g., "claude-sonnet-4-5", "gpt-4o")
                - response: The cached LLM response

        Returns:
            Tuple of (loaded_count, skipped_count):
                - loaded_count: Number of entries successfully loaded
                - skipped_count: Number of entries skipped (invalid or already cached)

        Examples:
            >>> cache = PromptCache()
            >>> entries = [
            ...     {
            ...         "prompt": "Fix the bug",
            ...         "provider": "anthropic",
            ...         "model": "claude-sonnet-4-5",
            ...         "response": "[]",
            ...     }
            ... ]
            >>> loaded, skipped = cache.warm_cache(entries)
            >>> print(f"Loaded {loaded} entries, skipped {skipped}")

        Note:
            - Existing cache entries are NOT overwritten (skip duplicates)
            - Invalid entries are logged and skipped
            - Thread-safe operation
        """
        loaded = 0
        skipped = 0

        with self._lock:
            for entry in entries:
                try:
                    # Validate required fields using helper (DRY + type narrowing)
                    prompt = self._validate_field(entry, "prompt")
                    provider = self._validate_field(entry, "provider")
                    model = self._validate_field(entry, "model")
                    response = self._validate_field(entry, "response")

                    if prompt is None or provider is None or model is None or response is None:
                        missing = [
                            name
                            for name, val in zip(
                                ["prompt", "provider", "model", "response"],
                                [prompt, provider, model, response],
                                strict=True,
                            )
                            if val is None
                        ]
                        logger.warning(f"Skipping invalid entry: missing/empty fields: {missing}")
                        skipped += 1
                        continue

                    # Compute cache key (type narrowed to str after None checks)
                    key = self.compute_key(prompt, provider, model)
                    cache_file = self.cache_dir / f"{key}.json"

                    # Skip if already cached (don't overwrite existing entries)
                    if cache_file.exists():
                        logger.debug(f"Skipping existing cache entry {key[:8]}...")
                        skipped += 1
                        continue

                    # Store entry (skip per-entry eviction for O(n) bulk load)
                    self._set_unlocked(
                        key,
                        response,
                        {"prompt": prompt, "provider": provider, "model": model},
                        skip_eviction=True,
                    )
                    loaded += 1

                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to warm cache entry: {e}")
                    skipped += 1

            # Single eviction check after bulk load (O(n) instead of O(n²))
            if loaded > 0:
                cache_size = self._get_cache_size_unlocked()
                if cache_size > self.max_size_bytes:
                    target_size = int(self.max_size_bytes * _EVICTION_TARGET_RATIO)
                    evicted = self._evict_lru_unlocked(target_size)
                    logger.info(f"Cache warming evicted {evicted} LRU entries after bulk load")

        logger.info(f"Cache warming complete: loaded={loaded}, skipped={skipped}")
        return (loaded, skipped)

    def export_entries(self) -> list[dict[str, str | int | float]]:
        """Export all cache entries for backup or transfer.

        Exports cache entries for analytics and backup purposes only.
        Note: Entries contain prompt_hash (not original prompts) and cannot
        be re-imported via warm_cache() which requires original prompts.

        Returns:
            List of cache entry dictionaries with:
                - prompt_hash: SHA256 hash of original prompt
                - provider: LLM provider name
                - model: Model name
                - response: The cached LLM response
                - timestamp: Unix timestamp (float/int)

        Examples:
            >>> cache = PromptCache()
            >>> entries = cache.export_entries()
            >>> # Save to file for later analysis or backup
            >>> import json
            >>> with open("cache_backup.json", "w") as f:
            ...     json.dump(entries, f)

        Note:
            - Thread-safe operation
            - Expired entries are included (check timestamp if needed)
            - Original prompts are not exported (privacy by design)
            - Exported entries cannot be re-imported via warm_cache() since
              original prompts are not stored; use for analytics/backup only
        """
        entries = []

        with self._lock:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, encoding="utf-8") as f:
                        data = json.load(f)

                    entries.append(
                        {
                            "prompt_hash": data.get("prompt_hash", ""),
                            "provider": data.get("provider", ""),
                            "model": data.get("model", ""),
                            "response": data.get("response", ""),
                            "timestamp": data.get("timestamp", 0),
                        }
                    )
                except (OSError, json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to export cache entry {cache_file.name}: {e}")

        logger.info(f"Exported {len(entries)} cache entries")
        return entries

    @staticmethod
    def get_common_patterns() -> list[str]:
        """Get common prompt pattern prefixes used in this application.

        Returns prompt template prefixes that are commonly used, which can help
        with cache analysis and optimization planning.

        Returns:
            List of common prompt pattern descriptions

        Examples:
            >>> patterns = PromptCache.get_common_patterns()
            >>> for pattern in patterns:
            ...     print(f"- {pattern}")

        Note:
            These patterns describe the prompt templates, not full prompts.
            Actual prompts contain dynamic content (file paths, line numbers, etc.)

            Maintenance: Update this list when adding new prompt templates to
            the parsing system.
        """
        return [
            "PARSE_COMMENT_PROMPT - Extracts code changes from CodeRabbit review comments",
            "Diff block parsing - Handles unified diff format with @@ headers",
            "Suggestion block parsing - Handles markdown suggestion blocks",
            "Natural language parsing - Extracts changes from prose descriptions",
        ]
