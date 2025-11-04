"""Test the main ConflictResolver class."""

from unittest.mock import Mock, patch

from pr_conflict_resolver import Change, ConflictResolver, FileType
from pr_conflict_resolver.utils.text import normalize_content


class TestConflictResolver:
    """Test the ConflictResolver class."""

    def test_init(self) -> None:
        """Test resolver initialization."""
        resolver = ConflictResolver()
        assert resolver.config == {}
        assert resolver.conflict_detector is not None
        assert FileType.JSON in resolver.handlers
        assert FileType.YAML in resolver.handlers
        assert FileType.TOML in resolver.handlers

    def test_detect_file_type(self) -> None:
        """Test file type detection."""
        resolver = ConflictResolver()

        assert resolver.detect_file_type("test.json") == FileType.JSON
        assert resolver.detect_file_type("test.yaml") == FileType.YAML
        assert resolver.detect_file_type("test.yml") == FileType.YAML
        assert resolver.detect_file_type("test.toml") == FileType.TOML
        assert resolver.detect_file_type("test.py") == FileType.PYTHON
        assert resolver.detect_file_type("test.ts") == FileType.TYPESCRIPT
        assert resolver.detect_file_type("test.txt") == FileType.PLAINTEXT

    def test_generate_fingerprint(self) -> None:
        """Test fingerprint generation."""
        resolver = ConflictResolver()

        fp1 = resolver.generate_fingerprint("test.py", 10, 15, "content")
        fp2 = resolver.generate_fingerprint("test.py", 10, 15, "content")
        fp3 = resolver.generate_fingerprint("test.py", 10, 15, "different")

        assert fp1 == fp2  # Same content should generate same fingerprint
        assert fp1 != fp3  # Different content should generate different fingerprint

    def test_normalize_content(self) -> None:
        """
        Verify normalize_content trims leading and trailing whitespace from each line and
            removes blank lines while preserving line order.
        """
        content = "  line1  \n  line2  \n  \n  line3  "
        normalized = normalize_content(content)
        expected = "line1\nline2\nline3"
        assert normalized == expected

    def test_extract_changes_from_comments(self) -> None:
        """Test extracting changes from comments."""
        resolver = ConflictResolver()

        comments = [
            {
                "path": "test.json",
                "body": '```suggestion\n{\n  "name": "test"\n}\n```',
                "start_line": 1,
                "line": 3,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            }
        ]

        changes = resolver.extract_changes_from_comments(comments)

        assert len(changes) == 1
        change = changes[0]
        assert change.path == "test.json"
        assert change.start_line == 1
        assert change.end_line == 3
        assert change.content == '{\n  "name": "test"\n}'
        assert change.file_type == FileType.JSON
        assert change.metadata["author"] == "coderabbit"

    def test_detect_conflicts(self) -> None:
        """
        Verify that ConflictResolver groups overlapping changes in the same file into a single
            conflict.

        Sets up two overlapping JSON Changes on "test.json" and asserts that detect_conflicts
            returns a single conflict covering both changes, that the conflict's file_path is
            "test.json", and that the conflict_type is either "major" or "partial".
        """
        resolver = ConflictResolver()

        changes = [
            Change(
                path="test.json",
                start_line=10,
                end_line=15,
                content='{"key": "value1"}',
                metadata={},
                fingerprint="fp1",
                file_type=FileType.JSON,
            ),
            Change(
                path="test.json",
                start_line=12,
                end_line=18,
                content='{"key": "value2"}',
                metadata={},
                fingerprint="fp2",
                file_type=FileType.JSON,
            ),
        ]

        conflicts = resolver.detect_conflicts(changes)

        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.file_path == "test.json"
        assert len(conflict.changes) == 2
        assert conflict.conflict_type in ["major", "partial"]

    def test_has_line_overlap(self) -> None:
        """Test line overlap detection."""
        resolver = ConflictResolver()

        change1 = Change("test.py", 10, 15, "content1", {}, "fp1", FileType.PYTHON)
        change2 = Change("test.py", 12, 18, "content2", {}, "fp2", FileType.PYTHON)
        change3 = Change("test.py", 20, 25, "content3", {}, "fp3", FileType.PYTHON)

        assert resolver._has_line_overlap(change1, change2) is True
        assert resolver._has_line_overlap(change1, change3) is False

    def test_classify_conflict_type(self) -> None:
        """Test conflict type classification."""
        resolver = ConflictResolver()

        change1 = Change("test.py", 10, 15, "content1", {}, "fp1", FileType.PYTHON)
        change2 = Change("test.py", 10, 15, "content2", {}, "fp2", FileType.PYTHON)
        change3 = Change("test.py", 12, 18, "content3", {}, "fp3", FileType.PYTHON)

        assert resolver._classify_conflict_type(change1, [change2]) == "exact"
        assert resolver._classify_conflict_type(change1, [change3]) in ["major", "partial"]

    def test_assess_conflict_severity(self) -> None:
        """Test conflict severity assessment."""
        resolver = ConflictResolver()

        # Security-related change
        security_change = Change("test.py", 10, 15, "security fix", {}, "fp1", FileType.PYTHON)
        assert resolver._assess_conflict_severity(security_change, []) == "high"

        # Syntax error fix
        syntax_change = Change("test.py", 10, 15, "fix error", {}, "fp1", FileType.PYTHON)
        assert resolver._assess_conflict_severity(syntax_change, []) == "medium"

        # Regular change
        regular_change = Change("test.py", 10, 15, "regular change", {}, "fp1", FileType.PYTHON)
        assert resolver._assess_conflict_severity(regular_change, []) == "low"

    def test_calculate_overlap_percentage(self) -> None:
        """Test overlap percentage calculation."""
        resolver = ConflictResolver()

        change1 = Change("test.py", 10, 15, "content1", {}, "fp1", FileType.PYTHON)
        change2 = Change("test.py", 12, 18, "content2", {}, "fp2", FileType.PYTHON)

        percentage = resolver._calculate_overlap_percentage(change1, [change2])
        assert 0 <= percentage <= 100

    @patch("pr_conflict_resolver.core.resolver.GitHubCommentExtractor")
    def test_resolve_pr_conflicts(self, mock_extractor: Mock) -> None:
        """Test resolving PR conflicts."""
        resolver = ConflictResolver()

        # Mock GitHub extractor
        mock_extractor.return_value.fetch_pr_comments.return_value = []

        result = resolver.resolve_pr_conflicts("owner", "repo", 123)

        assert result.applied_count == 0
        assert result.conflict_count == 0
        assert result.success_rate == 0
        assert result.resolutions == []
        assert result.conflicts == []

    @patch("pr_conflict_resolver.core.resolver.GitHubCommentExtractor")
    def test_analyze_conflicts(self, mock_extractor: Mock) -> None:
        """Test analyzing conflicts."""
        resolver = ConflictResolver()

        # Mock GitHub extractor
        mock_extractor.return_value.fetch_pr_comments.return_value = []

        conflicts = resolver.analyze_conflicts("owner", "repo", 123)

        assert conflicts == []

    def test_separate_changes_by_conflict_status_no_conflicts(self) -> None:
        """Test separating changes when there are no conflicts."""
        from pr_conflict_resolver.core.models import Conflict

        resolver = ConflictResolver()

        # Create non-conflicting changes
        changes = [
            Change("test.py", 10, 15, "content1", {}, "fp1", FileType.PYTHON),
            Change("test.py", 20, 25, "content2", {}, "fp2", FileType.PYTHON),
            Change("test.py", 30, 35, "content3", {}, "fp3", FileType.PYTHON),
        ]

        conflicts: list[Conflict] = []

        conflicting, non_conflicting = resolver.separate_changes_by_conflict_status(
            changes, conflicts
        )

        # All changes should be non-conflicting
        assert len(conflicting) == 0
        assert len(non_conflicting) == 3
        assert {c.fingerprint for c in non_conflicting} == {"fp1", "fp2", "fp3"}

    def test_separate_changes_by_conflict_status_all_conflicting(self) -> None:
        """Test separating changes when all changes are conflicting."""
        from pr_conflict_resolver.core.models import Conflict

        resolver = ConflictResolver()

        # Create overlapping changes
        change1 = Change("test.py", 10, 15, "content1", {}, "fp1", FileType.PYTHON)
        change2 = Change("test.py", 12, 18, "content2", {}, "fp2", FileType.PYTHON)
        change3 = Change("test.py", 14, 20, "content3", {}, "fp3", FileType.PYTHON)

        changes = [change1, change2, change3]

        # Create conflict containing all changes
        conflict = Conflict(
            file_path="test.py",
            line_range=(10, 20),
            changes=[change1, change2, change3],
            conflict_type="multiple",
            severity="low",
            overlap_percentage=50.0,
        )
        conflicts = [conflict]

        conflicting, non_conflicting = resolver.separate_changes_by_conflict_status(
            changes, conflicts
        )

        # All changes should be conflicting
        assert len(conflicting) == 3
        assert len(non_conflicting) == 0
        assert {c.fingerprint for c in conflicting} == {"fp1", "fp2", "fp3"}

    def test_separate_changes_by_conflict_status_mixed(self) -> None:
        """Test separating changes with mix of conflicting and non-conflicting."""
        from pr_conflict_resolver.core.models import Conflict

        resolver = ConflictResolver()

        # Create mixed changes: some conflicting, some not
        change1 = Change("test.py", 10, 15, "content1", {}, "fp1", FileType.PYTHON)
        change2 = Change("test.py", 12, 18, "content2", {}, "fp2", FileType.PYTHON)
        change3 = Change("test.py", 30, 35, "content3", {}, "fp3", FileType.PYTHON)
        change4 = Change("test.py", 50, 55, "content4", {}, "fp4", FileType.PYTHON)

        changes = [change1, change2, change3, change4]

        # Create conflict for change1 and change2 only
        conflict = Conflict(
            file_path="test.py",
            line_range=(10, 18),
            changes=[change1, change2],
            conflict_type="partial",
            severity="low",
            overlap_percentage=40.0,
        )
        conflicts = [conflict]

        conflicting, non_conflicting = resolver.separate_changes_by_conflict_status(
            changes, conflicts
        )

        # change1 and change2 should be conflicting, change3 and change4 non-conflicting
        assert len(conflicting) == 2
        assert len(non_conflicting) == 2
        assert {c.fingerprint for c in conflicting} == {"fp1", "fp2"}
        assert {c.fingerprint for c in non_conflicting} == {"fp3", "fp4"}

    def test_separate_changes_by_conflict_status_multiple_conflicts(self) -> None:
        """Test separating changes with multiple separate conflicts."""
        from pr_conflict_resolver.core.models import Conflict

        resolver = ConflictResolver()

        # Create changes with multiple separate conflict groups
        change1 = Change("test.py", 10, 15, "content1", {}, "fp1", FileType.PYTHON)
        change2 = Change("test.py", 12, 18, "content2", {}, "fp2", FileType.PYTHON)
        change3 = Change("test.py", 30, 35, "content3", {}, "fp3", FileType.PYTHON)
        change4 = Change("test.py", 50, 55, "content4", {}, "fp4", FileType.PYTHON)
        change5 = Change("test.py", 52, 58, "content5", {}, "fp5", FileType.PYTHON)

        changes = [change1, change2, change3, change4, change5]

        # Create two separate conflicts
        conflict1 = Conflict(
            file_path="test.py",
            line_range=(10, 18),
            changes=[change1, change2],
            conflict_type="partial",
            severity="low",
            overlap_percentage=40.0,
        )
        conflict2 = Conflict(
            file_path="test.py",
            line_range=(50, 58),
            changes=[change4, change5],
            conflict_type="partial",
            severity="low",
            overlap_percentage=30.0,
        )
        conflicts = [conflict1, conflict2]

        conflicting, non_conflicting = resolver.separate_changes_by_conflict_status(
            changes, conflicts
        )

        # change1, change2, change4, change5 should be conflicting; change3 non-conflicting
        assert len(conflicting) == 4
        assert len(non_conflicting) == 1
        assert {c.fingerprint for c in conflicting} == {"fp1", "fp2", "fp4", "fp5"}
        assert {c.fingerprint for c in non_conflicting} == {"fp3"}

    def test_separate_changes_by_conflict_status_empty_inputs(self) -> None:
        """Test separating changes with empty inputs."""

        resolver = ConflictResolver()

        # Test empty changes list
        conflicting, non_conflicting = resolver.separate_changes_by_conflict_status([], [])
        assert len(conflicting) == 0
        assert len(non_conflicting) == 0

        # Test empty conflicts list with changes
        changes = [
            Change("test.py", 10, 15, "content1", {}, "fp1", FileType.PYTHON),
        ]
        conflicting, non_conflicting = resolver.separate_changes_by_conflict_status(changes, [])
        assert len(conflicting) == 0
        assert len(non_conflicting) == 1

    def test_apply_changes_with_rollback_no_rollback_manager(self) -> None:
        """Test apply_changes_with_rollback when rollback_manager is None."""
        resolver = ConflictResolver()

        # When rollback_manager is None, should call apply_changes directly
        applied, skipped, failed = resolver.apply_changes_with_rollback([], validate=True)

        assert len(applied) == 0
        assert len(skipped) == 0
        assert len(failed) == 0

    @patch("pr_conflict_resolver.core.rollback.RollbackManager")
    def test_apply_changes_with_rollback_initialization_failure(
        self, mock_rollback_manager: Mock
    ) -> None:
        """Test apply_changes_with_rollback falls back when RollbackManager init fails."""
        # Make RollbackManager raise ValueError on initialization
        mock_rollback_manager.side_effect = ValueError("Git not available")

        resolver = ConflictResolver()

        # Should fall back to apply_changes when RollbackManager fails to initialize
        applied, skipped, failed = resolver.apply_changes_with_rollback([], validate=True)

        assert len(applied) == 0
        assert len(skipped) == 0
        assert len(failed) == 0
