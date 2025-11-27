from pathlib import Path

from review_bot_automator.core.models import Change, FileType
from review_bot_automator.handlers.yaml_handler import YamlHandler


def test_yaml_can_handle_extensions() -> None:
    """Verify can_handle accepts .yaml/.yml and rejects non-YAML like .json."""
    handler = YamlHandler()
    assert handler.can_handle("file.yaml") is True
    assert handler.can_handle("file.yml") is True
    assert handler.can_handle("file.json") is False


def test_yaml_validate_change_valid_and_controls() -> None:
    """Validate YAML parsing and security checks (null byte, !!python tags)."""
    handler = YamlHandler()

    ok, msg = handler.validate_change("config.yaml", "key: value", 1, 1)
    assert ok is True
    assert msg

    # Dangerous control character (null byte)
    ok2, msg2 = handler.validate_change("config.yaml", "key: value\x00", 1, 1)
    assert ok2 is False
    assert "control characters" in msg2

    # Dangerous python tag
    payload = "key: !!python/object/apply:os.system ['true']"
    ok3, msg3 = handler.validate_change("config.yaml", payload, 1, 1)
    assert ok3 is False
    assert "dangerous Python object tags" in msg3


def test_yaml_apply_change_merge_only(tmp_path: Path) -> None:
    """Verify YAML merge overrides/adds while preserving existing unrelated keys.

    Note: symlink behavior not asserted because path resolution may resolve
    parent symlinks before checks.
    """
    handler = YamlHandler(workspace_root=tmp_path)

    target = tmp_path / "config.yaml"
    target.write_text("a: 1\nb:\n  c: 2\n", encoding="utf-8")

    # Suggestion should override a and add d
    suggestion = "a: 10\nd: 3\n"
    ok = handler.apply_change(str(target), suggestion, 1, 2)
    assert ok is True
    content = target.read_text(encoding="utf-8")
    # Merged: a overridden, d added, b preserved
    assert "a: 10" in content
    assert "d: 3" in content
    assert "b:" in content

    # Note: Symlink-specific behavior intentionally not asserted here.


def test_yaml_apply_preserves_comments(tmp_path: Path) -> None:
    handler = YamlHandler(workspace_root=tmp_path)
    target = tmp_path / "config.yaml"
    original = "# top comment\nkey: value  # inline comment\n"
    target.write_text(original, encoding="utf-8")

    suggestion = "key: new\n"
    assert handler.apply_change(str(target), suggestion, 1, 1)

    updated = target.read_text(encoding="utf-8")
    assert "# top comment" in updated
    assert "inline comment" in updated


def test_yaml_detect_conflicts_same_key_and_no_conflict() -> None:
    """Verify conflict detection reports conflicts for same key and none for distinct keys."""
    handler = YamlHandler()

    changes_same_key = [
        Change(
            path="config.yaml",
            start_line=1,
            end_line=1,
            content="a: 1\n",
            metadata={},
            fingerprint="f1",
            file_type=FileType.YAML,
        ),
        Change(
            path="config.yaml",
            start_line=2,
            end_line=2,
            content="a: 2\n",
            metadata={},
            fingerprint="f2",
            file_type=FileType.YAML,
        ),
    ]

    conflicts = handler.detect_conflicts("config.yaml", changes_same_key)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.file_path == "config.yaml"
    assert c.conflict_type == "key_conflict"
    assert c.line_range == (1, 2)

    changes_distinct = [
        Change(
            path="config.yaml",
            start_line=1,
            end_line=1,
            content="a: 1\n",
            metadata={},
            fingerprint="f3",
            file_type=FileType.YAML,
        ),
        Change(
            path="config.yaml",
            start_line=2,
            end_line=2,
            content="b: 2\n",
            metadata={},
            fingerprint="f4",
            file_type=FileType.YAML,
        ),
    ]

    conflicts2 = handler.detect_conflicts("config.yaml", changes_distinct)
    assert conflicts2 == []
