"""Test configuration and fixtures."""

import io
import logging
import os
from collections.abc import Callable, Generator, Iterable
from pathlib import Path
from types import TracebackType
from typing import Any
from unittest.mock import Mock

import pytest
from click import Context
from hypothesis import HealthCheck, settings

from review_bot_automator.cli.main import cli
from review_bot_automator.handlers.json_handler import JsonHandler
from review_bot_automator.handlers.toml_handler import TomlHandler
from review_bot_automator.handlers.yaml_handler import YamlHandler


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
    return JsonHandler(workspace_root=temp_workspace)


@pytest.fixture
def yaml_handler(temp_workspace: Path) -> YamlHandler:
    """
    Create a YamlHandler instance configured with the temp workspace root.

    Args:
        temp_workspace: Temporary workspace directory.

    Returns:
        YamlHandler: Handler instance for testing.
    """
    return YamlHandler(workspace_root=temp_workspace)


@pytest.fixture
def toml_handler(temp_workspace: Path) -> TomlHandler:
    """
    Create a TomlHandler instance configured with the temp workspace root.

    Args:
        temp_workspace: Temporary workspace directory.

    Returns:
        TomlHandler: Handler instance for testing.
    """
    return TomlHandler(workspace_root=temp_workspace)


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
    github_logger = logging.getLogger("review_bot_automator.integrations.github")
    # Save original state
    original_level = github_logger.level
    original_propagate = github_logger.propagate

    github_logger.addHandler(handler)
    github_logger.setLevel(logging.ERROR)
    github_logger.propagate = False

    try:
        yield log_capture
    finally:
        # Clean up logging handler and restore state
        github_logger.removeHandler(handler)
        github_logger.setLevel(original_level)
        github_logger.propagate = original_propagate


@pytest.fixture
def mock_ctx() -> Context:
    """Provide a Click Context for testing."""
    return Context(cli)


@pytest.fixture
def mock_param() -> Mock:
    """Provide a Mock parameter with default name='test'."""
    param = Mock()
    param.name = "test"
    return param


# ============================================================================
# Hypothesis Configuration for Property-Based Testing / Fuzzing
# ============================================================================

# Configure Hypothesis profiles for different testing scenarios
# - dev: Quick local development (50 examples)
# - ci: Standard CI pipeline testing (100 examples)
# - fuzz: Extended fuzzing for comprehensive testing (1000 examples)

settings.register_profile(
    "dev",
    max_examples=50,
    deadline=300,  # 300ms per example
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "ci",
    max_examples=100,
    deadline=500,  # 500ms per example
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "fuzz",
    max_examples=1000,
    deadline=2000,  # 2s per example for complex scenarios
    suppress_health_check=[HealthCheck.too_slow],
)

# Load profile from environment or use "dev" as default
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))


# ============================================================================
# Synchronous Executor Utilities for Deterministic Testing
# ============================================================================

# Sentinel object to distinguish "no result set" from None as a valid result
_NOT_SET: object = object()


class SyncFuture[T]:
    """A synchronous future for deterministic testing.

    Supports both immediate result/exception setting (like ImmediateFuture)
    and deferred setting via set_result/set_exception (like concurrent.futures.Future).

    Type Parameters:
        T: The type of the result value.
    """

    def __init__(self, result: T | object = _NOT_SET, exc: Exception | None = None) -> None:
        """Initialize the future.

        Args:
            result: Optional immediate result value. Use _NOT_SET sentinel for no result.
            exc: Optional immediate exception.
        """
        self._result: T | object = result
        self._exc: Exception | None = exc
        self._has_result = result is not _NOT_SET or exc is not None

    def set_result(self, result: T) -> None:
        """Set the result value (for deferred assignment)."""
        self._result = result
        self._has_result = True

    def set_exception(self, exc: Exception) -> None:
        """Set an exception (for deferred assignment)."""
        self._exc = exc
        self._has_result = True

    def result(self) -> T:
        """Get the result, raising any stored exception."""
        if self._exc is not None:
            raise self._exc
        if self._result is _NOT_SET:
            raise RuntimeError("Future has no result set")
        return self._result  # type: ignore[return-value]


class SyncExecutor[T]:
    """A synchronous executor for deterministic testing.

    Executes tasks immediately in the calling thread, enabling
    predictable test behavior without threading non-determinism.

    Type Parameters:
        T: The return type of submitted callables.
    """

    def __init__(self, max_workers: int = 1) -> None:
        """Initialize the executor.

        Args:
            max_workers: Ignored, kept for API compatibility.
        """
        self.futures: list[SyncFuture[T]] = []
        self._max_workers = max_workers

    def __enter__(self) -> "SyncExecutor[T]":
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Exit context manager."""
        return None

    def submit(
        self,
        fn: Callable[..., T],
        *args: object,
        **kwargs: object,
    ) -> SyncFuture[T]:
        """Submit a callable for immediate execution.

        Args:
            fn: The callable to execute.
            *args: Positional arguments for the callable.
            **kwargs: Keyword arguments for the callable.

        Returns:
            SyncFuture containing the result or exception.
        """
        future: SyncFuture[T] = SyncFuture()
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as exc:  # pragma: no cover - defensive
            future.set_exception(exc)
        self.futures.append(future)
        return future


def fake_as_completed[T](
    futures: Iterable[SyncFuture[T]] | dict[SyncFuture[T], Any],
) -> list[SyncFuture[T]]:
    """Fake as_completed that returns futures in submission order.

    Handles both iterables and dicts consistently, matching the
    concurrent.futures.as_completed signature.

    Args:
        futures: Either an iterable of futures or a dict with futures as keys.

    Returns:
        List of futures in their original order.
    """
    if isinstance(futures, dict):
        return list(futures.keys())
    return list(futures)


def create_exception_injecting_executor(
    fail_indices: set[int],
    exception_factory: Callable[[], Exception] = lambda: RuntimeError("Injected failure"),
) -> type:
    """Create a SyncExecutor that injects exceptions for specific indices.

    This factory creates executor classes that set exceptions on futures
    for specific argument indices, useful for testing exception handling
    in the as_completed loop.

    Args:
        fail_indices: Set of indices that should fail with an exception.
        exception_factory: Callable that creates the exception to inject.

    Returns:
        A SyncExecutor subclass with exception injection behavior.

    Example:
        >>> FailingExecutor = create_exception_injecting_executor({1}, lambda: ValueError("fail"))
        >>> with patch("module.ThreadPoolExecutor", FailingExecutor):
        ...     # Index 1 will have set_exception called instead of set_result
    """

    class ExceptionInjectingExecutor(SyncExecutor[Any]):
        def submit(
            self,
            fn: Callable[..., Any],
            *args: object,
            **kwargs: object,
        ) -> SyncFuture[Any]:
            future: SyncFuture[Any] = SyncFuture()
            # Check if the first positional arg (typically idx) is in fail_indices
            idx = args[0] if args else None
            if idx in fail_indices:
                future.set_exception(exception_factory())
            else:
                try:
                    result = fn(*args, **kwargs)
                    future.set_result(result)
                except Exception as exc:  # pragma: no cover - defensive
                    future.set_exception(exc)
            self.futures.append(future)
            return future

    return ExceptionInjectingExecutor
