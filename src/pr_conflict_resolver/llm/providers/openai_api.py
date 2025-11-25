"""OpenAI API provider implementation.

This module provides the OpenAI API integration for LLM-powered comment parsing.
It includes:
- Retry logic with exponential backoff for transient failures
- Token counting using tiktoken
- Cost tracking per request
- Structured output support (JSON mode)
- Comprehensive error handling

The provider uses the official OpenAI Python SDK and implements the LLMProvider
protocol for type safety and polymorphic usage.
"""

import logging
import time
from typing import ClassVar

import tiktoken
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from pr_conflict_resolver.llm.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMConfigurationError,
)

logger = logging.getLogger(__name__)


class OpenAIAPIProvider:
    """OpenAI API provider for LLM text generation.

    This provider implements the LLMProvider protocol and provides access to
    OpenAI's GPT models via their official API. It includes:
    - Automatic retry logic for transient failures
    - Token counting for cost estimation
    - Cost tracking across requests
    - JSON mode for structured output
    - Comprehensive error handling

    The provider requires an OpenAI API key and supports all GPT models.

    Examples:
        >>> provider = OpenAIAPIProvider(api_key="sk-...", model="gpt-4")
        >>> response = provider.generate("Extract changes from this comment", max_tokens=2000)
        >>> tokens = provider.count_tokens("Some text to tokenize")
        >>> cost = provider.get_total_cost()

    Attributes:
        client: OpenAI client instance
        model: Model identifier (e.g., "gpt-4", "gpt-3.5-turbo")
        timeout: Request timeout in seconds
        total_input_tokens: Cumulative input tokens across all requests
        total_output_tokens: Cumulative output tokens across all requests

    Maintaining Pricing Data:
        The MODEL_PRICING dictionary (lines 65-73) contains hardcoded pricing per 1M tokens.
        When OpenAI updates their pricing:

        1. Check official pricing: https://openai.com/pricing
        2. Update the "as of [DATE]" comment with the current date
        3. Update pricing values in MODEL_PRICING dictionary
        4. Ensure both "input" and "output" prices are specified
        5. Add any new models with their pricing
        6. Consider adding a pricing version/date to enable change tracking

        Note: Unknown models return $0.00 cost (see _calculate_cost method).
    """

    # Pricing per 1M tokens (as of Nov 2024)
    # Source: https://openai.com/pricing
    MODEL_PRICING: ClassVar[dict[str, dict[str, float]]] = {
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-3.5-turbo": {"input": 1.00, "output": 2.00},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
    ) -> None:
        """Initialize OpenAI API provider.

        Args:
            api_key: OpenAI API key (starts with sk-)
            model: Model identifier (default: gpt-4o-mini for cost efficiency)
            timeout: Request timeout in seconds

        Raises:
            LLMConfigurationError: If api_key is empty or configuration is invalid
        """
        if not api_key:
            raise LLMConfigurationError(
                "OpenAI API key cannot be empty", details={"provider": "openai"}
            )

        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.timeout = timeout

        # Token usage tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Latency tracking
        self._request_latencies: list[float] = []
        self._last_request_latency: float | None = None

        # Get tokenizer for this model
        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for unknown models (GPT-4/3.5 compatible)
            logger.warning(
                f"Unknown model '{model}' - using cl100k_base tokenizer fallback. "
                f"This may affect tokenization accuracy, cost estimates, "
                f"and context window calculations. "
                f"Verify the model name or update tiktoken if this is a newly released model."
            )
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        logger.info(f"Initialized OpenAI provider: model={model}, timeout={timeout}s")

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text completion from prompt with retry logic.

        This method sends the prompt to OpenAI's API and returns the generated text.
        It automatically retries on transient failures (timeouts, rate limits,
        connection errors) using exponential backoff.

        The method uses JSON mode to ensure structured output that can be parsed
        reliably. Temperature is set to 0 for deterministic outputs.

        Args:
            prompt: Input prompt for generation
            max_tokens: Maximum tokens to generate in response

        Returns:
            Generated text from the model (typically JSON string)

        Raises:
            LLMAPIError: If generation fails after all retries exhausted
            LLMAuthenticationError: For authentication errors or invalid requests (no retry)
            ValueError: If prompt is empty or max_tokens is invalid

        Note:
            - Retries 3 times with exponential backoff (2s, 4s, 8s)
            - Does NOT retry on authentication errors or invalid requests
            - Tracks token usage for cost calculation
            - Uses JSON mode for structured output
        """
        retryer = Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((APITimeoutError, RateLimitError, APIConnectionError)),
        )
        return retryer(self._generate_once, prompt, max_tokens)

    def _generate_once(self, prompt: str, max_tokens: int = 2000) -> str:
        """Single generation attempt (called by retry logic).

        Args:
            prompt: Input prompt for generation
            max_tokens: Maximum tokens to generate in response

        Returns:
            Generated text from the model (typically JSON string)

        Raises:
            APITimeoutError, RateLimitError, APIConnectionError: Transient errors (will be retried)
            LLMAPIError: If generation fails
            LLMAuthenticationError: For authentication errors
            ValueError: If prompt is empty or max_tokens is invalid
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty")
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens}")

        try:
            logger.debug(f"Sending request to OpenAI: model={self.model}, max_tokens={max_tokens}")

            start_time = time.perf_counter()
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=0.0,  # Deterministic for consistency
                    response_format={"type": "json_object"},  # Force JSON output
                )
            finally:
                latency = time.perf_counter() - start_time
                self._last_request_latency = latency
                self._request_latencies.append(latency)

            # Track token usage
            usage = response.usage
            if usage:
                self.total_input_tokens += usage.prompt_tokens
                self.total_output_tokens += usage.completion_tokens

                logger.debug(
                    f"OpenAI API call: {usage.prompt_tokens} input + "
                    f"{usage.completion_tokens} output tokens "
                    f"(${self._calculate_cost(usage.prompt_tokens, usage.completion_tokens):.4f})"
                )

            # Extract generated text
            generated_text = response.choices[0].message.content or ""

            if not generated_text:
                raise LLMAPIError("OpenAI returned empty response", details={"model": self.model})

            return generated_text

        except (APITimeoutError, RateLimitError, APIConnectionError) as e:
            # Let these bubble up for retry - tenacity will handle them
            # Don't wrap them here, or retry won't work
            logger.warning(f"OpenAI transient error (will retry): {type(e).__name__}: {e}")
            raise

        except AuthenticationError as e:
            # Explicit auth error handling - don't retry
            logger.error(f"OpenAI authentication error: {e}")
            raise LLMAuthenticationError(
                "OpenAI API authentication failed - check API key",
                details={"model": self.model},
            ) from e

        except OpenAIError as e:
            # Other OpenAI errors (invalid requests, etc.) - don't retry
            logger.error(f"OpenAI API error: {e}")
            raise LLMAPIError(f"OpenAI API error: {e}", details={"model": self.model}) from e

        except Exception as e:
            # Unexpected errors
            logger.error(f"Unexpected error in OpenAI generation: {e}")
            raise LLMAPIError(
                f"Unexpected error during OpenAI generation: {e}", details={"model": self.model}
            ) from e

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken.

        This method uses OpenAI's official tokenizer (tiktoken) to count tokens
        exactly as the API would. This is essential for:
        - Cost estimation before making API calls
        - Ensuring prompts fit within model context windows
        - Tracking usage for budget management

        Args:
            text: Text to tokenize

        Returns:
            Number of tokens in the text according to the model's tokenizer

        Raises:
            ValueError: If text is None

        Note:
            Token counts are exact for OpenAI models using tiktoken.
            Different models may have different tokenizers.
        """
        if text is None:
            raise ValueError("Text cannot be None")

        try:
            tokens = self.tokenizer.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            # Fallback to rough estimation
            return len(text) // 4

    def get_total_cost(self) -> float:
        """Calculate total cost of all API calls made by this provider.

        Returns:
            Total cost in USD based on tracked token usage

        Note:
            Cost is calculated using MODEL_PRICING table. If model is not
            found, returns 0.0. Pricing is current as of Nov 2024.
        """
        return self._calculate_cost(self.total_input_tokens, self.total_output_tokens)

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for given token counts.

        Args:
            input_tokens: Number of prompt tokens
            output_tokens: Number of completion tokens

        Returns:
            Cost in USD

        Note:
            Returns 0.0 if model pricing is unknown.
        """
        if self.model not in self.MODEL_PRICING:
            logger.warning(f"Unknown model pricing for {self.model}, returning $0.00")
            return 0.0

        pricing = self.MODEL_PRICING[self.model]
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def reset_usage_tracking(self) -> None:
        """Reset token usage counters to zero.

        Useful for:
        - Starting fresh cost tracking for a new session
        - Testing scenarios that need clean state
        - Per-request cost tracking by resetting before each call
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
        """
        return self._request_latencies.copy()

    def reset_latency_tracking(self) -> None:
        """Reset latency tracking (separate from token/cost tracking).

        Clears all recorded latencies and resets last request latency.
        """
        self._request_latencies = []
        self._last_request_latency = None
        logger.debug("Reset latency tracking")
