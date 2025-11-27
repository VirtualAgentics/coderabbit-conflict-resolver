"""Tests for TOML handler formatting preservation.

This module tests that the TOML handler preserves formatting, comments, and
section ordering when applying changes using line-based targeted replacement.
"""

from pathlib import Path

import pytest

from review_bot_automator.handlers.toml_handler import TomlHandler


class TestTomlFormattingPreservation:
    """Test TOML handler preserves formatting, comments, and section ordering."""

    def test_preserves_comments(self, toml_handler: TomlHandler, temp_workspace: Path) -> None:
        """Test that comments are preserved during line replacement."""
        test_file = temp_workspace / "test.toml"
        original_content = """# This is a header comment
[section1]
# Comment about key1
key1 = "value1"
key2 = "value2"  # Inline comment

[section2]
key3 = "value3"
"""
        test_file.write_text(original_content)

        # Replace only line 4 (key1 = "value1")
        result = toml_handler.apply_change(str(test_file), 'key1 = "newvalue"', 4, 4)
        assert result is True

        # Verify all comments and formatting preserved
        content = test_file.read_text()
        assert "# This is a header comment" in content
        assert "# Comment about key1" in content
        assert "# Inline comment" in content
        assert 'key1 = "newvalue"' in content
        assert 'key2 = "value2"' in content
        assert "[section1]" in content
        assert "[section2]" in content

    def test_preserves_section_ordering(
        self, toml_handler: TomlHandler, temp_workspace: Path
    ) -> None:
        """Test that section ordering is preserved during line replacement."""
        test_file = temp_workspace / "test.toml"
        original_content = """[zebra]
name = "last"

[alpha]
name = "first"

[middle]
name = "middle"
"""
        test_file.write_text(original_content)

        # Replace line 5 (name = "first")
        result = toml_handler.apply_change(str(test_file), 'name = "updated"', 5, 5)
        assert result is True

        # Verify section order preserved (zebra, alpha, middle)
        content = test_file.read_text()
        zebra_pos = content.index("[zebra]")
        alpha_pos = content.index("[alpha]")
        middle_pos = content.index("[middle]")

        assert zebra_pos < alpha_pos < middle_pos
        assert 'name = "updated"' in content

    def test_preserves_custom_formatting(
        self, toml_handler: TomlHandler, temp_workspace: Path
    ) -> None:
        """Test that custom formatting (spacing, indentation) is preserved."""
        test_file = temp_workspace / "test.toml"
        original_content = """[section]
key1   =   "value1"    # Extra spaces
key2="value2"          # No spaces
key3 = "value3"        # Normal spacing
"""
        test_file.write_text(original_content)

        # Replace only line 3 (key2="value2")
        result = toml_handler.apply_change(str(test_file), 'key2="updated"', 3, 3)
        assert result is True

        # Verify other lines' formatting preserved
        content = test_file.read_text()
        assert 'key1   =   "value1"' in content  # Extra spaces preserved
        assert 'key2="updated"' in content  # Replacement applied
        assert 'key3 = "value3"' in content  # Normal spacing preserved

    def test_invalid_ranges_no_mutation(
        self, toml_handler: TomlHandler, temp_workspace: Path
    ) -> None:
        """Invalid line ranges should raise ValueError and not change the file."""
        test_file = temp_workspace / "bad_range.toml"
        original_content = """[section]
key = "value"
"""
        test_file.write_text(original_content)

        # Start/end far beyond EOF
        with pytest.raises(ValueError, match="end_line=99 > total_lines"):
            toml_handler.apply_change(str(test_file), 'key = "new"', 99, 99)
        assert test_file.read_text() == original_content

        # Inverted range where start > end
        with pytest.raises(ValueError, match="end_line=2 < start_line=3"):
            toml_handler.apply_change(str(test_file), 'key = "new"', 3, 2)
        assert test_file.read_text() == original_content

    def test_replaces_multiple_lines(self, toml_handler: TomlHandler, temp_workspace: Path) -> None:
        """Test replacing multiple lines while preserving surrounding content."""
        test_file = temp_workspace / "test.toml"
        original_content = """# Header
[section]
# Before
line1 = "old1"
line2 = "old2"
line3 = "old3"
# After
"""
        test_file.write_text(original_content)

        # Replace lines 4-5 (line1 and line2) so "# Before" remains
        replacement = """line1 = "new1"
line2 = "new2"
"""
        result = toml_handler.apply_change(str(test_file), replacement, 4, 5)
        assert result is True

        # Verify selective replacement with preserved comments
        content = test_file.read_text()
        assert "# Header" in content
        assert "# Before" in content
        assert "# After" in content
        assert 'line1 = "new1"' in content
        assert 'line2 = "new2"' in content
        assert 'line3 = "old3"' in content

    def test_rejects_start_line_below_one(
        self, toml_handler: TomlHandler, temp_workspace: Path
    ) -> None:
        """apply_change should raise ValueError for start_line < 1 and not mutate the file."""
        test_file = temp_workspace / "guard.toml"
        original_content = """[section]
key = "value"
"""
        test_file.write_text(original_content)

        with pytest.raises(ValueError, match="start_line=0 \\(<1\\)"):
            toml_handler.apply_change(str(test_file), 'key = "new"', 0, 1)
        assert test_file.read_text() == original_content
