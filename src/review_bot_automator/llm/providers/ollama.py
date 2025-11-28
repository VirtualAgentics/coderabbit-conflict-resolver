# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
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

import json
import logging
import time
from collections import deque
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
from urllib3.exceptions import PoolError

from review_bot_automator.llm.exceptions import (
    LLMAPIError,
    LLMConfigurationError,
)
from review_bot_automator.llm.providers.gpu_detector import GPUDetector, GPUInfo

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

        Auto-download models:
            >>> provider = OllamaProvider(model="qwen2.5-coder:7b", auto_download=True)
            # Model will be downloaded automatically if not available locally

        Get model recommendations:
            >>> models = OllamaProvider.list_recommended_models()
            >>> for model in models:
            ...     print(f"{model['name']}: {model['description']}")

    Attributes:
        base_url: Ollama API base URL (default: http://localhost:11434)
        model: Model identifier (e.g., "llama3.3:70b", "mistral")
        timeout: Request timeout in seconds (default: 120s for slow local inference)
        auto_download: Automatically download model if not available (default: False)
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
        auto_download: bool = False,
    ) -> None:
        """Initialize Ollama API provider.

        Args:
            model: Model identifier (default: llama3.3:70b for quality/speed balance)
            timeout: Request timeout in seconds (default: 120s for local inference)
            base_url: Ollama API base URL (default: http://localhost:11434)
            auto_download: Automatically download model if not available (default: False)

        Raises:
            LLMAPIError: If Ollama is not running or not reachable
            LLMConfigurationError: If requested model is not available and auto_download=False
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.auto_download = auto_download

        # Initialize HTTP session for connection pooling
        self.session = requests.Session()

        # Configure connection pool for efficient HTTP reuse
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools to cache
            pool_maxsize=10,  # Max connections to keep in pool
            max_retries=0,  # We handle retries with tenacity
            pool_block=True,  # Block and surface exhaustion instead of spawning extra sockets
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Token usage tracking (estimated via character count)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Latency tracking (bounded to prevent unbounded memory growth)
        self._request_latencies: deque[float] = deque(maxlen=1000)
        self._last_request_latency: float | None = None

        try:
            # Verify Ollama is running
            self._check_ollama_available()

            # Verify model is available
            self._check_model_available()
        except Exception:
            # Cleanup session if initialization fails
            self.session.close()
            raise

        # Detect GPU (non-blocking, best-effort)
        # Detection failure is non-fatal and logged at DEBUG level
        self.gpu_info: GPUInfo | None = None
        try:
            self.gpu_info = GPUDetector.detect_gpu(self.base_url, timeout=5)
            if self.gpu_info.available:
                vram_display = (
                    f" ({self.gpu_info.vram_total_mb // 1024}GB VRAM)"
                    if self.gpu_info.vram_total_mb
                    else ""
                )
                logger.info(
                    f"GPU detected: {self.gpu_info.gpu_type} "
                    f"{self.gpu_info.model_name}{vram_display}"
                )
            else:
                logger.info("GPU not detected, using CPU inference")
        except Exception as e:
            logger.debug(f"GPU detection failed (non-fatal): {e}")
            # Ensure we always have a GPUInfo object (CPU fallback)
            self.gpu_info = GPUInfo(
                available=False,
                gpu_type="CPU",
                model_name=None,
                vram_total_mb=None,
                vram_available_mb=None,
                compute_capability=None,
            )

        logger.info(
            f"Initialized Ollama provider: model={model}, timeout={timeout}s, base_url={base_url}"
        )

    def _check_ollama_available(self) -> None:
        """Check if Ollama is running and reachable.

        Raises:
            LLMAPIError: If Ollama is not reachable with instructions to start it
        """
        # Check if provider has been closed
        if self.session is None:
            raise LLMAPIError(
                "Provider has been closed",
                details={"hint": "Create a new provider or use context manager"},
            )

        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except PoolError as e:
            # Connection pool exhausted - all connections busy
            logger.error(
                f"Ollama connection pool exhausted (all 10 connections busy): {e}",
                extra={"pool_config": "pool_maxsize=10, pool_block=True"},
            )
            raise LLMAPIError(
                "Connection pool exhausted - too many concurrent requests",
                details={"pool_maxsize": 10, "error": str(e)},
            ) from e
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

        If auto_download is enabled and the model is not found, attempts to
        download it automatically.

        Raises:
            LLMConfigurationError: If model is not found and auto_download is False
            LLMAPIError: If auto-download fails
        """
        try:
            available_models = self._list_available_models()

            if self.model not in available_models:
                if self.auto_download:
                    # Attempt automatic download
                    logger.info(
                        f"Model '{self.model}' not found locally. "
                        f"Attempting automatic download (auto_download=True)..."
                    )
                    try:
                        if self._download_model(self.model):
                            logger.info(f"Successfully downloaded model: {self.model}")

                            # Re-verify model is now available after download
                            updated_models = self._list_available_models()
                            if self.model in updated_models:
                                logger.info(f"Verified model '{self.model}' is now available")
                                return
                            else:
                                # Model downloaded but not showing up - configuration error
                                logger.error(
                                    f"Model '{self.model}' downloaded successfully but not "
                                    f"visible in model list"
                                )
                                raise LLMConfigurationError(
                                    f"Model '{self.model}' downloaded but not available. "
                                    f"Try manually: ollama pull {self.model}",
                                    details={
                                        "model": self.model,
                                        "auto_download": True,
                                        "available_models": updated_models,
                                    },
                                )
                    except Exception as download_error:
                        # Download failed - provide helpful error message
                        logger.error(f"Auto-download failed for '{self.model}': {download_error}")
                        raise LLMConfigurationError(
                            f"Model '{self.model}' not found and auto-download failed. "
                            f"Install it manually with: ollama pull {self.model}\n\n"
                            f"Error: {download_error}",
                            details={
                                "model": self.model,
                                "auto_download": True,
                                "download_error": str(download_error),
                            },
                        ) from download_error
                else:
                    # auto_download disabled - provide manual instructions
                    models_list = "\n".join(f"  - {m}" for m in available_models[:10])
                    raise LLMConfigurationError(
                        f"Model '{self.model}' not found in Ollama. "
                        f"Install it with: ollama pull {self.model}\n\n"
                        f"Available models:\n{models_list}\n\n"
                        f"Or enable automatic download: auto_download=True",
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
        # Check if provider has been closed
        if self.session is None:
            raise LLMAPIError(
                "Provider has been closed",
                details={"hint": "Create a new provider or use context manager"},
            )

        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=10)
            response.raise_for_status()

            data = response.json()
            models = data.get("models", [])

            # Extract model names (format: "name:tag" or just "name")
            return [model.get("name", "") for model in models if model.get("name")]

        except PoolError as e:
            # Connection pool exhausted - all connections busy
            logger.error(
                f"Ollama connection pool exhausted (all 10 connections busy): {e}",
                extra={"pool_config": "pool_maxsize=10, pool_block=True"},
            )
            raise LLMAPIError(
                "Connection pool exhausted - too many concurrent requests",
                details={"pool_maxsize": 10, "error": str(e)},
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMAPIError(
                f"Failed to list Ollama models: {e}",
                details={"base_url": self.base_url, "error": str(e)},
            ) from e

    def _download_model(self, model_name: str) -> bool:
        """Download a model from Ollama registry.

        This method triggers a model download via the Ollama API. The download
        is synchronous and may take several minutes depending on model size.

        Args:
            model_name: Name of the model to download (e.g., "qwen2.5-coder:7b")

        Returns:
            True if download successful, False otherwise

        Raises:
            LLMAPIError: If Ollama API is not available or download fails

        Note:
            This method uses the /api/pull endpoint which streams the download
            progress. The stream is consumed but not displayed to avoid cluttering
            logs. For interactive downloads, use scripts/download_ollama_models.sh.
        """
        # Check if provider has been closed
        if self.session is None:
            raise LLMAPIError(
                "Provider has been closed",
                details={"hint": "Create a new provider or use context manager"},
            )

        logger.info(f"Downloading Ollama model: {model_name} (this may take several minutes)...")

        try:
            # Ollama pull API uses streaming response
            response = self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                timeout=600,  # 10 minutes timeout for large models
                stream=True,  # Stream the response to handle progress updates
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Ollama model download failed: {error_detail}")
                raise LLMAPIError(
                    f"Failed to download model '{model_name}': {error_detail}",
                    details={"model": model_name, "status_code": response.status_code},
                )

            # Parse streaming response and check for errors
            # Ollama sends JSON progress updates, including error events
            pull_error: str | None = None
            pull_complete = False

            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    logger.debug(f"Ignoring malformed Ollama pull event: {raw_line}")
                    continue

                # Check for error in event
                if event.get("error"):
                    pull_error = str(event["error"])
                    break

                # Check for success status
                if event.get("status") == "success":
                    pull_complete = True

            # Verify pull completed successfully
            if pull_error:
                raise LLMAPIError(
                    f"Failed to download model '{model_name}': {pull_error}",
                    details={"model": model_name, "error": pull_error},
                )

            if not pull_complete:
                raise LLMAPIError(
                    f"Ollama did not report success while downloading '{model_name}'",
                    details={"model": model_name},
                )

            logger.info(f"Successfully downloaded model: {model_name}")
            return True

        except PoolError as e:
            # Connection pool exhausted - all connections busy
            logger.error(
                f"Ollama connection pool exhausted (all 10 connections busy): {e}",
                extra={"pool_config": "pool_maxsize=10, pool_block=True"},
            )
            raise LLMAPIError(
                "Connection pool exhausted - too many concurrent requests",
                details={"pool_maxsize": 10, "error": str(e)},
            ) from e
        except requests.exceptions.Timeout as e:
            logger.error(f"Model download timed out after 10 minutes: {e}")
            raise LLMAPIError(
                f"Model download timed out for '{model_name}'. "
                f"Try again or use: ollama pull {model_name}",
                details={"model": model_name, "error": str(e)},
            ) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"Model download failed: {e}")
            raise LLMAPIError(
                f"Failed to download model '{model_name}': {e}",
                details={"model": model_name, "error": str(e)},
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error during model download: {e}")
            raise LLMAPIError(
                f"Unexpected error downloading model '{model_name}': {e}",
                details={"model": model_name},
            ) from e

    def _get_model_info(self, model_name: str) -> dict[str, Any] | None:
        """Get detailed information about a specific model.

        Args:
            model_name: Name of the model to get information for

        Returns:
            Dictionary with model information or None if model not found

        Raises:
            LLMAPIError: If API request fails

        Note:
            Uses the /api/show endpoint to retrieve model metadata including
            size, parameters, quantization, and other details.
        """
        # Check if provider has been closed
        if self.session is None:
            raise LLMAPIError(
                "Provider has been closed",
                details={"hint": "Create a new provider or use context manager"},
            )

        try:
            response = self.session.post(
                f"{self.base_url}/api/show",
                json={"name": model_name},
                timeout=10,
            )

            if response.status_code == 404:
                return None  # Model not found

            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

        except PoolError as e:
            logger.error(
                f"Ollama connection pool exhausted (all 10 connections busy): {e}",
                extra={"pool_config": "pool_maxsize=10, pool_block=True"},
            )
            raise LLMAPIError(
                "Connection pool exhausted - too many concurrent requests",
                details={"pool_maxsize": 10, "error": str(e)},
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMAPIError(
                f"Failed to get model info for '{model_name}': {e}",
                details={"model": model_name, "error": str(e)},
            ) from e

    @classmethod
    def list_recommended_models(cls) -> list[dict[str, str]]:
        """Get list of recommended Ollama models for code conflict resolution.

        Returns:
            List of dictionaries with model recommendations, each containing:
            - name: Model name (e.g., "qwen2.5-coder:7b")
            - size: Approximate download size
            - speed: Relative speed (Fast/Medium/Slow)
            - quality: Relative quality (Good/Better/Best)
            - description: Brief description

        Note:
            This is a static list of recommended models. It does not check
            which models are actually available in the Ollama registry.

        Example:
            >>> recommendations = OllamaProvider.list_recommended_models()
            >>> for model in recommendations:
            ...     print(f"{model['name']}: {model['description']}")
        """
        return [
            {
                "name": "qwen2.5-coder:7b",
                "size": "~4GB",
                "speed": "Fast",
                "quality": "Good",
                "description": "Best balance for code tasks (default preset)",
            },
            {
                "name": "qwen2.5-coder:14b",
                "size": "~8GB",
                "speed": "Medium",
                "quality": "Better",
                "description": "Higher quality code understanding",
            },
            {
                "name": "qwen2.5-coder:32b",
                "size": "~18GB",
                "speed": "Slow",
                "quality": "Best",
                "description": "Maximum quality for complex conflicts",
            },
            {
                "name": "codellama:7b",
                "size": "~4GB",
                "speed": "Fast",
                "quality": "Good",
                "description": "Alternative code-focused model",
            },
            {
                "name": "codellama:13b",
                "size": "~7GB",
                "speed": "Medium",
                "quality": "Better",
                "description": "Larger CodeLlama variant",
            },
            {
                "name": "deepseek-coder:6.7b",
                "size": "~4GB",
                "speed": "Fast",
                "quality": "Good",
                "description": "Specialized for code tasks",
            },
            {
                "name": "mistral:7b",
                "size": "~4GB",
                "speed": "Fast",
                "quality": "Good",
                "description": "General-purpose model",
            },
        ]

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

        # Check if provider has been closed
        if self.session is None:
            raise LLMAPIError(
                "Provider has been closed",
                details={"hint": "Create a new provider or use context manager"},
            )

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

            start_time = time.perf_counter()
            try:
                response = self.session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
            finally:
                latency = time.perf_counter() - start_time
                self._last_request_latency = latency
                self._request_latencies.append(latency)

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

        except PoolError as e:
            # Connection pool exhausted - all connections busy
            logger.error(
                f"Ollama connection pool exhausted (all 10 connections busy): {e}",
                extra={"pool_config": "pool_maxsize=10, pool_block=True"},
            )
            raise LLMAPIError(
                "Connection pool exhausted - too many concurrent requests",
                details={"pool_maxsize": 10, "error": str(e)},
            ) from e

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

    def get_last_request_latency(self) -> float | None:
        """Get latency of most recent request in seconds.

        Returns:
            Latency in seconds, or None if no requests made yet.
        """
        return self._last_request_latency

    def get_all_latencies(self) -> list[float]:
        """Get all recorded request latencies.

        Returns:
            Copy of list containing all request latencies in seconds.
            Note: Limited to most recent 1000 entries.
        """
        return list(self._request_latencies)

    def reset_latency_tracking(self) -> None:
        """Reset latency tracking (separate from token/cost tracking).

        Clears all recorded latencies and resets last request latency.
        """
        self._request_latencies.clear()
        self._last_request_latency = None
        logger.debug("Reset latency tracking")

    def close(self) -> None:
        """Close HTTP session and release connection pool resources.

        Should be called when provider is no longer needed to free up system
        resources. Can also be used automatically via context manager.

        Returns:
            None

        Example:
            >>> provider = OllamaProvider()
            >>> try:
            ...     result = provider.generate("test")
            ... finally:
            ...     provider.close()
        """
        if hasattr(self, "session") and self.session is not None:
            self.session.close()
            self.session = None  # type: ignore[assignment]
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

        Returns:
            None
        """
        self.close()
