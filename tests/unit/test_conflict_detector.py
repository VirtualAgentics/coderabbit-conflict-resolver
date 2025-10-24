"""Test conflict detection functionality."""

import pytest
from pr_conflict_resolver.analysis.conflict_detector import ConflictDetector


def test_detect_exact_overlap():
    """Test detection of exact line range overlaps."""
    detector = ConflictDetector()
    
    # Test exact overlap
    change1 = (10, 15, "content1", {})
    change2 = (10, 15, "content2", {})
    
    assert detector.detect_overlap(change1, change2) == "exact"


def test_detect_partial_overlap():
    """Test detection of partial line range overlaps."""
    detector = ConflictDetector()
    
    # Test partial overlap
    change1 = (10, 15, "content1", {})
    change2 = (12, 18, "content2", {})
    
    overlap = detector.detect_overlap(change1, change2)
    assert overlap in ["major", "partial"]


def test_detect_no_overlap():
    """Test detection when no overlap exists."""
    detector = ConflictDetector()
    
    # Test no overlap
    change1 = (10, 15, "content1", {})
    change2 = (20, 25, "content2", {})
    
    assert detector.detect_overlap(change1, change2) is None


def test_detect_semantic_duplicate():
    """Test detection of semantically identical changes."""
    detector = ConflictDetector()
    
    # Test semantic duplicate (same content, different formatting)
    change1 = (10, 15, '{"name": "test"}', {})
    change2 = (10, 15, '{\n  "name": "test"\n}', {})
    
    assert detector.is_semantic_duplicate(change1, change2) is True
