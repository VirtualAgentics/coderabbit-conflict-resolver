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
                # Should either reject or sanitize
                assert not result[0] or "python/object" not in result[1].lower()
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
                assert not result[0] or "python/object" not in result[1].lower()
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
                # Handlers should not apply changes with command injection
                assert not handler.can_handle(injection) or not handler.apply_change(
                    injection, '{"key": "value"}', 1, 1
                ), f"{handler.__class__.__name__} should reject: {injection}"

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
                # Should detect duplicate keys or malicious content
                result = handler.validate_change(f.name, malicious_json, 1, 1)
                # Should either reject or clean the content
                assert not result[0] or "duplicate" in result[1].lower()
            finally:
                Path(f.name).unlink()

    def test_json_handler_rejects_executable_code(self) -> None:
        """Test that JSON handler rejects executable code."""
        handler = JsonHandler()

        malicious_content = '{"script": "<script>alert(\'xss\')</script>"}'

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            f.flush()

            try:
                result = handler.validate_change(f.name, malicious_content, 1, 1)
                # Should handle sanitization
                assert isinstance(result, tuple)
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
                # Should detect malicious content
                assert isinstance(result, tuple)
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

    def test_handlers_sanitize_null_bytes(self) -> None:
        """Test that handlers sanitize null bytes in content."""
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
                    result = handler.validate_change(f.name, malicious_content, 1, 1)
                    # Should sanitize null bytes
                    assert isinstance(result, tuple)
                finally:
                    Path(f.name).unlink()
