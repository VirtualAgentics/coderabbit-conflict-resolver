"""Unit tests for text normalization utilities."""

from review_bot_automator.utils.text import normalize_content


def test_normalize_content_trims_and_removes_blank_lines() -> None:
    text = "  line1  \n\n  line2\n  \nline3   "
    assert normalize_content(text) == "line1\nline2\nline3"


def test_normalize_content_handles_crlf_and_tabs() -> None:
    text = "line1\r\n\tline2  \r\n\r\n\t  line3"
    # Tabs should remain if they are meaningful characters, but leading/trailing
    # whitespace on each line is stripped and blank lines removed.
    assert normalize_content(text) == "line1\nline2\nline3"


def test_normalize_content_empty_or_whitespace_only() -> None:
    assert normalize_content("") == ""
    assert normalize_content("   \n \t \r\n  ") == ""


def test_normalize_content_idempotent() -> None:
    text = "  a  \n  b\n\n c  "
    once = normalize_content(text)
    twice = normalize_content(once)
    assert once == twice
