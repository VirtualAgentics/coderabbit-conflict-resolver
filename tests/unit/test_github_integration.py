"""Test the GitHub integration."""

from unittest.mock import Mock, patch

from review_bot_automator import GitHubCommentExtractor


class TestGitHubCommentExtractor:
    """Test the GitHub comment extractor."""

    def test_init(self) -> None:
        """Test extractor initialization."""
        extractor = GitHubCommentExtractor()
        assert extractor.token is None
        assert extractor.base_url == "https://api.github.com"
        assert extractor.session is not None

    def test_init_with_token(self) -> None:
        """Test extractor initialization with token."""
        extractor = GitHubCommentExtractor(token="test_token")  # noqa: S106
        assert extractor.token == "test_token"  # noqa: S105
        assert "Authorization" in extractor.session.headers
        assert extractor.session.headers["Authorization"] == "token test_token"

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_review_comments(self, mock_get: Mock) -> None:
        """Test fetching review comments."""
        extractor = GitHubCommentExtractor()

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = [{"id": 1, "body": "test comment"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        comments = extractor._fetch_review_comments("owner", "repo", 123)

        assert len(comments) == 1
        assert comments[0]["id"] == 1
        assert comments[0]["body"] == "test comment"
        mock_get.assert_called_once()

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_issue_comments(self, mock_get: Mock) -> None:
        """Test fetching issue comments."""
        extractor = GitHubCommentExtractor()

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = [{"id": 2, "body": "issue comment"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        comments = extractor._fetch_issue_comments("owner", "repo", 123)

        assert len(comments) == 1
        assert comments[0]["id"] == 2
        assert comments[0]["body"] == "issue comment"
        mock_get.assert_called_once()

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_pr_comments(self, mock_get: Mock) -> None:
        """Test fetching all PR comments."""
        extractor = GitHubCommentExtractor()

        # Mock responses
        mock_response = Mock()
        mock_response.json.return_value = [{"id": 1, "body": "review comment"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        comments = extractor.fetch_pr_comments("owner", "repo", 123)

        # Should call both review and issue endpoints
        assert mock_get.call_count == 2
        assert len(comments) == 2  # One from each call

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_pr_metadata(self, mock_get: Mock) -> None:
        """Test fetching PR metadata."""
        extractor = GitHubCommentExtractor()

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {"id": 123, "title": "Test PR"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        metadata = extractor.fetch_pr_metadata("owner", "repo", 123)

        assert metadata is not None
        assert metadata["id"] == 123
        assert metadata["title"] == "Test PR"
        mock_get.assert_called_once()

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_pr_files(self, mock_get: Mock) -> None:
        """Test fetching PR files."""
        extractor = GitHubCommentExtractor()

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = [{"filename": "test.py", "status": "modified"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        files = extractor.fetch_pr_files("owner", "repo", 123)

        assert len(files) == 1
        assert files[0]["filename"] == "test.py"
        assert files[0]["status"] == "modified"
        mock_get.assert_called_once()

    def test_filter_bot_comments(self) -> None:
        """Test filtering bot comments."""
        extractor = GitHubCommentExtractor()

        comments = [
            {"user": {"login": "coderabbit"}, "body": "bot comment"},
            {"user": {"login": "human_user"}, "body": "human comment"},
            {"user": {"login": "code-review-bot"}, "body": "another bot comment"},
        ]

        filtered = extractor.filter_bot_comments(comments)

        assert len(filtered) == 2
        assert filtered[0]["user"]["login"] == "coderabbit"
        assert filtered[1]["user"]["login"] == "code-review-bot"

    def test_filter_bot_comments_custom_bots(self) -> None:
        """Test filtering with custom bot names."""
        extractor = GitHubCommentExtractor()

        comments = [
            {"user": {"login": "custom-bot"}, "body": "custom bot comment"},
            {"user": {"login": "human_user"}, "body": "human comment"},
        ]

        filtered = extractor.filter_bot_comments(comments, ["custom-bot"])

        assert len(filtered) == 1
        assert filtered[0]["user"]["login"] == "custom-bot"

    def test_extract_suggestion_blocks(self) -> None:
        """Test extracting suggestion blocks from comments."""
        extractor = GitHubCommentExtractor()

        comment = {
            "body": """Here's a suggestion:
```suggestion
{
  "name": "test"
}
```"""
        }

        blocks = extractor.extract_suggestion_blocks(comment)

        assert len(blocks) == 1
        assert "name" in blocks[0]["content"]
        assert blocks[0]["content"].strip() == '{\n  "name": "test"\n}'

    def test_extract_suggestion_blocks_with_options(self) -> None:
        """Test extracting suggestion blocks with option labels."""
        extractor = GitHubCommentExtractor()

        comment = {
            "body": """**Option 1:**
```suggestion
{
  "name": "test1"
}
```

**Option 2:**
```suggestion
{
  "name": "test2"
}
```"""
        }

        blocks = extractor.extract_suggestion_blocks(comment)

        assert len(blocks) == 2
        assert blocks[0]["option_label"] == "Option 1"
        assert blocks[1]["option_label"] == "Option 2"

    def test_get_comment_metadata(self) -> None:
        """Test extracting comment metadata."""
        extractor = GitHubCommentExtractor()

        comment = {
            "id": 123,
            "html_url": "https://github.com/test",
            "user": {"login": "coderabbit", "type": "Bot"},
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "path": "test.py",
            "line": 10,
            "start_line": 5,
            "original_line": 10,
            "original_start_line": 5,
            "position": 1,
            "side": "RIGHT",
            "in_reply_to_id": None,
        }

        metadata = extractor.get_comment_metadata(comment)

        assert metadata["id"] == 123
        assert metadata["url"] == "https://github.com/test"
        assert metadata["author"] == "coderabbit"
        assert metadata["author_type"] == "Bot"
        assert metadata["path"] == "test.py"
        assert metadata["line"] == 10
        assert metadata["start_line"] == 5

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_pr_comments_handles_request_error(self, mock_get: Mock) -> None:
        """Test that fetch_pr_comments handles RequestException gracefully."""
        import requests

        extractor = GitHubCommentExtractor()

        # Mock request to raise RequestException
        mock_get.side_effect = requests.RequestException("Network error")

        comments = extractor.fetch_pr_comments("owner", "repo", 123)

        # Should return empty list on error
        assert comments == []

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_pr_metadata_handles_request_error(self, mock_get: Mock) -> None:
        """Test that fetch_pr_metadata handles RequestException gracefully."""
        import requests

        extractor = GitHubCommentExtractor()

        # Mock request to raise RequestException
        mock_get.side_effect = requests.RequestException("API error")

        metadata = extractor.fetch_pr_metadata("owner", "repo", 123)

        # Should return None on request error
        assert metadata is None

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_pr_files_handles_network_error(self, mock_get: Mock) -> None:
        """Test that fetch_pr_files handles network errors gracefully."""
        import requests

        extractor = GitHubCommentExtractor()

        # Mock request to raise RequestException
        mock_get.side_effect = requests.RequestException("Connection timeout")

        files = extractor.fetch_pr_files("owner", "repo", 123)

        # Should return empty list on error
        assert files == []

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_review_comments_handles_http_error(self, mock_get: Mock) -> None:
        """Test handling of HTTP errors in review comments fetch."""
        from requests import HTTPError

        extractor = GitHubCommentExtractor()

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        comments = extractor._fetch_review_comments("owner", "repo", 123)

        # Should return empty list on HTTP error
        assert comments == []

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_review_comments_handles_json_error(self, mock_get: Mock) -> None:
        """Test handling of JSON decode errors in review comments fetch."""
        import json

        extractor = GitHubCommentExtractor()

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("bad json", "", 0)
        mock_get.return_value = mock_response

        comments = extractor._fetch_review_comments("owner", "repo", 123)

        # Should return empty list on JSON error
        assert comments == []

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_issue_comments_handles_http_error(self, mock_get: Mock) -> None:
        """Test handling of HTTP errors in issue comments fetch."""
        from requests import HTTPError

        extractor = GitHubCommentExtractor()

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError("503 Service Unavailable")
        mock_get.return_value = mock_response

        comments = extractor._fetch_issue_comments("owner", "repo", 123)

        # Should return empty list on HTTP error
        assert comments == []

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_issue_comments_handles_json_error(self, mock_get: Mock) -> None:
        """Test handling of JSON decode errors in issue comments fetch."""
        import json

        extractor = GitHubCommentExtractor()

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("invalid json", "", 0)
        mock_get.return_value = mock_response

        comments = extractor._fetch_issue_comments("owner", "repo", 123)

        # Should return empty list on JSON error
        assert comments == []

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_pr_files_handles_http_error(self, mock_get: Mock) -> None:
        """Test handling of HTTP errors in PR files fetch."""
        from requests import HTTPError

        extractor = GitHubCommentExtractor()

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        files = extractor.fetch_pr_files("owner", "repo", 123)

        # Should return empty list on HTTP error
        assert files == []

    @patch("review_bot_automator.integrations.github.requests.Session.get")
    def test_fetch_pr_files_handles_json_error(self, mock_get: Mock) -> None:
        """Test handling of JSON decode errors in PR files fetch."""
        import json

        extractor = GitHubCommentExtractor()

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("malformed json", "", 0)
        mock_get.return_value = mock_response

        files = extractor.fetch_pr_files("owner", "repo", 123)

        # Should return empty list on JSON error
        assert files == []
