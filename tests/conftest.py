"""Test configuration and fixtures."""

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture  # type: ignore[misc]
def sample_pr_comments() -> dict[str, Any]:
    """
    Provide a sample pull request comments payload for tests.

    Returns:
        dict[str, Any]: A dictionary with a "comments" key mapping to a list of comment objects.
            Each comment object contains the keys:
            - id: integer comment identifier
            - url: API URL for the comment
            - body: comment body (includes a fenced "suggestion" code block with JSON)
            - path: file path the comment targets
            - line: line number the comment references
            - start_line: start line of the suggested range
            - end_line: end line of the suggested range
            - author: comment author's username
            - created_at: ISO 8601 timestamp when the comment was created
    """
    return {
        "comments": [
            {
                "id": 123456,
                "url": "https://api.github.com/repos/owner/repo/issues/comments/123456",
                "body": '```suggestion\n{\n  "name": "test",\n  "version": "1.0.0"\n}\n```',
                "path": "package.json",
                "line": 1,
                "start_line": 1,
                "end_line": 3,
                "author": "coderabbit",
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]
    }


@pytest.fixture  # type: ignore[misc]
def temp_workspace(tmp_path: Path) -> Path:
    """
    Provide a temporary workspace directory for tests.

    Returns:
        Path: Path to the temporary directory provided for the test.
    """
    return tmp_path


@pytest.fixture  # type: ignore[misc]
def sample_json_file(temp_workspace: Path) -> Path:
    """
    Create a sample package.json file inside the given workspace for use in tests.

    Parameters:
        temp_workspace (Path): Directory in which to create the sample file.

    Returns:
        Path: Path to the created "package.json" file.
    """
    json_file = temp_workspace / "package.json"
    json_file.write_text('{\n  "name": "test",\n  "version": "1.0.0"\n}')
    return json_file


@pytest.fixture  # type: ignore[misc]
def sample_yaml_file(temp_workspace: Path) -> Path:
    """
    Create a YAML file named `config.yaml` containing sample settings inside the given workspace.

    Parameters:
        temp_workspace (Path): Directory in which to create the `config.yaml` file.

    Returns:
        Path: Path to the created `config.yaml` file.
    """
    yaml_file = temp_workspace / "config.yaml"
    yaml_file.write_text("name: test\nversion: 1.0.0\n")
    return yaml_file
