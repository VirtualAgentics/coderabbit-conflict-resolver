"""Property-based fuzzing tests for TOMLHandler.

This module uses Hypothesis to perform property-based testing on the TOMLHandler
class, focusing on finding edge cases in TOML parsing, validation, and section
handling.

Test Coverage:
- TOML parsing with arbitrary content
- Section name handling
- Table structure validation
- Type mismatch detection
"""

import tempfile
import tomllib
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from review_bot_automator.handlers.toml_handler import TomlHandler

# =============================================================================
# TOML Validation Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(content=st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_toml_validate_change_never_crashes(content: str) -> None:
    """Fuzz validate_change() with arbitrary text.

    Property: TOML validation should handle any string without crashing,
    returning a boolean result.

    Args:
        content: Arbitrary string to test as TOML content
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TomlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.toml", content, 1, 1)
        assert isinstance(is_valid, bool), "validate_change must return bool"
        assert isinstance(message, str), "validate_change must return message"


@pytest.mark.fuzz
@given(
    key=st.text(alphabet=st.characters(categories=("Lu", "Ll", "Nd")), min_size=1, max_size=20),
    value=st.one_of(st.integers(), st.text(max_size=30), st.booleans()),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_toml_validate_with_simple_pairs(key: str, value: int | str | bool) -> None:
    """Fuzz TOML validation with simple key-value pairs.

    Property: Simple TOML structures should be parsed without crashes.

    Args:
        key: TOML key
        value: TOML value
    """
    # Create valid TOML content
    if isinstance(value, str):
        content = f'{key} = "{value}"'
    else:
        content = f"{key} = {str(value).lower() if isinstance(value, bool) else value}"

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TomlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.toml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)


# =============================================================================
# TOML Section/Table Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(
    section=st.text(alphabet=st.characters(categories=("Lu", "Ll", "Nd")), min_size=1, max_size=20),
    key=st.text(alphabet=st.characters(categories=("Lu", "Ll")), min_size=1, max_size=15),
    value=st.integers(),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_toml_section_handling(section: str, key: str, value: int) -> None:
    """Fuzz TOML validation with sections/tables.

    Property: TOML with valid section names should be parsed correctly.

    Args:
        section: Section name
        key: Key within section
        value: Value for the key
    """
    content = f"[{section}]\n{key} = {value}"

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TomlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.toml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

        # Try to parse as TOML to verify validity
        try:
            tomllib.loads(content)
            # If it parses, validation should pass
            assert is_valid is True, "Valid TOML should pass validation"
        except tomllib.TOMLDecodeError:
            # If it doesn't parse, validation should fail
            pass


@pytest.mark.fuzz
@given(
    sections=st.lists(
        st.text(alphabet=st.characters(categories=("Lu", "Ll")), min_size=1, max_size=10),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_toml_multiple_sections(sections: list[str]) -> None:
    """Fuzz TOML validation with multiple sections.

    Property: TOML with multiple sections should be handled correctly.

    Args:
        sections: List of section names
    """
    content_parts = [f'[{section}]\nkey = "value"' for section in sections]
    content = "\n\n".join(content_parts)

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TomlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.toml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)


# =============================================================================
# TOML Type Handling Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(
    key=st.text(alphabet=st.characters(categories=("Lu", "Ll")), min_size=1, max_size=15),
    value_type=st.sampled_from(["int", "float", "bool", "string", "array"]),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_toml_different_types(key: str, value_type: str) -> None:
    """Fuzz TOML validation with different value types.

    Property: TOML should correctly handle various data types.

    Args:
        key: Key name
        value_type: Type of value to use
    """
    # Create content based on type
    if value_type == "int":
        content = f"{key} = 42"
    elif value_type == "float":
        content = f"{key} = 3.14"
    elif value_type == "bool":
        content = f"{key} = true"
    elif value_type == "string":
        content = f'{key} = "test"'
    else:  # array
        content = f'{key} = ["item1", "item2"]'

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TomlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.toml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)
        # Try to parse as TOML - if it's valid, handler should accept it
        try:
            tomllib.loads(content)
            assert is_valid is True, "Valid TOML with various types should pass"
        except tomllib.TOMLDecodeError:
            # If TOML lib can't parse it, that's expected for some keys
            pass


# =============================================================================
# Malformed TOML Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(
    malformed=st.sampled_from(
        [
            "[section\n",  # Missing closing bracket
            "key = \n",  # Missing value
            "= value\n",  # Missing key
            "[]\n",  # Empty section name
            "key value\n",  # Missing =
            "[[array]]\nkey = value\n[[array]]\nkey = value",  # Duplicate array tables
        ]
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_toml_malformed_structures(malformed: str) -> None:
    """Fuzz TOML validation with malformed TOML.

    Property: Malformed TOML should be rejected without crashing.

    Args:
        malformed: Malformed TOML content
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TomlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.toml", malformed, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

        # Malformed TOML should fail validation
        try:
            tomllib.loads(malformed)
        except tomllib.TOMLDecodeError:
            assert is_valid is False, "Malformed TOML should be rejected"


# =============================================================================
# Apply Change Fuzzing (Integration)
# =============================================================================


@pytest.mark.fuzz
@given(
    original_key=st.text(alphabet=st.characters(categories=("Lu", "Ll")), min_size=1, max_size=10),
    original_value=st.integers(),
    new_key=st.text(alphabet=st.characters(categories=("Lu", "Ll")), min_size=1, max_size=10),
    new_value=st.integers(),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_toml_apply_change_never_crashes(
    original_key: str, original_value: int, new_key: str, new_value: int
) -> None:
    """Fuzz apply_change() with various modifications.

    Property: Applying changes should either succeed or fail gracefully
    without crashing.

    Args:
        original_key: Original key name
        original_value: Original value
        new_key: New key to add
        new_value: New value
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create original file
        toml_file = Path(tmpdir) / "test.toml"
        toml_file.write_text(f"{original_key} = {original_value}\n")

        # Create modification
        new_content = f"{new_key} = {new_value}"

        handler = TomlHandler(workspace_root=Path(tmpdir))

        try:
            # Apply change may fail for invalid input, which is expected
            result = handler.apply_change("test.toml", new_content, 1, 1)
            # If it succeeds, should return a bool
            assert isinstance(result, bool)
        except (ValueError, OSError, tomllib.TOMLDecodeError):
            # Expected exceptions for invalid input
            pass


@pytest.mark.fuzz
@given(
    lines=st.lists(
        st.text(alphabet=st.characters(categories=("Lu", "Ll", "Nd", "Zs")), max_size=40),
        min_size=1,
        max_size=10,
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_toml_multiline_content(lines: list[str]) -> None:
    """Fuzz TOML validation with multiline content.

    Property: Multiline TOML should be handled without crashes.

    Args:
        lines: List of lines to construct TOML content
    """
    content = "\n".join(lines)

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = TomlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.toml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)
