"""GitHub integration for fetching PR comments and metadata.

This module provides the GitHubCommentExtractor class that fetches
PR comments from the GitHub API and extracts relevant information.
"""

import os
from typing import Any

import requests


class GitHubCommentExtractor:
    """Extracts comments from GitHub PRs."""

    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com") -> None:
        """Initialize the extractor with an optional GitHub token and API base URL.

        Parameters:
            token (str | None): Personal access token to authenticate GitHub API requests.
                If None, the value is read from the GITHUB_TOKEN environment variable.
            base_url (str): Base URL for the GitHub API endpoints (defaults to "https://api.github.com").
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = base_url
        self.session = requests.Session()

        if self.token:
            self.session.headers.update(
                {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
            )

    def fetch_pr_comments(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch all comments for a pull request.

        Returns:
            comments (list[dict[str, Any]]): Combined list of review comments and issue (general)
                comments for the specified pull request. Returns an empty list if no comments are
                found or if remote requests fail.
        """
        comments = []

        # Fetch PR review comments
        review_comments = self._fetch_review_comments(owner, repo, pr_number)
        comments.extend(review_comments)

        # Fetch issue comments (general PR comments)
        issue_comments = self._fetch_issue_comments(owner, repo, pr_number)
        comments.extend(issue_comments)

        return comments

    def _fetch_review_comments(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch review comments for a pull request from the GitHub API.

        Returns:
            list[dict[str, Any]]: A list of comment objects parsed from the API response; returns
                an empty list if the request fails or the response JSON is not a list.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.RequestException:
            return []

    def _fetch_issue_comments(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch issue comments for a pull request.

        Returns:
            comments (list[dict[str, Any]]): List of comment objects parsed from the GitHub API
                response.
                Returns an empty list if the response is not a list or if a network/error occurs.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.RequestException:
            return []

    def fetch_pr_metadata(self, owner: str, repo: str, pr_number: int) -> dict[str, Any] | None:
        """Fetch metadata for a GitHub pull request.

        Returns:
            dict: Pull request metadata as returned by the GitHub API, or `None` if the request
                fails or the response is not a JSON object.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None
        except requests.RequestException:
            return None

    def fetch_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Retrieve the list of files changed in a pull request.

        @returns list[dict[str, Any]]: A list of file objects as returned by the GitHub API for
            the pull request, or an empty list if the response is not a list or the request fails.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.RequestException:
            return []

    def filter_bot_comments(
        self, comments: list[dict[str, Any]], bot_names: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Filter a list of GitHub PR comments to those authored by specified bot accounts.

        Parameters:
            comments (list[dict[str, Any]]): List of comment objects as returned by the GitHub API.
            bot_names (list[str] | None): Optional list of substrings to match against each
                comment's user login (case-insensitive).
                Defaults to ["coderabbit", "code-review", "review-bot"] when omitted.

        Returns:
            list[dict[str, Any]]: Subset of `comments` where the comment author's login contains
                any of the `bot_names` substrings (case-insensitive).
        """
        if bot_names is None:
            bot_names = ["coderabbit", "code-review", "review-bot"]

        filtered = []
        for comment in comments:
            user = comment.get("user", {})
            login = user.get("login", "").lower()

            if any(bot_name.lower() in login for bot_name in bot_names):
                filtered.append(comment)

        return filtered

    def extract_suggestion_blocks(self, comment: dict[str, Any]) -> list[dict[str, Any]]:
        """Extracts code suggestion blocks from a comment body.

        Searches the comment's "body" for fenced suggestion blocks delimited by ```suggestion ...
        ```, and returns a list describing each found block.

        Parameters:
            comment (dict[str, Any]): Comment object expected to contain a "body" key with the
                comment text.

        Returns:
            list[dict[str, Any]]: A list of block dictionaries with the following keys:
                - content (str): The text inside the suggestion fence (trailing newlines removed).
                - option_label (str | None): If an option header like **Label** immediately
                    precedes the block, the header text without a trailing colon; otherwise `None`.
                - context (str): Up to 100 characters of text immediately before the block (used
                    to provide surrounding context).
                - position (int): The character index in the comment body where the suggestion
                    fence begins.
        """
        body = comment.get("body", "")
        if not body:
            return []

        import re

        # Regex pattern for suggestion fences
        suggestion_pattern = re.compile(r"```suggestion\s*\n(.*?)\n```", re.DOTALL)

        blocks = []
        for match in suggestion_pattern.finditer(body):
            content = match.group(1).rstrip("\n")
            start_pos = match.start()

            # Look for option headers in preceding text
            preceding_text = body[max(0, start_pos - 200) : start_pos]
            option_label = None

            # Check for option markers
            option_pattern = re.compile(r"\*\*([^*]+)\*\*\s*$", re.MULTILINE)
            option_matches = list(option_pattern.finditer(preceding_text))
            if option_matches:
                last_match = option_matches[-1]
                option_label = last_match.group(1).strip().rstrip(":")

            blocks.append(
                {
                    "content": content,
                    "option_label": option_label,
                    "context": (
                        preceding_text[-100:] if len(preceding_text) > 100 else preceding_text
                    ),
                    "position": start_pos,
                }
            )

        return blocks

    def get_comment_metadata(self, comment: dict[str, Any]) -> dict[str, Any]:
        """Return metadata extracted from a GitHub comment object.

        Parameters:
            comment (dict[str, Any]): Raw comment JSON returned by the GitHub API.

        Returns:
            dict[str, Any]: Mapping containing extracted fields:
                - id
                - url (html_url)
                - author (user login)
                - author_type (user type)
                - created_at
                - updated_at
                - path
                - line
                - start_line
                - original_line
                - original_start_line
                - position
                - side
                - in_reply_to_id
        """
        user = comment.get("user", {})

        return {
            "id": comment.get("id"),
            "url": comment.get("html_url"),
            "author": user.get("login"),
            "author_type": user.get("type"),
            "created_at": comment.get("created_at"),
            "updated_at": comment.get("updated_at"),
            "path": comment.get("path"),
            "line": comment.get("line"),
            "start_line": comment.get("start_line"),
            "original_line": comment.get("original_line"),
            "original_start_line": comment.get("original_start_line"),
            "position": comment.get("position"),
            "side": comment.get("side"),
            "in_reply_to_id": comment.get("in_reply_to_id"),
        }
