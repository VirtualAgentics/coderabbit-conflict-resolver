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
        """Initialize the conflict resolver with optional configuration."""
        self.config = config or {}
        self.conflict_detector = ConflictDetector()
        self.handlers = {
            FileType.JSON: JsonHandler(),
            FileType.YAML: YamlHandler(),
            FileType.TOML: TomlHandler(),
        }
        self.strategy = PriorityStrategy(config)

    def detect_file_type(self, path: str) -> FileType:
        """Detect file type from extension."""
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
        """Generate unique fingerprint for a change."""
        normalized = normalize_content(content)
        content_str = f"{path}:{start}:{end}:{normalized}"
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def extract_changes_from_comments(self, comments: list[dict[str, Any]]) -> list[Change]:
        """Extract changes from GitHub comments."""
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
        """Parse comment body to extract suggestion blocks."""
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
        """Detect conflicts between changes."""
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
        """Detect conflicts within a single file."""
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
        """Check if two changes have overlapping line ranges."""
        return not (change1.end_line < change2.start_line or change2.end_line < change1.start_line)

    def _classify_conflict_type(self, change1: Change, conflicting_changes: list[Change]) -> str:
        """Classify the type of conflict."""
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
        """Assess the severity of a conflict."""
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
        """Calculate the percentage of overlap between changes."""
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
        """Resolve conflicts using the configured strategy."""
        resolutions = []

        for conflict in conflicts:
            resolution = self.strategy.resolve(conflict)
            resolutions.append(resolution)

        return resolutions

    def apply_resolutions(self, resolutions: list[Resolution]) -> ResolutionResult:
        """Apply resolutions to the codebase."""
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
        """Apply a single change to a file."""
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
        """Apply change using plaintext method."""
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
        """Resolve conflicts in a pull request."""
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
        """Analyze conflicts in a pull request without applying changes."""
        # Extract comments from GitHub
        extractor = GitHubCommentExtractor()
        comments = extractor.fetch_pr_comments(owner, repo, pr_number)

        # Extract changes from comments
        changes = self.extract_changes_from_comments(comments)

        # Detect conflicts
        return self.detect_conflicts(changes)
