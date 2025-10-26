"""Tests for TOML handler formatting preservation.

This module tests that the TOML handler preserves formatting, comments, and
section ordering when applying changes using line-based targeted replacement.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from pr_conflict_resolver.handlers.toml_handler import TomlHandler


class TestTomlFormattingPreservation:
    """Test TOML handler preserves formatting, comments, and section ordering."""

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    def test_preserves_comments(self) -> None:
        """Test that comments are preserved during line replacement."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            original_content = """# This is a header comment
[section1]
# Comment about key1
key1 = "value1"
key2 = "value2"  # Inline comment

[section2]
key3 = "value3"
"""
            f.write(original_content)
            f.flush()
            temp_dir = os.path.dirname(f.name)

            handler = TomlHandler(workspace_root=temp_dir)

            try:
                # Replace only line 4 (key1 = "value1")
                result = handler.apply_change(f.name, 'key1 = "newvalue"', 4, 4)
                assert result is True

                # Verify all comments and formatting preserved
                content = Path(f.name).read_text()
                assert "# This is a header comment" in content
                assert "# Comment about key1" in content
                assert "# Inline comment" in content
                assert 'key1 = "newvalue"' in content
                assert 'key2 = "value2"' in content
                assert "[section1]" in content
                assert "[section2]" in content
            finally:
                os.unlink(f.name)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    def test_preserves_section_ordering(self) -> None:
        """Test that section ordering is preserved during line replacement."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            original_content = """[zebra]
name = "last"

[alpha]
name = "first"

[middle]
name = "middle"
"""
            f.write(original_content)
            f.flush()
            temp_dir = os.path.dirname(f.name)

            handler = TomlHandler(workspace_root=temp_dir)

            try:
                # Replace line 5 (name = "first")
                result = handler.apply_change(f.name, 'name = "updated"', 5, 5)
                assert result is True

                # Verify section order preserved (zebra, alpha, middle)
                content = Path(f.name).read_text()
                zebra_pos = content.index("[zebra]")
                alpha_pos = content.index("[alpha]")
                middle_pos = content.index("[middle]")

                assert zebra_pos < alpha_pos < middle_pos
                assert 'name = "updated"' in content
            finally:
                os.unlink(f.name)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    def test_preserves_custom_formatting(self) -> None:
        """Test that custom formatting (spacing, indentation) is preserved."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            original_content = """[section]
key1   =   "value1"    # Extra spaces
key2="value2"          # No spaces
key3 = "value3"        # Normal spacing
"""
            f.write(original_content)
            f.flush()
            temp_dir = os.path.dirname(f.name)

            handler = TomlHandler(workspace_root=temp_dir)

            try:
                # Replace only line 3 (key2="value2")
                result = handler.apply_change(f.name, 'key2="updated"', 3, 3)
                assert result is True

                # Verify other lines' formatting preserved
                content = Path(f.name).read_text()
                assert 'key1   =   "value1"' in content  # Extra spaces preserved
                assert 'key2="updated"' in content  # Replacement applied
                assert 'key3 = "value3"' in content  # Normal spacing preserved
            finally:
                os.unlink(f.name)

    @patch("pr_conflict_resolver.handlers.toml_handler.TOML_READ_AVAILABLE", True)
    def test_replaces_multiple_lines(self) -> None:
        """Test replacing multiple lines while preserving surrounding content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            original_content = """# Header
[section]
# Before
line1 = "old1"
line2 = "old2"
line3 = "old3"
# After
"""
            f.write(original_content)
            f.flush()
            temp_dir = os.path.dirname(f.name)

            handler = TomlHandler(workspace_root=temp_dir)

            try:
                # Replace lines 4-5 (line1 and line2)
                replacement = """line1 = "new1"
line2 = "new2"
"""
                result = handler.apply_change(f.name, replacement, 4, 5)
                assert result is True

                # Verify selective replacement with preserved comments
                content = Path(f.name).read_text()
                assert "# Header" in content
                assert "# Before" in content
                assert "# After" in content
                assert 'line1 = "new1"' in content
                assert 'line2 = "new2"' in content
                assert 'line3 = "old3"' in content
            finally:
                os.unlink(f.name)
