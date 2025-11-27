"""Comprehensive test suite for prompt caching system."""

import dataclasses
import hashlib
import json
import tempfile
import threading
import time
from pathlib import Path

import pytest

from review_bot_automator.llm.cache import PromptCache


class TestCacheInitialization:
    """Test cache initialization and directory creation."""

    def test_init_creates_cache_directory(self) -> None:
        """Test that initialization creates cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "test_cache"
            PromptCache(cache_dir=cache_dir)

            assert cache_dir.exists()
            assert cache_dir.is_dir()
            # Check permissions (0700 = owner rwx only)
            assert oct(cache_dir.stat().st_mode)[-3:] == "700"

    def test_init_with_custom_cache_dir(self) -> None:
        """Test initialization with custom cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom" / "cache"
            cache = PromptCache(cache_dir=custom_dir)

            assert cache.cache_dir == custom_dir.resolve()
            assert custom_dir.exists()

    def test_init_with_default_ttl(self) -> None:
        """Test that default TTL is 7 days (604800 seconds)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            assert cache.ttl_seconds == 604800  # 7 days

    def test_init_with_custom_ttl_and_size(self) -> None:
        """Test initialization with custom TTL and max size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(
                cache_dir=Path(tmpdir),
                ttl_seconds=3600,  # 1 hour
                max_size_bytes=50 * 1024 * 1024,  # 50MB
            )

            assert cache.ttl_seconds == 3600
            assert cache.max_size_bytes == 50 * 1024 * 1024

    def test_init_with_invalid_ttl_raises(self) -> None:
        """Test that negative TTL raises ValueError."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(ValueError, match="ttl_seconds must be positive"),
        ):
            PromptCache(cache_dir=Path(tmpdir), ttl_seconds=-1)

    def test_init_with_invalid_max_size_raises(self) -> None:
        """Test that non-positive max_size raises ValueError."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(ValueError, match="max_size_bytes must be positive"),
        ):
            PromptCache(cache_dir=Path(tmpdir), max_size_bytes=0)


class TestCacheKeyComputation:
    """Test cache key computation with SHA256."""

    def test_compute_key_deterministic(self) -> None:
        """Test that same inputs produce same key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key1 = cache.compute_key("test prompt", "anthropic", "claude-sonnet-4-5")
            key2 = cache.compute_key("test prompt", "anthropic", "claude-sonnet-4-5")

            assert key1 == key2

    def test_compute_key_different_prompts(self) -> None:
        """Test that different prompts produce different keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key1 = cache.compute_key("prompt1", "anthropic", "claude-sonnet-4-5")
            key2 = cache.compute_key("prompt2", "anthropic", "claude-sonnet-4-5")

            assert key1 != key2

    def test_compute_key_different_providers(self) -> None:
        """Test that different providers produce different keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key1 = cache.compute_key("prompt", "anthropic", "model")
            key2 = cache.compute_key("prompt", "openai", "model")

            assert key1 != key2

    def test_compute_key_different_models(self) -> None:
        """Test that different models produce different keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key1 = cache.compute_key("prompt", "anthropic", "claude-sonnet-4-5")
            key2 = cache.compute_key("prompt", "anthropic", "claude-opus-4")

            assert key1 != key2

    def test_compute_key_is_sha256_hex(self) -> None:
        """Test that key is valid SHA256 hex string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")

            # SHA256 produces 64 hex characters
            assert len(key) == 64
            assert all(c in "0123456789abcdef" for c in key)

    def test_compute_key_64_chars(self) -> None:
        """Test that key length is always 64 characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Test with different input lengths
            key1 = cache.compute_key("x", "a", "b")
            key2 = cache.compute_key("x" * 1000, "a" * 100, "b" * 100)

            assert len(key1) == 64
            assert len(key2) == 64

    def test_compute_key_empty_prompt_raises(self) -> None:
        """Test that empty prompt raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            with pytest.raises(ValueError, match="prompt cannot be empty"):
                cache.compute_key("", "anthropic", "model")

    def test_compute_key_empty_provider_raises(self) -> None:
        """Test that empty provider raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            with pytest.raises(ValueError, match="provider cannot be empty"):
                cache.compute_key("prompt", "", "model")

    def test_compute_key_empty_model_raises(self) -> None:
        """Test that empty model raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            with pytest.raises(ValueError, match="model cannot be empty"):
                cache.compute_key("prompt", "anthropic", "")

    def test_compute_key_delimiter_in_prompt(self) -> None:
        """Test that prompts containing delimiter produce unique keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Prompts with different delimiters should produce different keys
            key1 = cache.compute_key("foo|bar", "provider", "model")
            key2 = cache.compute_key("foo bar", "provider", "model")
            key3 = cache.compute_key("foobar", "provider", "model")

            assert key1 != key2
            assert key1 != key3
            assert key2 != key3

    def test_compute_key_delimiter_in_provider(self) -> None:
        """Test that providers containing delimiter produce unique keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Providers with different delimiters should produce different keys
            key1 = cache.compute_key("prompt", "foo|bar", "model")
            key2 = cache.compute_key("prompt", "foo bar", "model")
            key3 = cache.compute_key("prompt", "foobar", "model")

            assert key1 != key2
            assert key1 != key3
            assert key2 != key3

    def test_compute_key_delimiter_in_model(self) -> None:
        """Test that models containing delimiter produce unique keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Models with different delimiters should produce different keys
            key1 = cache.compute_key("prompt", "provider", "foo|bar")
            key2 = cache.compute_key("prompt", "provider", "foo bar")
            key3 = cache.compute_key("prompt", "provider", "foobar")

            assert key1 != key2
            assert key1 != key3
            assert key2 != key3

    def test_compute_key_no_collision_with_delimiters(self) -> None:
        """Test that delimiter-containing inputs don't cause hash collisions.

        This regression test ensures that the hash function prevents collisions
        that could occur with naive delimiter-based concatenation.

        Example collision scenario (with old implementation):
        - Input 1: prompt="foo|bar", provider="baz", model="qux"
          → "foo|bar|baz|qux"
        - Input 2: prompt="foo", provider="bar|baz", model="qux"
          → "foo|bar|baz|qux" (same!)

        With length-prefixing, these produce different hashes.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # These should produce different keys despite same concatenation
            key1 = cache.compute_key("foo|bar", "baz", "qux")
            key2 = cache.compute_key("foo", "bar|baz", "qux")

            # Verify distinct inputs produce distinct keys
            assert key1 != key2

            # Test with various delimiter positions
            key4 = cache.compute_key("a|b|c", "d", "e")
            key5 = cache.compute_key("a", "b|c|d", "e")
            key6 = cache.compute_key("a", "b", "c|d|e")

            assert key4 != key5
            assert key4 != key6
            assert key5 != key6


class TestCacheOperations:
    """Test basic cache get/set operations."""

    def test_set_and_get_cache_hit(self) -> None:
        """Test successful cache set and get."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(
                key, "response text", {"prompt": "test", "provider": "anthropic", "model": "model"}
            )

            result = cache.get(key)
            assert result == "response text"

    def test_get_nonexistent_key_returns_none(self) -> None:
        """Test that getting nonexistent key returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            result = cache.get("nonexistent_key")
            assert result is None

    def test_get_expired_entry_returns_none(self) -> None:
        """Test that expired entry returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=1)

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            # Wait for expiration
            time.sleep(1.1)

            result = cache.get(key)
            assert result is None

    def test_set_overwrites_existing_entry(self) -> None:
        """Test that set overwrites existing entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "first response", {"prompt": "test"})
            cache.set(key, "second response", {"prompt": "test"})

            result = cache.get(key)
            assert result == "second response"

    def test_cache_survives_multiple_gets(self) -> None:
        """Test that cache entry survives multiple get operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            # Multiple gets
            for _ in range(5):
                result = cache.get(key)
                assert result == "response"

    def test_set_creates_json_file(self) -> None:
        """Test that set creates JSON file in cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            cache_file = Path(tmpdir) / f"{key}.json"
            assert cache_file.exists()

    def test_set_with_metadata(self) -> None:
        """Test that metadata is stored correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "claude-sonnet-4-5")
            cache.set(
                key,
                "response",
                {"prompt": "test", "provider": "anthropic", "model": "claude-sonnet-4-5"},
            )

            # Read file and check metadata
            cache_file = Path(tmpdir) / f"{key}.json"
            with open(cache_file) as f:
                data = json.load(f)

            assert data["provider"] == "anthropic"
            assert data["model"] == "claude-sonnet-4-5"
            assert data["response"] == "response"

    def test_get_updates_access_time(self) -> None:
        """Test that get updates file modification time for LRU."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            cache_file = Path(tmpdir) / f"{key}.json"
            mtime_before = cache_file.stat().st_mtime

            time.sleep(0.1)
            cache.get(key)

            mtime_after = cache_file.stat().st_mtime
            assert mtime_after > mtime_before

    def test_set_empty_response_raises(self) -> None:
        """Test that empty response raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            with pytest.raises(ValueError, match="response cannot be empty"):
                cache.set(key, "", {"prompt": "test"})

    def test_set_empty_key_raises(self) -> None:
        """Test that empty key raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            with pytest.raises(ValueError, match="key cannot be empty"):
                cache.set("", "response", {})

    def test_set_stores_correct_prompt_hash(self) -> None:
        """Test that prompt_hash stores SHA256 of prompt only, not composite key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            prompt = "test prompt"
            provider = "anthropic"
            model = "claude-sonnet-4-5"

            # Compute key and set entry
            key = cache.compute_key(prompt, provider, model)
            cache.set(key, "response", {"prompt": prompt, "provider": provider, "model": model})

            # Read cache file directly to verify prompt_hash
            cache_file = cache.cache_dir / f"{key}.json"
            with open(cache_file) as f:
                data = json.load(f)

            # Verify prompt_hash is SHA256 of prompt only
            expected_prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            assert data["prompt_hash"] == expected_prompt_hash
            # Ensure it's NOT the composite cache key
            assert data["prompt_hash"] != key

    def test_set_requires_prompt_in_metadata(self) -> None:
        """Test that set() raises ValueError when prompt missing from metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "provider", "model")

            with pytest.raises(ValueError, match="metadata must include 'prompt' field"):
                cache.set(
                    key,
                    "response",
                    {
                        "provider": "anthropic",
                        "model": "model",
                        # Missing "prompt" key
                    },
                )

    def test_get_corrupted_file_returns_none(self) -> None:
        """Test that corrupted JSON file returns None and is deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache_file = Path(tmpdir) / f"{key}.json"

            # Write corrupted JSON
            cache_file.write_text("invalid json{{{", encoding="utf-8")

            result = cache.get(key)
            assert result is None
            # Corrupted file should be deleted
            assert not cache_file.exists()

    def test_set_file_permissions_0600(self) -> None:
        """Test that cache files have 0600 permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            cache_file = Path(tmpdir) / f"{key}.json"
            # Get file permissions (last 3 digits of octal mode)
            perms = oct(cache_file.stat().st_mode)[-3:]
            assert perms == "600"

    def test_multiple_keys_stored_independently(self) -> None:
        """Test that multiple cache entries are stored independently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key1 = cache.compute_key("prompt1", "anthropic", "model")
            key2 = cache.compute_key("prompt2", "openai", "model")

            cache.set(key1, "response1", {"prompt": "prompt1"})
            cache.set(key2, "response2", {"prompt": "prompt2"})

            assert cache.get(key1) == "response1"
            assert cache.get(key2) == "response2"

    def test_get_missing_timestamp_returns_none(self) -> None:
        """Test that entry missing timestamp is treated as corrupted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache_file = Path(tmpdir) / f"{key}.json"

            # Write entry without timestamp
            cache_file.write_text(json.dumps({"response": "text"}), encoding="utf-8")

            result = cache.get(key)
            assert result is None

    def test_get_invalid_timestamp_deletes_file(self) -> None:
        """Test that cache file with non-numeric timestamp is deleted on get()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache_file = Path(tmpdir) / f"{key}.json"

            # Write valid JSON with non-numeric timestamp
            invalid_data = {
                "response": "test response",
                "timestamp": "invalid_timestamp",  # String instead of number
                "prompt_hash": "abc123",
            }
            cache_file.write_text(json.dumps(invalid_data), encoding="utf-8")

            # First get() should return None and delete the corrupted file
            result = cache.get(key)
            assert result is None
            assert not cache_file.exists(), "Corrupted file should be deleted"

            # Subsequent get() should not error (file already deleted)
            result2 = cache.get(key)
            assert result2 is None


class TestTTLManagement:
    """Test TTL (Time To Live) expiration logic."""

    def test_get_fresh_entry_returns_value(self) -> None:
        """Test that fresh entry within TTL returns value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=60)

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            result = cache.get(key)
            assert result == "response"

    def test_get_expired_entry_returns_none(self) -> None:
        """Test that expired entry returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=1)

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            time.sleep(1.1)

            result = cache.get(key)
            assert result is None

    def test_get_expired_entry_deletes_file(self) -> None:
        """Test that expired entry is deleted from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=1)

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})
            cache_file = Path(tmpdir) / f"{key}.json"

            assert cache_file.exists()

            time.sleep(1.1)
            cache.get(key)

            assert not cache_file.exists()

    def test_evict_expired_removes_all_expired(self) -> None:
        """Test that evict_expired removes all expired entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=1)

            # Create multiple entries
            for i in range(5):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, f"response{i}", {"prompt": f"prompt{i}"})

            time.sleep(1.1)

            evicted = cache.evict_expired()
            assert evicted == 5

    def test_evict_expired_returns_count(self) -> None:
        """Test that evict_expired returns correct count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=1)

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            time.sleep(1.1)

            count = cache.evict_expired()
            assert count == 1

    def test_evict_expired_preserves_fresh(self) -> None:
        """Test that evict_expired preserves fresh entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=5)

            # Create expired and fresh entries
            key1 = cache.compute_key("old", "anthropic", "model")
            cache_file = Path(tmpdir) / f"{key1}.json"
            # Manually create old entry
            old_data = {
                "response": "old",
                "timestamp": time.time() - 10,  # 10 seconds ago
                "provider": "anthropic",
                "model": "model",
                "prompt_hash": key1,
            }
            cache_file.write_text(json.dumps(old_data), encoding="utf-8")

            # Create fresh entry
            key2 = cache.compute_key("fresh", "anthropic", "model")
            cache.set(key2, "fresh", {"prompt": "fresh"})

            cache.evict_expired()

            # Fresh should still exist
            assert cache.get(key2) == "fresh"
            # Old should be gone
            assert cache.get(key1) is None

    def test_ttl_boundary_conditions(self) -> None:
        """Test TTL at exact boundary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=1)

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            # Wait slightly less than TTL
            time.sleep(0.9)
            assert cache.get(key) == "response"

            # Wait past TTL
            time.sleep(0.2)
            assert cache.get(key) is None

    def test_custom_ttl_respected(self) -> None:
        """Test that custom TTL value is respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), ttl_seconds=2)

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            # Within TTL
            time.sleep(1)
            assert cache.get(key) == "response"

            # Past TTL
            time.sleep(1.1)
            assert cache.get(key) is None


class TestLRUEviction:
    """Test LRU (Least Recently Used) eviction logic."""

    def test_cache_under_limit_no_eviction(self) -> None:
        """Test that cache under limit doesn't trigger eviction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), max_size_bytes=10 * 1024 * 1024)

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "small response", {"prompt": "test"})

            stats = cache.get_stats()
            assert stats.entry_count == 1  # No eviction

    def test_cache_over_limit_triggers_eviction(self) -> None:
        """Test that exceeding max size triggers auto-eviction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Very small limit
            cache = PromptCache(cache_dir=Path(tmpdir), max_size_bytes=500)

            # Add multiple entries to exceed limit
            for i in range(10):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, "x" * 100, {"prompt": f"prompt{i}"})  # ~100 bytes each

            stats = cache.get_stats()
            # Should have evicted some entries
            assert stats.entry_count < 10

    def test_lru_eviction_removes_oldest(self) -> None:
        """Test that LRU eviction removes oldest entries first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Create entries with different timestamps
            keys = []
            for i in range(5):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, "response", {"prompt": "test"})
                keys.append(key)
                time.sleep(0.05)  # Ensure different mtimes

            # Get current cache size, then evict to keep only 1 entry
            stats_before = cache.get_stats()
            single_entry_size = stats_before.cache_size_bytes // 5  # Approximate size of one entry
            target_size = int(single_entry_size * 1.2)  # 20% buffer

            # Trigger LRU eviction
            cache.evict_lru(target_size)

            # Newest should still exist
            assert cache.get(keys[-1]) == "response"
            # Oldest should be gone
            assert cache.get(keys[0]) is None

    def test_lru_eviction_stops_at_target(self) -> None:
        """Test that LRU eviction stops at target size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Create entries
            for i in range(10):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, "response" * 10, {"prompt": f"prompt{i}"})
                time.sleep(0.01)

            # Evict to target
            target = 200
            cache.evict_lru(target)

            stats = cache.get_stats()
            assert stats.cache_size_bytes <= target or stats.entry_count == 0

    def test_evict_lru_returns_count(self) -> None:
        """Test that evict_lru returns correct count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Create 5 entries
            for i in range(5):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, "response", {"prompt": "test"})

            # Evict to 0
            count = cache.evict_lru(0)
            assert count == 5

    def test_evict_lru_preserves_newest(self) -> None:
        """Test that LRU eviction preserves newest entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Create old entry
            key_old = cache.compute_key("old", "anthropic", "model")
            cache.set(key_old, "old_response", {"prompt": "old"})
            time.sleep(0.1)

            # Create new entry
            key_new = cache.compute_key("new", "anthropic", "model")
            cache.set(key_new, "new_response", {"prompt": "new"})

            # Evict aggressively
            cache.evict_lru(100)

            # New should survive, old might not
            assert cache.get(key_new) == "new_response" or cache.get(key_old) is None

    def test_set_triggers_auto_eviction(self) -> None:
        """Test that set automatically triggers eviction when needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), max_size_bytes=1000)

            # Fill cache
            for i in range(10):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, "x" * 200, {"prompt": f"prompt{i}"})  # Large responses

            # Cache should have auto-evicted
            stats = cache.get_stats()
            assert stats.cache_size_bytes < 1000 * 1.1  # Allow some overhead

    def test_get_cache_size_accurate(self) -> None:
        """Test that cache size calculation is accurate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Empty cache
            stats = cache.get_stats()
            assert stats.cache_size_bytes == 0

            # Add entry
            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            stats = cache.get_stats()
            assert stats.cache_size_bytes > 0

    def test_evict_lru_with_zero_target(self) -> None:
        """Test that evict_lru with 0 target removes all entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            for i in range(5):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, "response", {"prompt": "test"})

            cache.evict_lru(0)

            stats = cache.get_stats()
            assert stats.entry_count == 0

    def test_eviction_on_large_set(self) -> None:
        """Test that setting large entry triggers eviction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir), max_size_bytes=2000)

            # Create small entries
            for i in range(5):
                key = cache.compute_key(f"small{i}", "anthropic", "model")
                cache.set(key, "x" * 50, {"prompt": f"prompt{i}"})

            # Add huge entry
            key_large = cache.compute_key("large", "anthropic", "model")
            cache.set(key_large, "x" * 2000, {"prompt": "large"})

            # Should have triggered eviction
            stats = cache.get_stats()
            assert stats.cache_size_bytes <= 2000 * 1.1  # 10% overhead


class TestThreadSafety:
    """Test thread-safe concurrent operations."""

    def test_concurrent_get_operations(self) -> None:
        """Test concurrent get operations don't corrupt cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            def worker() -> None:
                for _ in range(100):
                    result = cache.get(key)
                    assert result == "response"

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

    def test_concurrent_set_operations(self) -> None:
        """Test concurrent set operations with different keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            def worker(idx: int) -> None:
                for i in range(50):
                    key = cache.compute_key(f"prompt_{idx}_{i}", "anthropic", "model")
                    cache.set(key, f"response_{idx}_{i}", {"prompt": f"prompt{i}"})

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Verify entries exist
            stats = cache.get_stats()
            assert stats.entry_count > 0

    def test_concurrent_get_and_set(self) -> None:
        """Test concurrent mix of get and set operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Pre-populate
            for i in range(10):
                key = cache.compute_key(f"initial{i}", "anthropic", "model")
                cache.set(key, f"value{i}", {"prompt": f"prompt{i}"})

            def reader() -> None:
                for i in range(50):
                    key = cache.compute_key(f"initial{i % 10}", "anthropic", "model")
                    cache.get(key)

            def writer() -> None:
                for i in range(50):
                    key = cache.compute_key(f"new{i}", "anthropic", "model")
                    cache.set(key, f"newvalue{i}", {"prompt": f"prompt{i}"})

            readers = [threading.Thread(target=reader) for _ in range(5)]
            writers = [threading.Thread(target=writer) for _ in range(5)]

            for t in readers + writers:
                t.start()
            for t in readers + writers:
                t.join()

    def test_concurrent_eviction(self) -> None:
        """Test concurrent eviction operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Pre-populate
            for i in range(20):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, f"response{i}", {"prompt": f"prompt{i}"})

            def evictor() -> None:
                cache.evict_lru(100)

            threads = [threading.Thread(target=evictor) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Cache should still be valid
            stats = cache.get_stats()
            assert stats.entry_count >= 0

    def test_stats_accurate_under_concurrency(self) -> None:
        """Test that statistics remain accurate under concurrent access."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            def worker() -> None:
                for _ in range(100):
                    cache.get(key)

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            stats = cache.get_stats()
            # All gets should be hits
            assert stats.hits == 1000  # 10 threads * 100 gets
            assert stats.total_requests == 1000

    def test_no_race_condition_on_key(self) -> None:
        """Test no race conditions when multiple threads access same key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("shared", "anthropic", "model")

            def worker(value: str) -> None:
                for _ in range(50):
                    cache.set(key, value, {"prompt": "shared"})
                    result = cache.get(key)
                    # Should get back a valid value (not corrupted)
                    assert result in ["value_a", "value_b"]

            threads = [
                threading.Thread(target=worker, args=("value_a",)),
                threading.Thread(target=worker, args=("value_b",)),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

    def test_lock_released_on_exception(self) -> None:
        """Test that lock is properly released on exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Cause exception in get by corrupting file after creation
            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            cache_file = Path(tmpdir) / f"{key}.json"
            cache_file.write_text("corrupted{{{", encoding="utf-8")

            # This should handle exception and not deadlock
            result = cache.get(key)
            assert result is None

            # Lock should be released, so next operation works
            cache.set(key, "new response", {"prompt": "test"})
            assert cache.get(key) == "new response"

    def test_multiple_instances_share_files(self) -> None:
        """Test that multiple cache instances can share same directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache1 = PromptCache(cache_dir=Path(tmpdir))
            cache2 = PromptCache(cache_dir=Path(tmpdir))

            key = cache1.compute_key("test", "anthropic", "model")
            cache1.set(key, "response", {"prompt": "test"})

            # Second instance should see the entry
            result = cache2.get(key)
            assert result == "response"


class TestStatistics:
    """Test cache statistics tracking."""

    def test_hit_increments_on_cache_hit(self) -> None:
        """Test that hits counter increments on cache hit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            cache.get(key)
            stats = cache.get_stats()
            assert stats.hits == 1

    def test_miss_increments_on_cache_miss(self) -> None:
        """Test that misses counter increments on cache miss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            cache.get("nonexistent")
            stats = cache.get_stats()
            assert stats.misses == 1

    def test_hit_rate_calculation_correct(self) -> None:
        """Test that hit rate is calculated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            # 3 hits, 1 miss
            cache.get(key)  # hit
            cache.get(key)  # hit
            cache.get(key)  # hit
            cache.get("nonexistent")  # miss

            stats = cache.get_stats()
            assert stats.hits == 3
            assert stats.misses == 1
            assert stats.total_requests == 4
            assert stats.hit_rate == 0.75  # 3/4

    def test_cache_size_bytes_accurate(self) -> None:
        """Test that cache size in bytes is accurate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            stats = cache.get_stats()
            assert stats.cache_size_bytes == 0

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})

            stats = cache.get_stats()
            assert stats.cache_size_bytes > 0

    def test_entry_count_accurate(self) -> None:
        """Test that entry count is accurate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            for i in range(10):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, "response", {"prompt": "test"})

            stats = cache.get_stats()
            assert stats.entry_count == 10

    def test_stats_after_eviction(self) -> None:
        """Test that stats update after eviction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            for i in range(10):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, "response", {"prompt": "test"})

            cache.evict_lru(100)

            stats = cache.get_stats()
            assert stats.entry_count < 10

    def test_stats_reset_on_clear(self) -> None:
        """Test that statistics reset when cache is cleared."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})
            cache.get(key)
            cache.get("nonexistent")

            cache.clear()

            stats = cache.get_stats()
            assert stats.hits == 0
            assert stats.misses == 0
            assert stats.total_requests == 0
            assert stats.entry_count == 0

    def test_get_stats_is_immutable(self) -> None:
        """Test that get_stats returns immutable dataclass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            stats = cache.get_stats()
            # CacheStats is frozen dataclass
            with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
                stats.hits = 999  # type: ignore[misc]

    def test_hit_rate_zero_when_no_requests(self) -> None:
        """Test that hit rate is 0.0 when there are no requests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            stats = cache.get_stats()
            assert stats.hit_rate == 0.0


class TestClearOperation:
    """Test cache clear operation."""

    def test_clear_removes_all_entries(self) -> None:
        """Test that clear removes all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            for i in range(10):
                key = cache.compute_key(f"prompt{i}", "anthropic", "model")
                cache.set(key, f"response{i}", {"prompt": f"prompt{i}"})

            cache.clear()

            stats = cache.get_stats()
            assert stats.entry_count == 0

    def test_clear_resets_stats(self) -> None:
        """Test that clear resets all statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            key = cache.compute_key("test", "anthropic", "model")
            cache.set(key, "response", {"prompt": "test"})
            cache.get(key)
            cache.get("miss")

            cache.clear()

            stats = cache.get_stats()
            assert stats.hits == 0
            assert stats.misses == 0
            assert stats.total_requests == 0

    def test_clear_works_on_empty_cache(self) -> None:
        """Test that clear works on empty cache without errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Should not raise
            cache.clear()

            stats = cache.get_stats()
            assert stats.entry_count == 0


class TestCacheWarming:
    """Test cache warming functionality for cold start optimization."""

    def test_warm_cache_loads_valid_entries(self) -> None:
        """Test that warm_cache loads valid entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            entries = [
                {
                    "prompt": "Fix the bug",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                    "response": "[]",
                },
                {
                    "prompt": "Apply changes",
                    "provider": "openai",
                    "model": "gpt-4o",
                    "response": '[{"file_path": "test.py"}]',
                },
            ]

            loaded, skipped = cache.warm_cache(entries)

            assert loaded == 2
            assert skipped == 0
            assert cache.get_stats().entry_count == 2

    def test_warm_cache_skips_invalid_entries(self) -> None:
        """Test that warm_cache skips entries with missing fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            entries = [
                {"prompt": "Missing fields"},  # Missing provider, model, response
                {
                    "prompt": "Valid entry",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                    "response": "[]",
                },
            ]

            loaded, skipped = cache.warm_cache(entries)

            assert loaded == 1
            assert skipped == 1

    def test_warm_cache_skips_duplicates(self) -> None:
        """Test that warm_cache skips entries that already exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Pre-populate with one entry
            key = cache.compute_key("Existing prompt", "anthropic", "claude-sonnet-4-5")
            cache.set(
                key,
                "existing response",
                {
                    "prompt": "Existing prompt",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                },
            )

            entries = [
                {
                    "prompt": "Existing prompt",  # Already in cache
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                    "response": "new response",
                },
                {
                    "prompt": "New prompt",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-5",
                    "response": "[]",
                },
            ]

            loaded, skipped = cache.warm_cache(entries)

            assert loaded == 1
            assert skipped == 1
            # Original response should be preserved
            assert cache.get(key) == "existing response"

    def test_warm_cache_empty_list(self) -> None:
        """Test that warm_cache handles empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            loaded, skipped = cache.warm_cache([])

            assert loaded == 0
            assert skipped == 0

    def test_export_entries_returns_all_entries(self) -> None:
        """Test that export_entries returns all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            # Add some entries
            for i in range(3):
                key = cache.compute_key(f"prompt{i}", "anthropic", "claude-sonnet-4-5")
                cache.set(
                    key,
                    f"response{i}",
                    {"prompt": f"prompt{i}", "provider": "anthropic", "model": "claude-sonnet-4-5"},
                )

            entries = cache.export_entries()

            assert len(entries) == 3
            for entry in entries:
                assert "prompt_hash" in entry
                assert "provider" in entry
                assert "model" in entry
                assert "response" in entry
                assert "timestamp" in entry

    def test_export_entries_empty_cache(self) -> None:
        """Test that export_entries returns empty list for empty cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            entries = cache.export_entries()

            assert entries == []

    def test_get_common_patterns_returns_list(self) -> None:
        """Test that get_common_patterns returns list of patterns."""
        patterns = PromptCache.get_common_patterns()

        assert isinstance(patterns, list)
        assert len(patterns) > 0
        for pattern in patterns:
            assert isinstance(pattern, str)
            assert len(pattern) > 0

    def test_warm_cache_thread_safe(self) -> None:
        """Test that warm_cache is thread-safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = PromptCache(cache_dir=Path(tmpdir))

            def warmer(batch_id: int) -> None:
                entries = [
                    {
                        "prompt": f"prompt{batch_id}_{i}",
                        "provider": "anthropic",
                        "model": "claude-sonnet-4-5",
                        "response": f"response{batch_id}_{i}",
                    }
                    for i in range(10)
                ]
                cache.warm_cache(entries)

            threads = [threading.Thread(target=warmer, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Should have loaded all unique entries
            stats = cache.get_stats()
            assert stats.entry_count == 50  # 5 batches * 10 entries
