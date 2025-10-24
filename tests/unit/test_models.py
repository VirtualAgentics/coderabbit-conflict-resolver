"""Unit tests for data models in pr_conflict_resolver.core.models."""

from dataclasses import is_dataclass
from typing import Any

from pr_conflict_resolver import (
    Change,
    Conflict,
    FileType,
    Resolution,
    ResolutionResult,
)


def test_filetype_enum_members() -> None:
    """Ensure expected FileType enum members exist."""
    members = {m.name for m in FileType}
    assert {"PYTHON", "TYPESCRIPT", "JSON", "YAML", "TOML", "PLAINTEXT"} <= members


def test_change_dataclass_fields_and_equality() -> None:
    """Validate Change dataclass structure and equality semantics."""
    assert is_dataclass(Change)

    c1 = Change(
        path="a.json",
        start_line=1,
        end_line=3,
        content='{"k":"v"}',
        metadata={"author": "bot"},
        fingerprint="fp1",
        file_type=FileType.JSON,
    )
    c2 = Change(
        path="a.json",
        start_line=1,
        end_line=3,
        content='{"k":"v"}',
        metadata={"author": "bot"},
        fingerprint="fp1",
        file_type=FileType.JSON,
    )
    c3 = Change(
        path="a.json",
        start_line=1,
        end_line=3,
        content='{"k":"v2"}',
        metadata={"author": "bot"},
        fingerprint="fp2",
        file_type=FileType.JSON,
    )

    assert c1 == c2
    assert c1 != c3
    assert c1.file_type is FileType.JSON
    assert isinstance(c1.metadata, dict)


def test_conflict_dataclass() -> None:
    """Validate Conflict dataclass creation and fields."""
    ch = Change(
        path="file.yaml",
        start_line=10,
        end_line=12,
        content="name: test",
        metadata={},
        fingerprint="abc",
        file_type=FileType.YAML,
    )
    conflict = Conflict(
        file_path="file.yaml",
        line_range=(10, 12),
        changes=[ch],
        conflict_type="partial",
        severity="low",
        overlap_percentage=33.3,
    )

    assert is_dataclass(Conflict)
    assert conflict.file_path == "file.yaml"
    assert conflict.line_range == (10, 12)
    assert conflict.changes and conflict.changes[0] == ch
    assert conflict.conflict_type in {"exact", "major", "partial", "multiple", "key_conflict", "section_conflict"}
    assert conflict.severity in {"low", "medium", "high"}
    assert 0.0 <= conflict.overlap_percentage <= 100.0


def test_resolution_and_result_dataclasses() -> None:
    """Validate Resolution and ResolutionResult containers."""
    ch_applied = Change(
        path="config.toml",
        start_line=2,
        end_line=4,
        content='[tool]\nname="x"',
        metadata={},
        fingerprint="fp3",
        file_type=FileType.TOML,
    )
    res = Resolution(
        strategy="priority",
        applied_changes=[ch_applied],
        skipped_changes=[],
        success=True,
        message="ok",
    )
    result = ResolutionResult(
        applied_count=1,
        conflict_count=0,
        success_rate=100.0,
        resolutions=[res],
        conflicts=[],
    )

    assert is_dataclass(Resolution)
    assert is_dataclass(ResolutionResult)
    assert result.applied_count == 1
    assert result.conflict_count == 0
    assert result.success_rate == 100.0
    assert result.resolutions[0].success is True
    assert result.resolutions[0].strategy == "priority"