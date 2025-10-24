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
        """Initialize the conflict detector."""
        self.conflict_cache: dict[str, Any] = {}

    def detect_overlap(
        self,
        change1: Change,
        change2: Change,
    ) -> str | None:
        """Detect overlap between two changes."""
        start1, end1 = change1.start_line, change1.end_line
        start2, end2 = change2.start_line, change2.end_line

        # Check for exact overlap
        if start1 == start2 and end1 == end2:
            return "exact"

        # Check for partial overlap
        if not (end1 < start2 or end2 < start1):
            overlap_size = min(end1, end2) - max(start1, start2) + 1
            total_size = max(end1, end2) - min(start1, start2) + 1

            # Conservative default for degenerate case: avoid division by zero
            if total_size == 0:
                return "major"

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
        """Check if two changes are semantically identical."""
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
        """Check if content appears to be structured (JSON, YAML, etc.)."""
        content = content.strip()
        return (content.startswith(("{", "[")) and content.endswith(("}", "]"))) or (
            ":" in content and ("-" in content or "|" in content)
        )

    def _compare_structured_content(self, content1: str, content2: str) -> bool:
        """Compare structured content for semantic equivalence."""
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
        """Analyze the impact of a conflict."""
        changes = conflict.get("changes", [])
        if not changes:
            return {"impact": "none", "severity": "low"}

        # Analyze change types
        change_types = set()
        security_related = False
        syntax_related = False

        for change in changes:
            content = change.get("content", "").lower()

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
        """Generate a unique fingerprint for a conflict."""
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
        """Generate fingerprint for a single change."""
        path = change.get("path", "")
        start = change.get("start_line", 0)
        end = change.get("end_line", 0)
        content = change.get("content", "")

        normalized = normalize_content(content)
        content_str = f"{path}:{start}:{end}:{normalized}"

        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def detect_conflict_patterns(self, conflicts: list[Conflict]) -> dict[str, Any]:
        """Detect patterns in conflicts."""
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
