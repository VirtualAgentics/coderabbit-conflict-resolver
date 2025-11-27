"""Property-based fuzzing tests for JSONHandler.

This module uses Hypothesis to perform property-based testing on the JSONHandler
class, focusing on finding edge cases in JSON parsing, validation, and duplicate
key detection.

Test Coverage:
- JSON parsing with arbitrary content
- Duplicate key detection
- JSON structure validation
- Merge conflict handling
"""

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from review_bot_automator.handlers.json_handler import JsonHandler

# =============================================================================
# Hypothesis Strategies for JSON
# =============================================================================


# Define recursive JSON strategy for valid JSON structures
json_primitives = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=50)
)

json_values = st.recursive(
    json_primitives,
    lambda children: st.lists(children, max_size=10)
    | st.dictionaries(st.text(min_size=1, max_size=20), children, max_size=10),
    max_leaves=20,
)


# =============================================================================
# JSON Validation Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(content=st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_json_validate_change_never_crashes(content: str) -> None:
    """Fuzz validate_change() with arbitrary text.

    Property: JSON validation should handle any string without crashing,
    returning a boolean result.

    Args:
        content: Arbitrary string to test as JSON content
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = JsonHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.json", content, 1, 1)
        assert isinstance(is_valid, bool), "validate_change must return bool"
        assert isinstance(message, str), "validate_change must return message"


@pytest.mark.fuzz
@given(json_obj=json_values)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_json_validate_with_valid_structures(
    json_obj: dict[str, object] | list[object] | str | int | float | bool | None,
) -> None:
    """Fuzz JSON validation with structurally valid JSON.

    Property: Valid JSON structures should be accepted by validation.

    Args:
        json_obj: Valid JSON-serializable object
    """
    try:
        content = json.dumps(json_obj)
    except (TypeError, ValueError):
        # If json.dumps fails, skip this example
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = JsonHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.json", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

        # Valid JSON should pass validation
        if content:  # Non-empty valid JSON
            assert is_valid is True, "Valid JSON should pass validation"


# =============================================================================
# Duplicate Key Detection Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(key=st.text(min_size=1, max_size=20), value1=st.integers(), value2=st.integers())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_json_duplicate_key_detection(key: str, value1: int, value2: int) -> None:
    """Fuzz JSON validation with duplicate keys.

    Property: JSON with duplicate keys should be detected and rejected.

    Args:
        key: Key name to duplicate
        value1: First value
        value2: Second value
    """
    # Create JSON with duplicate keys (manually constructed to bypass json.dumps)
    # Properly escape the key using json.dumps
    key_escaped = json.dumps(key)
    content = f"{{{key_escaped}: {value1}, {key_escaped}: {value2}}}"

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = JsonHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.json", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

        # Duplicate keys should be rejected
        assert is_valid is False, "JSON with duplicate keys must be rejected"


# =============================================================================
# JSON Structure Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(
    keys=st.lists(
        st.text(alphabet=st.characters(categories=("Lu", "Ll")), min_size=1, max_size=15),
        min_size=1,
        max_size=10,
        unique=True,
    ),
    values=st.lists(
        st.one_of(st.integers(), st.text(max_size=30), st.booleans()), min_size=1, max_size=10
    ),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_json_object_structures(keys: list[str], values: list[int | str | bool]) -> None:
    """Fuzz JSON validation with various object structures.

    Property: Valid JSON objects should be parsed correctly.

    Args:
        keys: List of keys for JSON object
        values: List of values for JSON object
    """
    # Create JSON object - truncate to minimum length for strict zip
    min_len = min(len(keys), len(values))
    json_obj = dict(zip(keys[:min_len], values[:min_len], strict=True))
    try:
        content = json.dumps(json_obj)
    except (TypeError, ValueError):
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = JsonHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.json", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)
        # Valid JSON should pass
        assert is_valid is True, "Valid JSON object should pass validation"


@pytest.mark.fuzz
@given(
    items=st.lists(
        st.one_of(st.integers(), st.text(max_size=30), st.booleans(), st.none()), max_size=20
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_json_array_structures(items: list[int | str | bool | None]) -> None:
    """Fuzz JSON validation with array structures.

    Property: Valid JSON arrays should be parsed correctly.

    Args:
        items: List items for JSON array
    """
    try:
        content = json.dumps(items)
    except (TypeError, ValueError):
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = JsonHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.json", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)
        # Valid JSON should pass
        assert is_valid is True, "Valid JSON array should pass validation"


# =============================================================================
# Malformed JSON Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(
    prefix=st.sampled_from(["{", "[", '{"key":', "[1,", "{"]),
    suffix=st.sampled_from(["", "}", "]", ",", "extra"]),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_json_malformed_structures(prefix: str, suffix: str) -> None:
    """Fuzz JSON validation with malformed JSON.

    Property: Malformed JSON should be rejected without crashing.

    Args:
        prefix: JSON prefix
        suffix: JSON suffix
    """
    content = prefix + suffix

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = JsonHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.json", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

        # Malformed JSON should fail validation
        try:
            json.loads(content)
            # If it parses, validation might pass
        except json.JSONDecodeError:
            # If it doesn't parse, validation should fail
            assert is_valid is False, "Malformed JSON should be rejected"


# =============================================================================
# Apply Change Fuzzing (Integration)
# =============================================================================


@pytest.mark.fuzz
@given(
    original_obj=st.dictionaries(
        st.text(min_size=1, max_size=10),
        st.one_of(st.integers(), st.text(max_size=20)),
        min_size=1,
        max_size=5,
    ),
    new_key=st.text(min_size=1, max_size=10),
    new_value=st.one_of(st.integers(), st.text(max_size=20)),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_json_apply_change_never_crashes(
    original_obj: dict[str, int | str], new_key: str, new_value: int | str
) -> None:
    """Fuzz apply_change() with various modifications.

    Property: Applying changes should either succeed or fail gracefully
    without crashing.

    Args:
        original_obj: Original JSON object
        new_key: New key to add or modify
        new_value: New value for the key
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create original file
        json_file = Path(tmpdir) / "test.json"
        json_file.write_text(json.dumps(original_obj, indent=2))

        # Create modification
        modified_obj = {**original_obj, new_key: new_value}
        new_content = json.dumps(modified_obj, indent=2)

        handler = JsonHandler(workspace_root=Path(tmpdir))

        try:
            # Apply change may fail for invalid input, which is expected
            result = handler.apply_change(
                "test.json", new_content, 1, len(json_file.read_text().splitlines())
            )
            # If it succeeds, should return a bool
            assert isinstance(result, bool)
        except (ValueError, OSError, json.JSONDecodeError):
            # Expected exceptions for invalid input
            pass


@pytest.mark.fuzz
@given(
    content=st.text(
        alphabet=st.characters(categories=("Lu", "Ll", "Nd", "Zs", "Po")),
        min_size=1,
        max_size=100,
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_json_special_characters_in_values(content: str) -> None:
    """Fuzz JSON validation with special characters in string values.

    Property: JSON with special characters should be properly escaped and validated.

    Args:
        content: String content with various characters
    """
    json_obj = {"key": content}
    try:
        json_content = json.dumps(json_obj)
    except (TypeError, ValueError):
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = JsonHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.json", json_content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)
        # Properly escaped JSON should pass
        assert is_valid is True, "Valid JSON with escaped special characters should pass"
