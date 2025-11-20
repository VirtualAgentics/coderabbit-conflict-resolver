"""Universal LLM-powered comment parser.

This module implements the core parsing logic that uses LLM providers to extract
code changes from CodeRabbit review comments. The parser:
- Accepts any comment format (diff blocks, suggestions, natural language)
- Uses prompt templates to guide the LLM
- Returns structured ParsedChange objects
- Handles errors gracefully with optional fallback
- Filters results by confidence threshold

The parser is provider-agnostic and works with any LLMProvider implementation.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from pr_conflict_resolver.llm.base import LLMParser, ParsedChange
from pr_conflict_resolver.llm.prompts import PARSE_COMMENT_PROMPT
from pr_conflict_resolver.llm.providers.base import LLMProvider

# Import kept in TYPE_CHECKING to avoid circular import:
# parser.py -> parallel_parser.py -> parser.py (for UniversalLLMParser)
if TYPE_CHECKING:
    from pr_conflict_resolver.llm.parallel_parser import ParsingProgress

logger = logging.getLogger(__name__)


class UniversalLLMParser(LLMParser):
    """LLM-powered universal comment parser.

    This parser uses LLM providers to extract code changes from any CodeRabbit
    comment format. It handles:
    - Diff blocks (```diff with @@ headers)
    - Suggestion blocks (```suggestion)
    - Natural language descriptions
    - Multi-option suggestions

    The parser validates LLM output against the ParsedChange schema and filters
    by confidence threshold to ensure quality results.

    Examples:
        >>> from pr_conflict_resolver.llm.providers.openai_api import OpenAIAPIProvider
        >>> provider = OpenAIAPIProvider(api_key="sk-...")
        >>> parser = UniversalLLMParser(provider, confidence_threshold=0.7)
        >>> changes = parser.parse_comment("Apply this fix: ...", file_path="test.py")

    Attributes:
        provider: LLM provider instance for text generation
        fallback_to_regex: If True, return empty list on failure (enables fallback)
        confidence_threshold: Minimum confidence score (0.0-1.0) to accept changes
    """

    def __init__(
        self,
        provider: LLMProvider,
        fallback_to_regex: bool = True,
        confidence_threshold: float = 0.5,
        max_tokens: int = 2000,
    ) -> None:
        """Initialize universal LLM parser.

        Args:
            provider: LLM provider instance implementing LLMProvider protocol
            fallback_to_regex: If True, return empty list on failure to trigger
                regex fallback. If False, raise exception on parsing errors.
            confidence_threshold: Minimum confidence (0.0-1.0) to accept a change.
                Lower threshold accepts more changes but with potentially lower quality.
                Recommended: 0.5 for balanced results, 0.7 for high quality only.
            max_tokens: Maximum tokens for LLM response generation. Default 2000 is
                sufficient for most PR comments while keeping costs low. Increase for
                very long comments with many changes.

        Raises:
            ValueError: If confidence_threshold is not in [0.0, 1.0]
        """
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be in [0.0, 1.0], got {confidence_threshold}"
            )

        self.provider = provider
        self.fallback_to_regex = fallback_to_regex
        self.confidence_threshold = confidence_threshold
        self.max_tokens = max_tokens

        logger.info(
            "Initialized UniversalLLMParser: fallback=%s, threshold=%s, max_tokens=%s",
            fallback_to_regex,
            confidence_threshold,
            max_tokens,
        )

    def parse_comment(
        self,
        comment_body: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ) -> list[ParsedChange]:
        """Parse comment using LLM to extract code changes.

        This method:
        1. Builds a prompt with comment body and context
        2. Sends prompt to LLM provider
        3. Parses JSON response into ParsedChange objects
        4. Validates and filters by confidence threshold
        5. Returns structured changes or empty list on failure

        Args:
            comment_body: Raw comment text from GitHub (markdown format)
            file_path: Optional file path for context (helps LLM with ambiguous comments)
            line_number: Optional line number where comment was posted

        Returns:
            List of ParsedChange objects meeting confidence threshold.
            Empty list if:
            - No changes found in comment
            - LLM parsing failed and fallback_to_regex=True
            - All changes filtered out by confidence threshold

        Raises:
            RuntimeError: If parsing fails and fallback_to_regex=False
            ValueError: If comment_body is None or empty

        Note:
            The method logs all parsing failures for debugging. Check logs
            if you're not getting expected results.
        """
        if not comment_body:
            raise ValueError("comment_body cannot be None or empty")

        try:
            # Build prompt with context
            prompt = PARSE_COMMENT_PROMPT.format(
                comment_body=comment_body,
                file_path=file_path or "unknown",
                line_number=line_number or "unknown",
            )

            logger.debug(
                f"Parsing comment: file={file_path}, line={line_number}, "
                f"body_length={len(comment_body)}"
            )

            # Generate response from LLM
            response = self.provider.generate(prompt, max_tokens=self.max_tokens)

            logger.debug(f"LLM response length: {len(response)} characters")

            # Parse JSON response
            try:
                changes_data = json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(
                    f"LLM returned invalid JSON: {response[:200]}... "
                    f"(truncated, total {len(response)} chars)"
                )
                raise RuntimeError(f"Invalid JSON from LLM: {e}") from e

            # Validate response is a list
            if not isinstance(changes_data, list):
                logger.error(f"LLM returned non-list: {type(changes_data).__name__}")
                raise RuntimeError(f"LLM must return JSON array, got {type(changes_data).__name__}")

            # Convert to ParsedChange objects with validation
            parsed_changes = []
            for idx, change_dict in enumerate(changes_data):
                try:
                    # ParsedChange.__post_init__ validates all fields
                    change = ParsedChange(**change_dict)

                    # Filter by confidence threshold
                    if change.confidence < self.confidence_threshold:
                        logger.info(
                            f"Filtered change {idx+1}/{len(changes_data)}: "
                            f"confidence {change.confidence:.2f} < "
                            f"threshold {self.confidence_threshold}"
                        )
                        continue

                    parsed_changes.append(change)
                    logger.debug(
                        f"Parsed change {idx+1}/{len(changes_data)}: "
                        f"{change.file_path}:{change.start_line}-{change.end_line} "
                        f"(confidence={change.confidence:.2f}, risk={change.risk_level})"
                    )

                except (TypeError, ValueError) as e:
                    logger.warning(
                        f"Invalid change format from LLM at index {idx}: {change_dict}. "
                        f"Error: {e}"
                    )
                    continue

            logger.info(
                f"LLM parsed {len(parsed_changes)}/{len(changes_data)} changes "
                f"(threshold={self.confidence_threshold})"
            )

            return parsed_changes

        except Exception as e:
            logger.error(f"LLM parsing failed: {type(e).__name__}: {e}")

            if self.fallback_to_regex:
                logger.info("Returning empty list to trigger regex fallback")
                return []
            else:
                raise RuntimeError(f"LLM parsing failed: {e}") from e

    def parse_comments_parallel(
        self,
        comments: list[str],
        max_workers: int = 4,
        timeout: float | None = 60.0,
        progress_callback: Callable[[ParsingProgress], None] | None = None,
    ) -> list[ParsedChange]:
        """Parse multiple comments in parallel using concurrent workers.

        This method provides significant performance improvements for large PRs
        with many comments. Speedup is typically 3-4x with 8 workers on 50+ comments.

        Args:
            comments: List of comment bodies to parse
            max_workers: Maximum number of concurrent worker threads (default: 4)
                Recommended: 4-8 for API providers, 2-4 for CLI providers
            timeout: Maximum time in seconds for each LLM call (default: 60.0)
            progress_callback: Optional callback receiving ParsingProgress updates

        Returns:
            List of ParsedChange objects from all successfully parsed comments

        Raises:
            RuntimeError: If all comments fail to parse
            ValueError: If comments list is empty or None

        Example:
            >>> parser = UniversalLLMParser(provider)
            >>> comments = ["Fix bug in X", "Update docs", ...]
            >>> changes = parser.parse_comments_parallel(comments, max_workers=8)
            >>> print(f"Found {len(changes)} changes from {len(comments)} comments")

        Note:
            - Falls back to sequential parsing on error
            - Each comment parsed independently (order not preserved)
            - Thread-safe result aggregation
            - Progress callback called after each comment completes
        """
        if not comments:
            raise ValueError("comments list cannot be empty or None")

        # Validate max_workers type first, then value
        if not isinstance(max_workers, int):
            raise ValueError(f"max_workers must be an integer, got: {type(max_workers).__name__}")
        if max_workers <= 0:
            raise ValueError(f"max_workers must be positive, got: {max_workers}")

        # Local import to avoid circular dependency at runtime
        # (moved here because parallel_parser imports UniversalLLMParser)
        from pr_conflict_resolver.llm.parallel_parser import ParallelCommentParser

        logger.info(f"Parsing {len(comments)} comments in parallel with {max_workers} workers")

        try:
            # Create parallel parser with this instance as the provider
            parallel_parser = ParallelCommentParser(
                provider=self.provider,
                max_workers=max_workers,
                progress_callback=progress_callback,
            )

            # Parse all comments concurrently
            all_changes = parallel_parser.parse_comments(
                comments=comments,
                timeout=timeout,
            )

            logger.info(f"Parallel parsing completed: {len(all_changes)} total changes found")

            return all_changes

        except Exception as e:
            logger.error(f"Parallel parsing failed: {e}. Falling back to sequential parsing.")

            # Fallback to sequential parsing (best-effort, no per-comment timeouts)
            all_changes = []
            successful_parses = 0
            failed_parses = 0
            last_error: Exception | None = None

            # Parse comments sequentially without timeout enforcement
            for comment in comments:
                try:
                    changes = self.parse_comment(comment)
                    all_changes.extend(changes)
                    successful_parses += 1
                except Exception as comment_error:
                    logger.warning(
                        f"Failed to parse comment in sequential fallback: {comment_error}"
                    )
                    failed_parses += 1
                    last_error = comment_error

            # Log summary of fallback results
            logger.info(
                f"Sequential fallback completed: {successful_parses} successful, "
                f"{failed_parses} failed out of {len(comments)} comments"
            )

            # If every comment failed, raise exception instead of returning empty list
            if failed_parses == len(comments):
                logger.error("All comments failed to parse in fallback mode")
                if last_error:
                    raise RuntimeError(
                        f"Failed to parse all {len(comments)} comments. "
                        f"Last error ({type(last_error).__name__}): {last_error}"
                    ) from last_error
                else:
                    raise RuntimeError(f"Failed to parse all {len(comments)} comments") from None

            return all_changes

    def set_confidence_threshold(self, threshold: float) -> None:
        """Update confidence threshold dynamically.

        Useful for:
        - Adjusting quality requirements per file type
        - Lowering threshold for exploratory parsing
        - Raising threshold for production changes

        Args:
            threshold: New confidence threshold (0.0-1.0)

        Raises:
            ValueError: If threshold not in valid range
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be in [0.0, 1.0], got {threshold}")

        old_threshold = self.confidence_threshold
        self.confidence_threshold = threshold
        logger.info(f"Updated confidence threshold: {old_threshold} -> {threshold}")
