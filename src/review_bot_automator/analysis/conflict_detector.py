# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Conflict detection and analysis functionality.

This module provides the ConflictDetector class that analyzes changes
for potential conflicts and categorizes them by type and severity.
"""

import hashlib
from typing import Any

from ..core.models import Change, Conflict
from ..utils.text import normalize_content


class ConflictDetector:
    """Detects and analyzes conflicts between changes."""

    def __init__(self) -> None:
        """Create a ConflictDetector instance and initialize its internal cache.

        The instance starts with an empty `conflict_cache` dictionary used to store
        cached analysis results keyed by conflict fingerprints.
        """
        self.conflict_cache: dict[str, Any] = {}

    def detect_overlap(
        self,
        change1: Change,
        change2: Change,
    ) -> str | None:
        """Determine the overlap category between two Change objects.

        Based on their start and end lines.

        Returns:
            "exact" if start and end lines are identical; "major" if overlap covers at least 80%
            of the combined range; "partial" if overlap is at least 50% but less than 80%;
            "minor" if ranges overlap but less than 50%; `None` if ranges do not overlap.
        """
        start1, end1 = change1.start_line, change1.end_line
        start2, end2 = change2.start_line, change2.end_line

        # Check for exact overlap
        if start1 == start2 and end1 == end2:
            return "exact"

        # Check for partial overlap
        if not (end1 < start2 or end2 < start1):
            overlap_size = min(end1, end2) - max(start1, start2) + 1
            total_size = max(end1, end2) - min(start1, start2) + 1
            # Validate input: total_size should never be 0 for valid ranges
            if total_size == 0:
                raise ValueError(
                    f"Invalid range configuration: total_size=0 for ranges "
                    f"[{start1}-{end1}] and [{start2}-{end2}]. "
                    f"This indicates malformed or degenerate input ranges."
                )

            overlap_percentage = (overlap_size / total_size) * 100

            if overlap_percentage >= 80:
                return "major"
            elif overlap_percentage >= 50:
                return "partial"
            else:
                return "minor"

        return None

    def is_semantic_duplicate(
        self,
        change1: Change,
        change2: Change,
    ) -> bool:
        """Determine whether two changes contain equivalent semantic content.

        Compares normalized text contents; if the raw contents appear to be structured
        (JSON/YAML) for both changes, compares their parsed structures for semantic equivalence.

        Returns:
            True if the changes are semantically equivalent, False otherwise.
        """
        content1 = change1.content
        content2 = change2.content

        # Normalize content for comparison
        norm1 = normalize_content(content1)
        norm2 = normalize_content(content2)

        # Check for exact match
        if norm1 == norm2:
            return True

        # Check for structural similarity in JSON/YAML
        if self._is_structured_content(content1) and self._is_structured_content(content2):
            return self._compare_structured_content(content1, content2)

        return False

    def _is_structured_content(self, content: str) -> bool:
        """Detect whether a string likely contains structured data such as JSON or YAML.

        Uses simple heuristics: detects JSON-like bracing (starts with `{` or `[` and ends with
        `}` or `]`) or YAML-like indicators (contains `:` and either `-` or `|`).

        Returns:
            True if content likely represents structured data, False otherwise.
        """
        content = content.strip()
        return (content.startswith(("{", "[")) and content.endswith(("}", "]"))) or (
            ":" in content and ("-" in content or "|" in content)
        )

    def _compare_structured_content(self, content1: str, content2: str) -> bool:
        """Determine whether two structured-content strings are semantically equivalent.

        Attempts to parse the inputs as JSON, then YAML; if parsing succeeds for both inputs,
        compares the resulting data structures for equality.

        Parameters:
            content1 (str): First content string, expected to contain JSON or YAML.
            content2 (str): Second content string, expected to contain JSON or YAML.

        Returns:
            bool: `True` if both inputs parse to equal data structures, `False` otherwise.
        """
        try:
            import json

            # Try JSON parsing
            data1 = json.loads(content1)
            data2 = json.loads(content2)
            return bool(data1 == data2)
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            import yaml

            # Try YAML parsing
            data1 = yaml.safe_load(content1)
            data2 = yaml.safe_load(content2)
            return bool(data1 == data2)
        except (yaml.YAMLError, TypeError):
            pass

        return False

    def analyze_conflict_impact(self, conflict: dict[str, Any]) -> dict[str, Any]:
        """Estimate the impact and severity of a conflict based on its constituent changes.

        Parameters:
            conflict (dict[str, Any]): A conflict object containing a "changes" list where each
                change is a dict that may include "content" (str) and optional "metadata".

        Returns:
            dict[str, Any]: Analysis including:
                - impact (str): One of "none", "low", "medium", or "high".
                - severity (str): One of "low", "medium", "high", or "critical".
                - change_types (list[str]): Detected change kinds
                    (e.g., "code_block", "diff", "text").
                - security_related (bool): True if any change content contains security-related
                    keywords.
                - syntax_related (bool): True if any change content contains syntax/bug-related
                    keywords.
                - change_count (int): Number of changes analyzed.
        """
        changes = conflict.get("changes", [])
        if not changes:
            return {"impact": "none", "severity": "low"}

        # Analyze change types
        change_types = set()
        security_related = False
        syntax_related = False

        for change in changes:
            content = change.get("content", "").lower()
            change.get("metadata", {})

            # Check for security-related changes
            security_keywords = ["security", "vulnerability", "auth", "token", "key", "password"]
            if any(keyword in content for keyword in security_keywords):
                security_related = True

            # Check for syntax-related changes
            syntax_keywords = ["error", "fix", "bug", "issue", "syntax"]
            if any(keyword in content for keyword in syntax_keywords):
                syntax_related = True

            # Determine change type
            if "```" in content:
                change_types.add("code_block")
            elif content.startswith(("+", "-")):
                change_types.add("diff")
            else:
                change_types.add("text")

        # Determine impact level
        if security_related:
            impact = "high"
            severity = "critical"
        elif syntax_related:
            impact = "medium"
            severity = "high"
        elif len(changes) > 2:
            impact = "medium"
            severity = "medium"
        else:
            impact = "low"
            severity = "low"

        return {
            "impact": impact,
            "severity": severity,
            "change_types": list(change_types),
            "security_related": security_related,
            "syntax_related": syntax_related,
            "change_count": len(changes),
        }

    def generate_conflict_fingerprint(self, conflict: dict[str, Any]) -> str:
        """Compute a stable, order-independent fingerprint for a conflict.

        Built from its constituent changes.

        Parameters:
            conflict (dict[str, Any]): Conflict dictionary containing a "changes" key with an
                iterable of change dicts. Each change should include identifying fields (e.g., path,
                start_line, end_line, content) used to derive per-change fingerprints.

        Returns:
            str: A 16-character hexadecimal fingerprint derived from the sorted per-change
                fingerprints, or an empty string if the conflict has no changes.
        """
        changes = conflict.get("changes", [])
        if not changes:
            return ""

        # Create fingerprint from change fingerprints
        change_fingerprints = []
        for change in changes:
            fp = self._generate_change_fingerprint(change)
            change_fingerprints.append(fp)

        # Sort to ensure consistent fingerprint regardless of order
        change_fingerprints.sort()
        combined = "|".join(change_fingerprints)

        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _generate_change_fingerprint(self, change: dict[str, Any]) -> str:
        """Produce a stable 16-character fingerprint for a single change.

        Parameters:
            change (dict[str, Any]): Change dictionary with keys used to form the fingerprint:
                - "path" (str): file path (optional).
                - "start_line" (int): starting line number (optional).
                - "end_line" (int): ending line number (optional).
                - "content" (str): change content (optional).

        Returns:
            str: 16-character hexadecimal fingerprint representing the change's path, range, and
                normalized content.
        """
        path = change.get("path", "")
        start = change.get("start_line", 0)
        end = change.get("end_line", 0)
        content = change.get("content", "")

        normalized = normalize_content(content)
        content_str = f"{path}:{start}:{end}:{normalized}"

        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def detect_conflict_patterns(self, conflicts: list[Conflict]) -> dict[str, Any]:
        """Analyze a list of conflicts and extract summary statistics and common patterns.

        Parameters:
            conflicts (list[Conflict]): List of Conflict objects (expected to expose `file_path`,
                `conflict_type`, and `severity` attributes).

        Returns:
            dict[str, Any]: Summary dictionary with keys:
                - total_conflicts (int): Total number of conflicts processed.
                - file_conflicts (dict[str, int]): Mapping from file path to number of conflicts
                    in that file.
                - conflict_types (dict[str, int]): Counts of conflicts grouped by conflict type.
                - severity_distribution (dict[str, int]): Counts of conflicts grouped by severity.
                - common_patterns (list[str]): Detected high-level patterns; may include
                    - "high_exact_overlap" when a majority of conflicts are exact overlaps,
                    - "high_severity_conflicts" when a substantial portion of conflicts are
                        high severity.
        """
        patterns: dict[str, Any] = {
            "total_conflicts": len(conflicts),
            "file_conflicts": {},
            "conflict_types": {},
            "severity_distribution": {},
            "common_patterns": [],
        }

        for conflict in conflicts:
            file_path = conflict.file_path
            conflict_type = conflict.conflict_type
            severity = conflict.severity

            # Count by file
            if file_path not in patterns["file_conflicts"]:
                patterns["file_conflicts"][file_path] = 0
            patterns["file_conflicts"][file_path] += 1

            # Count by type
            if conflict_type not in patterns["conflict_types"]:
                patterns["conflict_types"][conflict_type] = 0
            patterns["conflict_types"][conflict_type] += 1

            # Count by severity
            if severity not in patterns["severity_distribution"]:
                patterns["severity_distribution"][severity] = 0
            patterns["severity_distribution"][severity] += 1

        # Detect common patterns
        if patterns["conflict_types"].get("exact", 0) > len(conflicts) * 0.5:
            patterns["common_patterns"].append("high_exact_overlap")

        if patterns["severity_distribution"].get("high", 0) > len(conflicts) * 0.3:
            patterns["common_patterns"].append("high_severity_conflicts")

        return patterns
