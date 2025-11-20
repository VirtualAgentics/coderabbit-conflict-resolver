"""Tests for ParallelCommentParser initialization and validation."""

from unittest.mock import MagicMock

import pytest

from pr_conflict_resolver.llm.parallel_parser import ParallelCommentParser


class TestParallelCommentParserInitialization:
    """Test ParallelCommentParser initialization and parameter validation."""

    def test_init_with_valid_max_workers(self) -> None:
        """Test initialization with valid max_workers value."""
        mock_provider = MagicMock()
        parser = ParallelCommentParser(mock_provider, max_workers=4)

        assert parser.max_workers == 4
        assert parser.provider == mock_provider

    def test_init_with_max_workers_one(self) -> None:
        """Test initialization with minimum valid max_workers (1)."""
        mock_provider = MagicMock()
        parser = ParallelCommentParser(mock_provider, max_workers=1)

        assert parser.max_workers == 1

    def test_init_with_zero_max_workers_raises_error(self) -> None:
        """Test that max_workers=0 raises ValueError."""
        mock_provider = MagicMock()

        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            ParallelCommentParser(mock_provider, max_workers=0)

    def test_init_with_negative_max_workers_raises_error(self) -> None:
        """Test that negative max_workers raises ValueError."""
        mock_provider = MagicMock()

        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            ParallelCommentParser(mock_provider, max_workers=-1)

    def test_init_with_default_max_workers(self) -> None:
        """Test initialization with default max_workers value."""
        mock_provider = MagicMock()
        parser = ParallelCommentParser(mock_provider)

        assert parser.max_workers == 4  # Default value

    def test_init_with_progress_callback(self) -> None:
        """Test initialization with progress callback function."""
        mock_provider = MagicMock()
        mock_callback = MagicMock()

        parser = ParallelCommentParser(
            mock_provider, max_workers=4, progress_callback=mock_callback
        )

        assert parser.progress_callback == mock_callback
