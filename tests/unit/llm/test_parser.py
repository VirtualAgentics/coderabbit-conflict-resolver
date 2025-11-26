"""Tests for UniversalLLMParser.

This module tests the LLM-powered parser implementation including:
- Parser initialization and configuration
- Successful parsing with valid JSON responses
- JSON validation and error handling
- Confidence threshold filtering
- Fallback behavior (return empty list vs raise exception)
- Various comment formats (diff blocks, suggestions, natural language)
- Edge cases (malformed JSON, invalid fields, empty responses)
"""

from unittest.mock import MagicMock

import pytest

from pr_conflict_resolver.llm.base import LLMParser
from pr_conflict_resolver.llm.parser import UniversalLLMParser
from pr_conflict_resolver.llm.providers.base import LLMProvider


class TestUniversalLLMParserProtocol:
    """Test that UniversalLLMParser conforms to LLMParser protocol."""

    def test_parser_implements_protocol(self) -> None:
        """Test that UniversalLLMParser implements LLMParser protocol."""
        mock_provider = MagicMock(spec=LLMProvider)
        parser = UniversalLLMParser(mock_provider)
        assert isinstance(parser, LLMParser)

    def test_parser_has_parse_comment_method(self) -> None:
        """Test that parser has parse_comment() method with correct signature."""
        mock_provider = MagicMock(spec=LLMProvider)
        parser = UniversalLLMParser(mock_provider)
        assert hasattr(parser, "parse_comment")
        assert callable(parser.parse_comment)


class TestUniversalLLMParserInitialization:
    """Test UniversalLLMParser initialization and configuration."""

    def test_init_with_valid_params(self) -> None:
        """Test initialization with valid parameters."""
        mock_provider = MagicMock(spec=LLMProvider)
        parser = UniversalLLMParser(
            provider=mock_provider,
            fallback_to_regex=False,
            confidence_threshold=0.7,
        )
        assert parser.provider is mock_provider
        assert parser.fallback_to_regex is False
        assert parser.confidence_threshold == 0.7

    def test_init_with_default_params(self) -> None:
        """Test initialization with default parameters."""
        mock_provider = MagicMock(spec=LLMProvider)
        parser = UniversalLLMParser(mock_provider)
        assert parser.fallback_to_regex is True
        assert parser.confidence_threshold == 0.5

    def test_init_with_invalid_threshold_raises(self) -> None:
        """Test that invalid confidence threshold raises ValueError."""
        mock_provider = MagicMock(spec=LLMProvider)
        with pytest.raises(ValueError, match="must be in \\[0.0, 1.0\\]"):
            UniversalLLMParser(mock_provider, confidence_threshold=1.5)

    def test_init_with_negative_threshold_raises(self) -> None:
        """Test that negative confidence threshold raises ValueError."""
        mock_provider = MagicMock(spec=LLMProvider)
        with pytest.raises(ValueError, match="must be in \\[0.0, 1.0\\]"):
            UniversalLLMParser(mock_provider, confidence_threshold=-0.1)

    def test_set_confidence_threshold_valid(self) -> None:
        """Test setting valid confidence threshold."""
        mock_provider = MagicMock(spec=LLMProvider)
        parser = UniversalLLMParser(mock_provider, confidence_threshold=0.5)
        parser.set_confidence_threshold(0.8)
        assert parser.confidence_threshold == 0.8

    def test_set_confidence_threshold_invalid_raises(self) -> None:
        """Test that invalid threshold in setter raises ValueError."""
        mock_provider = MagicMock(spec=LLMProvider)
        parser = UniversalLLMParser(mock_provider)
        with pytest.raises(ValueError, match="must be in \\[0.0, 1.0\\]"):
            parser.set_confidence_threshold(2.0)


class TestUniversalLLMParserValidation:
    """Test input validation in parse_comment."""

    def test_parse_comment_empty_body_raises(self) -> None:
        """Test that empty comment body raises ValueError."""
        mock_provider = MagicMock(spec=LLMProvider)
        parser = UniversalLLMParser(mock_provider)
        with pytest.raises(ValueError, match="cannot be None or empty"):
            parser.parse_comment("", file_path="test.py")

    def test_parse_comment_none_body_raises(self) -> None:
        """Test that None comment body raises ValueError."""
        mock_provider = MagicMock(spec=LLMProvider)
        parser = UniversalLLMParser(mock_provider)
        with pytest.raises(ValueError, match="cannot be None or empty"):
            parser.parse_comment(None, file_path="test.py")  # type: ignore[arg-type]


class TestUniversalLLMParserSuccessfulParsing:
    """Test successful parsing scenarios."""

    def test_parse_diff_block_success(self) -> None:
        """Test parsing a diff block comment successfully."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = (
            '[{"file_path": "src/auth.py", "start_line": 42, "end_line": 45, '
            '"new_content": "def authenticate(username, password):\\\\n'
            '    # Use parameterized query\\\\n    return True", '
            '"change_type": "modification", "confidence": 0.95, '
            '"rationale": "SQL injection vulnerability fix", "risk_level": "high"}]'
        )

        parser = UniversalLLMParser(mock_provider, confidence_threshold=0.5)
        changes = parser.parse_comment(
            "Fix SQL injection in auth:\n```diff\n...\n```",
            file_path="src/auth.py",
            line_number=42,
        )

        assert len(changes) == 1
        assert changes[0].file_path == "src/auth.py"
        assert changes[0].start_line == 42
        assert changes[0].end_line == 45
        assert changes[0].confidence == 0.95
        assert changes[0].risk_level == "high"

    def test_parse_multiple_changes(self) -> None:
        """Test parsing multiple changes from single comment."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = """[
            {
                "file_path": "src/utils.py",
                "start_line": 10,
                "end_line": 12,
                "new_content": "# Change 1",
                "change_type": "modification",
                "confidence": 0.85,
                "rationale": "First change",
                "risk_level": "low"
            },
            {
                "file_path": "src/utils.py",
                "start_line": 20,
                "end_line": 22,
                "new_content": "# Change 2",
                "change_type": "addition",
                "confidence": 0.75,
                "rationale": "Second change",
                "risk_level": "medium"
            }
        ]"""

        parser = UniversalLLMParser(mock_provider, confidence_threshold=0.5)
        changes = parser.parse_comment("Apply these two changes", file_path="src/utils.py")

        assert len(changes) == 2
        assert changes[0].start_line == 10
        assert changes[1].start_line == 20

    def test_parse_empty_changes_array(self) -> None:
        """Test parsing comment with no actionable changes."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = "[]"

        parser = UniversalLLMParser(mock_provider)
        changes = parser.parse_comment("This looks good to me!", file_path="src/test.py")

        assert len(changes) == 0

    def test_parse_with_optional_context(self) -> None:
        """Test parsing with file_path and line_number context."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = """[
            {
                "file_path": "src/main.py",
                "start_line": 100,
                "end_line": 105,
                "new_content": "# Fixed",
                "change_type": "modification",
                "confidence": 0.88,
                "rationale": "Context helps parsing",
                "risk_level": "low"
            }
        ]"""

        parser = UniversalLLMParser(mock_provider)
        changes = parser.parse_comment(
            "Fix this issue",
            file_path="src/main.py",
            line_number=100,
        )

        assert len(changes) == 1
        # Verify context was passed to provider (check call args)
        call_args = mock_provider.generate.call_args[0][0]
        assert "src/main.py" in call_args
        assert "100" in call_args


class TestUniversalLLMParserConfidenceFiltering:
    """Test confidence threshold filtering."""

    def test_filter_low_confidence_changes(self) -> None:
        """Test that changes below threshold are filtered out."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = """[
            {
                "file_path": "src/test.py",
                "start_line": 1,
                "end_line": 2,
                "new_content": "# High confidence",
                "change_type": "modification",
                "confidence": 0.9,
                "rationale": "Clear fix",
                "risk_level": "low"
            },
            {
                "file_path": "src/test.py",
                "start_line": 10,
                "end_line": 12,
                "new_content": "# Low confidence",
                "change_type": "addition",
                "confidence": 0.4,
                "rationale": "Unclear",
                "risk_level": "medium"
            }
        ]"""

        parser = UniversalLLMParser(mock_provider, confidence_threshold=0.7)
        changes = parser.parse_comment("Apply these changes", file_path="src/test.py")

        # Only high-confidence change should pass
        assert len(changes) == 1
        assert changes[0].confidence == 0.9

    def test_all_changes_filtered(self) -> None:
        """Test when all changes are below threshold."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = """[
            {
                "file_path": "src/test.py",
                "start_line": 1,
                "end_line": 2,
                "new_content": "# Low confidence",
                "change_type": "modification",
                "confidence": 0.3,
                "rationale": "Unclear",
                "risk_level": "low"
            }
        ]"""

        parser = UniversalLLMParser(mock_provider, confidence_threshold=0.7)
        changes = parser.parse_comment("Maybe fix this?", file_path="src/test.py")

        assert len(changes) == 0

    def test_exact_threshold_boundary(self) -> None:
        """Test change exactly at threshold is included."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = """[
            {
                "file_path": "src/test.py",
                "start_line": 1,
                "end_line": 2,
                "new_content": "# Exact threshold",
                "change_type": "modification",
                "confidence": 0.7,
                "rationale": "At boundary",
                "risk_level": "low"
            }
        ]"""

        parser = UniversalLLMParser(mock_provider, confidence_threshold=0.7)
        changes = parser.parse_comment("Fix this", file_path="src/test.py")

        # Change at exactly threshold should be included (>= behavior)
        assert len(changes) == 1
        assert changes[0].confidence == 0.7


class TestUniversalLLMParserErrorHandling:
    """Test error handling and fallback behavior."""

    def test_invalid_json_with_fallback(self) -> None:
        """Test that invalid JSON returns empty list when fallback enabled."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = "not valid json {{"

        parser = UniversalLLMParser(mock_provider, fallback_to_regex=True)
        changes = parser.parse_comment("Fix this", file_path="src/test.py")

        assert len(changes) == 0

    def test_invalid_json_without_fallback(self) -> None:
        """Test that invalid JSON raises error when fallback disabled."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = "not valid json {{"

        parser = UniversalLLMParser(mock_provider, fallback_to_regex=False)
        with pytest.raises(RuntimeError, match="LLM parsing failed"):
            parser.parse_comment("Fix this", file_path="src/test.py")

    def test_non_list_response_with_fallback(self) -> None:
        """Test that non-list JSON returns empty list when fallback enabled."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = '{"error": "not an array"}'

        parser = UniversalLLMParser(mock_provider, fallback_to_regex=True)
        changes = parser.parse_comment("Fix this", file_path="src/test.py")

        assert len(changes) == 0

    def test_non_list_response_without_fallback(self) -> None:
        """Test that non-list JSON raises error when fallback disabled."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = '{"error": "not an array"}'

        parser = UniversalLLMParser(mock_provider, fallback_to_regex=False)
        with pytest.raises(RuntimeError, match="LLM parsing failed"):
            parser.parse_comment("Fix this", file_path="src/test.py")

    def test_invalid_change_format_skipped(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that invalid change objects are skipped with warning."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = """[
            {
                "file_path": "src/test.py",
                "start_line": 1,
                "end_line": 2,
                "new_content": "# Valid",
                "change_type": "modification",
                "confidence": 0.9,
                "rationale": "Good",
                "risk_level": "low"
            },
            {
                "file_path": "src/test.py",
                "missing_required_field": true
            }
        ]"""

        parser = UniversalLLMParser(mock_provider)
        changes = parser.parse_comment("Fix this", file_path="src/test.py")

        # Only valid change should be returned
        assert len(changes) == 1
        assert changes[0].confidence == 0.9
        # Check warning was logged
        assert "Invalid change format" in caplog.text

    def test_provider_exception_with_fallback(self) -> None:
        """Test that provider exceptions return empty list when fallback enabled."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.side_effect = RuntimeError("Provider error")

        parser = UniversalLLMParser(mock_provider, fallback_to_regex=True)
        changes = parser.parse_comment("Fix this", file_path="src/test.py")

        assert len(changes) == 0

    def test_provider_exception_without_fallback(self) -> None:
        """Test that provider exceptions raise error when fallback disabled."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.side_effect = RuntimeError("Provider error")

        parser = UniversalLLMParser(mock_provider, fallback_to_regex=False)
        with pytest.raises(RuntimeError, match="LLM parsing failed"):
            parser.parse_comment("Fix this", file_path="src/test.py")


class TestUniversalLLMParserEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_parse_with_none_file_path(self) -> None:
        """Test parsing with None file_path (should use 'unknown')."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = """[
            {
                "file_path": "inferred.py",
                "start_line": 1,
                "end_line": 2,
                "new_content": "# Fixed",
                "change_type": "modification",
                "confidence": 0.8,
                "rationale": "Inferred path",
                "risk_level": "low"
            }
        ]"""

        parser = UniversalLLMParser(mock_provider)
        changes = parser.parse_comment("Fix this", file_path=None, line_number=None)

        assert len(changes) == 1
        # Verify 'unknown' was used in prompt
        call_args = mock_provider.generate.call_args[0][0]
        assert "unknown" in call_args

    def test_parse_with_very_long_comment(self) -> None:
        """Test parsing with very long comment body."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = "[]"

        parser = UniversalLLMParser(mock_provider)
        long_comment = "Fix this issue. " * 1000  # 16,000 chars
        changes = parser.parse_comment(long_comment, file_path="src/test.py")

        # Should handle long comments without error
        assert len(changes) == 0
        mock_provider.generate.assert_called_once()

    def test_parse_with_unicode_content(self) -> None:
        """Test parsing with unicode characters in content."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = """[
            {
                "file_path": "src/test.py",
                "start_line": 1,
                "end_line": 2,
                "new_content": "# 修复错误 🔧",
                "change_type": "modification",
                "confidence": 0.9,
                "rationale": "Unicode content",
                "risk_level": "low"
            }
        ]"""

        parser = UniversalLLMParser(mock_provider)
        changes = parser.parse_comment("修复这个问题 🐛", file_path="src/test.py")

        assert len(changes) == 1
        assert "修复错误" in changes[0].new_content

    def test_parse_with_max_tokens_parameter(self) -> None:
        """Test that parser passes max_tokens to provider."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = "[]"

        parser = UniversalLLMParser(mock_provider)
        parser.parse_comment("Fix this", file_path="src/test.py")

        # Verify max_tokens=2000 was passed
        call_kwargs = mock_provider.generate.call_args[1]
        assert call_kwargs["max_tokens"] == 2000

    def test_multiple_risk_levels(self) -> None:
        """Test parsing changes with different risk levels."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = """[
            {
                "file_path": "src/test.py",
                "start_line": 1,
                "end_line": 2,
                "new_content": "# Low risk",
                "change_type": "modification",
                "confidence": 0.9,
                "rationale": "Formatting",
                "risk_level": "low"
            },
            {
                "file_path": "src/test.py",
                "start_line": 10,
                "end_line": 15,
                "new_content": "# High risk",
                "change_type": "modification",
                "confidence": 0.95,
                "rationale": "Security fix",
                "risk_level": "high"
            }
        ]"""

        parser = UniversalLLMParser(mock_provider, confidence_threshold=0.5)
        changes = parser.parse_comment("Apply changes", file_path="src/test.py")

        assert len(changes) == 2
        assert changes[0].risk_level == "low"
        assert changes[1].risk_level == "high"


class TestUniversalLLMParserFallbackStats:
    """Test fallback statistics tracking."""

    def test_initial_fallback_stats_zero(self) -> None:
        """Test that initial fallback stats are zero."""
        mock_provider = MagicMock(spec=LLMProvider)
        parser = UniversalLLMParser(mock_provider)

        fallback_count, total_count, rate = parser.get_fallback_stats()

        assert fallback_count == 0
        assert total_count == 0
        assert rate == 0.0

    def test_successful_parse_increments_success_count(self) -> None:
        """Test that successful parsing increments success count."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = "[]"
        mock_provider.get_total_cost.return_value = 0.0

        parser = UniversalLLMParser(mock_provider)
        parser.parse_comment("Fix this", file_path="src/test.py")

        fallback_count, total_count, rate = parser.get_fallback_stats()

        assert fallback_count == 0
        assert total_count == 1
        assert rate == 0.0

    def test_failed_parse_with_fallback_increments_fallback_count(self) -> None:
        """Test that failed parsing increments fallback count."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.side_effect = RuntimeError("LLM failed")

        parser = UniversalLLMParser(mock_provider, fallback_to_regex=True)
        result = parser.parse_comment("Fix this", file_path="src/test.py")

        assert result == []  # Empty list for fallback
        fallback_count, total_count, rate = parser.get_fallback_stats()

        assert fallback_count == 1
        assert total_count == 1
        assert rate == 1.0

    def test_fallback_rate_calculation(self) -> None:
        """Test that fallback rate is calculated correctly."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.get_total_cost.return_value = 0.0

        # First call succeeds
        mock_provider.generate.return_value = "[]"
        parser = UniversalLLMParser(mock_provider, fallback_to_regex=True)
        parser.parse_comment("Fix this", file_path="src/test.py")

        # Second call fails (triggers fallback)
        mock_provider.generate.side_effect = RuntimeError("LLM failed")
        parser.parse_comment("Fix that", file_path="src/other.py")

        fallback_count, total_count, rate = parser.get_fallback_stats()

        assert fallback_count == 1
        assert total_count == 2
        assert rate == 0.5  # 1 fallback / 2 total = 50%

    def test_reset_fallback_stats(self) -> None:
        """Test that reset_fallback_stats clears counters."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = "[]"
        mock_provider.get_total_cost.return_value = 0.0

        parser = UniversalLLMParser(mock_provider)
        parser.parse_comment("Fix this", file_path="src/test.py")

        # Verify stats are non-zero
        _, total_count, _ = parser.get_fallback_stats()
        assert total_count == 1

        # Reset and verify
        parser.reset_fallback_stats()
        fallback_count, total_count, rate = parser.get_fallback_stats()

        assert fallback_count == 0
        assert total_count == 0
        assert rate == 0.0

    def test_invalid_json_triggers_fallback(self) -> None:
        """Test that invalid JSON response triggers fallback count."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.generate.return_value = "not valid json"
        mock_provider.get_total_cost.return_value = 0.0

        parser = UniversalLLMParser(mock_provider, fallback_to_regex=True)
        parser.parse_comment("Fix this", file_path="src/test.py")

        fallback_count, total_count, rate = parser.get_fallback_stats()

        assert fallback_count == 1
        assert total_count == 1
        assert rate == 1.0
