"""Core conflict resolution logic extracted and generalized from ContextForge Memory.

This module provides the main ConflictResolver class that handles intelligent
conflict resolution for GitHub PR comments, specifically designed for CodeRabbit
but extensible to other code review bots.
"""

import contextlib
import hashlib
import logging
import os
import stat
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from os import PathLike
from pathlib import Path
from typing import Any

from pr_conflict_resolver.analysis.conflict_detector import ConflictDetector
from pr_conflict_resolver.core.models import (
    Change,
    Conflict,
    FileType,
    Resolution,
    ResolutionResult,
)
from pr_conflict_resolver.handlers.json_handler import JsonHandler
from pr_conflict_resolver.handlers.toml_handler import TomlHandler
from pr_conflict_resolver.handlers.yaml_handler import YamlHandler
from pr_conflict_resolver.integrations.github import GitHubCommentExtractor
from pr_conflict_resolver.llm.base import LLMParser, ParsedChange
from pr_conflict_resolver.security.input_validator import InputValidator
from pr_conflict_resolver.strategies.priority_strategy import PriorityStrategy
from pr_conflict_resolver.utils.path_utils import resolve_file_path
from pr_conflict_resolver.utils.text import normalize_content


class WorkspaceError(ValueError):
    """Exception raised when workspace_root is invalid or inaccessible.

    Indicates that the provided workspace_root path does not exist, is not a
    directory, or cannot be accessed. Also raised when the current working
    directory cannot be determined.
    """


class ConflictResolver:
    """Main conflict resolver class."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        workspace_root: str | PathLike[str] | None = None,
        llm_parser: LLMParser | None = None,
    ) -> None:
        """Create a ConflictResolver configured with optional settings.

        Args:
            config: Optional configuration dictionary used to customize resolver behavior
                (for example, strategy parameters or handler options). If not provided,
                defaults to an empty dict.
            workspace_root: Root directory for validating absolute file paths. Accepts a
                string path or any path-like object. If None, defaults to current working
                directory.
            llm_parser: Optional LLM parser for extracting changes from natural language
                comments. If provided, enables LLM-powered parsing with automatic fallback
                to regex parsing. If None, uses regex-only parsing (backward compatible).

        New in Phase 1 (LLM Foundation):
            The llm_parser parameter enables advanced comment parsing beyond regex patterns,
            supporting natural language descriptions, diff blocks without markers, and
            context-based suggestions. When LLM parsing fails, automatically falls back
            to regex-based extraction for reliability.
        """
        self.config = config or {}
        # Convert input to Path, handling None and PathLike objects
        try:
            workspace_path = Path(workspace_root) if workspace_root is not None else Path.cwd()
        except OSError as e:
            raise WorkspaceError(f"Failed to determine workspace root: {e}") from e

        # Resolve to absolute path
        resolved_path = workspace_path.resolve()

        # Validate path exists and is a directory using single stat() call to avoid TOCTOU
        try:
            path_stat = os.stat(resolved_path)
            if not stat.S_ISDIR(path_stat.st_mode):
                raise WorkspaceError(f"workspace_root must be a directory: {resolved_path}")
        except OSError as e:
            raise WorkspaceError(
                f"workspace_root does not exist or is inaccessible: {resolved_path}"
            ) from e

        self.workspace_root: Path = resolved_path
        self.logger = logging.getLogger(__name__)
        self.conflict_detector = ConflictDetector()
        self.handlers = {
            FileType.JSON: JsonHandler(self.workspace_root),
            FileType.YAML: YamlHandler(self.workspace_root),
            FileType.TOML: TomlHandler(self.workspace_root),
        }
        self.strategy = PriorityStrategy(self.config)
        self.github_extractor = GitHubCommentExtractor()
        self.llm_parser = llm_parser  # Optional LLM parser for advanced comment parsing

    def detect_file_type(self, path: str) -> FileType:
        """Determine the file type based on the file path's extension.

        Returns:
            FileType: The FileType corresponding to the path's extension. Returns
                FileType.PLAINTEXT when the extension is unknown or missing.
        """
        suffix = Path(path).suffix.lower()
        mapping = {
            ".py": FileType.PYTHON,
            ".ts": FileType.TYPESCRIPT,
            ".tsx": FileType.TYPESCRIPT,
            ".js": FileType.TYPESCRIPT,
            ".jsx": FileType.TYPESCRIPT,
            ".json": FileType.JSON,
            ".yaml": FileType.YAML,
            ".yml": FileType.YAML,
            ".toml": FileType.TOML,
        }
        return mapping.get(suffix, FileType.PLAINTEXT)

    def generate_fingerprint(self, path: str, start: int, end: int, content: str) -> str:
        """Create a short deterministic fingerprint that identifies a proposed change in a file.

        Args:
            path (str): File path the change targets.
            start (int): Starting line number of the change.
            end (int): Ending line number of the change.
            content (str): Suggested replacement content for the specified range.

        Returns:
            str: 16-character hexadecimal fingerprint (SHA-256 digest) derived from the
                path, line range, and normalized content.
        """
        normalized = normalize_content(content)
        content_str = f"{path}:{start}:{end}:{normalized}"
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def extract_changes_from_comments(self, comments: list[dict[str, Any]]) -> list[Change]:
        """Extracts suggested code changes from GitHub PR comment bodies.

        Parsing Strategy (Phase 1 - LLM Foundation):
            1. If LLM parser is configured: Try LLM parsing first for each comment
            2. If LLM returns no changes or is not configured: Fall back to regex parsing
            3. This provides both broad coverage (LLM) and reliability (regex fallback)

        The method parses each comment using available parsing methods (LLM and/or regex)
        and constructs Change objects with metadata, fingerprints, and file types.

        Args:
            comments (list[dict[str, Any]]): List of GitHub comment dictionaries. Each
                comment may contain keys used by this function:
                  - "path": repository file path the comment targets (required to extract).
                  - "body": comment text (used to parse suggestion code blocks).
                  - "start_line" or "original_start_line": optional starting line of the suggestion.
                  - "line" or "original_line": ending line of the suggestion (required).
                  - "html_url": URL of the comment.
                  - "user": dict containing "login" for author username.

        Returns:
            list[Change]: A list of Change objects representing parsed suggestions. Each
            Change contains path, start_line, end_line, content, metadata (url, author,
            source, parsing_method), fingerprint, file_type, and LLM metadata (if parsed
            via LLM).
        """
        changes = []

        for comment in comments:
            path = comment.get("path")
            if not path:
                continue

            # Try LLM parsing first (if configured)
            llm_changes = self._extract_changes_with_llm(comment)
            if llm_changes:
                changes.extend(llm_changes)
                continue  # Skip regex parsing if LLM succeeded

            # Fall back to regex parsing
            suggestion_blocks = self._parse_comment_suggestions(comment.get("body", ""))

            for block in suggestion_blocks:
                start_line = comment.get("start_line") or comment.get("original_start_line")
                end_line = comment.get("line") or comment.get("original_line")

                if not end_line:
                    continue
                if start_line is None:
                    start_line = end_line

                file_type = self.detect_file_type(path)
                fingerprint = self.generate_fingerprint(
                    path, start_line, end_line, block["content"]
                )

                change = Change(
                    path=path,
                    start_line=int(start_line),
                    end_line=int(end_line),
                    content=block["content"],
                    metadata={
                        "url": comment.get("html_url", ""),
                        "author": (comment.get("user") or {}).get("login", ""),
                        "source": "suggestion",
                        "option_label": block.get("option_label"),
                    },
                    fingerprint=fingerprint,
                    file_type=file_type,
                    parsing_method="regex",  # Mark as regex-parsed for tracking
                )
                changes.append(change)

        return changes

    def _parse_comment_suggestions(self, body: str) -> list[dict[str, Any]]:
        """Extract suggestion blocks from a GitHub-style comment body.

        Args:
            body (str): Raw comment text which may contain fenced suggestion code blocks.

        Returns:
            list[dict[str, Any]]: A list of suggestion blocks where each dict contains:
                - `content` (str): The code suggested inside the ```suggestion``` fence.
                - `option_label` (str | None): An optional label extracted from bolded text
                    immediately preceding the suggestion (e.g., "**Option A**"), or `None` if
                    absent.
                - `context` (str): Up to 100 characters of text immediately before the
                    suggestion block to provide surrounding context.
        """
        import re

        # Regex pattern for suggestion fences
        suggestion_pattern = re.compile(r"```suggestion\s*\n(.*?)\n```", re.DOTALL)

        blocks = []
        for match in suggestion_pattern.finditer(body):
            content = match.group(1).rstrip("\n")
            start_pos = match.start()

            # Look for option headers in preceding text
            preceding_text = body[max(0, start_pos - 200) : start_pos]
            option_label = None

            # Check for option markers
            option_pattern = re.compile(r"\*\*([^*]+)\*\*\s*$", re.MULTILINE)
            option_matches = list(option_pattern.finditer(preceding_text))
            if option_matches:
                last_match = option_matches[-1]
                option_label = last_match.group(1).strip().rstrip(":")

            blocks.append(
                {
                    "content": content,
                    "option_label": option_label,
                    "context": (
                        preceding_text[-100:] if len(preceding_text) > 100 else preceding_text
                    ),
                }
            )

        return blocks

    def _extract_changes_with_llm(self, comment: dict[str, Any]) -> list[Change]:
        """Extract changes from comment using LLM parser.

        This method uses the configured LLM parser to extract code changes from
        any comment format (diff blocks, suggestions, natural language, etc.).
        Returns empty list if LLM parser is not configured or parsing fails.

        Args:
            comment: GitHub comment dictionary containing:
                - "body": comment text to parse
                - "path": target file path
                - "start_line" or "original_start_line": optional starting line
                - "line" or "original_line": ending line number
                - "html_url": comment URL
                - "user": dict with "login" for author

        Returns:
            list[Change]: List of Change objects extracted via LLM, or empty list
                if LLM parsing is not available or fails.

        Note:
            This method is designed for use with automatic fallback. If it returns
            an empty list, the caller should fall back to regex-based extraction.
        """
        if not self.llm_parser:
            return []

        body = comment.get("body", "")
        if not body:
            return []

        path = comment.get("path")
        if not path:
            return []

        # Extract line context from comment
        line = comment.get("line") or comment.get("original_line")
        if not line:
            return []

        try:
            # Parse comment with LLM
            parsed_changes = self.llm_parser.parse_comment(
                comment_body=body,
                file_path=path,
                line_number=line,
            )

            # Convert ParsedChange objects to Change objects
            changes = []
            for parsed_change in parsed_changes:
                change = self._convert_parsed_change_to_change(
                    parsed_change=parsed_change,
                    comment=comment,
                )
                changes.append(change)

            if changes:
                self.logger.info(
                    f"LLM extracted {len(changes)} change(s) from comment on {path}:{line}"
                )

            return changes

        except Exception as e:
            self.logger.warning(f"LLM parsing failed for comment on {path}:{line}: {e}")
            return []

    def _convert_parsed_change_to_change(
        self, parsed_change: ParsedChange, comment: dict[str, Any]
    ) -> Change:
        """Convert ParsedChange from LLM to Change model.

        This method performs the conversion from the LLM parser's output format
        (ParsedChange) to the resolver's Change model, adding all necessary
        metadata and computed fields.

        Args:
            parsed_change: ParsedChange object from LLM parser containing:
                - file_path, start_line, end_line, new_content
                - change_type, confidence, rationale, risk_level
            comment: Original GitHub comment dict for extracting metadata

        Returns:
            Change: Fully populated Change object with:
                - Core fields from ParsedChange
                - Computed fingerprint and file_type
                - Comment metadata (url, author)
                - LLM metadata (confidence, provider, rationale, risk)
        """
        file_type = self.detect_file_type(parsed_change.file_path)
        fingerprint = self.generate_fingerprint(
            parsed_change.file_path,
            parsed_change.start_line,
            parsed_change.end_line,
            parsed_change.new_content,
        )

        # Determine LLM provider from parser (if available)
        llm_provider = None
        if hasattr(self.llm_parser, "provider"):
            provider = self.llm_parser.provider  # type: ignore[union-attr]
            if hasattr(provider, "model"):
                llm_provider = provider.model

        return Change(
            path=parsed_change.file_path,
            start_line=parsed_change.start_line,
            end_line=parsed_change.end_line,
            content=parsed_change.new_content,
            metadata={
                "url": comment.get("html_url", ""),
                "author": (comment.get("user") or {}).get("login", ""),
                "source": "llm_parsed",
                "llm_confidence": parsed_change.confidence,
                "llm_provider": llm_provider,
                "parsing_method": "llm",
                "change_rationale": parsed_change.rationale,
                "risk_level": parsed_change.risk_level,
            },
            fingerprint=fingerprint,
            file_type=file_type,
            # LLM metadata fields (also in metadata dict for backward compatibility)
            llm_confidence=parsed_change.confidence,
            llm_provider=llm_provider,
            parsing_method="llm",
            change_rationale=parsed_change.rationale,
            risk_level=parsed_change.risk_level,
        )

    def detect_conflicts(self, changes: list[Change]) -> list[Conflict]:
        """Identify conflicts among the provided list of changes across files.

        Returns:
            conflicts (list[Conflict]): Detected Conflict objects for any overlapping or
                conflicting changes.
        """
        conflicts = []

        # Group changes by file
        changes_by_file: dict[str, list[Change]] = {}
        for change in changes:
            if change.path not in changes_by_file:
                changes_by_file[change.path] = []
            changes_by_file[change.path].append(change)

        # Check for conflicts within each file
        for file_path, file_changes in changes_by_file.items():
            file_conflicts = self._detect_file_conflicts(file_path, file_changes)
            conflicts.extend(file_conflicts)

        return conflicts

    def _detect_file_conflicts(self, file_path: str, changes: list[Change]) -> list[Conflict]:
        """Detects and returns conflicts among proposed changes within a single file.

        For each change that overlaps in line range with one or more other changes,
        constructs a Conflict containing the involved changes, the classified conflict
        type, assessed severity, and calculated overlap percentage.

        Returns:
            list[Conflict]: A list of Conflict objects representing each detected
                overlapping change group; empty list if no conflicts are found.
        """
        conflicts = []

        # Sort changes by line number
        sorted_changes = sorted(changes, key=lambda c: (c.start_line, c.end_line))

        # Check for overlaps
        for i, change1 in enumerate(sorted_changes):
            conflicting_changes = []

            for j, change2 in enumerate(sorted_changes):
                if i >= j:  # Skip self and already processed
                    continue

                # Check for line range overlap
                if self._has_line_overlap(change1, change2):
                    conflicting_changes.append(change2)

            if conflicting_changes:
                # Create conflict
                all_changes = [change1, *conflicting_changes]
                conflict_type = self._classify_conflict_type(change1, conflicting_changes)
                severity = self._assess_conflict_severity(change1, conflicting_changes)
                overlap_percentage = self._calculate_overlap_percentage(
                    change1, conflicting_changes
                )

                # Use union of all involved changes for conflict line_range
                min_start = min(c.start_line for c in all_changes)
                max_end = max(c.end_line for c in all_changes)

                conflict = Conflict(
                    file_path=file_path,
                    line_range=(min_start, max_end),
                    changes=all_changes,
                    conflict_type=conflict_type,
                    severity=severity,
                    overlap_percentage=overlap_percentage,
                )
                conflicts.append(conflict)

        return conflicts

    def _has_line_overlap(self, change1: Change, change2: Change) -> bool:
        """Determine whether two changes overlap in their line ranges.

        Returns:
            True if the line ranges overlap, False otherwise.
        """
        return not (change1.end_line < change2.start_line or change2.end_line < change1.start_line)

    def _classify_conflict_type(self, change1: Change, conflicting_changes: list[Change]) -> str:
        """Determine the category of conflict between changes.

        Args:
            change1 (Change): The primary change to classify against other changes.
            conflicting_changes (list[Change]): Other changes that overlap with `change1`.

        Returns:
            str: One of:
                - "exact" — the conflicting change covers the same start and end lines as `change1`.
                - "major" — a single conflicting change fully contains `change1`'s range.
                - "partial" — a single conflicting change partially overlaps `change1`'s range.
                - "multiple" — more than one conflicting change overlaps `change1`.
        """
        if len(conflicting_changes) == 1:
            change2 = conflicting_changes[0]
            if change1.start_line == change2.start_line and change1.end_line == change2.end_line:
                return "exact"
            elif (
                change1.start_line <= change2.start_line and change1.end_line >= change2.end_line
            ) or (
                change2.start_line <= change1.start_line and change2.end_line >= change1.end_line
            ):
                return "major"
            else:
                return "partial"
        else:
            return "multiple"

    def _assess_conflict_severity(self, change1: Change, conflicting_changes: list[Change]) -> str:
        """Determine conflict severity based on the contents of the involved changes.

        Args:
            change1 (Change): The primary change participating in the conflict.
            conflicting_changes (list[Change]): Other changes that overlap or conflict with the
                primary change.

        Returns:
            str: `"high"` if any involved change contains security-related keywords,
            `"medium"` if none are security-related but any contain syntax/error-related keywords,
            `"low"` otherwise.
        """
        # Check for security-related changes
        security_keywords = ["security", "vulnerability", "auth", "token", "key", "password"]
        for change in [change1, *conflicting_changes]:
            content_lower = change.content.lower()
            if any(keyword in content_lower for keyword in security_keywords):
                return "high"

        # Check for syntax errors
        syntax_keywords = ["error", "fix", "bug", "issue"]
        for change in [change1, *conflicting_changes]:
            content_lower = change.content.lower()
            if any(keyword in content_lower for keyword in syntax_keywords):
                return "medium"

        return "low"

    def _calculate_overlap_percentage(
        self, change1: Change, conflicting_changes: list[Change]
    ) -> float:
        """Compute percentage of lines covered by >=2 changes over the union of all lines.

        Uses a line-sweep algorithm to accurately compute overlaps across multiple changes.

        Args:
            change1: The primary change to analyze.
            conflicting_changes: List of changes that conflict with change1.

        Returns:
            float: Percentage (0.0-100.0) of lines covered by 2+ changes relative to total
                union; `float(0)` if fewer than 2 changes or no overlap.
        """
        changes = [change1, *conflicting_changes]
        if len(changes) < 2:
            return float(0)

        # Build sweep events for inclusive ranges
        events: list[tuple[int, int]] = []
        for c in changes:
            start = min(c.start_line, c.end_line)
            end = max(c.start_line, c.end_line)
            events.append((start, +1))
            events.append((end + 1, -1))

        events.sort()
        active = 0
        prev: int | None = None
        union_len = 0
        overlap_len = 0

        for pos, delta in events:
            if prev is not None:
                span = pos - prev
                if active > 0:
                    union_len += span
                if active > 1:
                    overlap_len += span
            active += delta
            prev = pos

        if union_len <= 0:
            return float(0)

        return (overlap_len / union_len) * 100.0

    def separate_changes_by_conflict_status(
        self, changes: list[Change], conflicts: list[Conflict]
    ) -> tuple[list[Change], list[Change]]:
        """Separate changes into conflicting and non-conflicting sets.

        A change is considered conflicting if its fingerprint appears in any of the
        provided conflicts. Non-conflicting changes can be safely applied independently
        without resolution logic.

        Args:
            changes: List of all changes extracted from PR comments.
            conflicts: List of detected conflicts containing overlapping changes.

        Returns:
            Tuple of (conflicting_changes, non_conflicting_changes) where:
                - conflicting_changes: Changes that appear in at least one conflict
                - non_conflicting_changes: Changes that don't appear in any conflict
        """
        # Extract all fingerprints from conflicting changes
        conflicting_fingerprints: set[str] = set()
        for conflict in conflicts:
            for change in conflict.changes:
                conflicting_fingerprints.add(change.fingerprint)

        # Partition changes based on whether they're in conflicts
        conflicting_changes: list[Change] = []
        non_conflicting_changes: list[Change] = []

        for change in changes:
            if change.fingerprint in conflicting_fingerprints:
                conflicting_changes.append(change)
            else:
                non_conflicting_changes.append(change)

        return conflicting_changes, non_conflicting_changes

    def apply_changes(
        self,
        changes: list[Change],
        validate: bool = True,
        parallel: bool = False,
        max_workers: int = 4,
    ) -> tuple[list[Change], list[Change], list[tuple[Change, str]]]:
        """Apply a batch of changes and track results.

        Applies each change either sequentially or in parallel (if enabled) and tracks
        which succeeded, were skipped, or failed. This method provides more granular
        tracking than apply_resolutions() and is designed for applying non-conflicting
        changes directly.

        Args:
            changes: List of changes to apply.
            validate: If True, validate each change before applying (default: True).
                When False, skips validation for performance (use with caution).
            parallel: If True, apply changes in parallel using ThreadPoolExecutor (default: False).
            max_workers: Maximum number of worker threads for parallel processing (default: 4).
                Only used when parallel=True. Recommended range: 4-8 for optimal performance.

        Returns:
            Tuple of three lists:
                - applied: Changes that were successfully applied
                - skipped: Changes that were skipped (validation failed but not an error)
                - failed: Tuples of (change, error_message) for changes that failed to apply

        Example:
            >>> # Sequential processing
            >>> applied, skipped, failed = resolver.apply_changes(non_conflicting_changes)
            >>> print(f"Applied: {len(applied)}, Skipped: {len(skipped)}, Failed: {len(failed)}")
            >>>
            >>> # Parallel processing (faster for large batches)
            >>> applied, skipped, failed = resolver.apply_changes(
            ...     non_conflicting_changes, parallel=True, max_workers=8
            ... )
        """
        if parallel:
            return self._apply_changes_parallel(changes, validate, max_workers)
        else:
            return self._apply_changes_sequential(changes, validate)

    def _apply_changes_sequential(
        self, changes: list[Change], validate: bool
    ) -> tuple[list[Change], list[Change], list[tuple[Change, str]]]:
        """Apply changes sequentially (internal helper).

        Args:
            changes: List of changes to apply.
            validate: If True, validate each change before applying.

        Returns:
            Tuple of (applied, skipped, failed) lists.
        """
        applied: list[Change] = []
        skipped: list[Change] = []
        failed: list[tuple[Change, str]] = []

        for change in changes:
            # Optional validation step
            if validate:
                is_valid, reason = self._validate_change(change)
                if not is_valid:
                    self.logger.debug(
                        f"Skipping change {change.fingerprint} in {change.path}: {reason}"
                    )
                    skipped.append(change)
                    continue

            # Attempt to apply the change
            try:
                success = self._apply_change(change)
                if success:
                    self.logger.info(
                        f"Applied change {change.fingerprint} to {change.path} "
                        f"(lines {change.start_line}-{change.end_line})"
                    )
                    applied.append(change)
                else:
                    error_msg = "Application returned False (unspecified failure)"
                    self.logger.warning(
                        f"Failed to apply change {change.fingerprint} to {change.path}: {error_msg}"
                    )
                    failed.append((change, error_msg))
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                self.logger.error(
                    f"Exception applying change {change.fingerprint} to {change.path}: {error_msg}"
                )
                failed.append((change, error_msg))

        return applied, skipped, failed

    def _apply_changes_parallel(
        self, changes: list[Change], validate: bool, max_workers: int
    ) -> tuple[list[Change], list[Change], list[tuple[Change, str]]]:
        """Apply changes in parallel with file-level serialization to prevent race conditions.

        Groups changes by file path and processes each file's changes sequentially, while
        processing different files in parallel. This prevents concurrent modifications to
        the same file. Results are accumulated in completion order (not input order).
        Parallel processing is particularly beneficial for large batches of changes (>20-30).

        Args:
            changes: List of changes to apply.
            validate: If True, validate each change before applying.
            max_workers: Maximum number of worker threads.

        Returns:
            Tuple of (applied, skipped, failed) lists.
        """
        # Group changes by file path to prevent same-file race conditions
        from collections import defaultdict

        changes_by_file: dict[str, list[Change]] = defaultdict(list)
        for change in changes:
            changes_by_file[change.path].append(change)

        # Thread-safe collections with locks
        applied_lock = threading.Lock()
        skipped_lock = threading.Lock()
        failed_lock = threading.Lock()

        applied: list[Change] = []
        skipped: list[Change] = []
        failed: list[tuple[Change, str]] = []

        def process_file_changes(file_changes: list[Change]) -> None:
            """Process all changes for a single file sequentially (thread worker function)."""
            for change in file_changes:
                # Optional validation step
                if validate:
                    is_valid, reason = self._validate_change(change)
                    if not is_valid:
                        self.logger.debug(
                            f"Skipping change {change.fingerprint} in {change.path}: {reason}"
                        )
                        with skipped_lock:
                            skipped.append(change)
                        continue

                # Attempt to apply the change
                try:
                    success = self._apply_change(change)
                    if success:
                        self.logger.info(
                            f"Applied change {change.fingerprint} to {change.path} "
                            f"(lines {change.start_line}-{change.end_line})"
                        )
                        with applied_lock:
                            applied.append(change)
                    else:
                        error_msg = "Application returned False (unspecified failure)"
                        self.logger.warning(
                            "Failed to apply change %s to %s: %s",
                            change.fingerprint,
                            change.path,
                            error_msg,
                        )
                        with failed_lock:
                            failed.append((change, error_msg))
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {e}"
                    self.logger.error(
                        "Exception applying change %s to %s: %s",
                        change.fingerprint,
                        change.path,
                        error_msg,
                    )
                    with failed_lock:
                        failed.append((change, error_msg))

        # Process different files in parallel (each file's changes are processed sequentially)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit one task per file and maintain a mapping to track which changes
            # each future is responsible for (following the future_to_url pattern
            # from Python's concurrent.futures documentation)
            future_to_changes: dict[Future[None], list[Change]] = {}

            for file_changes in changes_by_file.values():
                future = executor.submit(process_file_changes, file_changes)
                future_to_changes[future] = file_changes

            # Wait for all tasks to complete
            for future in as_completed(future_to_changes):
                # Propagate any exceptions from worker threads
                try:
                    future.result()
                except Exception as e:
                    # Identify which changes failed due to this worker thread exception
                    affected_changes = future_to_changes[future]
                    error_msg = f"Worker thread exception: {type(e).__name__}: {e}"
                    self.logger.error(
                        f"Worker thread raised exception while processing {len(affected_changes)} "
                        f"change(s): {error_msg}"
                    )

                    # Add all affected changes to the failed list with thread-safe access
                    with failed_lock:
                        for change in affected_changes:
                            failed.append((change, error_msg))

        return applied, skipped, failed

    def _validate_change(self, change: Change) -> tuple[bool, str]:
        """Validate a change before applying it.

        Checks if the change can be safely applied by delegating to the appropriate
        handler's validate_change() method if available, or performing basic checks
        for plaintext files.

        Args:
            change: Change to validate.

        Returns:
            Tuple of (is_valid, reason) where:
                - is_valid: True if change is valid and can be applied
                - reason: Empty string if valid, otherwise explanation of why invalid
        """
        # Get appropriate handler
        handler = self.handlers.get(change.file_type)

        # If handler exists and has validate_change method, use it
        if handler and hasattr(handler, "validate_change"):
            try:
                return handler.validate_change(
                    change.path, change.content, change.start_line, change.end_line
                )
            except Exception as e:
                return False, f"Validation error: {e}"

        # For plaintext or when handler doesn't have validation, do basic checks
        # Validate path
        if not InputValidator.validate_file_path(
            change.path, base_dir=str(self.workspace_root), allow_absolute=True
        ):
            return False, "Invalid or unsafe file path"

        # Check file exists
        try:
            file_path = resolve_file_path(
                change.path,
                self.workspace_root,
                allow_absolute=True,
                validate_workspace=True,
                enforce_containment=True,
            )
            if not file_path.exists():
                return False, "Target file does not exist"

            # Check for symlinks
            for component in (file_path, *file_path.parents):
                try:
                    if component.is_symlink():
                        return False, "Symlink detected in path hierarchy"
                except OSError as e:
                    return False, f"OSError checking symlink in path hierarchy: {e}"

        except (ValueError, OSError) as e:
            return False, f"Path resolution error: {e}"

        # Basic validation passed
        return True, ""

    def apply_changes_with_rollback(
        self,
        changes: list[Change],
        validate: bool = True,
        parallel: bool = False,
        max_workers: int = 4,
    ) -> tuple[list[Change], list[Change], list[tuple[Change, str]]]:
        """Apply changes with automatic rollback on failure.

        This method wraps apply_changes() with RollbackManager to provide automatic
        rollback capability. If any change fails to apply or an exception occurs,
        all changes are rolled back to the pre-application state.

        Args:
            changes: List of changes to apply.
            validate: If True, validate each change before applying (default: True).
            parallel: If True, apply changes in parallel using ThreadPoolExecutor (default: False).
            max_workers: Maximum number of worker threads for parallel processing (default: 4).

        Returns:
            Tuple of three lists (same as apply_changes()):
                - applied: Changes that were successfully applied
                - skipped: Changes that were skipped due to validation failures
                - failed: Tuples of (change, error_message) for changes that failed

        Raises:
            RollbackError: If rollback operation fails after a change application failure.

        Example:
            >>> try:
            >>>     applied, skipped, failed = resolver.apply_changes_with_rollback(
            ...         changes, parallel=True, max_workers=8
            ...     )
            >>>     if failed:
            >>>         print(f"Failed to apply {len(failed)} changes (rolled back)")
            >>> except RollbackError as e:
            >>>     print(f"Rollback failed: {e}")
        """
        from pr_conflict_resolver.core.rollback import RollbackError, RollbackManager

        try:
            rollback_manager = RollbackManager(self.workspace_root)
        except (ValueError, RollbackError) as e:
            self.logger.warning(
                f"Could not initialize RollbackManager: {e}. "
                "Proceeding without rollback support."
            )
            # Fall back to regular apply_changes without rollback
            return self.apply_changes(
                changes, validate=validate, parallel=parallel, max_workers=max_workers
            )

        try:
            # Create checkpoint before applying changes
            checkpoint_id = rollback_manager.create_checkpoint()
            self.logger.info(f"Created rollback checkpoint: {checkpoint_id}")

            # Apply changes
            applied, skipped, failed = self.apply_changes(
                changes, validate=validate, parallel=parallel, max_workers=max_workers
            )

            # Check if any changes failed
            if failed:
                # Some changes failed, rollback
                self.logger.warning(f"{len(failed)} changes failed. Rolling back all changes...")
                rollback_manager.rollback()
                # Return empty applied list because, although some changes were applied earlier,
                # rollback_manager.rollback() reverted them all, leaving no net applied changes
                return [], skipped, failed
            else:
                # All changes succeeded, commit checkpoint
                self.logger.info("All changes applied successfully. Committing checkpoint.")
                rollback_manager.commit()
                return applied, skipped, failed

        except Exception as e:
            # Unexpected exception, attempt rollback
            self.logger.error(f"Exception during change application: {e}. Attempting rollback...")
            try:
                if rollback_manager.has_checkpoint():
                    rollback_manager.rollback()
                    self.logger.info("Rollback successful after exception")
            except RollbackError as rollback_err:
                self.logger.error(f"Rollback failed: {rollback_err}")
                raise
            # Re-raise the original exception
            raise

    def resolve_conflicts(self, conflicts: list[Conflict]) -> list[Resolution]:
        """Resolve each provided conflict using the configured priority strategy.

        Args:
            conflicts (list[Conflict]): Detected conflicts to resolve.

        Returns:
            list[Resolution]: A list of resolution objects corresponding to each input conflict.
        """
        resolutions = []

        for conflict in conflicts:
            resolution = self.strategy.resolve(conflict)
            resolutions.append(resolution)

        return resolutions

    def apply_resolutions(self, resolutions: list[Resolution]) -> ResolutionResult:
        """Apply a sequence of resolution decisions to the repository.

        Args:
            resolutions (list[Resolution]): Resolutions to process; entries with `success == True`
                will have their associated changes applied, while others are counted as conflicts.

        Returns:
            ResolutionResult: Summary of the application run containing:
                - `applied_count`: number of individual changes successfully applied,
                - `conflict_count`: number of resolutions that were not applied,
                - `success_rate`: percentage of successful applications (0-100),
                - `resolutions`: list of resolutions that were applied successfully,
                - `conflicts`: list of detected conflicts (empty in this implementation).
        """
        applied_count = 0
        conflict_count = 0
        successful_resolutions = []

        for resolution in resolutions:
            if resolution.success:
                # Apply the resolution
                for change in resolution.applied_changes:
                    if self._apply_change(change):
                        applied_count += 1
                successful_resolutions.append(resolution)
            else:
                conflict_count += 1

        success_rate = (
            (applied_count / (applied_count + conflict_count)) * 100
            if (applied_count + conflict_count) > 0
            else 0
        )

        return ResolutionResult(
            applied_count=applied_count,
            conflict_count=conflict_count,
            success_rate=success_rate,
            resolutions=successful_resolutions,
            conflicts=[],
        )

    def _apply_change(self, change: Change) -> bool:
        """Apply the provided Change to its target file.

        Returns:
            True if the change was successfully applied, False otherwise.
        """
        # Existence and safety checks are delegated to handlers/plaintext path resolver.
        # Get appropriate handler
        handler = self.handlers.get(change.file_type)
        if not handler:
            # Use plaintext fallback
            return self._apply_plaintext_change(change)

        # Use specialized handler
        return handler.apply_change(change.path, change.content, change.start_line, change.end_line)

    def _apply_plaintext_change(self, change: Change) -> bool:
        """Apply a plaintext file change by replacing the specified line range.

        The function reads the target file, replaces lines from `change.start_line` to
        `change.end_line` (1-based, inclusive) with `change.content`, clamps out-of-range indices
        to the file bounds, ensures the file ends with a newline, and writes the result back.

        Args:
            change (Change): Change describing the target `path`, 1-based `start_line` and
                `end_line`, and the replacement `content`.

        Returns:
            bool: True if the file was successfully updated, False otherwise.
        """
        # Validate and resolve path within workspace
        if not InputValidator.validate_file_path(
            change.path, base_dir=str(self.workspace_root), allow_absolute=True
        ):
            self.logger.error(f"Invalid or unsafe path rejected: {change.path}")
            return False

        try:
            file_path = resolve_file_path(
                change.path,
                self.workspace_root,
                allow_absolute=True,
                validate_workspace=True,
                enforce_containment=True,
            )
        except (ValueError, OSError) as e:
            self.logger.error(f"Failed to resolve path {change.path}: {e}")
            return False

        # Check for symlinks in the target path and all parent components (consistent with handlers)
        for component in (file_path, *file_path.parents):
            try:
                if component.is_symlink():
                    self.logger.error(
                        f"Symlink detected in path hierarchy, rejecting for security: {component}"
                    )
                    return False
            except OSError:
                self.logger.error(
                    f"Error probing filesystem component (possible symlink), rejecting: {component}"
                )
                return False

        import tempfile

        temp_path: Path | None = None
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
            replacement = change.content.split("\n")

            start_idx = max(0, change.start_line - 1)
            end_idx = max(0, change.end_line)

            if start_idx > len(lines):
                return False
            if end_idx > len(lines):
                end_idx = len(lines)

            new_lines = lines[:start_idx] + replacement + lines[end_idx:]
            new_text = "\n".join(new_lines) + "\n"

            # Atomic write with permission preservation
            original_mode = None
            if file_path.exists():
                original_mode = os.stat(file_path).st_mode

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=file_path.parent,
                prefix=f".{file_path.name}.tmp",
                delete=False,
            ) as tmp:
                temp_path = Path(tmp.name)
                tmp.write(new_text)
                tmp.flush()
                os.fsync(tmp.fileno())

            if original_mode is not None:
                os.chmod(temp_path, stat.S_IMODE(original_mode))

            os.replace(temp_path, file_path)
            temp_path = None

            # Best-effort parent dir fsync
            try:
                dir_fd = os.open(file_path.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                self.logger.debug("Directory fsync failed for %s", file_path.parent, exc_info=True)

            return True
        except (OSError, UnicodeDecodeError, UnicodeEncodeError) as e:
            self.logger.error(
                f"Failed to apply plaintext change to {file_path} "
                f"(lines {change.start_line}-{change.end_line}): {e}"
            )
            return False
        finally:
            # Clean up temp file if it still exists
            if temp_path and temp_path.exists():
                with contextlib.suppress(OSError):
                    temp_path.unlink()

    def _fetch_comments_with_error_context(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict[str, Any]]:
        """Fetch PR comments with proper error context.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name.
            pr_number (int): Pull request number.

        Returns:
            list[dict[str, Any]]: List of PR comments.

        Raises:
            RuntimeError: If fetching PR comments fails.
        """
        try:
            return self.github_extractor.fetch_pr_comments(owner, repo, pr_number)
        except Exception as e:
            raise RuntimeError(
                f"Failed to fetch PR comments "
                f"(owner={owner}, repo={repo}, pr_number={pr_number}): {e}"
            ) from e

    def resolve_pr_conflicts(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        mode: str = "conflicts-only",
        validate: bool = True,
        parallel: bool = False,
        max_workers: int = 4,
        enable_rollback: bool = True,
    ) -> ResolutionResult:
        """Orchestrates detection, resolution, and application of suggested changes.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.
            mode: Application mode controlling which changes to apply:
                - "all": Apply both conflicting (resolved) and non-conflicting changes
                - "conflicts-only": Only apply conflicting changes after resolution
                  (default, legacy behavior)
                - "non-conflicts-only": Only apply non-conflicting changes, skip conflicts
            validate: Whether to validate changes before applying (default: True).
            parallel: Whether to use parallel processing (default: False).
            max_workers: Number of worker threads for parallel processing (default: 4).
            enable_rollback: Whether to enable automatic rollback on failure (default: True).

        Returns:
            ResolutionResult: Summary of applied resolutions and statistics. The returned object's
                `conflicts` attribute is populated with the list of detected conflicts for the PR.
                When mode="all" or mode="non-conflicts-only", the non_conflicting_* fields will
                contain statistics about non-conflicting change application.

        Raises:
            RuntimeError: If fetching PR comments fails.
            ValueError: If mode parameter is invalid.
        """
        # Validate mode parameter
        valid_modes = {"all", "conflicts-only", "non-conflicts-only"}
        if mode not in valid_modes:
            raise ValueError(
                f"Invalid mode '{mode}'. Must be one of: {', '.join(sorted(valid_modes))}"
            )

        # Extract comments from GitHub
        comments = self._fetch_comments_with_error_context(owner, repo, pr_number)

        # Extract changes from comments
        changes = self.extract_changes_from_comments(comments)

        # Detect conflicts
        conflicts = self.detect_conflicts(changes)

        # Separate changes by conflict status
        # Conflicting changes intentionally ignored here - we only apply non-conflicting changes
        _conflicting_changes, non_conflicting_changes = self.separate_changes_by_conflict_status(
            changes, conflicts
        )

        # Initialize counters for non-conflicting changes
        non_conflicting_applied = 0
        non_conflicting_skipped = 0
        non_conflicting_failed = 0
        total_applied = 0
        total_conflicts = 0
        conflict_resolutions: list[Resolution] = []

        # Apply changes based on mode
        if mode in ("all", "conflicts-only"):
            # Resolve and apply conflicting changes
            resolutions = self.resolve_conflicts(conflicts)
            result = self.apply_resolutions(resolutions)

            total_applied += result.applied_count
            total_conflicts += result.conflict_count
            conflict_resolutions = result.resolutions

        if mode in ("all", "non-conflicts-only"):
            # Apply non-conflicting changes directly with runtime config parameters
            if enable_rollback:
                applied, skipped, failed = self.apply_changes_with_rollback(
                    non_conflicting_changes,
                    validate=validate,
                    parallel=parallel,
                    max_workers=max_workers,
                )
            else:
                applied, skipped, failed = self.apply_changes(
                    non_conflicting_changes,
                    validate=validate,
                    parallel=parallel,
                    max_workers=max_workers,
                )

            non_conflicting_applied = len(applied)
            non_conflicting_skipped = len(skipped)
            non_conflicting_failed = len(failed)
            total_applied += non_conflicting_applied
            total_conflicts += non_conflicting_failed + non_conflicting_skipped

            self.logger.info(
                f"Non-conflicting changes: {non_conflicting_applied} applied, "
                f"{non_conflicting_skipped} skipped, {non_conflicting_failed} failed"
            )
        else:
            # mode == "conflicts-only": count non-conflicting changes as conflicts for success_rate
            total_conflicts += len(non_conflicting_changes)

        # Calculate success rate
        total_attempts = total_applied + total_conflicts
        success_rate = (total_applied / total_attempts * 100) if total_attempts > 0 else 0

        # Return comprehensive result
        return ResolutionResult(
            applied_count=total_applied,
            conflict_count=total_conflicts,
            success_rate=success_rate,
            resolutions=conflict_resolutions,
            conflicts=conflicts,
            non_conflicting_applied=non_conflicting_applied,
            non_conflicting_skipped=non_conflicting_skipped,
            non_conflicting_failed=non_conflicting_failed,
        )

    def analyze_conflicts(self, owner: str, repo: str, pr_number: int) -> list[Conflict]:
        """Analyze conflicts in a pull request without applying any changes.

        Args:
            owner (str): Repository owner.
            repo (str): Repository name.
            pr_number (int): Pull request number.

        Returns:
            list[Conflict]: List of detected Conflict objects representing overlapping or
                incompatible suggested changes found in the pull request.

        Raises:
            RuntimeError: If fetching PR comments fails.
        """
        # Extract comments from GitHub
        comments = self._fetch_comments_with_error_context(owner, repo, pr_number)

        # Extract changes from comments
        changes = self.extract_changes_from_comments(comments)

        # Detect conflicts
        return self.detect_conflicts(changes)
