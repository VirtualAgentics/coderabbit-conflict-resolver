# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""GitHub integration for fetching PR comments and metadata.

This module provides the GitHubCommentExtractor class that fetches
PR comments from the GitHub API and extracts relevant information.
"""

import json
import logging
import os
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _sanitize_error_message(error_message: str) -> str:
    """Sanitize error messages to remove sensitive information like tokens.

    Args:
        error_message: The raw error message that may contain sensitive data.

    Returns:
        A sanitized error message with tokens and sensitive paths redacted.
    """
    # Redact GitHub tokens (all known patterns)
    # Classic tokens: ghp_, gho_, ghu_, ghs_, ghr_ (typically 40+ chars after prefix)
    # Match tokens with underscores too for test compatibility
    sanitized = re.sub(
        r"gh[pousr]_[A-Za-z0-9_]{20,}",
        "[REDACTED_TOKEN]",
        error_message,
    )

    # Fine-grained personal access tokens: github_pat_ (variable length)
    sanitized = re.sub(
        r"github_pat_[A-Za-z0-9_]{40,}",
        "[REDACTED_TOKEN]",
        sanitized,
    )

    # Redact internal file paths (basic pattern for absolute paths)
    sanitized = re.sub(
        r"/(?:home|root|etc|usr|var)/[^\s]*",
        "[REDACTED_PATH]",
        sanitized,
    )

    return sanitized


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

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

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

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

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
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(
                "Failed to fetch review comments from %s: %s",
                url,
                _sanitize_error_message(str(e)),
            )
            return []

    def _fetch_issue_comments(self, owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch issue comments for a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            List of comment objects parsed from the GitHub API response. Returns an empty list if
            the response is not a list or if a network/error occurs.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{pr_number}/comments"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(
                "Failed to fetch issue comments from %s: %s",
                url,
                _sanitize_error_message(str(e)),
            )
            return []

    def fetch_pr_metadata(self, owner: str, repo: str, pr_number: int) -> dict[str, Any] | None:
        """Fetch metadata for a GitHub pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            Pull request metadata as returned by the GitHub API, or None if the request fails
            or the response is not a JSON object.
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

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            A list of file objects as returned by the GitHub API for the pull request, or an empty
            list if the response is not a list or the request fails.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(
                "Failed to fetch PR files from %s: %s",
                url,
                _sanitize_error_message(str(e)),
            )
            return []

    def filter_bot_comments(
        self, comments: list[dict[str, Any]], bot_names: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Filter a list of GitHub PR comments to those authored by specified bot accounts.

        Args:
            comments: List of comment objects as returned by the GitHub API.
            bot_names: Optional list of substrings to match against each comment's user login
                (case-insensitive). Defaults to ["coderabbit", "code-review", "review-bot"].

        Returns:
            Subset of comments where the comment author's login contains any of the bot_names
            substrings (case-insensitive).
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
        """Extract code suggestion blocks from a comment body.

        Args:
            comment: Comment dict containing a "body" string.

        Returns:
            List of dicts with keys: content (str), option_label (str|None), context (str),
            position (int).
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
