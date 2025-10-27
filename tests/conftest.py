"""Test configuration and fixtures."""

import io
import logging
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from pr_conflict_resolver.handlers.json_handler import JsonHandler
from pr_conflict_resolver.handlers.toml_handler import TomlHandler
from pr_conflict_resolver.handlers.yaml_handler import YamlHandler


@pytest.fixture
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


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """
    Provide a temporary workspace directory for tests.

    Returns:
        Path: Path to the temporary directory provided for the test.
    """
    return tmp_path


@pytest.fixture
def sample_json_file(temp_workspace: Path) -> Path:
    """
    Create a sample package.json file inside the given workspace for use in tests.

    Args:
        temp_workspace: Directory in which to create the sample file.

    Returns:
        Path: Path to the created "package.json" file.
    """
    json_file = temp_workspace / "package.json"
    json_file.write_text('{\n  "name": "test",\n  "version": "1.0.0"\n}')
    return json_file


@pytest.fixture
def sample_yaml_file(temp_workspace: Path) -> Path:
    """
    Create a YAML file named `config.yaml` containing sample settings inside the given workspace.

    Args:
        temp_workspace: Directory in which to create the `config.yaml` file.

    Returns:
        Path: Path to the created `config.yaml` file.
    """
    yaml_file = temp_workspace / "config.yaml"
    yaml_file.write_text("name: test\nversion: 1.0.0\n")
    return yaml_file


@pytest.fixture
def json_handler(temp_workspace: Path) -> JsonHandler:
    """
    Create a JsonHandler instance configured with the temp workspace root.

    Args:
        temp_workspace: Temporary workspace directory.

    Returns:
        JsonHandler: Handler instance for testing.
    """
    return JsonHandler(workspace_root=str(temp_workspace))


@pytest.fixture
def yaml_handler(temp_workspace: Path) -> YamlHandler:
    """
    Create a YamlHandler instance configured with the temp workspace root.

    Args:
        temp_workspace: Temporary workspace directory.

    Returns:
        YamlHandler: Handler instance for testing.
    """
    return YamlHandler(workspace_root=str(temp_workspace))


@pytest.fixture
def toml_handler(temp_workspace: Path) -> TomlHandler:
    """
    Create a TomlHandler instance configured with the temp workspace root.

    Args:
        temp_workspace: Temporary workspace directory.

    Returns:
        TomlHandler: Handler instance for testing.
    """
    return TomlHandler(workspace_root=str(temp_workspace))


@pytest.fixture
def github_logger_capture() -> Generator[io.StringIO, None, None]:
    """Capture log messages from the GitHub integration module.

    Creates a StringIO buffer, attaches a StreamHandler to the GitHub logger,
    yields the buffer for reading logs, and cleans up the handler after use.

    Yields:
        io.StringIO: Buffer containing log messages.

    Example:
        >>> def test_something(github_logger_capture):
        ...     # Trigger some logging
        ...     log_output = github_logger_capture.getvalue()
        ...     assert "expected message" in log_output
    """
    # Create a string buffer to capture log messages
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.ERROR)

    # Get the logger for the GitHub module
    github_logger = logging.getLogger("pr_conflict_resolver.integrations.github")
    github_logger.addHandler(handler)
    github_logger.setLevel(logging.ERROR)

    try:
        yield log_capture
    finally:
        # Clean up logging handler
        github_logger.removeHandler(handler)
