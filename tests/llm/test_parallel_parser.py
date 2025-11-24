"""Unit tests for parallel LLM comment parser.

Tests for ParallelLLMParser including rate limiting, progress tracking,
circuit breaker integration, and error handling.
"""

from collections.abc import Callable, Iterable
from types import TracebackType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from pr_conflict_resolver.llm.base import ParsedChange
from pr_conflict_resolver.llm.parallel_parser import (
    CommentInput,
    ParallelLLMParser,
    RateLimiter,
)
from pr_conflict_resolver.llm.resilience.circuit_breaker import CircuitState

ResultTuple = tuple[int, list[ParsedChange]]


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
            "pr_conflict_resolver.llm.parallel_parser.time.monotonic", fake_monotonic
        )
        monkeypatch.setattr("pr_conflict_resolver.llm.parallel_parser.time.sleep", fake_sleep)

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
            return fake_time

        def fake_sleep(dt: float) -> None:
            nonlocal fake_time
            with lock:
                fake_time += dt

        monkeypatch.setattr(
            "pr_conflict_resolver.llm.parallel_parser.time.monotonic", fake_monotonic
        )
        monkeypatch.setattr("pr_conflict_resolver.llm.parallel_parser.time.sleep", fake_sleep)

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
            assert diff == pytest.approx(0.1, rel=1e-6)

    def test_rate_limiter_reserves_future_slot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test rate limiter updates last-call timestamp before sleeping."""
        limiter = RateLimiter(rate=10.0)  # 0.1s interval

        times = iter([1.0, 1.02])
        monkeypatch.setattr(
            "pr_conflict_resolver.llm.parallel_parser.time.monotonic", lambda: next(times)
        )

        sleep_calls: list[float] = []
        monkeypatch.setattr(
            "pr_conflict_resolver.llm.parallel_parser.time.sleep", sleep_calls.append
        )

        limiter.wait_if_needed()  # First call should not sleep
        limiter.wait_if_needed()  # Second call should compute delay and sleep once

        assert sleep_calls, "Expected rate limiter to sleep on second call"
        assert pytest.approx(limiter._last_call_time, rel=1e-6) == 1.1
        assert pytest.approx(sleep_calls[0], rel=1e-2) == 0.08


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

        # Extract index from comment body to avoid dependency on call order
        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            # Extract index from comment body in prompt (stable input data)
            import re

            match = re.search(r"Comment (\d+)", prompt)
            if match:
                idx = int(match.group(1))
            else:
                # Fallback: try to extract from file_path in prompt
                match = re.search(r"test(\d+)\.py", prompt)
                idx = int(match.group(1)) if match else 0
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
            import re

            match = re.search(r"Comment (\d+)", prompt)
            idx = int(match.group(1)) if match else -1
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

    def test_progress_callback_called_on_failures(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
    ) -> None:
        """Progress callback receives updates even when parsing fails."""

        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            import re

            match = re.search(r"Comment (\d+)", prompt)
            idx = int(match.group(1)) if match else -1
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
        assert progress_calls == [(1, 2), (2, 2)]

    def test_parse_comments_failure_branch_sync_executor(
        self,
        parser: ParallelLLMParser,
        mock_provider: MagicMock,
        sample_parsed_change_json: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cover failure branch by running executor synchronously."""

        class ImmediateFuture:
            def __init__(
                self, result: ResultTuple | None = None, exc: Exception | None = None
            ) -> None:
                self._result = result
                self._exc = exc

            def result(self) -> ResultTuple:
                if self._exc is not None:
                    raise self._exc
                assert self._result is not None
                return self._result

        class SynchronousExecutor:
            def __init__(self, max_workers: int) -> None:
                self._futures: list[ImmediateFuture] = []

            def __enter__(self) -> "SynchronousExecutor":
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                return None

            def submit(
                self,
                fn: Callable[[int, CommentInput], ResultTuple],
                idx: int,
                comment: CommentInput,
            ) -> ImmediateFuture:
                try:
                    value = fn(idx, comment)
                    future = ImmediateFuture(result=value)
                except Exception as exc:  # pragma: no cover - defensive
                    future = ImmediateFuture(exc=exc)
                self._futures.append(future)
                return future

        def fake_as_completed(
            futures: Iterable[ImmediateFuture] | dict[Any, ImmediateFuture],
        ) -> list[ImmediateFuture]:
            if isinstance(futures, dict):
                return list(futures.keys())
            return list(futures)

        monkeypatch.setattr(
            "pr_conflict_resolver.llm.parallel_parser.ThreadPoolExecutor", SynchronousExecutor
        )
        monkeypatch.setattr(
            "pr_conflict_resolver.llm.parallel_parser.as_completed", fake_as_completed
        )

        def mock_generate(prompt: str, max_tokens: int = 2000) -> str:
            import re

            match = re.search(r"Comment (\d+)", prompt)
            idx = int(match.group(1)) if match else -1
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
        from concurrent.futures import Future

        parser = ParallelLLMParser(provider=mock_provider, fallback_to_regex=True)
        mock_provider.generate.return_value = sample_parsed_change_json

        FutureResult = Future[tuple[int, list[ParsedChange]]]

        class DummyExecutor:
            def __init__(self, max_workers: int) -> None:
                self.futures: list[FutureResult] = []

            def __enter__(self) -> "DummyExecutor":
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: TracebackType | None,
            ) -> None:
                return None

            def submit(
                self,
                fn: Callable[[int, CommentInput], tuple[int, list[ParsedChange]]],
                idx: int,
                comment: CommentInput,
            ) -> FutureResult:
                future: FutureResult = Future()
                if idx == 1:
                    future.set_exception(RuntimeError("Future cancelled"))
                else:
                    result = fn(idx, comment)
                    future.set_result(result)
                self.futures.append(future)
                return future

        def fake_executor_factory(max_workers: int) -> DummyExecutor:
            return DummyExecutor(max_workers)

        def fake_as_completed(
            futures: Iterable[FutureResult] | dict[Any, FutureResult],
        ) -> list[FutureResult]:
            if isinstance(futures, dict):
                return list(futures.keys())
            return list(futures)

        comments = [
            CommentInput(body=f"Comment {i}", file_path=f"test{i}.py", line_number=i)
            for i in range(3)
        ]

        with (
            patch(
                "pr_conflict_resolver.llm.parallel_parser.ThreadPoolExecutor", fake_executor_factory
            ),
            patch("pr_conflict_resolver.llm.parallel_parser.as_completed", fake_as_completed),
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
