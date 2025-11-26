"""Tests for injection attack prevention.

This module tests that handlers and the resolver properly prevent injection attacks
including YAML deserialization, command injection, and other malicious content.
"""

import re
from pathlib import Path

import pytest

from review_bot_automator import ConflictResolver
from review_bot_automator.core.models import Change, FileType
from review_bot_automator.handlers.json_handler import JsonHandler
from review_bot_automator.handlers.toml_handler import TomlHandler
from review_bot_automator.handlers.yaml_handler import YamlHandler


class TestYAMLDeserializationAttacks:
    """Tests for YAML deserialization attack prevention."""

    def test_yaml_handler_rejects_python_object_serialization(
        self, yaml_handler: YamlHandler, tmp_path: Path
    ) -> None:
        """Test that YAML handler rejects Python object serialization."""
        test_file = tmp_path / "test.yaml"

        # YAML deserialization attack
        malicious_content = "!!python/object/apply:os.system\nargs: ['rm -rf /']"
        test_file.write_text(malicious_content)

        # Handler should validate and reject malicious content
        result = yaml_handler.validate_change(str(test_file), malicious_content, 1, 1)
        # Explicitly assert validation rejected the malicious content
        assert result[0] is False, "Handler should reject malicious YAML with python/object"

        # Assert error message structure and content
        error_message = result[1]
        assert re.search(
            r"(?i)(dangerous|validation|reject|invalid|unsafe)",
            error_message,
        ), f"Error message should indicate validation failure: {error_message}"
        assert re.search(
            r"(?i)(python.*object|object.*tag)",
            error_message,
        ), f"Error message should reference Python object: {error_message}"

    def test_yaml_handler_rejects_module_imports(
        self, yaml_handler: YamlHandler, tmp_path: Path
    ) -> None:
        """Test that YAML handler rejects module imports."""
        test_file = tmp_path / "test.yaml"

        malicious_content = "!!python/object/apply:subprocess.call\nargs: [['cat', '/etc/passwd']]"
        test_file.write_text(malicious_content)

        result = yaml_handler.validate_change(str(test_file), malicious_content, 1, 1)
        # Explicitly assert validation rejected the malicious content
        assert result[0] is False, "Handler should reject malicious YAML with subprocess.call"

        # Assert error message structure and content
        error_message = result[1]
        assert re.search(
            r"(?i)(dangerous|validation|reject|invalid|unsafe)",
            error_message,
        ), f"Error message should indicate validation failure: {error_message}"
        assert re.search(
            r"(?i)(python.*object|object.*tag|subprocess)",
            error_message,
        ), f"Error message should reference unsafe Python construct: {error_message}"


class TestCommandInjectionAttacks:
    """Tests for command injection prevention."""

    def test_handlers_reject_command_substitution(
        self,
        json_handler: JsonHandler,
        yaml_handler: YamlHandler,
        toml_handler: TomlHandler,
        tmp_path: Path,
    ) -> None:
        """Test that handlers reject command substitution attempts."""
        handlers = [json_handler, yaml_handler, toml_handler]

        ext_map = {
            type(json_handler): ".json",
            type(yaml_handler): ".yaml",
            type(toml_handler): ".toml",
        }
        base = [
            "file$(whoami)",
            "file`cat /etc/passwd`",
            "file;rm -rf /",
            "file|cat /etc/passwd",
        ]

        def payload_for(h: object) -> str:
            if isinstance(h, JsonHandler):
                return '{"key": "value"}'
            if isinstance(h, YamlHandler):
                return "key: value"
            return 'key = "value"'

        for handler in handlers:
            ext = ext_map[type(handler)]
            for base_name in base:
                injection = (
                    f"{base_name}{ext}"
                    if not base_name.endswith((".json", ".yaml", ".toml"))
                    else base_name
                )
                if handler.can_handle(injection):
                    result = handler.apply_change(injection, payload_for(handler), 1, 1)
                    assert not result, f"{handler.__class__.__name__} should reject: {injection}"

    def test_resolver_handles_command_injection_in_content(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that resolver handles command injection in content."""
        from unittest.mock import Mock

        resolver = ConflictResolver()

        malicious_change = Change(
            path="test.json",
            start_line=1,
            end_line=1,
            content='{"key": "value $(rm -rf /)"}',
            metadata={},
            fingerprint="test",
            file_type=FileType.JSON,
        )

        # Mock subprocess/os.system to ensure they're never called
        mock_subprocess = Mock()
        mock_os_system = Mock()
        monkeypatch.setattr("subprocess.call", mock_subprocess, raising=True)
        monkeypatch.setattr("subprocess.run", mock_subprocess, raising=True)
        monkeypatch.setattr("subprocess.Popen", mock_subprocess, raising=True)
        monkeypatch.setattr("os.system", mock_os_system, raising=True)

        # Resolver should handle this without executing commands
        conflicts = resolver.detect_conflicts([malicious_change])

        # Verify resolver processes without crashing
        assert conflicts is not None
        assert isinstance(conflicts, list)

        # Verify no subprocess calls were made (command injection prevented)
        assert not mock_subprocess.called, "subprocess should not be called"
        assert not mock_os_system.called, "os.system should not be called"

        # Verify structure and boolean success without asserting exact message text
        assert isinstance(conflicts, list)


class TestShellMetacharacterInjection:
    """Tests for shell metacharacter injection prevention."""

    @pytest.mark.parametrize(
        "handler,payload",
        [
            (JsonHandler(), '{"key": "value"}'),
            (YamlHandler(), "key: value"),
            (TomlHandler(), 'key = "value"'),
        ],
    )
    def test_handlers_reject_shell_metacharacters_in_paths(
        self, handler: JsonHandler | YamlHandler | TomlHandler, payload: str
    ) -> None:
        """All handlers should reject shell metacharacters in paths."""
        dangerous_chars = [";", "|", "&", "`", "$", "(", ")", ">", "<", "\n", "\r"]

        for char in dangerous_chars:
            ext = (
                ".json"
                if isinstance(handler, JsonHandler)
                else (".yaml" if isinstance(handler, YamlHandler) else ".toml")
            )
            test_path = f"test{char}file{ext}"
            result = handler.apply_change(test_path, payload, 1, 1)
            assert not result, f"Should reject path with character: {char!r}"


class TestJSONInjection:
    """Tests for JSON injection prevention."""

    def test_json_handler_validates_structure(
        self, json_handler: JsonHandler, tmp_path: Path
    ) -> None:
        """Test that JSON handler validates JSON structure."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        malicious_json = '{"key": "value", "key": "duplicate", "exec": "malicious"}'

        # Should detect and reject duplicate keys
        result = json_handler.validate_change(str(test_file), malicious_json, 1, 1)
        assert result[0] is False, "Handler should reject duplicate keys"
        assert (
            "duplicate" in result[1].lower()
        ), f"Error message should mention duplicate: {result[1]}"

    def test_json_handler_accepts_valid_json_with_string_content(
        self, json_handler: JsonHandler, tmp_path: Path
    ) -> None:
        """Test that JSON handler accepts valid JSON regardless of string content.

        This test verifies scope boundaries: the JSON handler validates JSON
        syntax and structure only. XSS prevention is the responsibility of
        presentation layers (templates, output encoding, sanitization middleware).

        Security Responsibility Boundaries:
        - Input validation: InputValidator (paths/structure)
        - Content sanitization: Presentation layers/middleware
        - JSON handler: JSON syntax and structure validation only
        """
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        # XSS payloads are valid JSON string content
        # Filtering/encoding is the responsibility of output handlers
        malicious_content = '{"script": "<script>alert(\'xss\')</script>"}'

        result = json_handler.validate_change(str(test_file), malicious_content, 1, 1)
        # JSON handler should accept valid JSON regardless of string content
        # XSS filtering is not the JSON handler's responsibility
        assert result[0] is True, "JSON handler should accept valid JSON with string values"
        assert isinstance(result, tuple), "Result should be a tuple"

    @pytest.mark.parametrize(
        "malformed_json,description",
        [
            ('{"key": "value",}', "Trailing comma"),
            ('{"key": value}', "Missing quotes around value"),
            ('{"key": "value"', "Unclosed brace"),
            ('{"key": "value" "key2": "value2"}', "Missing comma"),
        ],
    )
    def test_json_handler_validates_structure_strictly(
        self, json_handler: JsonHandler, tmp_path: Path, malformed_json: str, description: str
    ) -> None:
        """Test that JSON handler validates JSON structure and rejects malformed JSON."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        result = json_handler.validate_change(str(test_file), malformed_json, 1, 1)
        assert result[0] is False, f"Should reject {description}: {malformed_json}"
        assert (
            "Invalid JSON" in result[1] or "duplicate" in result[1].lower()
        ), f"Error message should indicate issue: {result[1]}"

    def test_json_handler_accepts_valid_nested_json(
        self, json_handler: JsonHandler, tmp_path: Path
    ) -> None:
        """Test that JSON handler accepts valid deeply nested JSON."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        # Test JSON bombs - deeply nested objects (but not so deep as to cause recursion)
        nested_json = '{"a":' * 10 + '"value"' + "}" * 10
        result = json_handler.validate_change(str(test_file), nested_json, 1, 1)

        # Should handle nested objects gracefully without crashing
        assert isinstance(result, tuple), "Should return tuple even for nested input"
        # Assert explicit success for valid nested JSON
        assert result[0] is True, "Handler should accept valid nested JSON"
        assert isinstance(result[1], str) and result[1], "Message must be a non-empty string"

    def test_json_handler_rejects_invalid_unicode_escape(
        self, json_handler: JsonHandler, tmp_path: Path
    ) -> None:
        """Test that JSON handler rejects invalid Unicode escape sequences."""
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        # Test invalid escape sequences
        invalid_escape_json = '{"key": "value\\uXXXX"}'
        result = json_handler.validate_change(str(test_file), invalid_escape_json, 1, 1)

        assert result[0] is False, "Should reject invalid Unicode escape"
        assert "Invalid JSON" in result[1], f"Error message should indicate JSON issue: {result[1]}"


class TestTOMLInjection:
    """Tests for TOML injection prevention."""

    def test_toml_handler_validates_structure(
        self, toml_handler: TomlHandler, tmp_path: Path
    ) -> None:
        """Test that TOML handler validates TOML structure."""
        test_file = tmp_path / "test.toml"
        test_file.write_text('[section]\nkey = "value"')

        malicious_toml = '[section]\nkey = "value" $rm -rf /'

        result = toml_handler.validate_change(str(test_file), malicious_toml, 1, 2)
        # Should reject TOML with shell metacharacters
        assert isinstance(result, tuple), "Should return tuple"
        assert result[0] is False, "Should reject TOML with shell metacharacters"
        assert (
            "Invalid" in result[1] or "detected" in result[1].lower()
        ), f"Error message should indicate security issue: {result[1]}"


class TestEnvironmentVariableInjection:
    """Tests for environment variable injection prevention."""

    @pytest.mark.parametrize(
        "handler_fixture,content",
        [
            ("json_handler", '{"key": "value"}'),
            ("yaml_handler", "key: value"),
            ("toml_handler", 'key = "value"'),
        ],
    )
    def test_handlers_reject_env_var_injection_in_paths(
        self, request: pytest.FixtureRequest, handler_fixture: str, content: str
    ) -> None:
        """All handlers must reject environment variable injection in paths."""
        handler = request.getfixturevalue(handler_fixture)
        injection_attempts = [
            "$HOME/file.json",
            "${PWD}/file.json",
            "$(pwd)/file.json",
        ]

        for injection in injection_attempts:
            result = handler.apply_change(injection, content, 1, 1)
            assert (
                not result
            ), f"{handler.__class__.__name__} should reject path with env var: {injection}"


class TestContentSanitization:
    """Tests for content sanitization across handlers."""

    def test_handlers_reject_null_bytes(
        self,
        json_handler: JsonHandler,
        yaml_handler: YamlHandler,
        toml_handler: TomlHandler,
        tmp_path: Path,
    ) -> None:
        """Test that handlers reject content containing null bytes."""
        handlers = [json_handler, yaml_handler, toml_handler]

        malicious_content = '{"key": "value\x00malicious"}'

        def _ext_for(h: object) -> str:
            name = h.__class__.__name__.lower()
            if "json" in name:
                return ".json"
            if "yaml" in name or "yml" in name:
                return ".yaml"
            if "toml" in name:
                return ".toml"
            return ".txt"

        for handler in handlers:
            ext = _ext_for(handler)
            test_file = tmp_path / f"test{ext}"
            # create benign baseline content for the file
            baseline = (
                '{"key": "value"}'
                if ext == ".json"
                else ("key: value" if ext in (".yaml", ".yml") else 'key = "value"')
            )
            test_file.write_text(baseline)

            result = handler.validate_change(str(test_file), malicious_content, 1, 1)

            # Should reject content with null bytes
            assert isinstance(result, tuple), "Result should be a tuple"
            assert (
                result[0] is False
            ), f"{handler.__class__.__name__} should reject content with null bytes"
            assert (
                "Invalid" in result[1]
            ), f"Error message should indicate invalid content: {result[1]}"
            assert "\x00" not in result[1], "Error message should not contain null bytes"
