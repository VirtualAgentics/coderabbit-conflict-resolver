"""Test the file handlers."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from pr_conflict_resolver import JsonHandler, YamlHandler, TomlHandler


class TestJsonHandler:
    """Test the JSON handler."""
    
    def test_can_handle(self):
        """Test file type detection."""
        handler = JsonHandler()
        
        assert handler.can_handle("test.json") is True
        assert handler.can_handle("test.JSON") is True
        assert handler.can_handle("test.yaml") is False
        assert handler.can_handle("test.txt") is False
    
    def test_has_duplicate_keys(self):
        """Test duplicate key detection."""
        handler = JsonHandler()
        
        # No duplicates
        data = {"key1": "value1", "key2": "value2"}
        assert handler._has_duplicate_keys(data) is False
        
        # Has duplicates
        data = {"key1": "value1", "key1": "value2"}
        assert handler._has_duplicate_keys(data) is True
        
        # Nested duplicates
        data = {"outer": {"key1": "value1", "key1": "value2"}}
        assert handler._has_duplicate_keys(data) is True
    
    def test_validate_change(self):
        """Test change validation."""
        handler = JsonHandler()
        
        # Valid JSON
        valid, msg = handler.validate_change("test.json", '{"key": "value"}', 1, 3)
        assert valid is True
        assert "Valid JSON" in msg
        
        # Invalid JSON
        valid, msg = handler.validate_change("test.json", '{"key": "value"', 1, 3)
        assert valid is False
        assert "Invalid JSON" in msg
        
        # Duplicate keys
        valid, msg = handler.validate_change("test.json", '{"key": "value", "key": "value2"}', 1, 3)
        assert valid is False
        assert "Duplicate keys" in msg
    
    def test_detect_conflicts(self):
        """Test conflict detection."""
        handler = JsonHandler()
        
        changes = [
            {"content": '{"key1": "value1"}'},
            {"content": '{"key1": "value2"}'},
            {"content": '{"key2": "value3"}'}
        ]
        
        conflicts = handler.detect_conflicts("test.json", changes)
        
        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "key_conflict"
        assert conflicts[0]["key"] == "key1"
        assert len(conflicts[0]["changes"]) == 2
    
    def test_smart_merge_json(self):
        """Test smart JSON merging."""
        handler = JsonHandler()
        
        original = {"key1": "value1", "key2": "value2"}
        suggestion = {"key1": "new_value1", "key3": "value3"}
        
        result = handler._smart_merge_json(original, suggestion, 1, 3)
        
        expected = {"key1": "new_value1", "key2": "value2", "key3": "value3"}
        assert result == expected
    
    def test_is_complete_object(self):
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
    
    def test_can_handle(self):
        """Test file type detection."""
        handler = YamlHandler()
        
        assert handler.can_handle("test.yaml") is True
        assert handler.can_handle("test.yml") is True
        assert handler.can_handle("test.YAML") is True
        assert handler.can_handle("test.json") is False
        assert handler.can_handle("test.txt") is False
    
    @patch('pr_conflict_resolver.handlers.yaml_handler.YAML_AVAILABLE', False)
    def test_yaml_not_available(self):
        """Test behavior when ruamel.yaml is not available."""
        handler = YamlHandler()
        
        valid, msg = handler.validate_change("test.yaml", "key: value", 1, 3)
        assert valid is False
        assert "not available" in msg
    
    @patch('pr_conflict_resolver.handlers.yaml_handler.YAML_AVAILABLE', True)
    def test_validate_change(self):
        """Test change validation."""
        handler = YamlHandler()
        
        with patch('ruamel.yaml.YAML') as mock_yaml:
            mock_yaml.return_value.load.return_value = {"key": "value"}
            
            valid, msg = handler.validate_change("test.yaml", "key: value", 1, 3)
            assert valid is True
            assert "Valid YAML" in msg
    
    def test_extract_keys(self):
        """Test key extraction."""
        handler = YamlHandler()
        
        data = {
            "key1": "value1",
            "key2": {
                "nested1": "value2",
                "nested2": ["item1", "item2"]
            }
        }
        
        keys = handler._extract_keys(data)
        
        expected_keys = ["key1", "key2", "key2.nested1", "key2.nested2", "key2.nested2[0]", "key2.nested2[1]"]
        assert all(key in keys for key in expected_keys)


class TestTomlHandler:
    """Test the TOML handler."""
    
    def test_can_handle(self):
        """Test file type detection."""
        handler = TomlHandler()
        
        assert handler.can_handle("test.toml") is True
        assert handler.can_handle("test.TOML") is True
        assert handler.can_handle("test.json") is False
        assert handler.can_handle("test.txt") is False
    
    @patch('pr_conflict_resolver.handlers.toml_handler.TOML_AVAILABLE', False)
    def test_toml_not_available(self):
        """Test behavior when tomli is not available."""
        handler = TomlHandler()
        
        valid, msg = handler.validate_change("test.toml", "key = 'value'", 1, 3)
        assert valid is False
        assert "not available" in msg
    
    @patch('pr_conflict_resolver.handlers.toml_handler.TOML_AVAILABLE', True)
    def test_validate_change(self):
        """Test change validation."""
        handler = TomlHandler()
        
        with patch('tomli.loads') as mock_tomli:
            mock_tomli.return_value = {"key": "value"}
            
            valid, msg = handler.validate_change("test.toml", "key = 'value'", 1, 3)
            assert valid is True
            assert "Valid TOML" in msg
    
    def test_extract_sections(self):
        """Test section extraction."""
        handler = TomlHandler()
        
        data = {
            "section1": "value1",
            "section2": {
                "subsection1": "value2",
                "subsection2": "value3"
            }
        }
        
        sections = handler._extract_sections(data)
        
        expected_sections = ["section1", "section2", "section2.subsection1", "section2.subsection2"]
        assert all(section in sections for section in expected_sections)
