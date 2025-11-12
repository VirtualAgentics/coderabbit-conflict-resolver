"""Ollama API provider implementation.

This module provides the Ollama HTTP API integration for local LLM inference.
It includes:
- HTTP connection pooling for improved performance
- Ollama availability checking on initialization
- Model availability validation with helpful error messages
- Retry logic with exponential backoff for transient failures
- Token counting via character-based estimation
- Cost tracking (always $0.00 for local models)
- Comprehensive error handling
- Session cleanup via close() or context manager

The provider uses requests.Session for connection pooling to reduce latency
and implements the LLMProvider protocol for type safety and polymorphic usage.
"""

import logging
from typing import Any, ClassVar

import requests
from requests.adapters import HTTPAdapter
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pr_conflict_resolver.llm.exceptions import (
    LLMAPIError,
    LLMConfigurationError,
)

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Ollama API provider for local LLM inference.

    This provider implements the LLMProvider protocol and provides access to
    local Ollama models via HTTP API. It includes:
    - HTTP connection pooling for efficient request reuse
    - Automatic availability checking for Ollama and requested model
    - Retry logic for transient failures
    - Token counting via character estimation
    - Cost tracking (always $0.00 for local models)
    - Comprehensive error handling with helpful install/startup commands
    - Session cleanup via close() or context manager

    The provider requires Ollama to be running locally and supports all
    Ollama-compatible models. Connection pooling significantly reduces latency
    by reusing HTTP connections across multiple requests.

    Examples:
        Basic usage:
            >>> provider = OllamaProvider(model="llama3.3:70b")
            >>> response = provider.generate("Extract changes from this comment", max_tokens=2000)
            >>> tokens = provider.count_tokens("Some text to tokenize")
            >>> cost = provider.get_total_cost()  # Always returns 0.0
            >>> provider.close()  # Cleanup connection pool

        Context manager (recommended):
            >>> with OllamaProvider(model="llama3.3:70b") as provider:
            ...     response = provider.generate("test")
            # Session automatically closed

    Attributes:
        base_url: Ollama API base URL (default: http://localhost:11434)
        model: Model identifier (e.g., "llama3.3:70b", "mistral")
        timeout: Request timeout in seconds (default: 120s for slow local inference)
        session: HTTP session with connection pooling (pool_connections=10, pool_maxsize=10)
        total_input_tokens: Cumulative input tokens across all requests
        total_output_tokens: Cumulative output tokens across all requests

    Note:
        Token counts are estimated using character-based approximation (chars // 4)
        since Ollama doesn't expose a tokenization API.
    """

    DEFAULT_MODEL: ClassVar[str] = "llama3.3:70b"
    DEFAULT_BASE_URL: ClassVar[str] = "http://localhost:11434"
    DEFAULT_TIMEOUT: ClassVar[int] = 120

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        """Initialize Ollama API provider.

        Args:
            model: Model identifier (default: llama3.3:70b for quality/speed balance)
            timeout: Request timeout in seconds (default: 120s for local inference)
            base_url: Ollama API base URL (default: http://localhost:11434)

        Raises:
            LLMAPIError: If Ollama is not running or not reachable
            LLMConfigurationError: If requested model is not available
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        # Initialize HTTP session for connection pooling
        self.session = requests.Session()

        # Configure connection pool for efficient HTTP reuse
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools to cache
            pool_maxsize=10,  # Max connections to keep in pool
            max_retries=0,  # We handle retries with tenacity
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Token usage tracking (estimated via character count)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Verify Ollama is running
        self._check_ollama_available()

        # Verify model is available
        self._check_model_available()

        logger.info(
            f"Initialized Ollama provider: model={model}, timeout={timeout}s, base_url={base_url}"
        )

    def _check_ollama_available(self) -> None:
        """Check if Ollama is running and reachable.

        Raises:
            LLMAPIError: If Ollama is not reachable with instructions to start it
        """
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMAPIError(
                "Ollama is not running or not reachable. Start Ollama with: ollama serve",
                details={"base_url": self.base_url, "error": str(e)},
            ) from e
        except requests.exceptions.Timeout as e:
            raise LLMAPIError(
                f"Ollama did not respond within 5 seconds at {self.base_url}",
                details={"base_url": self.base_url, "error": str(e)},
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMAPIError(
                f"Failed to connect to Ollama at {self.base_url}: {e}",
                details={"base_url": self.base_url, "error": str(e)},
            ) from e

    def _check_model_available(self) -> None:
        """Check if requested model is available locally.

        Raises:
            LLMConfigurationError: If model is not found with instructions to pull it
        """
        try:
            available_models = self._list_available_models()

            if self.model not in available_models:
                models_list = "\n".join(f"  - {m}" for m in available_models[:10])
                raise LLMConfigurationError(
                    f"Model '{self.model}' not found in Ollama. "
                    f"Install it with: ollama pull {self.model}\n\n"
                    f"Available models:\n{models_list}",
                    details={"model": self.model, "available_models": available_models},
                )

        except LLMConfigurationError:
            raise
        except Exception as e:
            raise LLMAPIError(
                f"Failed to check model availability: {e}",
                details={"model": self.model, "error": str(e)},
            ) from e

    def _list_available_models(self) -> list[str]:
        """List all models available in Ollama.

        Returns:
            List of model names available locally

        Raises:
            LLMAPIError: If failed to fetch model list
        """
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()

            data = response.json()
            models = data.get("models", [])

            # Extract model names (format: "name:tag" or just "name")
            return [model.get("name", "") for model in models if model.get("name")]

        except requests.exceptions.RequestException as e:
            raise LLMAPIError(
                f"Failed to list Ollama models: {e}",
                details={"base_url": self.base_url, "error": str(e)},
            ) from e

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text completion from prompt with retry logic.

        This method sends the prompt to Ollama's API and returns the generated text.
        It automatically retries on transient failures (timeouts, connection errors)
        using exponential backoff.

        Temperature is set to 0 for deterministic outputs.

        Args:
            prompt: Input prompt for generation
            max_tokens: Maximum tokens to generate in response

        Returns:
            Generated text from the model

        Raises:
            LLMAPIError: If generation fails after all retries exhausted
            ValueError: If prompt is empty or max_tokens is invalid

        Note:
            - Retries 3 times with exponential backoff (2s, 4s, 8s)
            - Retries on: Timeout, ConnectionError
            - Tracks token usage via character estimation for cost tracking
            - Uses temperature=0 for deterministic output
        """
        retryer = Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(
                (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
            ),
        )

        try:
            return retryer(self._generate_once, prompt, max_tokens)
        except RetryError as e:
            # Extract underlying exception for better error reporting
            underlying_exception = e.last_attempt.exception()
            error_type = (
                type(underlying_exception).__name__ if underlying_exception else "RetryError"
            )
            logger.error(
                f"Ollama API call failed after 3 retry attempts: "
                f"{error_type}: {underlying_exception or e}"
            )
            raise LLMAPIError(
                f"Ollama API call failed after 3 retry attempts: {underlying_exception or e}",
                details={"model": self.model, "error_type": error_type},
            ) from e

    def _generate_once(self, prompt: str, max_tokens: int = 2000) -> str:
        """Single generation attempt (called by retry logic).

        Args:
            prompt: Input prompt for generation
            max_tokens: Maximum tokens to generate in response

        Returns:
            Generated text from the model

        Raises:
            requests.exceptions.Timeout: Timeout error (will be retried)
            requests.exceptions.ConnectionError: Connection error (will be retried)
            LLMAPIError: If generation fails
            ValueError: If prompt is empty or max_tokens is invalid
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty")
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens}")

        try:
            logger.debug(f"Sending request to Ollama: model={self.model}, max_tokens={max_tokens}")

            # Prepare request payload
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,  # Disable streaming for simpler response handling
                "options": {
                    "temperature": 0.0,  # Deterministic for consistency
                    "num_predict": max_tokens,  # Max tokens to generate
                },
            }

            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )

            # Handle HTTP errors
            if response.status_code != 200:
                error_detail = response.text
                raise LLMAPIError(
                    f"Ollama API returned status {response.status_code}: {error_detail}",
                    details={"model": self.model, "status_code": response.status_code},
                )

            # Parse response
            data = response.json()
            generated_text = str(data.get("response", ""))

            if not generated_text:
                raise LLMAPIError("Ollama returned empty response", details={"model": self.model})

            # Track token usage (estimated via character count)
            input_tokens = self.count_tokens(prompt)
            output_tokens = self.count_tokens(generated_text)

            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            logger.debug(
                f"Ollama API call: {input_tokens} input + "
                f"{output_tokens} output tokens (estimated)"
            )

            return generated_text

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # Let these bubble up for retry
            logger.warning(f"Ollama transient error (will retry): {type(e).__name__}: {e}")
            raise

        except requests.exceptions.RequestException as e:
            # Other request errors - don't retry
            logger.error(f"Ollama API error: {e}")
            raise LLMAPIError(f"Ollama API error: {e}", details={"model": self.model}) from e

        except Exception as e:
            # Unexpected errors
            logger.error(f"Unexpected error in Ollama generation: {e}")
            raise LLMAPIError(
                f"Unexpected error during Ollama generation: {e}",
                details={"model": self.model},
            ) from e

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using character-based estimation.

        Since Ollama doesn't expose a tokenization API, this method uses a
        character-based approximation of ~4 characters per token, which is
        a reasonable average for English text across most LLM tokenizers.

        Args:
            text: Text to tokenize

        Returns:
            Estimated number of tokens (len(text) // 4)

        Raises:
            ValueError: If text is None

        Note:
            Token counts are estimates only. Actual token counts may vary
            based on the model's tokenizer.
        """
        if text is None:
            raise ValueError("Text cannot be None")

        # Character-based estimation (~4 chars per token)
        return len(text) // 4

    def get_total_cost(self) -> float:
        """Calculate total cost of all API calls made by this provider.

        Returns:
            Total cost in USD (always 0.0 for local Ollama models)

        Note:
            Ollama models run locally and incur no API costs, so this
            method always returns 0.0. Token tracking is still maintained
            for usage monitoring.
        """
        return 0.0

    def reset_usage_tracking(self) -> None:
        """Reset token usage counters to zero.

        Useful for:
        - Starting fresh usage tracking for a new session
        - Testing scenarios that need clean state
        - Per-request usage tracking by resetting before each call
        """
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        logger.debug("Reset token usage tracking")

    def close(self) -> None:
        """Close HTTP session and release connection pool resources.

        Should be called when provider is no longer needed to free up system
        resources. Can also be used automatically via context manager.

        Example:
            >>> provider = OllamaProvider()
            >>> try:
            ...     result = provider.generate("test")
            ... finally:
            ...     provider.close()
        """
        if hasattr(self, "session"):
            self.session.close()
            logger.debug("Closed Ollama HTTP session and connection pool")

    def __enter__(self) -> "OllamaProvider":
        """Context manager entry.

        Returns:
            Self for context manager usage

        Example:
            >>> with OllamaProvider() as provider:
            ...     result = provider.generate("test")
            # Session automatically closed on exit
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,  # noqa: ANN401
    ) -> None:
        """Context manager exit - cleanup session.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        self.close()
