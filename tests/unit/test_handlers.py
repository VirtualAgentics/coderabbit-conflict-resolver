"""Test the file handlers."""

import os
import stat
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pr_conflict_resolver import JsonHandler, TomlHandler, YamlHandler


class TestJsonHandler:
    """Test the JSON handler."""

    def test_can_handle(self) -> None:
        """Test file type detection."""
        handler = JsonHandler()

        assert handler.can_handle("test.json") is True
        assert handler.can_handle("test.JSON") is True
        assert handler.can_handle("test.yaml") is False
        assert handler.can_handle("test.txt") is False

    def test_has_duplicate_keys(self) -> None:
        """Test duplicate key detection."""
        handler = JsonHandler()

        # No duplicates
        data = {"key1": "value1", "key2": "value2"}
        assert handler._has_duplicate_keys(data) is False

        # Test with string representation that would have duplicates
        # Since Python dicts can't have duplicate keys, we test the logic differently
        # This would be detected as duplicate if parsed as JSON string
        assert handler._has_duplicate_keys({"key1": "value1"}) is False  # No duplicates in dict

        # Nested structure without duplicates
        nested_data: dict[str, Any] = {"outer": {"key1": "value1", "key2": "value2"}}
        assert handler._has_duplicate_keys(nested_data) is False

    def test_validate_change(self) -> None:
        """
        Verify JsonHandler.validate_change accepts valid JSON and rejects malformed JSON.

        Asserts that:
        - a well-formed JSON string produces (True, message) and the message contains "Valid JSON";
        - a malformed JSON string produces (False, message) and the message contains "Invalid JSON";
        - re-validating a well-formed JSON string still reports valid JSON (duplicate-key
            behavior is tested via parsing semantics).
        """
        handler = JsonHandler()

        # Valid JSON
        valid, msg = handler.validate_change("test.json", '{"key": "value"}', 1, 3)
        assert valid is True
        assert "Valid JSON" in msg

        # Invalid JSON
        valid, msg = handler.validate_change("test.json", '{"key": "value"', 1, 3)
        assert valid is False
        assert "Invalid JSON" in msg

        # Test validation logic - duplicate keys would be caught during parsing
        # Since Python dicts can't have duplicate keys, we test the validation logic differently
        valid, msg = handler.validate_change("test.json", '{"key": "value"}', 1, 3)
        assert valid is True
        assert "Valid JSON" in msg

    def test_detect_conflicts(self) -> None:
        """
        Verify that JsonHandler.detect_conflicts identifies key conflicts among multiple JSON
            changes.

        This test constructs three Change objects for the same JSON path where two changes
            modify the same key across different line ranges and the third changes a different
            key. It asserts that exactly one conflict is reported, that the conflict type is
            "key_conflict", and that the conflict includes the two related changes.
        """
        handler = JsonHandler()

        from pr_conflict_resolver import Change, FileType

        changes = [
            Change(
                path="test.json",
                start_line=1,
                end_line=3,
                content='{"key1": "value1"}',
                metadata={},
                fingerprint="test1",
                file_type=FileType.JSON,
            ),
            Change(
                path="test.json",
                start_line=4,
                end_line=6,
                content='{"key1": "value2"}',
                metadata={},
                fingerprint="test2",
                file_type=FileType.JSON,
            ),
            Change(
                path="test.json",
                start_line=7,
                end_line=9,
                content='{"key2": "value3"}',
                metadata={},
                fingerprint="test3",
                file_type=FileType.JSON,
            ),
        ]

        conflicts = handler.detect_conflicts("test.json", changes)

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "key_conflict"
        assert len(conflicts[0].changes) == 2

    def test_smart_merge_json(self) -> None:
        """Test smart JSON merging."""
        handler = JsonHandler()

        original = {"key1": "value1", "key2": "value2"}
        suggestion = {"key1": "new_value1", "key3": "value3"}

        result = handler._smart_merge_json(original, suggestion, 1, 3)

        expected = {"key1": "new_value1", "key2": "value2", "key3": "value3"}
        assert result == expected

    def test_is_complete_object(self) -> None:
        """Test complete object detection."""
        handler = JsonHandler()

        original = {"key1": "value1", "key2": "value2"}

        # Complete object
        suggestion = {"key1": "value1", "key2": "value2", "key3": "value3"}
        assert handler._is_complete_object(suggestion, original) is True

        # Partial object
        suggestion = {"key1": "value1"}
        assert handler._is_complete_object(suggestion, original) is False


class TestYamlHandler:
    """Test the YAML handler."""

    def test_can_handle(self) -> None:
        """Test file type detection."""
        handler = YamlHandler()

        assert handler.can_handle("test.yaml") is True
        assert handler.can_handle("test.yml") is True
        assert handler.can_handle("test.YAML") is True
        assert handler.can_handle("test.json") is False
        assert handler.can_handle("test.txt") is False

    @patch("pr_conflict_resolver.handlers.yaml_handler.YAML_AVAILABLE", False)
    def test_yaml_not_available(self) -> None:
        """Test behavior when ruamel.yaml is not available."""
        handler = YamlHandler()

        valid, msg = handler.validate_change("test.yaml", "key: value", 1, 3)
        assert valid is False
        assert "not available" in msg

    @patch("pr_conflict_resolver.handlers.yaml_handler.YAML_AVAILABLE", True)
    def test_validate_change(self) -> None:
        """Test change validation."""
        handler = YamlHandler()

        with patch("ruamel.yaml.YAML") as mock_yaml:
            mock_yaml.return_value.load.return_value = {"key": "value"}

            valid, msg = handler.validate_change("test.yaml", "key: value", 1, 3)
            assert valid is True
            assert "Valid YAML" in msg

    def test_extract_keys(self) -> None:
        """Test key extraction."""
        handler = YamlHandler()

        data = {"key1": "value1", "key2": {"nested1": "value2", "nested2": ["item1", "item2"]}}

        keys = handler._extract_keys(data)

        expected_keys = [
            "key1",
            "key2",
            "key2.nested1",
            "key2.nested2",
            "key2.nested2[0]",
            "key2.nested2[1]",
        ]
        assert set(expected_keys) <= set(keys)

    def test_yaml_deeply_nested_structures(self) -> None:
        """Test deeply nested YAML structures (3+ levels)."""
        handler = YamlHandler()

        # Create deeply nested structure
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "value": "deep_value",
                            "list": ["item1", "item2", {"nested": "value"}],
                        }
                    }
                }
            }
        }

        keys = handler._extract_keys(data)

        # Should extract all nested dotted paths and indexed list entries
        expected_keys = [
            "level1",
            "level1.level2",
            "level1.level2.level3",
            "level1.level2.level3.level4",
            "level1.level2.level3.level4.value",
            "level1.level2.level3.level4.list",
            "level1.level2.level3.level4.list[0]",
            "level1.level2.level3.level4.list[1]",
            "level1.level2.level3.level4.list[2]",
        ]
        assert set(expected_keys) <= set(keys)

    @patch("pr_conflict_resolver.handlers.yaml_handler.YAML_AVAILABLE", True)
    def test_validate_change_dangerous_tags(self) -> None:
        """Test validation rejects dangerous YAML tags."""
        handler = YamlHandler()

        # Test dangerous Python object tags
        dangerous_yaml = "key: !!python/object/apply:os.system ['rm -rf /']"
        valid, msg = handler.validate_change("test.yaml", dangerous_yaml, 1, 3)
        assert valid is False
        assert "dangerous Python object tags" in msg

        # Test other dangerous tags
        dangerous_yaml2 = "key: !!python/name:os.system"
        valid, msg = handler.validate_change("test.yaml", dangerous_yaml2, 1, 3)
        assert valid is False
        assert "dangerous Python object tags" in msg

    @patch("pr_conflict_resolver.handlers.yaml_handler.YAML_AVAILABLE", True)
    def test_validate_change_dangerous_characters(self) -> None:
        """Test validation rejects dangerous control characters."""
        handler = YamlHandler()

        # Test null byte
        dangerous_yaml = "key: value\x00"
        valid, msg = handler.validate_change("test.yaml", dangerous_yaml, 1, 3)
        assert valid is False
        assert "dangerous control characters" in msg

    def test_contains_dangerous_tags_none(self) -> None:
        """Test _contains_dangerous_tags with None value."""
        handler = YamlHandler()
        assert handler._contains_dangerous_tags(None) is False

    def test_contains_dangerous_tags_nested_dict(self) -> None:
        """Test _contains_dangerous_tags with nested dictionaries."""
        handler = YamlHandler()

        # Create a mock tagged object
        class MockTaggedObject:
            def __init__(self, tag: str):
                self.tag = tag

        dangerous_data = {
            "safe_key": "safe_value",
            "dangerous_key": MockTaggedObject("!!python/object"),
            "nested": {"another_dangerous": MockTaggedObject("!!python/name")},
        }

        assert handler._contains_dangerous_tags(dangerous_data) is True

    def test_contains_dangerous_tags_nested_list(self) -> None:
        """Test _contains_dangerous_tags with nested lists."""
        handler = YamlHandler()

        # Create a mock tagged object
        class MockTaggedObject:
            def __init__(self, tag: str):
                self.tag = tag

        dangerous_data = [
            "safe_item",
            MockTaggedObject("!!python/function"),
            ["nested", MockTaggedObject("!!python/module")],
        ]

        assert handler._contains_dangerous_tags(dangerous_data) is True

    def test_detect_conflicts_unparseable_content(self) -> None:
        """Test detect_conflicts with unparseable change content."""
        handler = YamlHandler()

        from pr_conflict_resolver import Change, FileType

        # Create changes with unparseable content
        changes = [
            Change(
                path="test.yaml",
                start_line=1,
                end_line=3,
                content="invalid: yaml: content: [",
                metadata={},
                fingerprint="test1",
                file_type=FileType.YAML,
            ),
            Change(
                path="test.yaml",
                start_line=4,
                end_line=6,
                content="key: value",
                metadata={},
                fingerprint="test2",
                file_type=FileType.YAML,
            ),
        ]

        # Should handle unparseable content gracefully
        conflicts = handler.detect_conflicts("test.yaml", changes)
        # Should not crash and may return empty list or partial results
        assert isinstance(conflicts, list)

    @patch("pr_conflict_resolver.handlers.yaml_handler.YAML_AVAILABLE", True)
    def test_apply_change_invalid_path(self) -> None:
        """Test apply_change with invalid file path (security rejection)."""
        handler = YamlHandler()

        # Test with path traversal attempt
        result = handler.apply_change("../../../etc/passwd", "key: value", 1, 3)
        assert result is False

    def test_yaml_empty_dict_and_list(self) -> None:
        """Test empty dictionaries and empty lists."""
        handler = YamlHandler()

        # Test empty dictionary
        empty_dict: dict[str, Any] = {}
        keys = handler._extract_keys(empty_dict)
        assert keys == []

        # Test empty list
        data_with_empty_list: dict[str, list[Any]] = {"key": []}
        keys = handler._extract_keys(data_with_empty_list)
        assert "key" in keys
        assert "key[0]" not in keys  # No items in empty list

        # Test dictionary with empty nested structures
        data_with_empty_nested = {"empty_dict": {}, "empty_list": [], "normal_key": "value"}
        keys = handler._extract_keys(data_with_empty_nested)
        expected_keys = ["empty_dict", "empty_list", "normal_key"]
        assert set(expected_keys) <= set(keys)

    @patch("pr_conflict_resolver.handlers.yaml_handler.YAML_AVAILABLE", True)
    def test_yaml_anchors_and_aliases(self) -> None:
        """Test YAML with anchors/aliases."""
        handler = YamlHandler()

        with patch("ruamel.yaml.YAML") as mock_yaml:
            # Mock YAML structure with shared references
            mock_yaml.return_value.load.return_value = {
                "anchor": "&anchor_value",
                "alias": "*anchor_value",
                "shared": {"ref": "*anchor_value"},
            }

            # Test that validate_change handles anchors/aliases
            valid, msg = handler.validate_change("test.yaml", "key: &ref value\nother: *ref", 1, 3)
            assert valid is True
            assert "Valid YAML" in msg

            # Test key extraction with anchors/aliases
            data = {"anchor": "&ref", "alias": "*ref"}
            keys = handler._extract_keys(data)
            assert "anchor" in keys
            assert "alias" in keys


class TestTomlHandler:
    """Test the TOML handler."""

    def test_can_handle(self) -> None:
        """Test file type detection."""
        handler = TomlHandler()

        assert handler.can_handle("test.toml") is True
        assert handler.can_handle("test.TOML") is True
        assert handler.can_handle("test.json") is False
        assert handler.can_handle("test.txt") is False

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", False)
    def test_toml_not_available(self) -> None:
        """Test behavior when tomllib is not available."""
        handler = TomlHandler()

        valid, msg = handler.validate_change("test.toml", "key = 'value'", 1, 3)
        assert valid is False
        assert "not available" in msg

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_WRITE_AVAILABLE", True)
    def test_validate_change(self) -> None:
        """Test change validation."""
        handler = TomlHandler()

        with patch("tomllib.loads") as mock_tomllib:
            mock_tomllib.return_value = {"key": "value"}

            valid, msg = handler.validate_change("test.toml", "key = 'value'", 1, 3)
            assert valid is True
            assert "Valid TOML" in msg

    def test_extract_sections(self) -> None:
        """Test section extraction."""
        handler = TomlHandler()

        data = {
            "section1": "value1",
            "section2": {"subsection1": "value2", "subsection2": "value3"},
        }

        sections = handler._extract_sections(data)

        expected_sections = ["section1", "section2", "section2.subsection1", "section2.subsection2"]
        assert set(expected_sections) <= set(sections)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_WRITE_AVAILABLE", True)
    def test_apply_change_nonexistent_file(self) -> None:
        """Test apply_change handles non-existent files."""
        handler = TomlHandler()

        # Test with non-existent file
        result = handler.apply_change("nonexistent.toml", "key = 'value'", 1, 3)
        assert result is False

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_WRITE_AVAILABLE", True)
    def test_apply_change_unicode_error(self) -> None:
        """Test apply_change handles Unicode decode errors."""
        handler = TomlHandler()

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            # Write invalid UTF-8
            f.write(b"\xff\xfe\x00\x00")
            f.flush()

            try:
                result = handler.apply_change(f.name, "key = 'value'", 1, 3)
                assert result is False
            finally:
                os.unlink(f.name)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_WRITE_AVAILABLE", True)
    def test_apply_change_toml_parse_error(self) -> None:
        """Test apply_change handles TOML parse errors."""
        handler = TomlHandler()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write invalid TOML
            f.write("invalid toml content [")
            f.flush()

            try:
                result = handler.apply_change(f.name, "key = 'value'", 1, 3)
                assert result is False
            finally:
                os.unlink(f.name)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_WRITE_AVAILABLE", True)
    def test_apply_change_suggestion_parse_error(self) -> None:
        """Test apply_change handles suggestion parse errors."""
        handler = TomlHandler()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write valid original TOML
            f.write("key = 'value'")
            f.flush()

            try:
                # Invalid suggestion TOML
                result = handler.apply_change(f.name, "invalid suggestion [", 1, 3)
                assert result is False
            finally:
                os.unlink(f.name)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_WRITE_AVAILABLE", True)
    def test_apply_change_success_with_permissions(self) -> None:
        """Test apply_change successfully preserves file permissions."""
        handler = TomlHandler()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write original TOML
            f.write("key = 'value'")
            f.flush()

            # Set specific permissions
            original_mode = 0o644
            os.chmod(f.name, original_mode)

            try:
                result = handler.apply_change(f.name, "newkey = 'newvalue'", 1, 3)
                assert result is True

                # Check that permissions were preserved
                current_mode = stat.S_IMODE(os.stat(f.name).st_mode)
                assert current_mode == original_mode
            finally:
                os.unlink(f.name)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_WRITE_AVAILABLE", True)
    def test_apply_change_atomic_replacement(self) -> None:
        """Test apply_change uses atomic file replacement."""
        handler = TomlHandler()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            # Write original TOML
            f.write("key = 'value'")
            f.flush()

            try:
                result = handler.apply_change(f.name, "newkey = 'newvalue'", 1, 3)
                assert result is True

                # Verify content was merged
                content = Path(f.name).read_text()
                assert 'key = "value"' in content  # TOML normalizes quotes
                assert 'newkey = "newvalue"' in content
            finally:
                os.unlink(f.name)

    def test_validate_change_only_parses_toml(self) -> None:
        """Test that validate_change only validates TOML content, not file paths."""
        handler = TomlHandler()

        # validate_change only validates TOML parsing, not paths
        valid, _ = handler.validate_change("../../../etc/passwd", "key = 'value'", 1, 3)
        # Path validation is performed in apply_change
        assert valid is True  # TOML content is valid

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", False)
    def test_validate_change_toml_not_available(self) -> None:
        """Test validate_change when TOML is not available."""
        handler = TomlHandler()

        valid, msg = handler.validate_change("test.toml", "key = 'value'", 1, 3)
        assert valid is False
        assert "not available" in msg.lower()

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_WRITE_AVAILABLE", True)
    def test_validate_change_parse_validation(self) -> None:
        """Test validate_change validates TOML parsing."""
        handler = TomlHandler()

        # Valid TOML
        valid, msg = handler.validate_change("test.toml", "key = 'value'", 1, 3)
        assert valid is True
        assert "valid toml" in msg.lower()

        # Invalid TOML
        valid, msg = handler.validate_change("test.toml", "invalid toml [", 1, 3)
        assert valid is False
        assert "invalid toml" in msg.lower()

    def test_detect_conflicts_section_overlap(self) -> None:
        """Test detect_conflicts identifies section conflicts."""
        handler = TomlHandler()

        from pr_conflict_resolver import Change, FileType

        changes = [
            Change(
                path="test.toml",
                start_line=1,
                end_line=3,
                content="[section1]\nkey1 = 'value1'",
                metadata={},
                fingerprint="test1",
                file_type=FileType.TOML,
            ),
            Change(
                path="test.toml",
                start_line=4,
                end_line=6,
                content="[section1]\nkey2 = 'value2'",
                metadata={},
                fingerprint="test2",
                file_type=FileType.TOML,
            ),
        ]

        conflicts = handler.detect_conflicts("test.toml", changes)
        assert len(conflicts) > 0
        assert conflicts[0].conflict_type == "section_conflict"

    def test_extract_sections_helper(self) -> None:
        """Test _extract_sections helper method."""
        handler = TomlHandler()

        data = {
            "section1": "value1",
            "section2": {"subsection1": "value2", "subsection2": {"nested": "value3"}},
        }

        sections = handler._extract_sections(data)

        expected = [
            "section1",
            "section2",
            "section2.subsection1",
            "section2.subsection2",
            "section2.subsection2.nested",
        ]
        for expected_section in expected:
            assert expected_section in sections


@pytest.fixture
def test_handler() -> Any:
    """Fixture providing a concrete TestHandler instance for testing BaseHandler functionality."""
    from pr_conflict_resolver.handlers.base import BaseHandler

    class TestHandler(BaseHandler):
        def can_handle(self, file_path: str) -> bool:
            return True

        def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
            return True

        def validate_change(
            self, path: str, content: str, start_line: int, end_line: int
        ) -> tuple[bool, str]:
            return True, "Valid"

        def detect_conflicts(self, path: str, changes: list[Any]) -> list[Any]:
            return []

    return TestHandler()


class TestBaseHandlerBackupRestore:
    """Test BaseHandler backup and restore functionality."""

    def test_backup_file_success(self, test_handler: Any) -> None:
        """Test successful backup file creation."""
        import stat
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            # Create backup
            backup_path = test_handler.backup_file(str(test_file))

            # Verify backup was created
            assert Path(backup_path).exists()
            assert Path(backup_path).read_text() == "test content"
            assert backup_path.endswith(".backup")

            # Verify backup file has secure permissions (0o600)
            assert stat.S_IMODE(Path(backup_path).stat().st_mode) == 0o600

    def test_backup_file_nonexistent(self, test_handler: Any) -> None:
        """Test backup_file with non-existent file raises FileNotFoundError."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a valid path that doesn't exist
            nonexistent_file = Path(tmpdir) / "nonexistent.txt"

            with pytest.raises(FileNotFoundError, match="Source file does not exist"):
                test_handler.backup_file(str(nonexistent_file))

    def test_backup_file_directory(self, test_handler: Any) -> None:
        """Test backup_file with directory instead of file raises ValueError."""
        import tempfile

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(ValueError, match="Source path is not a regular file"),
        ):
            test_handler.backup_file(tmpdir)

    def test_backup_file_collision_handling(self, test_handler: Any) -> None:
        """Test backup file collision handling with timestamp and counter."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            # Create existing backup file
            existing_backup = test_file.with_suffix(".txt.backup")
            existing_backup.write_text("existing backup")

            # Mock time.time to return a fixed timestamp
            with patch("time.time", return_value=1234567890):
                backup_path = test_handler.backup_file(str(test_file))

            # Should create timestamped backup
            assert Path(backup_path).exists()
            assert backup_path.endswith(".backup.1234567890")

    def test_backup_file_collision_counter_limit(self, test_handler: Any) -> None:
        """Test backup file collision handling with >1000 attempts raises OSError."""
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            # Create the initial .backup file to trigger timestamp-based naming
            backup_base = test_file.with_suffix(f"{test_file.suffix}.backup")
            backup_base.write_text("initial backup")

            # Create a side_effect that only simulates collisions for backup files
            # by checking if the path matches backup file patterns
            def exists_side_effect(path: Path) -> bool:
                # For backup target files, simulate collision after pattern match
                path_str = str(path)
                if path_str.endswith(".backup") or ".backup." in path_str:
                    # Always return True for backup files to simulate infinite collisions
                    return True
                # For source file validation, use os.path.exists() to avoid recursion
                return os.path.exists(str(path))

            # Mock Path.exists with side_effect that only affects backup files
            with (
                patch(
                    "pathlib.Path.exists",
                    side_effect=exists_side_effect,
                    autospec=True,
                ),
                pytest.raises(
                    OSError, match="Unable to create unique backup filename after 1000 attempts"
                ),
            ):
                test_handler.backup_file(str(test_file))

    def test_backup_file_permission_error(self, test_handler: Any) -> None:
        """Test backup file creation with permission errors triggers cleanup."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            # Mock shutil.copy2 to raise OSError
            with (
                patch("shutil.copy2", side_effect=OSError("Permission denied")),
                pytest.raises(OSError, match="Failed to create backup"),
            ):
                test_handler.backup_file(str(test_file))

    def test_restore_file_success(self, test_handler: Any) -> None:
        """Test successful file restoration."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create original file
            original_file = Path(tmpdir) / "original.txt"
            original_file.write_text("original content")

            # Create backup file
            backup_file = Path(tmpdir) / "backup.txt"
            backup_file.write_text("backup content")

            # Restore file
            result = test_handler.restore_file(str(backup_file), str(original_file))

            # Verify restoration
            assert result is True
            assert original_file.read_text() == "backup content"
            assert not backup_file.exists()  # Backup should be removed

    def test_restore_file_failure(self, test_handler: Any) -> None:
        """Test restore_file failure returns False."""
        from unittest.mock import patch

        # Mock shutil.copy2 to raise an exception
        with patch("shutil.copy2", side_effect=OSError("Copy failed")):
            result = test_handler.restore_file(
                "/nonexistent/backup.txt", "/nonexistent/original.txt"
            )
            assert result is False
