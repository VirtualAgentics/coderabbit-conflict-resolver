"""Test configuration and fixtures."""

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_pr_comments() -> dict[str, Any]:
    """Load sample PR comments for testing."""
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
    """Create temporary workspace for testing."""
    return tmp_path


@pytest.fixture
def sample_json_file(temp_workspace: Path) -> Path:
    """Create a sample JSON file for testing."""
    json_file = temp_workspace / "package.json"
    json_file.write_text('{\n  "name": "test",\n  "version": "1.0.0"\n}')
    return json_file


@pytest.fixture
def sample_yaml_file(temp_workspace: Path) -> Path:
    """Create a sample YAML file for testing."""
    yaml_file = temp_workspace / "config.yaml"
    yaml_file.write_text("name: test\nversion: 1.0.0\n")
    return yaml_file
