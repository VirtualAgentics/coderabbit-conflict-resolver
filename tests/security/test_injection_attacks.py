"""Tests for injection attack prevention.

This module tests that handlers and the resolver properly prevent injection attacks
including YAML deserialization, command injection, and other malicious content.
"""

from pathlib import Path

from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.core.models import Change, FileType
from pr_conflict_resolver.handlers.json_handler import JsonHandler
from pr_conflict_resolver.handlers.toml_handler import TomlHandler
from pr_conflict_resolver.handlers.yaml_handler import YamlHandler


class TestYAMLDeserializationAttacks:
    """Tests for YAML deserialization attack prevention."""

    def test_yaml_handler_rejects_python_object_serialization(self, tmp_path: Path) -> None:
        """Test that YAML handler rejects Python object serialization."""
        handler = YamlHandler(workspace_root=str(tmp_path))
        test_file = tmp_path / "test.yaml"

        # YAML deserialization attack
        malicious_content = "!!python/object/apply:os.system\nargs: ['rm -rf /']"
        test_file.write_text(malicious_content)

        # Handler should validate and reject malicious content
        result = handler.validate_change(str(test_file), malicious_content, 1, 1)
        # Explicitly assert validation rejected the malicious content
        assert result[0] is False, "Handler should reject malicious YAML with python/object"
        # Explicitly assert sanitized content contains no dangerous tokens
        assert (
            "python/object" not in result[1].lower()
        ), f"Sanitized content should not contain 'python/object' token: {result[1]}"

    def test_yaml_handler_rejects_module_imports(self, tmp_path: Path) -> None:
        """Test that YAML handler rejects module imports."""
        handler = YamlHandler(workspace_root=str(tmp_path))
        test_file = tmp_path / "test.yaml"

        malicious_content = "!!python/object/apply:subprocess.call\nargs: [['cat', '/etc/passwd']]"
        test_file.write_text(malicious_content)

        result = handler.validate_change(str(test_file), malicious_content, 1, 1)
        # Explicitly assert validation rejected the malicious content
        assert result[0] is False, "Handler should reject malicious YAML with python/object"
        # Explicitly assert sanitized content contains no dangerous tokens
        assert (
            "python/object" not in result[1].lower()
        ), f"Sanitized content should not contain 'python/object' token: {result[1]}"


class TestCommandInjectionAttacks:
    """Tests for command injection prevention."""

    def test_handlers_reject_command_substitution(self, tmp_path: Path) -> None:
        """Test that handlers reject command substitution attempts."""
        handlers = [
            JsonHandler(workspace_root=str(tmp_path)),
            YamlHandler(workspace_root=str(tmp_path)),
            TomlHandler(workspace_root=str(tmp_path)),
        ]

        injection_attempts = [
            "file$(whoami).json",
            "file`cat /etc/passwd`.json",
            "file;rm -rf /",
            "file|cat /etc/passwd",
        ]

        for handler in handlers:
            for injection in injection_attempts:
                # First check if handler would accept the extension
                if handler.can_handle(injection):
                    # If handler accepts the extension, it must still reject
                    # command injection in the path
                    result = handler.apply_change(injection, '{"key": "value"}', 1, 1)
                    assert not result, f"{handler.__class__.__name__} should reject: {injection}"

    def test_resolver_handles_command_injection_in_content(self) -> None:
        """Test that resolver handles command injection in content."""
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

        # Resolver should handle this without executing commands
        conflicts = resolver.detect_conflicts([malicious_change])
        assert conflicts is not None
        assert isinstance(conflicts, list)


class TestShellMetacharacterInjection:
    """Tests for shell metacharacter injection prevention."""

    def test_handlers_reject_shell_metacharacters_in_paths(self, tmp_path: Path) -> None:
        """Test that handlers reject shell metacharacters in paths."""
        handler = JsonHandler(workspace_root=str(tmp_path))

        dangerous_chars = [";", "|", "&", "`", "$", "(", ")", ">", "<", "\n", "\r"]

        for char in dangerous_chars:
            test_path = f"test{char}file.json"
            # Should be rejected
            result = handler.apply_change(test_path, '{"key": "value"}', 1, 1)
            assert not result, f"Should reject path with character: {char!r}"


class TestJSONInjection:
    """Tests for JSON injection prevention."""

    def test_json_handler_validates_structure(self, tmp_path: Path) -> None:
        """Test that JSON handler validates JSON structure."""
        handler = JsonHandler(workspace_root=str(tmp_path))
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        malicious_json = '{"key": "value", "key": "duplicate", "exec": "malicious"}'

        # Should detect and reject duplicate keys
        result = handler.validate_change(str(test_file), malicious_json, 1, 1)
        assert result[0] is False, "Handler should reject duplicate keys"
        assert (
            "duplicate" in result[1].lower()
        ), f"Error message should mention duplicate: {result[1]}"

    def test_json_handler_parses_string_values_safely(self, tmp_path: Path) -> None:
        """Test that JSON handler safely parses string values without XSS filtering.

        Note: JSON parsing should not perform XSS filtering. XSS prevention
        belongs to the presentation layer (templates, output encoding, or
        sanitization middleware). The JSON handler's role is to parse and
        validate JSON structure, not to filter content for specific contexts.
        See: OWASP XSS Prevention Cheat Sheet
        """
        handler = JsonHandler(workspace_root=str(tmp_path))
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        # XSS payloads are valid JSON string content
        # Filtering/encoding is the responsibility of output handlers
        malicious_content = '{"script": "<script>alert(\'xss\')</script>"}'

        result = handler.validate_change(str(test_file), malicious_content, 1, 1)
        # JSON handler should accept valid JSON regardless of string content
        # XSS filtering is not the JSON handler's responsibility
        assert result[0] is True, "JSON handler should accept valid JSON with string values"
        assert isinstance(result, tuple), "Result should be a tuple"

    def test_json_handler_validates_structure_strictly(self, tmp_path: Path) -> None:
        """Test that JSON handler validates JSON structure and rejects malformed/malicious JSON."""
        handler = JsonHandler(workspace_root=str(tmp_path))
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        # Test cases for malformed JSON syntax
        malformed_cases = [
            ('{"key": "value",}', "Trailing comma"),
            ('{"key": value}', "Missing quotes around value"),
            ('{"key": "value"', "Unclosed brace"),
            ('{"key": "value" "key2": "value2"}', "Missing comma"),
        ]

        for malformed_json, description in malformed_cases:
            result = handler.validate_change(str(test_file), malformed_json, 1, 1)
            assert result[0] is False, f"Should reject {description}: {malformed_json}"
            assert (
                "Invalid JSON" in result[1] or "duplicate" in result[1].lower()
            ), f"Error message should indicate issue: {result[1]}"

        # Test JSON bombs - deeply nested objects (but not so deep as to cause recursion)
        nested_json = '{"a":' * 10 + '"value"' + "}" * 10
        result = handler.validate_change(str(test_file), nested_json, 1, 1)
        # Should handle nested objects gracefully without crashing
        assert isinstance(result, tuple), "Should return tuple even for nested input"
        # Note: The handler may accept or reject this depending on implementation
        # The important thing is it doesn't crash

        # Test invalid escape sequences
        invalid_escape_json = '{"key": "value\\uXXXX"}'
        result = handler.validate_change(str(test_file), invalid_escape_json, 1, 1)
        assert result[0] is False, "Should reject invalid Unicode escape"
        assert "Invalid JSON" in result[1], f"Error message should indicate JSON issue: {result[1]}"


class TestTOMLInjection:
    """Tests for TOML injection prevention."""

    def test_toml_handler_validates_structure(self, tmp_path: Path) -> None:
        """Test that TOML handler validates TOML structure."""
        handler = TomlHandler(workspace_root=str(tmp_path))
        test_file = tmp_path / "test.toml"
        test_file.write_text('[section]\nkey = "value"')

        malicious_toml = '[section]\nkey = "value" $rm -rf /'

        result = handler.validate_change(str(test_file), malicious_toml, 1, 2)
        # Should reject TOML with shell metacharacters
        assert isinstance(result, tuple), "Should return tuple"
        assert result[0] is False, "Should reject TOML with shell metacharacters"
        assert (
            "Invalid" in result[1] or "detected" in result[1].lower()
        ), f"Error message should indicate security issue: {result[1]}"


class TestEnvironmentVariableInjection:
    """Tests for environment variable injection prevention."""

    def test_handlers_reject_env_var_injection_in_paths(self, tmp_path: Path) -> None:
        """Test that handlers reject environment variable injection in paths."""
        handler = JsonHandler(workspace_root=str(tmp_path))

        injection_attempts = [
            "$HOME/file.json",
            "${PWD}/file.json",
            "$(pwd)/file.json",
        ]

        for injection in injection_attempts:
            result = handler.apply_change(injection, '{"key": "value"}', 1, 1)
            assert not result, f"Should reject path with env var: {injection}"


class TestContentSanitization:
    """Tests for content sanitization across handlers."""

    def test_handlers_reject_null_bytes(self, tmp_path: Path) -> None:
        """Test that handlers reject content containing null bytes."""
        handlers = [
            JsonHandler(workspace_root=str(tmp_path)),
            YamlHandler(workspace_root=str(tmp_path)),
            TomlHandler(workspace_root=str(tmp_path)),
        ]

        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        malicious_content = '{"key": "value\x00malicious"}'

        for handler in handlers:
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
