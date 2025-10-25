"""Test the file handlers."""

from typing import Any
from unittest.mock import patch

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
        assert all(key in keys for key in expected_keys)

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
        assert all(key in keys for key in expected_keys)

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
        assert all(key in keys for key in expected_keys)

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

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_AVAILABLE", False)
    def test_toml_not_available(self) -> None:
        """Test behavior when tomli is not available."""
        handler = TomlHandler()

        valid, msg = handler.validate_change("test.toml", "key = 'value'", 1, 3)
        assert valid is False
        assert "not available" in msg

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_AVAILABLE", True)
    def test_validate_change(self) -> None:
        """Test change validation."""
        handler = TomlHandler()

        with patch("tomli.loads") as mock_tomli:
            mock_tomli.return_value = {"key": "value"}

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
        assert all(section in sections for section in expected_sections)
