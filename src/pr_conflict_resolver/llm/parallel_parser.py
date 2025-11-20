"""Parallel LLM comment parsing for large PRs.

This module provides ThreadPoolExecutor-based parallel parsing with:
- Concurrent LLM calls for multiple comments
- Progress tracking with callbacks
- Exception aggregation
- Configurable worker count
- Thread-safe result collection

Example:
    >>> from pr_conflict_resolver.llm.parallel_parser import ParallelCommentParser
    >>> from pr_conflict_resolver.llm.factory import LLMProviderFactory
    >>>
    >>> provider = LLMProviderFactory.create_provider("openai-api-mini")
    >>> parser = ParallelCommentParser(provider, max_workers=8)
    >>> results = parser.parse_comments(comments)
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

# Import for type checking and runtime (needed for instantiation)
from pr_conflict_resolver.llm.base import ParsedChange
from pr_conflict_resolver.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class ParsingProgress:
    """Progress tracking for parallel parsing operations.

    Attributes:
        total: Total number of comments to parse
        completed: Number of comments successfully parsed
        failed: Number of comments that failed to parse
        in_progress: Number of comments currently being parsed
        changes_found: Total number of changes extracted so far
    """

    total: int
    completed: int = 0
    failed: int = 0
    in_progress: int = 0
    changes_found: int = 0

    @property
    def percent_complete(self) -> float:
        """Calculate percentage of completion."""
        if self.total == 0:
            return 100.0
        return ((self.completed + self.failed) / self.total) * 100

    def __str__(self) -> str:
        """Human-readable progress string."""
        return (
            f"Progress: {self.completed}/{self.total} completed, "
            f"{self.failed} failed, {self.changes_found} changes found "
            f"({self.percent_complete:.1f}%)"
        )


class ParallelCommentParser:
    """Parallel comment parser using ThreadPoolExecutor.

    This class provides efficient parallel parsing of GitHub PR comments
    using multiple worker threads. Each comment is parsed independently
    by an LLM provider, with results aggregated in a thread-safe manner.

    Attributes:
        provider: LLM provider to use for parsing
        max_workers: Maximum number of concurrent worker threads
        progress_callback: Optional callback for progress updates
    """

    def __init__(
        self,
        provider: LLMProvider,
        max_workers: int = 4,
        progress_callback: Callable[[ParsingProgress], None] | None = None,
    ) -> None:
        """Initialize parallel comment parser.

        Args:
            provider: LLM provider instance for parsing comments
            max_workers: Maximum number of concurrent workers (default: 4)
                Recommended: 4-8 for API-based providers, 2-4 for CLI-based
            progress_callback: Optional callback function called with progress updates

        Raises:
            ValueError: If max_workers < 1
        """
        if max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {max_workers}")

        self.provider = provider
        self.max_workers = max_workers
        self.progress_callback = progress_callback

        # Thread-safe result collection
        self._lock = threading.Lock()
        self._all_changes: list[ParsedChange] = []
        self._failed_comments: list[tuple[str, Exception]] = []

    def parse_comments(
        self,
        comments: list[str],
        timeout: float | None = 60.0,
    ) -> list[ParsedChange]:
        """Parse multiple comments in parallel.

        Args:
            comments: List of comment bodies to parse
            timeout: Maximum time in seconds for EACH comment's parsing operation.
                This is a per-future timeout applied to each comment individually,
                NOT a total batch timeout. Each comment gets the full timeout period.
                Set to None for no per-comment timeout (default: 60.0).

        Returns:
            List of ParsedChange objects extracted from all comments

        Raises:
            RuntimeError: If all comments fail to parse
            concurrent.futures.TimeoutError: If any individual comment parsing
                exceeds the per-comment timeout

        Note:
            The timeout is applied independently to each comment. If you have 10
            comments and timeout=60, each comment can take up to 60 seconds, so
            the total time could be much longer than 60 seconds if they run
            sequentially. However, with parallel execution, the wall-clock time
            will be determined by the slowest comment.

        Example:
            >>> parser = ParallelCommentParser(provider, max_workers=8)
            >>> comments = ["Fix bug in X", "Update documentation"]
            >>> # Each comment gets 60 seconds, not 60 total
            >>> changes = parser.parse_comments(comments, timeout=60.0)
            >>> print(f"Found {len(changes)} changes")
        """
        if not comments:
            logger.info("No comments to parse")
            return []

        # Initialize progress tracking
        progress = ParsingProgress(total=len(comments))
        self._report_progress(progress)

        logger.info(f"Parsing {len(comments)} comments with {self.max_workers} workers")

        # Reset result collections
        with self._lock:
            self._all_changes.clear()
            self._failed_comments.clear()

        # Submit all parsing tasks
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Create future for each comment
            future_to_comment: dict[Future[list[ParsedChange]], str] = {
                executor.submit(self._parse_single_comment, comment): comment
                for comment in comments
            }

            # Update in-progress count
            with self._lock:
                progress.in_progress = len(future_to_comment)
            self._report_progress(progress)

            # Collect results as they complete
            for future in as_completed(future_to_comment):
                comment = future_to_comment[future]

                try:
                    changes = (
                        future.result(timeout=timeout) if timeout is not None else future.result()
                    )

                    # Thread-safe result aggregation
                    with self._lock:
                        self._all_changes.extend(changes)
                        progress.completed += 1
                        progress.in_progress -= 1
                        progress.changes_found = len(self._all_changes)

                    logger.debug(f"Successfully parsed comment ({len(changes)} changes found)")

                except concurrent.futures.TimeoutError as e:
                    # Handle timeout separately from other exceptions
                    # Note: Timeout only limits how long we wait for the result.
                    # The underlying LLM call may still be running and cannot be forcibly stopped.
                    with self._lock:
                        self._failed_comments.append((comment[:100], e))
                        progress.failed += 1
                        progress.in_progress -= 1

                    logger.error(
                        f"Timeout after {timeout}s waiting for comment parsing result. "
                        f"Note: Underlying LLM call may still be running."
                    )

                except Exception as e:
                    # Record failure
                    with self._lock:
                        self._failed_comments.append((comment[:100], e))
                        progress.failed += 1
                        progress.in_progress -= 1

                    logger.warning(f"Failed to parse comment: {e.__class__.__name__}: {e}")

                finally:
                    # Report progress after each completion
                    self._report_progress(progress)

        # Log final statistics
        logger.info(
            f"Parallel parsing complete: {progress.completed} succeeded, "
            f"{progress.failed} failed, {progress.changes_found} changes found"
        )

        # Raise error if all comments failed
        if progress.completed == 0 and progress.failed > 0:
            error_summary = self._format_error_summary()
            raise RuntimeError(
                f"All {progress.failed} comments failed to parse. Errors:\n{error_summary}"
            )

        # Return all successfully parsed changes
        return self._all_changes.copy()

    def _parse_single_comment(
        self,
        comment: str,
    ) -> list[ParsedChange]:
        """Parse a single comment using the LLM provider.

        Args:
            comment: Comment body to parse

        Returns:
            List of ParsedChange objects extracted from the comment

        Raises:
            Exception: Any exception from the LLM provider

        Note:
            Timeout is handled at the executor level (future.result(timeout=...))
            not at the parser level.
        """
        # Import here to avoid circular dependency:
        # parser.py -> parallel_parser.py (for ParsingProgress type in TYPE_CHECKING)
        # parallel_parser.py -> parser.py (for UniversalLLMParser runtime usage)
        # Local import breaks the cycle by deferring until method execution.
        from pr_conflict_resolver.llm.parser import UniversalLLMParser

        # Create parser instance (lightweight, no state)
        parser = UniversalLLMParser(self.provider)

        # Parse comment (provider handles its own timeout/retry logic)
        changes = parser.parse_comment(comment)

        return changes

    def _report_progress(self, progress: ParsingProgress) -> None:
        """Report progress to callback if configured.

        Args:
            progress: Current parsing progress
        """
        if self.progress_callback:
            try:
                self.progress_callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    def _format_error_summary(self) -> str:
        """Format error summary for failed comments.

        Returns:
            Human-readable error summary string
        """
        lines = []
        for i, (comment_preview, error) in enumerate(self._failed_comments[:5], 1):
            lines.append(
                f"  {i}. Comment: '{comment_preview}...' "
                f"Error: {error.__class__.__name__}: {error}"
            )

        if len(self._failed_comments) > 5:
            lines.append(f"  ... and {len(self._failed_comments) - 5} more errors")

        return "\n".join(lines)

    @property
    def statistics(self) -> dict[str, Any]:
        """Get parsing statistics.

        Returns:
            Dictionary with parsing statistics including:
            - total_changes: Total number of changes parsed
            - failed_count: Number of failed comments
            - max_workers: Configured worker count
        """
        with self._lock:
            return {
                "total_changes": len(self._all_changes),
                "failed_count": len(self._failed_comments),
                "max_workers": self.max_workers,
            }
