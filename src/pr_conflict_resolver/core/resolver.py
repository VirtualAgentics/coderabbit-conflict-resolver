"""Core conflict resolution logic extracted and generalized from ContextForge Memory.

This module provides the main ConflictResolver class that handles intelligent
conflict resolution for GitHub PR comments, specifically designed for CodeRabbit
but extensible to other code review bots.
"""

import hashlib
from pathlib import Path
from typing import Any

from ..analysis.conflict_detector import ConflictDetector
from ..handlers.json_handler import JsonHandler
from ..handlers.toml_handler import TomlHandler
from ..handlers.yaml_handler import YamlHandler
from ..integrations.github import GitHubCommentExtractor
from ..strategies.priority_strategy import PriorityStrategy
from ..utils.text import normalize_content
from .models import Change, Conflict, FileType, Resolution, ResolutionResult


class ConflictResolver:
    """Main conflict resolver class."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Create a ConflictResolver configured with optional settings.

        Parameters:
            config (dict[str, Any] | None): Optional configuration dictionary used to customize
                resolver behavior (for example, strategy parameters or handler options). If not
                provided, defaults to an empty dict.
        """
        self.config = config or {}
        self.conflict_detector = ConflictDetector()
        self.handlers = {
            FileType.JSON: JsonHandler(),
            FileType.YAML: YamlHandler(),
            FileType.TOML: TomlHandler(),
        }
        self.strategy = PriorityStrategy(config)

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

        Parameters:
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

        Parses each comment for fenced "suggestion" blocks and constructs Change objects
        for suggestions that reference a file path and a valid line range. For each
        suggestion the returned Change includes computed fingerprint, detected file type,
        and metadata about the comment.

        Parameters:
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
            source, option_label), fingerprint, and file_type.
        """
        changes = []

        for comment in comments:
            path = comment.get("path")
            if not path:
                continue

            # Extract suggestion blocks
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
                )
                changes.append(change)

        return changes

    def _parse_comment_suggestions(self, body: str) -> list[dict[str, Any]]:
        """Extract suggestion blocks from a GitHub-style comment body.

        Parameters:
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

                conflict = Conflict(
                    file_path=file_path,
                    line_range=(change1.start_line, change1.end_line),
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

        Parameters:
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
            elif change1.start_line <= change2.start_line and change1.end_line >= change2.end_line:
                return "major"
            else:
                return "partial"
        else:
            return "multiple"

    def _assess_conflict_severity(self, change1: Change, conflicting_changes: list[Change]) -> str:
        """Determine conflict severity based on the contents of the involved changes.

        Parameters:
            change1 (Change): The primary change participating in the conflict.
            conflicting_changes (list[Change]): Other changes that overlap or conflict with the
                primary change.

        Returns:
            severity (str): `"high"` if any involved change contains security-related keywords,
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
        """Compute the overlap percentage between changes using inclusive line ranges.

        Returns:
            float: Percentage (0.0-100.0) of the combined span covered by the intersection;
                `0.0` if `conflicting_changes` is empty or there is no overlap.
        """
        if not conflicting_changes:
            return 0.0

        change2 = conflicting_changes[0]  # Use first conflicting change
        overlap_start = max(change1.start_line, change2.start_line)
        overlap_end = min(change1.end_line, change2.end_line)

        if overlap_start > overlap_end:
            return 0.0

        overlap_size = overlap_end - overlap_start + 1
        total_size = (
            max(change1.end_line, change2.end_line)
            - min(change1.start_line, change2.start_line)
            + 1
        )

        return (overlap_size / total_size) * 100

    def resolve_conflicts(self, conflicts: list[Conflict]) -> list[Resolution]:
        """Resolve each provided conflict using the configured priority strategy.

        Parameters:
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

        Parameters:
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
            `true` if the change was successfully applied, `false` otherwise.
        """
        file_path = Path(change.path)
        if not file_path.exists():
            return False

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

        Parameters:
            change (Change): Change describing the target `path`, 1-based `start_line` and
                `end_line`, and the replacement `content`.

        Returns:
            True if the file was successfully updated, False otherwise.
        """
        file_path = Path(change.path)
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
            file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return True
        except Exception:
            return False

    def resolve_pr_conflicts(self, owner: str, repo: str, pr_number: int) -> ResolutionResult:
        """Orchestrates detection, resolution, and application of suggested changes.

        Returns:
            ResolutionResult: Summary of applied resolutions and statistics. The returned object's
                `conflicts` attribute is populated with the list of detected conflicts for the PR.
        """
        # Extract comments from GitHub
        extractor = GitHubCommentExtractor()
        comments = extractor.fetch_pr_comments(owner, repo, pr_number)

        # Extract changes from comments
        changes = self.extract_changes_from_comments(comments)

        # Detect conflicts
        conflicts = self.detect_conflicts(changes)

        # Resolve conflicts
        resolutions = self.resolve_conflicts(conflicts)

        # Apply resolutions
        result = self.apply_resolutions(resolutions)
        result.conflicts = conflicts

        return result

    def analyze_conflicts(self, owner: str, repo: str, pr_number: int) -> list[Conflict]:
        """Analyze conflicts in a pull request without applying any changes.

        Parameters:
            owner (str): Repository owner.
            repo (str): Repository name.
            pr_number (int): Pull request number.

        Returns:
            list[Conflict]: List of detected Conflict objects representing overlapping or
                incompatible suggested changes found in the pull request.
        """
        # Extract comments from GitHub
        extractor = GitHubCommentExtractor()
        try:
            comments = extractor.fetch_pr_comments(owner, repo, pr_number)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch PR comments: {e}") from e

        # Extract changes from comments
        changes = self.extract_changes_from_comments(comments)

        # Detect conflicts
        return self.detect_conflicts(changes)
