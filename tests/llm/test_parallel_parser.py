"""Unit tests for parallel LLM comment parser.

Tests for ParallelLLMParser including rate limiting, progress tracking,
circuit breaker integration, and error handling.
"""

import re
from unittest.mock import MagicMock, patch

import pytest

from review_bot_automator.llm.base import ParsedChange
from review_bot_automator.llm.parallel_parser import (
    CommentInput,
    ParallelLLMParser,
    RateLimiter,
)
from review_bot_automator.llm.resilience.circuit_breaker import CircuitState
from tests.conftest import (
    SyncExecutor,
    create_exception_injecting_executor,
    fake_as_completed,
)

ResultTuple = tuple[int, list[ParsedChange]]


def _extract_comment_index(prompt: str) -> int:
    """Extract comment index from prompt body.

    Parses 'Comment N' pattern first, falls back to 'testN.py' pattern.
    Returns -1 if no match found.
    """
    match = re.search(r"Comment (\d+)", prompt)
    if match:
        return int(match.group(1))
    match = re.search(r"test(\d+)\.py", prompt)
    if match:
        return int(match.group(1))
    return -1


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
            "confidence": 0.9,
            "risk_level": "low"
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

    def test_rate_limiter_enforces_rate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rate limiter enforces minimum interval between calls."""
        limiter = RateLimiter(rate=10.0)  # 0.1s between calls

        fake_time = 1.0

        def fake_monotonic() -> float:
            return fake_time

        def fake_sleep(dt: float) -> None:
            nonlocal fake_time
            fake_time += dt

        monkeypatch.setattr(
            "review_bot_automator.llm.parallel_parser.time.monotonic", fake_monotonic
        )
        monkeypatch.setattr("review_bot_automator.llm.parallel_parser.time.sleep", fake_sleep)

        limiter.wait_if_needed()
        limiter.wait_if_needed()
        elapsed = fake_time - 1.0

        # Should advance by exactly the enforced interval (0.1s)
        assert elapsed == pytest.approx(0.1, rel=1e-6)

    def test_rate_limiter_thread_safe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rate limiter is thread-safe and serializes calls."""
        import threading

        limiter = RateLimiter(rate=10.0)  # 0.1s between calls
        fake_time = 1.0
        lock = threading.Lock()

        def fake_monotonic() -> float:
            with lock:
                return fake_time

        def fake_sleep(dt: float) -> None:
            nonlocal fake_time
            with lock:
                fake_time += dt

        monkeypatch.setattr(
            "review_bot_automator.llm.parallel_parser.time.monotonic", fake_monotonic
        )
        monkeypatch.setattr("review_bot_automator.llm.parallel_parser.time.sleep", fake_sleep)

        timestamps: list[float] = []

        def worker() -> None:
            limiter.wait_if_needed()
            with lock:
                timestamps.append(fake_time - 1.0)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(timestamps) == 5

        timestamps_sorted = sorted(timestamps)
        for i in range(1, len(timestamps_sorted)):
            diff = timestamps_sorted[i] - timestamps_sorted[i - 1]
            assert diff >= limiter.min_interval - 1e-6

    def test_rate_limiter_reserves_future_slot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rate limiter updates last-call timestamp before sleeping."""
        limiter = RateLimiter(rate=10.0)  # 0.1s interval

        times = iter([1.0, 1.02, 1.15])
        monkeypatch.setattr(
            "review_bot_automator.llm.parallel_parser.time.monotonic", lambda: next(times)
        )

        sleep_calls: list[float] = []
        monkeypatch.setattr(
            "review_bot_automator.llm.parallel_parser.time.sleep", sleep_calls.append
        )

        limiter.wait_if_needed()  # First call at t=1.0, no sleep, reserves slot at 1.0
        limiter.wait_if_needed()  # Second call at t=1.02, sleeps to 1.1, reserves slot at 1.1
        limiter.wait_if_needed()  # Third call at t=1.15, sleeps to 1.2 (verifies slot at 1.1)

        # Verify behavior through observable effects (sleep durations) not private state
        assert len(sleep_calls) == 2, "Expected rate limiter to sleep on 2nd and 3rd calls"
        assert pytest.approx(sleep_calls[0], rel=1e-2) == 0.08  # 1.1 - 1.02
        assert pytest.approx(sleep_calls[1], rel=1e-2) == 0.05  # 1.2 - 1.15


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

    def test_parser_invalid_rate_limit(self, mock_provider: MagicMock) -> None:
        """Test parser rejects invalid rate_limit values."""
        with pytest.raises(ValueError, match="rate must be positive"):
            ParallelLLMParser(provider=mock_provider, rate_limit=0.0)

        with pytest.raises(ValueError, match="rate must be positive"):
            ParallelLLMParser(provider=mock_provider, rate_limit=-1.0)

    def test_parser_rejects_high_max_workers(self, mock_provider: MagicMock) -> None:
        """Test that high max_workers values are rejected (security limit)."""
        with pytest.raises(ValueError, match="cannot exceed 32"):
            ParallelLLMParser(provider=mock_provider, max_workers=64)

    def test_parser_accepts_max_workers_at_limit(self, mock_provider: MagicMock) -> None:
        """Test that max_workers at exactly 32 is accepted."""
        parser = ParallelLLMParser(provider=mock_provider, max_workers=32)
        assert parser.max_workers == 32

    def test_parse_comments_empty_list(self, parser: ParallelLLMParser) -> None:
        """Test parsing empty comment list returns empty results."""
        assert parser.parse_comments([]) == []

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
        assert mock_provider.generate.call_count == 1

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
        assert mock_provider.generate.call_count == 3

    def test_parse_comments_preserves_order(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
    ) -> None:
        """Test results are returned in same order as input."""

        # Extract index from comment body to avoid dependency on call order
        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            idx = _extract_comment_index(prompt)
            if idx == -1:
                idx = 0
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
        # Verify order is preserved (independent of provider call order)
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

        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            idx = _extract_comment_index(prompt)
            if idx == 1:  # Fail comment with index 1
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
        # Verify all expected progress invocations occurred (order-independent)
        assert sorted(progress_calls) == [(1, 3), (2, 3), (3, 3)]

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

    def test_progress_callback_called_on_failures(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Progress callback receives updates even when parsing fails."""

        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            idx = _extract_comment_index(prompt)
            if idx == 0:
                raise RuntimeError("Simulated failure")
            return sample_parsed_change_json

        mock_provider.generate.side_effect = mock_generate

        progress_calls: list[tuple[int, int]] = []

        def progress_callback(completed: int, total: int) -> None:
            progress_calls.append((completed, total))

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(2)
        ]
        results = parser.parse_comments(comments, progress_callback=progress_callback)

        assert len(results[0]) == 0  # Failed comment returns empty list
        assert len(results[1]) == 1  # Second comment succeeds
        # Use sorted comparison as parallel execution order is non-deterministic
        assert sorted(progress_calls) == sorted([(1, 2), (2, 2)])

    def test_parse_comments_failure_branch_sync_executor(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test partial-failure handling where worker internally catches exceptions.

        This test exercises the scenario where parse_single_comment catches
        exceptions internally and returns (idx, []) for failed comments,
        while neighboring comments succeed. Uses a synchronous executor
        to ensure deterministic execution order.

        Note: The actual future.result() exception path is tested separately
        in test_parse_comments_future_result_exception using future.set_exception().
        """
        monkeypatch.setattr(
            "review_bot_automator.llm.parallel_parser.ThreadPoolExecutor",
            SyncExecutor,
        )
        monkeypatch.setattr(
            "review_bot_automator.llm.parallel_parser.as_completed", fake_as_completed
        )

        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            idx = _extract_comment_index(prompt)
            if idx == 1:
                raise RuntimeError("boom")
            return sample_parsed_change_json

        mock_provider.generate.side_effect = mock_generate

        progress_calls: list[tuple[int, int]] = []

        def progress_callback(completed: int, total: int) -> None:
            progress_calls.append((completed, total))

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(2)
        ]

        results = parser.parse_comments(comments, progress_callback=progress_callback)
        assert len(results[0]) == 1
        assert results[1] == []
        assert progress_calls == [(1, 2), (2, 2)]

    def test_parse_sequential_progress_callback_success(
        self,
        mock_provider: MagicMock,
    ) -> None:
        """_parse_sequential invokes progress callback on success."""
        parser = ParallelLLMParser(provider=mock_provider)
        comments = [
            CommentInput(body="Comment 0", file_path="test.py", line_number=1),
            CommentInput(body="Comment 1", file_path="test.py", line_number=2),
        ]

        progress_calls: list[tuple[int, int]] = []

        with patch.object(parser, "parse_comment", return_value=[MagicMock()]):
            results = parser._parse_sequential(
                comments, progress_callback=lambda c, t: progress_calls.append((c, t))
            )

        assert len(results) == 2
        assert progress_calls == [(1, 2), (2, 2)]

    def test_parse_sequential_progress_callback_failure_branch(
        self,
        mock_provider: MagicMock,
    ) -> None:
        """_parse_sequential invokes progress callback even when parsing fails."""
        parser = ParallelLLMParser(provider=mock_provider, fallback_to_regex=True)
        comments = [
            CommentInput(body="Comment 0", file_path="test.py", line_number=1),
            CommentInput(body="Comment 1", file_path="test.py", line_number=2),
        ]

        progress_calls: list[tuple[int, int]] = []

        with patch.object(
            parser,
            "parse_comment",
            side_effect=([MagicMock()], RuntimeError("sequential failure")),
        ):
            results = parser._parse_sequential(
                comments, progress_callback=lambda c, t: progress_calls.append((c, t))
            )

        assert len(results) == 2
        assert results[1] == []
        assert progress_calls == [(1, 2), (2, 2)]

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

    def test_parse_comments_future_result_exception(
        self,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Test exception handling when future.result() raises in as_completed loop."""
        parser = ParallelLLMParser(provider=mock_provider, fallback_to_regex=True)
        mock_provider.generate.return_value = sample_parsed_change_json

        # Create executor that injects exception for index 1
        FailingExecutor = create_exception_injecting_executor(
            fail_indices={1},
            exception_factory=lambda: RuntimeError("Future cancelled"),
        )

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(3)
        ]

        with (
            patch("review_bot_automator.llm.parallel_parser.ThreadPoolExecutor", FailingExecutor),
            patch("review_bot_automator.llm.parallel_parser.as_completed", fake_as_completed),
        ):
            results = parser.parse_comments(comments)

        assert len(results) == 3
        assert len(results[0]) == 1
        assert len(results[1]) == 0
        assert len(results[2]) == 1

    def test_parse_comments_failure_no_fallback_raises(
        self,
        mock_provider: MagicMock,
    ) -> None:
        """Ensure exceptions surface when fallback_to_regex is False."""
        parser = ParallelLLMParser(provider=mock_provider, fallback_to_regex=False)
        mock_provider.generate.side_effect = RuntimeError("LLM failure")

        comments = [
            CommentInput(body="Comment 0", file_path="test.py", line_number=1),
        ]

        with pytest.raises(RuntimeError, match="LLM failure"):
            parser.parse_comments(comments)

    def test_parse_sequential_exception_handling(
        self,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Test exception handling in _parse_sequential."""
        # Create parser with fallback_to_regex=True (default)
        parser = ParallelLLMParser(provider=mock_provider, fallback_to_regex=True)

        # First comment succeeds, second fails, third succeeds
        mock_provider.generate.side_effect = [
            sample_parsed_change_json,
            RuntimeError("LLM API error"),
            sample_parsed_change_json,
        ]

        # Mock circuit breaker to force sequential parsing
        mock_provider.circuit_state = CircuitState.OPEN
        mock_provider.circuit_breaker = MagicMock()

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(3)
        ]
        results = parser.parse_comments(comments)

        # Should handle exceptions and return empty list for failed comment
        assert len(results) == 3
        assert len(results[0]) == 1  # First succeeds
        assert len(results[1]) == 0  # Second fails (exception caught)
        assert len(results[2]) == 1  # Third succeeds

    def test_parse_sequential_no_fallback_raises(
        self,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Test that _parse_sequential re-raises when fallback_to_regex=False."""
        # Create parser with fallback_to_regex=False
        parser = ParallelLLMParser(provider=mock_provider, fallback_to_regex=False)

        # First comment succeeds, second fails
        mock_provider.generate.side_effect = [
            sample_parsed_change_json,
            RuntimeError("LLM API error"),
        ]

        # Mock circuit breaker to force sequential parsing
        mock_provider.circuit_state = CircuitState.OPEN
        mock_provider.circuit_breaker = MagicMock()

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(2)
        ]

        # Should re-raise exception when fallback_to_regex=False
        with pytest.raises(RuntimeError, match="LLM API error"):
            parser.parse_comments(comments)
