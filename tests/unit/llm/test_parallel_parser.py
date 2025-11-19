"""Unit tests for ParallelCommentParser."""

from __future__ import annotations

import threading
import time
from unittest.mock import Mock, patch

import pytest

from pr_conflict_resolver.llm.base import ParsedChange
from pr_conflict_resolver.llm.parallel_parser import (
    ParallelCommentParser,
    ParsingProgress,
)


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, delay: float = 0.0, should_fail: bool = False) -> None:
        """Initialize mock provider.

        Args:
            delay: Simulated processing delay in seconds
            should_fail: Whether to raise exceptions
        """
        self.delay = delay
        self.should_fail = should_fail
        self.call_count = 0
        self._lock = threading.Lock()

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Mock generate method."""
        with self._lock:
            self.call_count += 1
        if self.delay > 0:
            time.sleep(self.delay)
        if self.should_fail:
            raise RuntimeError("Mock provider failure")
        return "[]"  # Empty JSON array

    def count_tokens(self, text: str) -> int:
        """Mock token counting."""
        return len(text.split())


@pytest.fixture
def mock_provider() -> MockLLMProvider:
    """Fixture for mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def mock_failing_provider() -> MockLLMProvider:
    """Fixture for mock failing LLM provider."""
    return MockLLMProvider(should_fail=True)


@pytest.fixture
def mock_slow_provider() -> MockLLMProvider:
    """Fixture for mock slow LLM provider."""
    return MockLLMProvider(delay=0.2)


class TestParsingProgress:
    """Tests for ParsingProgress dataclass."""

    def test_initial_progress(self) -> None:
        """Test initial progress state."""
        progress = ParsingProgress(total=10)
        assert progress.total == 10
        assert progress.completed == 0
        assert progress.failed == 0
        assert progress.in_progress == 0
        assert progress.changes_found == 0

    def test_percent_complete(self) -> None:
        """Test percentage calculation."""
        progress = ParsingProgress(total=10, completed=5, failed=2)
        assert progress.percent_complete == 70.0

    def test_percent_complete_zero_total(self) -> None:
        """Test percentage when total is zero."""
        progress = ParsingProgress(total=0)
        assert progress.percent_complete == 100.0

    def test_str_representation(self) -> None:
        """Test string representation."""
        progress = ParsingProgress(total=10, completed=5, failed=2, changes_found=15)
        result = str(progress)
        assert "5/10" in result
        assert "2 failed" in result
        assert "15 changes" in result
        assert "70.0%" in result


class TestParallelCommentParser:
    """Tests for ParallelCommentParser."""

    def test_initialization(self, mock_provider: MockLLMProvider) -> None:
        """Test parser initialization."""
        parser = ParallelCommentParser(mock_provider, max_workers=4)
        assert parser.provider == mock_provider
        assert parser.max_workers == 4
        assert parser.progress_callback is None

    def test_initialization_with_callback(self, mock_provider: MockLLMProvider) -> None:
        """Test parser initialization with callback."""
        callback = Mock()
        parser = ParallelCommentParser(mock_provider, max_workers=4, progress_callback=callback)
        assert parser.progress_callback == callback

    def test_initialization_invalid_max_workers(self, mock_provider: MockLLMProvider) -> None:
        """Test that invalid max_workers raises ValueError."""
        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            ParallelCommentParser(mock_provider, max_workers=0)

        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            ParallelCommentParser(mock_provider, max_workers=-1)

    @patch("pr_conflict_resolver.llm.parser.UniversalLLMParser")
    def test_parse_comments_basic(
        self, mock_parser_class: Mock, mock_provider: MockLLMProvider
    ) -> None:
        """Test basic parallel parsing with multiple inputs."""
        # Setup mock parser to return different changes for each comment
        mock_parser_instance = Mock()
        mock_parser_class.return_value = mock_parser_instance

        changes_1 = [
            ParsedChange(
                file_path="file1.py",
                start_line=1,
                end_line=2,
                new_content="code1",
                change_type="modification",
                confidence=0.9,
                rationale="test1",
            )
        ]
        changes_2 = [
            ParsedChange(
                file_path="file2.py",
                start_line=3,
                end_line=4,
                new_content="code2",
                change_type="modification",
                confidence=0.95,
                rationale="test2",
            )
        ]

        # Mock parser returns different changes for each call
        mock_parser_instance.parse_comment.side_effect = [changes_1, changes_2]

        parser = ParallelCommentParser(mock_provider, max_workers=2)
        comments = ["comment 1", "comment 2"]
        results = parser.parse_comments(comments)

        # Verify results are combined and ordered
        assert len(results) == 2
        assert results[0].file_path == "file1.py"
        assert results[1].file_path == "file2.py"

        # Verify parser was called for each comment
        assert mock_parser_instance.parse_comment.call_count == 2

    def test_parse_comments_empty_list(self, mock_provider: MockLLMProvider) -> None:
        """Test parsing empty comment list returns empty result."""
        parser = ParallelCommentParser(mock_provider, max_workers=2)
        results = parser.parse_comments([])
        assert results == []

    @patch("pr_conflict_resolver.llm.parser.UniversalLLMParser")
    def test_progress_callback_invoked(
        self, mock_parser_class: Mock, mock_provider: MockLLMProvider
    ) -> None:
        """Test that progress callback is invoked with expected progress counts."""
        mock_parser_instance = Mock()
        mock_parser_class.return_value = mock_parser_instance
        mock_parser_instance.parse_comment.return_value = []

        # Track progress updates
        progress_updates: list[ParsingProgress] = []

        def capture_progress(progress: ParsingProgress) -> None:
            # Create a copy to avoid reference issues
            progress_updates.append(
                ParsingProgress(
                    total=progress.total,
                    completed=progress.completed,
                    failed=progress.failed,
                    in_progress=progress.in_progress,
                    changes_found=progress.changes_found,
                )
            )

        parser = ParallelCommentParser(
            mock_provider, max_workers=2, progress_callback=capture_progress
        )
        parser.parse_comments(["comment 1", "comment 2"])

        # Verify progress callback was called
        assert len(progress_updates) > 0

        # First update should show total
        assert progress_updates[0].total == 2

        # Final update should show completion
        final_progress = progress_updates[-1]
        assert final_progress.completed + final_progress.failed == 2
        assert final_progress.in_progress == 0

    @patch("pr_conflict_resolver.llm.parser.UniversalLLMParser")
    def test_timeout_behavior(
        self, mock_parser_class: Mock, mock_slow_provider: MockLLMProvider
    ) -> None:
        """Test timeout behavior by injecting a slow parser."""
        from concurrent.futures import TimeoutError as FutureTimeout

        mock_parser_instance = Mock()
        mock_parser_class.return_value = mock_parser_instance

        # Simulate parsing that raises TimeoutError
        mock_parser_instance.parse_comment.side_effect = FutureTimeout("Timeout")

        parser = ParallelCommentParser(mock_slow_provider, max_workers=2)

        # Should fail all comments due to timeout
        with pytest.raises(RuntimeError, match="All .* comments failed to parse"):
            parser.parse_comments(["comment 1"], timeout=0.1)

    @patch("pr_conflict_resolver.llm.parser.UniversalLLMParser")
    def test_fallback_on_partial_failure(
        self, mock_parser_class: Mock, mock_provider: MockLLMProvider
    ) -> None:
        """Test that parser returns successful results when some parsing fails."""
        mock_parser_instance = Mock()
        mock_parser_class.return_value = mock_parser_instance

        success_change = ParsedChange(
            file_path="file1.py",
            start_line=1,
            end_line=2,
            new_content="code",
            change_type="modification",
            confidence=0.9,
            rationale="test",
        )

        # First comment succeeds, second fails
        mock_parser_instance.parse_comment.side_effect = [
            [success_change],
            RuntimeError("Parse failed"),
        ]

        parser = ParallelCommentParser(mock_provider, max_workers=2)
        results = parser.parse_comments(["comment 1", "comment 2"])

        # Should return the successful result
        assert len(results) == 1
        assert results[0].file_path == "file1.py"

    @patch("pr_conflict_resolver.llm.parser.UniversalLLMParser")
    def test_all_failures_raises_runtime_error(
        self, mock_parser_class: Mock, mock_failing_provider: MockLLMProvider
    ) -> None:
        """Test that RuntimeError is raised when all comments fail."""
        mock_parser_instance = Mock()
        mock_parser_class.return_value = mock_parser_instance
        mock_parser_instance.parse_comment.side_effect = RuntimeError("Parse failed")

        parser = ParallelCommentParser(mock_failing_provider, max_workers=2)

        with pytest.raises(RuntimeError, match="All .* comments failed to parse"):
            parser.parse_comments(["comment 1", "comment 2"])

    def test_max_workers_respected(self, mock_provider: MockLLMProvider) -> None:
        """Test that max_workers limit is respected."""
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0
        lock = threading.Lock()

        def track_concurrency(*args: object, **kwargs: object) -> list[ParsedChange]:
            nonlocal concurrent_count, max_concurrent
            with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)

            time.sleep(0.05)  # Simulate work

            with lock:
                concurrent_count -= 1

            return []

        # Use real executor to verify actual concurrent behavior
        with patch("pr_conflict_resolver.llm.parser.UniversalLLMParser") as mock_parser_class:
            mock_parser_instance = Mock()
            mock_parser_class.return_value = mock_parser_instance
            mock_parser_instance.parse_comment.side_effect = track_concurrency

            parser = ParallelCommentParser(mock_provider, max_workers=2)
            parser.parse_comments(["c1", "c2", "c3", "c4"])

        # Verify concurrency was limited to max_workers=2
        assert max_concurrent <= 2

    def test_statistics_property(self, mock_provider: MockLLMProvider) -> None:
        """Test statistics property returns expected data."""
        parser = ParallelCommentParser(mock_provider, max_workers=4)

        stats = parser.statistics
        assert "total_changes" in stats
        assert "failed_count" in stats
        assert "max_workers" in stats
        assert stats["max_workers"] == 4
        assert stats["total_changes"] == 0
        assert stats["failed_count"] == 0

    def test_format_error_summary(self, mock_provider: MockLLMProvider) -> None:
        """Test error summary formatting."""
        parser = ParallelCommentParser(mock_provider, max_workers=2)

        # Manually add some failed comments for testing
        parser._failed_comments = [
            ("comment 1", ValueError("error 1")),
            ("comment 2", RuntimeError("error 2")),
        ]

        summary = parser._format_error_summary()
        assert "comment 1" in summary
        assert "ValueError" in summary
        assert "comment 2" in summary
        assert "RuntimeError" in summary

    def test_format_error_summary_truncation(self, mock_provider: MockLLMProvider) -> None:
        """Test error summary truncates after 5 errors."""
        parser = ParallelCommentParser(mock_provider, max_workers=2)

        # Add 10 failed comments
        parser._failed_comments = [(f"comment {i}", ValueError(f"error {i}")) for i in range(10)]

        summary = parser._format_error_summary()
        assert "... and 5 more errors" in summary

    def test_progress_callback_exception_handling(self, mock_provider: MockLLMProvider) -> None:
        """Test that exceptions in progress callback are caught."""

        def failing_callback(progress: ParsingProgress) -> None:
            raise RuntimeError("Callback failed")

        parser = ParallelCommentParser(
            mock_provider, max_workers=2, progress_callback=failing_callback
        )

        with patch("pr_conflict_resolver.llm.parser.UniversalLLMParser") as mock_parser_class:
            mock_parser_instance = Mock()
            mock_parser_class.return_value = mock_parser_instance
            mock_parser_instance.parse_comment.return_value = []

            # Should not raise despite callback failure
            results = parser.parse_comments(["comment 1"])
            assert results == []
