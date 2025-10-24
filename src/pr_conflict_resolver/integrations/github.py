"""GitHub integration for fetching PR comments and metadata.

This module provides the GitHubCommentExtractor class that fetches
PR comments from the GitHub API and extracts relevant information.
"""

import logging
import os
import time
from typing import Any

import requests


class GitHubCommentExtractor:
    """Extracts comments from GitHub PRs."""

    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com") -> None:
        """Initialize the GitHub comment extractor."""
        self.logger = logging.getLogger(__name__)
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = base_url
        self.session = requests.Session()

        if self.token:
            self.session.headers.update(
                {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
            )

    def fetch_pr_comments(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch all comments for a PR."""
        comments = []

        # Fetch PR review comments
        review_comments = self._fetch_review_comments(owner, repo, pr_number)
        comments.extend(review_comments)

        # Fetch issue comments (general PR comments)
        issue_comments = self._fetch_issue_comments(owner, repo, pr_number)
        comments.extend(issue_comments)

        return comments

    def _fetch_review_comments(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch PR review comments."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.RequestException:
            return []

    def _fetch_issue_comments(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch issue comments (general PR comments)."""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except requests.RequestException:
            return []

    def fetch_pr_metadata(self, owner: str, repo: str, pr_number: int) -> dict[str, Any] | None:
        """Fetch PR metadata."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()
                return data if isinstance(data, dict) else None
            except requests.RequestException as e:
                self.logger.error(
                    f"Request failed for {url} (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if hasattr(e, "response") and e.response is not None:
                    self.logger.error(
                        f"Response status: {e.response.status_code}, "
                        f"Response body: {e.response.text[:500]}"
                    )

                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    self.logger.debug(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    self.logger.error(f"All {max_retries} attempts failed for {url}")
                    return None

        return None

    def fetch_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch files changed in the PR."""
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
        """Filter comments to only include those from specified bots."""
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
        """Extract suggestion blocks from a comment."""
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
        """Extract metadata from a comment."""
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
