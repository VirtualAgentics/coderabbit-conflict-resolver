"""Unit tests for parallel LLM comment parser.

Tests for ParallelLLMParser including rate limiting, progress tracking,
circuit breaker integration, and error handling.
"""

import itertools
import time
from unittest.mock import MagicMock

import pytest

from pr_conflict_resolver.llm.parallel_parser import (
    CommentInput,
    ParallelLLMParser,
    RateLimiter,
)
from pr_conflict_resolver.llm.resilience.circuit_breaker import CircuitState


@pytest.fixture
def sample_parsed_change_json() -> str:
    """Fixture providing a reusable JSON response for ParsedChange."""
    return """[
        {
            "file_path": "test.py",
            "start_line": 10,
            "end_line": 12,
            "new_content": "def test():\\n    pass",
            "change_type": "modification",
            "rationale": "Test change",
            "confidence": 0.9
        }
    ]"""


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_rate_limiter_initialization(self) -> None:
        """Test rate limiter initializes correctly."""
        limiter = RateLimiter(rate=10.0)
        assert limiter.rate == 10.0
        assert limiter.min_interval == 0.1

    def test_rate_limiter_invalid_rate(self) -> None:
        """Test rate limiter rejects invalid rates."""
        with pytest.raises(ValueError, match="rate must be positive"):
            RateLimiter(rate=0.0)

        with pytest.raises(ValueError, match="rate must be positive"):
            RateLimiter(rate=-1.0)

    def test_rate_limiter_enforces_rate(self) -> None:
        """Test rate limiter enforces minimum interval between calls."""
        limiter = RateLimiter(rate=10.0)  # 0.1s between calls

        start = time.monotonic()
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        elapsed = time.monotonic() - start

        # Should take at least 0.1s (with some tolerance for CI)
        assert elapsed >= 0.08, f"Expected >= 0.08s, got {elapsed:.3f}s"

    def test_rate_limiter_thread_safe(self) -> None:
        """Test rate limiter is thread-safe and serializes calls."""
        import threading

        limiter = RateLimiter(rate=10.0)  # 0.1s between calls
        timestamps: list[float] = []
        lock = threading.Lock()

        def worker() -> None:
            limiter.wait_if_needed()
            with lock:
                timestamps.append(time.monotonic())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All calls should complete without errors
        assert len(timestamps) == 5

        # Verify calls are serialized: consecutive differences should be >= 80% of interval
        timestamps_sorted = sorted(timestamps)
        min_interval = 0.1 * 0.8  # 80% of 0.1s interval
        for i in range(1, len(timestamps_sorted)):
            diff = timestamps_sorted[i] - timestamps_sorted[i - 1]
            assert (
                diff >= min_interval
            ), f"Call {i} too close to previous: {diff:.3f}s < {min_interval:.3f}s"


class TestParallelLLMParser:
    """Test ParallelLLMParser class."""

    @pytest.fixture
    def mock_provider(self) -> MagicMock:
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.generate.return_value = "[]"
        return provider

    @pytest.fixture
    def parser(self, mock_provider: MagicMock) -> ParallelLLMParser:
        """Create a ParallelLLMParser instance."""
        return ParallelLLMParser(
            provider=mock_provider,
            max_workers=2,
            rate_limit=100.0,  # High rate for fast tests
        )

    def test_parser_initialization(self, mock_provider: MagicMock) -> None:
        """Test parser initializes correctly."""
        parser = ParallelLLMParser(
            provider=mock_provider,
            max_workers=4,
            rate_limit=10.0,
        )
        assert parser.max_workers == 4
        assert parser.rate_limit == 10.0

    def test_parser_invalid_max_workers(self, mock_provider: MagicMock) -> None:
        """Test parser rejects invalid max_workers."""
        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            ParallelLLMParser(provider=mock_provider, max_workers=0)

    def test_parser_accepts_high_max_workers(self, mock_provider: MagicMock) -> None:
        """Test that high max_workers values are accepted."""
        parser = ParallelLLMParser(provider=mock_provider, max_workers=64)

        # Parser should accept high max_workers (no exception)
        assert parser.max_workers == 64

    def test_parse_comments_empty_list(self, parser: ParallelLLMParser) -> None:
        """Test parsing empty comment list raises ValueError."""
        with pytest.raises(ValueError, match="comments list cannot be empty"):
            parser.parse_comments([])

    def test_parse_comments_single_comment(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Test parsing a single comment."""
        mock_provider.generate.return_value = sample_parsed_change_json

        comments = [CommentInput(body="Test comment", file_path="test.py", line_number=1)]
        results = parser.parse_comments(comments)

        assert len(results) == 1
        assert len(results[0]) == 1
        assert results[0][0].file_path == "test.py"
        assert results[0][0].start_line == 10

    def test_parse_comments_multiple_comments(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Test parsing multiple comments."""
        mock_provider.generate.return_value = sample_parsed_change_json

        comments = [
            CommentInput(body="Comment 1", file_path="test1.py", line_number=1),
            CommentInput(body="Comment 2", file_path="test2.py", line_number=2),
            CommentInput(body="Comment 3", file_path="test3.py", line_number=3),
        ]
        results = parser.parse_comments(comments)

        assert len(results) == 3
        assert all(len(r) == 1 for r in results)

    def test_parse_comments_preserves_order(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
    ) -> None:
        """Test results are returned in same order as input."""
        # Return different file paths to verify order
        counter = itertools.count()

        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            idx = next(counter)
            return (
                f'[{{"file_path": "test{idx}.py", "start_line": 1, "end_line": 1, '
                f'"new_content": "code", "change_type": "modification", '
                f'"confidence": 0.9, "rationale": "test", "risk_level": "low"}}]'
            )

        mock_provider.generate.side_effect = mock_generate

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(5)
        ]
        results = parser.parse_comments(comments)

        assert len(results) == 5
        # Verify order is preserved
        for i, result in enumerate(results):
            assert len(result) == 1
            assert result[0].file_path == f"test{i}.py"

    def test_parse_comments_partial_failures(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Test handling of partial failures."""
        counter = itertools.count()

        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            idx = next(counter)
            if idx == 1:  # Fail second comment
                raise RuntimeError("Simulated failure")
            return sample_parsed_change_json

        mock_provider.generate.side_effect = mock_generate

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(3)
        ]
        results = parser.parse_comments(comments)

        assert len(results) == 3
        assert len(results[0]) == 1  # First succeeds
        assert len(results[1]) == 0  # Second fails
        assert len(results[2]) == 1  # Third succeeds

    def test_parse_comments_progress_callback(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Test progress callback is invoked correctly."""
        mock_provider.generate.return_value = sample_parsed_change_json

        progress_calls: list[tuple[int, int]] = []

        def progress_callback(completed: int, total: int) -> None:
            progress_calls.append((completed, total))

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(3)
        ]
        results = parser.parse_comments(comments, progress_callback=progress_callback)

        assert len(results) == 3
        assert len(progress_calls) == 3
        # Verify all expected progress invocations occurred
        assert sorted(progress_calls) == [(1, 3), (2, 3), (3, 3)]
        # Final call should be (3, 3)
        assert progress_calls[-1] == (3, 3)

    def test_parse_comments_progress_callback_exception(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Test progress callback exceptions don't break parsing."""
        mock_provider.generate.return_value = sample_parsed_change_json

        def progress_callback(completed: int, total: int) -> None:
            raise RuntimeError("Callback error")

        comments = [CommentInput(body="Comment", file_path="test.py", line_number=1)]
        # Should not raise, callback errors are caught
        results = parser.parse_comments(comments, progress_callback=progress_callback)
        assert len(results) == 1

    def test_parse_comments_circuit_breaker_open(
        self,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Test fallback to sequential when circuit breaker is open."""
        # Create a mock provider with circuit breaker
        mock_circuit_breaker = MagicMock()
        mock_circuit_breaker.state = CircuitState.OPEN

        mock_provider.circuit_state = CircuitState.OPEN
        mock_provider.circuit_breaker = mock_circuit_breaker
        mock_provider.generate.return_value = sample_parsed_change_json

        parser = ParallelLLMParser(provider=mock_provider, max_workers=4)

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(3)
        ]
        results = parser.parse_comments(comments)

        # Should still parse all comments (sequentially)
        assert len(results) == 3
        # Verify generate was called (sequential parsing)
        assert mock_provider.generate.call_count == 3
