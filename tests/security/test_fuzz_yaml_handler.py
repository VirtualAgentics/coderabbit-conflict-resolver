"""Property-based fuzzing tests for YAMLHandler.

This module uses Hypothesis to perform property-based testing on the YAMLHandler
class, focusing on finding edge cases in YAML parsing, validation, and dangerous
content detection.

Test Coverage:
- YAML parsing with arbitrary content
- Dangerous tag detection (!!python, etc.)
- Control character detection
- YAML structure validation
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from review_bot_automator.handlers.yaml_handler import YamlHandler

# =============================================================================
# YAML Validation Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(content=st.text())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_yaml_validate_change_never_crashes(content: str) -> None:
    """Fuzz validate_change() with arbitrary text.

    Property: YAML validation should handle any string without crashing,
    returning a boolean result.

    Args:
        content: Arbitrary string to test as YAML content
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = YamlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.yaml", content, 1, 1)
        assert isinstance(is_valid, bool), "validate_change must return bool"
        assert isinstance(message, str), "validate_change must return message"


@pytest.mark.fuzz
@given(
    key=st.text(alphabet=st.characters(categories=("Lu", "Ll")), min_size=1, max_size=20),
    value=st.one_of(
        st.none(), st.booleans(), st.integers(), st.floats(allow_nan=False), st.text(max_size=50)
    ),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_yaml_validate_with_simple_structures(
    key: str, value: str | int | float | bool | None
) -> None:
    """Fuzz YAML validation with simple key-value pairs.

    Property: Simple YAML structures should be parsed without crashes.

    Args:
        key: YAML key
        value: YAML value
    """
    import yaml

    try:
        content = yaml.dump({key: value})
    except Exception:
        # If yaml.dump fails, that's fine - we're testing handler robustness
        content = f"{key}: {value}"

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = YamlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.yaml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)


# =============================================================================
# Dangerous Tag Detection Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(
    tag=st.sampled_from(
        [
            "!!python/object",
            "!!python/object/apply",
            "!!python/object/new",
            "!!python/name",
            "!!python/module",
            "!!tag",
            "!custom",
        ]
    ),
    payload=st.text(max_size=50),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_yaml_dangerous_tag_detection(tag: str, payload: str) -> None:
    """Fuzz YAML dangerous tag detection.

    Property: Content with dangerous YAML tags (!!python/*) should be detected
    and rejected.

    Args:
        tag: YAML tag to test
        payload: Content after the tag
    """
    content = f"{tag} {payload}"
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = YamlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.yaml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

        # Python object tags should always be rejected
        if "!!python" in content:
            assert is_valid is False, "YAML with !!python tags must be rejected"


@pytest.mark.fuzz
@given(prefix=st.text(max_size=20), suffix=st.text(max_size=20))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_yaml_tag_like_content(prefix: str, suffix: str) -> None:
    """Fuzz YAML validation with content containing '!!'.

    Property: Any content with '!!' should be carefully validated for dangerous tags.

    Args:
        prefix: Text before the !! marker
        suffix: Text after the !! marker
    """
    content = f"{prefix}!!{suffix}"

    with tempfile.TemporaryDirectory() as tmpdir:
        handler = YamlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.yaml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)


# =============================================================================
# Control Character Detection Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(content=st.text(alphabet=st.characters(categories=["Cc"]), min_size=1, max_size=100))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_yaml_control_character_detection(content: str) -> None:
    """Fuzz YAML validation with control characters.

    Property: YAML content with control characters should be handled safely.

    Args:
        content: String containing control characters
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = YamlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.yaml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

        # Content with null bytes or other dangerous control chars should be rejected
        if "\x00" in content or "\x1b" in content:
            assert is_valid is False, "YAML with dangerous control characters must be rejected"


# =============================================================================
# YAML Structure Fuzzing
# =============================================================================


@pytest.mark.fuzz
@given(
    lines=st.lists(
        st.text(alphabet=st.characters(categories=("Lu", "Ll", "Nd", "Zs")), max_size=50),
        min_size=1,
        max_size=20,
    )
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_yaml_multiline_content(lines: list[str]) -> None:
    """Fuzz YAML validation with multiline content.

    Property: Multiline YAML should be handled without crashes.

    Args:
        lines: List of lines to construct YAML content
    """
    content = "\n".join(lines)
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = YamlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.yaml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)


@pytest.mark.fuzz
@given(
    indent=st.integers(min_value=0, max_value=10),
    key=st.text(alphabet=st.characters(categories=("Lu", "Ll")), min_size=1, max_size=20),
    value=st.text(max_size=50),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_yaml_indentation_variations(indent: int, key: str, value: str) -> None:
    """Fuzz YAML validation with various indentation levels.

    Property: YAML with different indentation levels should be parsed correctly
    or rejected with proper error handling.

    Args:
        indent: Number of spaces for indentation
        key: YAML key
        value: YAML value
    """
    content = f"{' ' * indent}{key}: {value}"
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = YamlHandler(workspace_root=Path(tmpdir))

        is_valid, message = handler.validate_change("test.yaml", content, 1, 1)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)


# =============================================================================
# Apply Change Fuzzing (Integration)
# =============================================================================


@pytest.mark.fuzz
@given(
    original_content=st.sampled_from(
        [
            "name: test\nversion: 1.0",
            "key: value\nnested:\n  item: data",
            "list:\n  - item1\n  - item2",
        ]
    ),
    new_value=st.text(max_size=30),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_fuzz_yaml_apply_change_never_crashes(original_content: str, new_value: str) -> None:
    """Fuzz apply_change() with various modifications.

    Property: Applying changes should either succeed or fail gracefully
    without crashing.

    Args:
        original_content: Original YAML content
        new_value: New value to apply
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create original file
        yaml_file = Path(tmpdir) / "test.yaml"
        yaml_file.write_text(original_content)

        handler = YamlHandler(workspace_root=Path(tmpdir))

        try:
            # Apply change may fail for invalid YAML, which is expected behavior
            result = handler.apply_change("test.yaml", f"name: {new_value}", 1, 1)
            # If it succeeds, should return a bool
            assert isinstance(result, bool)
        except (ValueError, OSError):
            # Expected exceptions for invalid input
            pass
