"""Tests for Codex CLI provider.

This module tests the Codex CLI provider implementation including:
- Provider protocol conformance
- CLI availability checking
- Token counting via character estimation
- Cost calculation (always $0.00)
- Subprocess execution with mocked failures
- Error handling for various failure modes
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from review_bot_automator.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
)
from review_bot_automator.llm.providers.base import LLMProvider
from review_bot_automator.llm.providers.codex_cli import CodexCLIProvider


class TestCodexCLIProviderProtocol:
    """Test that CodexCLIProvider conforms to LLMProvider protocol."""

    @patch("shutil.which")
    def test_provider_implements_protocol(self, mock_which: Mock) -> None:
        """Test that CodexCLIProvider implements LLMProvider protocol."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        assert isinstance(provider, LLMProvider)

    @patch("shutil.which")
    def test_provider_has_generate_method(self, mock_which: Mock) -> None:
        """Test that provider has generate() method with correct signature."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        assert hasattr(provider, "generate")
        assert callable(provider.generate)

    @patch("shutil.which")
    def test_provider_has_count_tokens_method(self, mock_which: Mock) -> None:
        """Test that provider has count_tokens() method with correct signature."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        assert hasattr(provider, "count_tokens")
        assert callable(provider.count_tokens)

    @patch("shutil.which")
    def test_provider_has_get_total_cost_method(self, mock_which: Mock) -> None:
        """Test that provider has get_total_cost() method."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        assert hasattr(provider, "get_total_cost")
        assert callable(provider.get_total_cost)

    @patch("shutil.which")
    def test_provider_has_reset_usage_tracking_method(self, mock_which: Mock) -> None:
        """Test that provider has reset_usage_tracking() method."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        assert hasattr(provider, "reset_usage_tracking")
        assert callable(provider.reset_usage_tracking)


class TestCodexCLIProviderInitialization:
    """Test CodexCLIProvider initialization and configuration."""

    @patch("shutil.which")
    def test_init_with_valid_params(self, mock_which: Mock) -> None:
        """Test initialization with valid parameters."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider(model="codex-pro", timeout=90)

        assert provider.model == "codex-pro"
        assert provider.timeout == 90
        assert provider.total_input_tokens == 0
        assert provider.total_output_tokens == 0

    @patch("shutil.which")
    def test_init_with_default_model(self, mock_which: Mock) -> None:
        """Test that default model is codex-latest."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        assert provider.model == "codex-latest"

    @patch("shutil.which")
    def test_init_with_default_timeout(self, mock_which: Mock) -> None:
        """Test that default timeout is 60 seconds."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        assert provider.timeout == 60

    @patch("shutil.which")
    def test_init_checks_cli_availability(self, mock_which: Mock) -> None:
        """Test that initialization checks CLI availability."""
        mock_which.return_value = "/usr/bin/codex"

        # Should not raise
        CodexCLIProvider()

        # Verify shutil.which was called
        assert mock_which.called
        mock_which.assert_called_with("codex")

    @patch("shutil.which")
    def test_init_raises_on_cli_not_found(self, mock_which: Mock) -> None:
        """Test that LLMConfigurationError is raised when CLI is not found."""
        mock_which.return_value = None

        with pytest.raises(LLMConfigurationError, match="Codex CLI not found"):
            CodexCLIProvider()

    @patch("shutil.which")
    def test_init_error_includes_install_url(self, mock_which: Mock) -> None:
        """Test that CLI not found error includes installation URL."""
        mock_which.return_value = None

        with pytest.raises(LLMConfigurationError, match="https://codex.ai/cli"):
            CodexCLIProvider()

    @patch("shutil.which")
    def test_init_error_includes_details(self, mock_which: Mock) -> None:
        """Test that CLI not found error includes provider details."""
        mock_which.return_value = None

        with pytest.raises(LLMConfigurationError) as exc_info:
            CodexCLIProvider()

        assert exc_info.value.details["provider"] == "codex-cli"
        assert exc_info.value.details["cli_command"] == "codex"


class TestCodexCLIProviderTokenCounting:
    """Test token counting using character-based estimation."""

    @patch("shutil.which")
    def test_count_tokens_simple_text(self, mock_which: Mock) -> None:
        """Test counting tokens for simple text."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        text = "Hello world"
        count = provider.count_tokens(text)

        assert count == len(text) // 4
        assert count > 0
        assert isinstance(count, int)

    @patch("shutil.which")
    def test_count_tokens_empty_string(self, mock_which: Mock) -> None:
        """Test counting tokens for empty string."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        count = provider.count_tokens("")
        assert count == 0

    @patch("shutil.which")
    def test_count_tokens_code(self, mock_which: Mock) -> None:
        """Test counting tokens for code snippet."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        code = """def hello():
    print("Hello world")
    return 42"""
        count = provider.count_tokens(code)
        assert count == len(code) // 4
        assert count > 5  # Should tokenize to multiple tokens

    @patch("shutil.which")
    def test_count_tokens_none_raises(self, mock_which: Mock) -> None:
        """Test that None text raises ValueError."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        with pytest.raises(ValueError, match="Text cannot be None"):
            provider.count_tokens(None)  # type: ignore[arg-type]

    @patch("shutil.which")
    def test_count_tokens_consistent(self, mock_which: Mock) -> None:
        """Test that token counting is consistent for same text."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        text = "The quick brown fox jumps over the lazy dog"
        count1 = provider.count_tokens(text)
        count2 = provider.count_tokens(text)
        assert count1 == count2

    @patch("shutil.which")
    def test_count_tokens_multiline(self, mock_which: Mock) -> None:
        """Test counting tokens for multi-line text."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        multiline = "Line 1\nLine 2\nLine 3"
        count = provider.count_tokens(multiline)
        assert count == len(multiline) // 4


class TestCodexCLIProviderCostCalculation:
    """Test cost tracking and calculation."""

    @patch("shutil.which")
    def test_get_total_cost_initial_zero(self, mock_which: Mock) -> None:
        """Test that initial total cost is zero."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        assert provider.get_total_cost() == 0.0

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_get_total_cost_always_zero(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that cost is always zero (subscription covered)."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response text"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        provider = CodexCLIProvider()
        provider.generate("test prompt")

        # Cost should still be zero after usage
        assert provider.get_total_cost() == 0.0

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_get_total_cost_multiple_calls(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that cost remains zero after multiple calls."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        provider = CodexCLIProvider()
        provider.generate("prompt 1")
        provider.generate("prompt 2")
        provider.generate("prompt 3")

        assert provider.get_total_cost() == 0.0


class TestCodexCLIProviderGenerate:
    """Test generate() method with various scenarios."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_generate_success(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test successful generation."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Generated response text"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        provider = CodexCLIProvider()
        result = provider.generate("test prompt")

        assert result == "Generated response text"
        mock_run.assert_called_once_with(
            ["codex", "exec"],
            input="test prompt",
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_generate_strips_whitespace(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that response whitespace is stripped."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  Response with spaces  \n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        provider = CodexCLIProvider()
        result = provider.generate("test prompt")

        assert result == "Response with spaces"

    @patch("shutil.which")
    def test_generate_empty_prompt_raises(self, mock_which: Mock) -> None:
        """Test that empty prompt raises ValueError."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            provider.generate("")

    @patch("shutil.which")
    def test_generate_whitespace_only_prompt_raises(self, mock_which: Mock) -> None:
        """Test that whitespace-only prompt raises ValueError."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            provider.generate("   \n\t  ")

    @patch("shutil.which")
    def test_generate_invalid_max_tokens_raises(self, mock_which: Mock) -> None:
        """Test that invalid max_tokens raises ValueError."""
        mock_which.return_value = "/usr/bin/codex"

        provider = CodexCLIProvider()
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider.generate("test", max_tokens=0)

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            provider.generate("test", max_tokens=-1)

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_generate_timeout_raises(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that timeout raises LLMAPIError."""
        import subprocess

        mock_which.return_value = "/usr/bin/codex"
        mock_run.side_effect = subprocess.TimeoutExpired("codex", 60)

        provider = CodexCLIProvider(timeout=60)
        with pytest.raises(LLMAPIError, match="timed out after 60s"):
            provider.generate("test prompt")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_generate_non_zero_exit_code_raises(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that non-zero exit code raises LLMAPIError."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "Error: Something went wrong"
        mock_run.return_value = mock_result

        provider = CodexCLIProvider()
        with pytest.raises(LLMAPIError, match="exit code 2"):
            provider.generate("test prompt")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_generate_authentication_error_raises(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that authentication error raises LLMAuthenticationError."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: Authentication failed"
        mock_run.return_value = mock_result

        provider = CodexCLIProvider()
        with pytest.raises(LLMAuthenticationError, match="authentication failed"):
            provider.generate("test prompt")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_generate_empty_response_raises(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that empty response raises LLMAPIError."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        provider = CodexCLIProvider()
        with pytest.raises(LLMAPIError, match="empty response"):
            provider.generate("test prompt")

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_generate_tracks_token_usage(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that token usage is tracked."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response text here"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        provider = CodexCLIProvider()
        provider.generate("test prompt")

        assert provider.total_input_tokens > 0
        assert provider.total_output_tokens > 0

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_generate_uses_custom_timeout(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that custom timeout is used."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        provider = CodexCLIProvider(timeout=120)
        provider.generate("test prompt")

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 120

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_generate_subprocess_error_raises(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that subprocess errors are handled."""
        import subprocess

        mock_which.return_value = "/usr/bin/codex"
        mock_run.side_effect = subprocess.SubprocessError("Subprocess failed")

        provider = CodexCLIProvider()
        with pytest.raises(LLMAPIError, match="subprocess execution failed"):
            provider.generate("test prompt")


class TestCodexCLIProviderUsageTracking:
    """Test usage tracking and reset functionality."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_reset_usage_tracking(self, mock_run: Mock, mock_which: Mock) -> None:
        """Test that reset_usage_tracking resets counters."""
        mock_which.return_value = "/usr/bin/codex"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Response"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        provider = CodexCLIProvider()
        provider.generate("test prompt")

        assert provider.total_input_tokens > 0
        assert provider.total_output_tokens > 0

        provider.reset_usage_tracking()

        assert provider.total_input_tokens == 0
        assert provider.total_output_tokens == 0
