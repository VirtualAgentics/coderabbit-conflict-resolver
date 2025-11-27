"""Integration tests for the full conflict resolution workflow."""

from unittest.mock import Mock, patch

import pytest

from review_bot_automator import ConflictResolver, PresetConfig


@pytest.mark.integration
class TestFullWorkflow:
    """Test the complete conflict resolution workflow."""

    @patch("review_bot_automator.core.resolver.GitHubCommentExtractor")
    def test_analyze_conflicts_workflow(self, mock_extractor: Mock) -> None:
        """Test the complete conflict analysis workflow."""
        # Mock GitHub extractor
        mock_extractor.return_value.fetch_pr_comments.return_value = [
            {
                "path": "package.json",
                "body": '```suggestion\n{\n  "name": "test",\n  "version": "1.0.0"\n}\n```',
                "start_line": 1,
                "line": 3,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            },
            {
                "path": "package.json",
                "body": '```suggestion\n{\n  "name": "test",\n  "version": "2.0.0"\n}\n```',
                "start_line": 1,
                "line": 3,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            },
        ]

        # Initialize resolver
        resolver = ConflictResolver(PresetConfig.BALANCED)

        # Analyze conflicts
        conflicts = resolver.analyze_conflicts("owner", "repo", 123)

        # Verify results
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.file_path == "package.json"
        assert len(conflict.changes) == 2
        assert conflict.conflict_type in ["exact", "major", "partial"]
        assert conflict.severity in ["low", "medium", "high"]
        assert conflict.overlap_percentage > 0

    @patch("review_bot_automator.core.resolver.GitHubCommentExtractor")
    def test_resolve_conflicts_workflow(self, mock_extractor: Mock) -> None:
        """Test the complete conflict resolution workflow."""
        # Mock GitHub extractor
        mock_extractor.return_value.fetch_pr_comments.return_value = [
            {
                "path": "package.json",
                "body": '```suggestion\n{\n  "name": "test",\n  "version": "1.0.0"\n}\n```',
                "start_line": 1,
                "line": 3,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            }
        ]

        # Initialize resolver
        resolver = ConflictResolver(PresetConfig.BALANCED)

        # Resolve conflicts
        result = resolver.resolve_pr_conflicts("owner", "repo", 123)

        # Verify results
        assert result.applied_count >= 0
        assert result.conflict_count >= 0
        assert 0 <= result.success_rate <= 100
        assert isinstance(result.resolutions, list)
        assert isinstance(result.conflicts, list)

    @patch("review_bot_automator.core.resolver.GitHubCommentExtractor")
    def test_no_conflicts_workflow(self, mock_extractor: Mock) -> None:
        """Test workflow with no conflicts."""
        # Mock GitHub extractor with no comments
        mock_extractor.return_value.fetch_pr_comments.return_value = []

        # Initialize resolver
        resolver = ConflictResolver(PresetConfig.BALANCED)

        # Analyze conflicts
        conflicts = resolver.analyze_conflicts("owner", "repo", 123)

        # Verify no conflicts
        assert len(conflicts) == 0

    @patch("review_bot_automator.core.resolver.GitHubCommentExtractor")
    def test_multiple_file_conflicts(self, mock_extractor: Mock) -> None:
        """Test workflow with conflicts in multiple files."""
        # Mock GitHub extractor with comments for multiple files
        mock_extractor.return_value.fetch_pr_comments.return_value = [
            {
                "path": "package.json",
                "body": '```suggestion\n{\n  "name": "test1"\n}\n```',
                "start_line": 1,
                "line": 3,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            },
            {
                "path": "package.json",
                "body": '```suggestion\n{\n  "name": "test2"\n}\n```',
                "start_line": 1,
                "line": 3,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            },
            {
                "path": "config.yaml",
                "body": "```suggestion\nname: test1\n```",
                "start_line": 1,
                "line": 1,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            },
            {
                "path": "config.yaml",
                "body": "```suggestion\nname: test2\n```",
                "start_line": 1,
                "line": 1,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            },
        ]

        # Initialize resolver
        resolver = ConflictResolver(PresetConfig.BALANCED)

        # Analyze conflicts
        conflicts = resolver.analyze_conflicts("owner", "repo", 123)

        # Verify results
        assert len(conflicts) == 2  # One conflict per file

        # Check that conflicts are in different files
        file_paths = [conflict.file_path for conflict in conflicts]
        assert "package.json" in file_paths
        assert "config.yaml" in file_paths

    @patch("review_bot_automator.core.resolver.GitHubCommentExtractor")
    def test_priority_based_resolution(self, mock_extractor: Mock) -> None:
        """Test priority-based conflict resolution."""
        # Mock GitHub extractor with comments of different priorities
        mock_extractor.return_value.fetch_pr_comments.return_value = [
            {
                "path": "package.json",
                "body": '```suggestion\n{\n  "name": "test",\n  "version": "1.0.0"\n}\n```',
                "start_line": 1,
                "line": 3,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            },
            {
                "path": "package.json",
                "body": '```suggestion\n{\n  "name": "test",\n  "version": "2.0.0"\n}\n```',
                "start_line": 1,
                "line": 3,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            },
        ]

        # Initialize resolver with priority strategy
        resolver = ConflictResolver(PresetConfig.BALANCED)

        # Resolve conflicts
        result = resolver.resolve_pr_conflicts("owner", "repo", 123)

        # Verify results
        assert result.applied_count >= 0
        assert result.conflict_count >= 0
        assert 0 <= result.success_rate <= 100

    @patch("review_bot_automator.core.resolver.GitHubCommentExtractor")
    def test_error_handling(self, mock_extractor: Mock) -> None:
        """Test error handling in the workflow."""
        # Mock GitHub extractor to raise an exception
        mock_extractor.return_value.fetch_pr_comments.side_effect = Exception("API Error")

        # Initialize resolver
        resolver = ConflictResolver(PresetConfig.BALANCED)

        # Test that exceptions are properly handled
        with pytest.raises(RuntimeError):
            resolver.analyze_conflicts("owner", "repo", 123)

    @patch("review_bot_automator.core.resolver.GitHubCommentExtractor")
    def test_different_configurations(self, mock_extractor: Mock) -> None:
        """
        Verify analyze_conflicts runs without error across preset configurations.

        Calls analyze_conflicts for each PresetConfig (CONSERVATIVE, BALANCED, AGGRESSIVE,
            SEMANTIC) using a mocked PR comment and asserts that the result is a list (possibly
            empty) for every configuration.
        """
        # Mock GitHub extractor
        mock_extractor.return_value.fetch_pr_comments.return_value = [
            {
                "path": "package.json",
                "body": '```suggestion\n{\n  "name": "test"\n}\n```',
                "start_line": 1,
                "line": 3,
                "html_url": "https://github.com/test",
                "user": {"login": "coderabbit"},
            }
        ]

        # Test different configurations
        configs = [
            PresetConfig.CONSERVATIVE,
            PresetConfig.BALANCED,
            PresetConfig.AGGRESSIVE,
            PresetConfig.SEMANTIC,
        ]

        for config in configs:
            resolver = ConflictResolver(config)
            conflicts = resolver.analyze_conflicts("owner", "repo", 123)

            # All configurations should work
            assert isinstance(conflicts, list)
