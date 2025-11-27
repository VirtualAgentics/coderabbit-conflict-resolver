"""Test conflict detection functionality."""

from review_bot_automator.analysis.conflict_detector import ConflictDetector
from review_bot_automator.core.models import Change, FileType


def test_detect_exact_overlap() -> None:
    """Test detection of exact line range overlaps."""
    detector = ConflictDetector()

    # Test exact overlap
    change1 = Change(
        path="test.py",
        start_line=10,
        end_line=15,
        content="content1",
        metadata={},
        fingerprint="test1",
        file_type=FileType.PYTHON,
    )
    change2 = Change(
        path="test.py",
        start_line=10,
        end_line=15,
        content="content2",
        metadata={},
        fingerprint="test2",
        file_type=FileType.PYTHON,
    )

    assert detector.detect_overlap(change1, change2) == "exact"


def test_detect_partial_overlap() -> None:
    """Test detection of partial line range overlaps."""
    detector = ConflictDetector()

    # Test partial overlap
    change1 = Change(
        path="test.py",
        start_line=10,
        end_line=15,
        content="content1",
        metadata={},
        fingerprint="test1",
        file_type=FileType.PYTHON,
    )
    change2 = Change(
        path="test.py",
        start_line=12,
        end_line=18,
        content="content2",
        metadata={},
        fingerprint="test2",
        file_type=FileType.PYTHON,
    )

    overlap = detector.detect_overlap(change1, change2)
    assert overlap in ["major", "partial", "minor"]


def test_detect_no_overlap() -> None:
    """Test detection when no overlap exists."""
    detector = ConflictDetector()

    # Test no overlap
    change1 = Change(
        path="test.py",
        start_line=10,
        end_line=15,
        content="content1",
        metadata={},
        fingerprint="test1",
        file_type=FileType.PYTHON,
    )
    change2 = Change(
        path="test.py",
        start_line=20,
        end_line=25,
        content="content2",
        metadata={},
        fingerprint="test2",
        file_type=FileType.PYTHON,
    )

    assert detector.detect_overlap(change1, change2) is None


def test_detect_semantic_duplicate() -> None:
    """Test detection of semantically identical changes."""
    detector = ConflictDetector()

    # Test semantic duplicate (same content, different formatting)
    change1 = Change(
        path="test.json",
        start_line=10,
        end_line=15,
        content='{"name": "test"}',
        metadata={},
        fingerprint="test1",
        file_type=FileType.JSON,
    )
    change2 = Change(
        path="test.json",
        start_line=10,
        end_line=15,
        content='{\n  "name": "test"\n}',
        metadata={},
        fingerprint="test2",
        file_type=FileType.JSON,
    )

    assert detector.is_semantic_duplicate(change1, change2) is True
