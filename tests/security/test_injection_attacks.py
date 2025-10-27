"""Tests for injection attack prevention.

This module tests that handlers and the resolver properly prevent injection attacks
including YAML deserialization, command injection, and other malicious content.
"""

import tempfile
from pathlib import Path

from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.core.models import Change, FileType
from pr_conflict_resolver.handlers.json_handler import JsonHandler
from pr_conflict_resolver.handlers.toml_handler import TomlHandler
from pr_conflict_resolver.handlers.yaml_handler import YamlHandler


class TestYAMLDeserializationAttacks:
    """Tests for YAML deserialization attack prevention."""

    def test_yaml_handler_rejects_python_object_serialization(self) -> None:
        """Test that YAML handler rejects Python object serialization."""
        handler = YamlHandler()

        # YAML deserialization attack
        malicious_content = "!!python/object/apply:os.system\nargs: ['rm -rf /']"

        # Handler should reject or sanitize this
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(malicious_content)
            f.flush()

            try:
                # Handler should validate and reject malicious content
                result = handler.validate_change(f.name, malicious_content, 1, 1)
                # Explicitly assert validation rejected the malicious content
                assert result[0] is False, "Handler should reject malicious YAML with python/object"
                # Explicitly assert sanitized content contains no dangerous tokens
                assert (
                    "python/object" not in result[1].lower()
                ), f"Sanitized content should not contain 'python/object' token: {result[1]}"
            finally:
                Path(f.name).unlink()

    def test_yaml_handler_rejects_module_imports(self) -> None:
        """Test that YAML handler rejects module imports."""
        handler = YamlHandler()

        malicious_content = "!!python/object/apply:subprocess.call\nargs: [['cat', '/etc/passwd']]"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(malicious_content)
            f.flush()

            try:
                result = handler.validate_change(f.name, malicious_content, 1, 1)
                # Explicitly assert validation rejected the malicious content
                assert result[0] is False, "Handler should reject malicious YAML with python/object"
                # Explicitly assert sanitized content contains no dangerous tokens
                assert (
                    "python/object" not in result[1].lower()
                ), f"Sanitized content should not contain 'python/object' token: {result[1]}"
            finally:
                Path(f.name).unlink()


class TestCommandInjectionAttacks:
    """Tests for command injection prevention."""

    def test_handlers_reject_command_substitution(self) -> None:
        """Test that handlers reject command substitution attempts."""
        handlers = [
            JsonHandler(),
            YamlHandler(),
            TomlHandler(),
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

    def test_handlers_reject_shell_metacharacters_in_paths(self) -> None:
        """Test that handlers reject shell metacharacters in paths."""
        handler = JsonHandler()

        dangerous_chars = [";", "|", "&", "`", "$", "(", ")", ">", "<", "\n", "\r"]

        for char in dangerous_chars:
            test_path = f"test{char}file.json"
            # Should be rejected
            result = handler.apply_change(test_path, '{"key": "value"}', 1, 1)
            assert not result, f"Should reject path with character: {char!r}"


class TestJSONInjection:
    """Tests for JSON injection prevention."""

    def test_json_handler_validates_structure(self) -> None:
        """Test that JSON handler validates JSON structure."""
        handler = JsonHandler()

        malicious_json = '{"key": "value", "key": "duplicate", "exec": "malicious"}'

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            try:
                # Should detect and reject duplicate keys
                result = handler.validate_change(f.name, malicious_json, 1, 1)
                assert result[0] is False, "Handler should reject duplicate keys"
                assert (
                    "duplicate" in result[1].lower()
                ), f"Error message should mention duplicate: {result[1]}"
            finally:
                Path(f.name).unlink()

    def test_json_handler_parses_string_values_safely(self) -> None:
        """Test that JSON handler safely parses string values without XSS filtering.

        Note: JSON parsing should not perform XSS filtering. XSS prevention
        belongs to the presentation layer (templates, output encoding, or
        sanitization middleware). The JSON handler's role is to parse and
        validate JSON structure, not to filter content for specific contexts.
        See: OWASP XSS Prevention Cheat Sheet
        """
        handler = JsonHandler()

        # XSS payloads are valid JSON string content
        # Filtering/encoding is the responsibility of output handlers
        malicious_content = '{"script": "<script>alert(\'xss\')</script>"}'

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            try:
                # Use relative path to avoid absolute path validation issues
                relative_path = Path(f.name).name
                result = handler.validate_change(relative_path, malicious_content, 1, 1)
                # JSON handler should accept valid JSON regardless of string content
                # XSS filtering is not the JSON handler's responsibility
                assert result[0] is True, "JSON handler should accept valid JSON with string values"
                assert isinstance(result, tuple), "Result should be a tuple"
            finally:
                Path(f.name).unlink()

    def test_json_handler_validates_structure_strictly(self) -> None:
        """Test that JSON handler validates JSON structure and rejects malformed/malicious JSON."""
        handler = JsonHandler()

        # Test cases for malformed JSON syntax
        malformed_cases = [
            ('{"key": "value",}', "Trailing comma"),
            ('{"key": value}', "Missing quotes around value"),
            ('{"key": "value"', "Unclosed brace"),
            ('{"key": "value" "key2": "value2"}', "Missing comma"),
        ]

        for malformed_json, description in malformed_cases:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                f.write('{"key": "value"}')
                f.flush()

                try:
                    # Use relative path to avoid absolute path validation issues
                    relative_path = Path(f.name).name
                    result = handler.validate_change(relative_path, malformed_json, 1, 1)
                    assert result[0] is False, f"Should reject {description}: {malformed_json}"
                    assert (
                        "Invalid JSON" in result[1] or "duplicate" in result[1].lower()
                    ), f"Error message should indicate issue: {result[1]}"
                finally:
                    Path(f.name).unlink()

        # Test JSON bombs - deeply nested objects (but not so deep as to cause recursion)
        nested_json = '{"a":' * 10 + '"value"' + "}" * 10
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            try:
                # Use relative path to avoid absolute path validation issues
                relative_path = Path(f.name).name
                result = handler.validate_change(relative_path, nested_json, 1, 1)
                # Should handle nested objects gracefully without crashing
                assert isinstance(result, tuple), "Should return tuple even for nested input"
                # Note: The handler may accept or reject this depending on implementation
                # The important thing is it doesn't crash
            finally:
                Path(f.name).unlink()

        # Test invalid escape sequences
        invalid_escape_json = '{"key": "value\\uXXXX"}'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            try:
                # Use relative path to avoid absolute path validation issues
                relative_path = Path(f.name).name
                result = handler.validate_change(relative_path, invalid_escape_json, 1, 1)
                assert result[0] is False, "Should reject invalid Unicode escape"
                assert (
                    "Invalid JSON" in result[1]
                ), f"Error message should indicate JSON issue: {result[1]}"
            finally:
                Path(f.name).unlink()


class TestTOMLInjection:
    """Tests for TOML injection prevention."""

    def test_toml_handler_validates_structure(self) -> None:
        """Test that TOML handler validates TOML structure."""
        handler = TomlHandler()

        malicious_toml = '[section]\nkey = "value" $rm -rf /'

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('[section]\nkey = "value"')
            f.flush()

            try:
                result = handler.validate_change(f.name, malicious_toml, 1, 2)
                # Should reject TOML with shell metacharacters
                assert isinstance(result, tuple), "Should return tuple"
                assert result[0] is False, "Should reject TOML with shell metacharacters"
                assert (
                    "Invalid" in result[1] or "detected" in result[1].lower()
                ), f"Error message should indicate security issue: {result[1]}"
            finally:
                Path(f.name).unlink()


class TestEnvironmentVariableInjection:
    """Tests for environment variable injection prevention."""

    def test_handlers_reject_env_var_injection_in_paths(self) -> None:
        """Test that handlers reject environment variable injection in paths."""
        handler = JsonHandler()

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

    def test_handlers_reject_null_bytes(self) -> None:
        """Test that handlers reject content containing null bytes."""
        handlers = [
            JsonHandler(),
            YamlHandler(),
            TomlHandler(),
        ]

        malicious_content = '{"key": "value\x00malicious"}'

        for handler in handlers:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                f.write('{"key": "value"}')
                f.flush()

                try:
                    # Use relative path to avoid absolute path validation issues
                    relative_path = Path(f.name).name
                    result = handler.validate_change(relative_path, malicious_content, 1, 1)

                    # Should reject content with null bytes
                    assert isinstance(result, tuple), "Result should be a tuple"
                    assert (
                        result[0] is False
                    ), f"{handler.__class__.__name__} should reject content with null bytes"
                    assert (
                        "Invalid" in result[1]
                    ), f"Error message should indicate invalid content: {result[1]}"
                    assert "\x00" not in result[1], "Error message should not contain null bytes"
                finally:
                    Path(f.name).unlink()
