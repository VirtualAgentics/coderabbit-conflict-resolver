"""Anthropic API provider implementation.

This module provides the Anthropic API integration for LLM-powered comment parsing.
It includes:
- Retry logic with exponential backoff for transient failures
- Token counting using Anthropic's count_tokens API
- Cost tracking per request (including cache metrics)
- Prompt caching support for cost reduction
- Comprehensive error handling

The provider uses the official Anthropic Python SDK and implements the LLMProvider
protocol for type safety and polymorphic usage.
"""

import logging
from typing import ClassVar

from anthropic import (
    Anthropic,
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from anthropic.types import TextBlock
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


class AnthropicAPIProvider:
    """Anthropic API provider for LLM text generation.

    This provider implements the LLMProvider protocol and provides access to
    Anthropic's Claude models via their official API. It includes:
    - Automatic retry logic for transient failures
    - Token counting via Anthropic's count_tokens API
    - Cost tracking across requests (including cache costs)
    - Prompt caching support for 50-90% cost reduction
    - Comprehensive error handling

    The provider requires an Anthropic API key and supports all Claude models.

    Examples:
        >>> provider = AnthropicAPIProvider(api_key="sk-ant-...", model="claude-sonnet-4-5")
        >>> response = provider.generate("Extract changes from this comment", max_tokens=2000)
        >>> tokens = provider.count_tokens("Some text to tokenize")
        >>> cost = provider.get_total_cost()

    Attributes:
        client: Anthropic client instance
        model: Model identifier (e.g., "claude-sonnet-4-5", "claude-opus-4")
        timeout: Request timeout in seconds
        total_input_tokens: Cumulative input tokens across all requests
        total_output_tokens: Cumulative output tokens across all requests
        total_cache_write_tokens: Cumulative cache write tokens
        total_cache_read_tokens: Cumulative cache read tokens

    Maintaining Pricing Data:
        The MODEL_PRICING dictionary contains hardcoded pricing per 1M tokens.
        When Anthropic updates their pricing:

        1. Check official pricing: https://docs.claude.com/en/docs/about-claude/pricing
        2. Update the "as of [DATE]" comment with the current date
        3. Update pricing values in MODEL_PRICING dictionary
        4. Ensure "input", "output", "cache_write", and "cache_read" prices are specified
        5. Add any new models with their pricing
        6. Note: Cache write pricing is for 5-minute cache (standard tier)

        Note: Unknown models return $0.00 cost (see _calculate_cost method).
    """

    # Pricing per 1M tokens (as of Nov 2025)
    # Source: https://docs.claude.com/en/docs/about-claude/pricing
    MODEL_PRICING: ClassVar[dict[str, dict[str, float]]] = {
        # Current models (2025)
        "claude-opus-4-1": {
            "input": 15.00,
            "output": 75.00,
            "cache_write": 18.75,  # 5-minute cache
            "cache_read": 1.50,
        },
        "claude-sonnet-4-5": {
            "input": 3.00,
            "output": 15.00,
            "cache_write": 3.75,  # 5-minute cache
            "cache_read": 0.30,
        },
        "claude-haiku-4-5": {
            "input": 1.00,
            "output": 5.00,
            "cache_write": 1.25,  # 5-minute cache
            "cache_read": 0.10,
        },
        # Legacy models
        "claude-3-5-haiku-20241022": {
            "input": 1.00,
            "output": 5.00,
            "cache_write": 1.25,  # 5-minute cache
            "cache_read": 0.10,
        },
    }

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-5",
        timeout: int = 60,
    ) -> None:
        """Initialize Anthropic API provider.

        Args:
            api_key: Anthropic API key (starts with sk-ant-)
            model: Model identifier (default: claude-sonnet-4-5 for best value)
            timeout: Request timeout in seconds

        Raises:
            LLMConfigurationError: If api_key is empty or configuration is invalid
        """
        if not api_key:
            raise LLMConfigurationError(
                "Anthropic API key cannot be empty", details={"provider": "anthropic"}
            )

        # Create client with max_retries=0 to implement our own retry logic
        self.client = Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
        self.model = model
        self.timeout = timeout

        # Token usage tracking (4 types for Anthropic)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_write_tokens = 0
        self.total_cache_read_tokens = 0

        logger.info(f"Initialized Anthropic provider: model={model}, timeout={timeout}s")

    def generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """Generate text completion from prompt with retry logic.

        This method sends the prompt to Anthropic's API and returns the generated text.
        It automatically retries on transient failures (rate limits, connection errors,
        and timeouts) using exponential backoff.

        Temperature is set to 0 for deterministic outputs.

        Args:
            prompt: Input prompt for generation
            max_tokens: Maximum tokens to generate in response

        Returns:
            Generated text from the model (typically JSON string)

        Raises:
            LLMAPIError: If generation fails after all retries exhausted
            LLMAuthenticationError: For authentication errors (no retry)
            ValueError: If prompt is empty or max_tokens is invalid

        Note:
            - Retries 3 times with exponential backoff (2s, 4s, 8s)
            - Retries on: RateLimitError, APIConnectionError, APITimeoutError
            - Does NOT retry on authentication errors or invalid requests
            - Tracks token usage for cost calculation (including cache metrics)
            - Uses temperature=0 for deterministic output
        """
        retryer = Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
        )
        return retryer(self._generate_once, prompt, max_tokens)

    def _generate_once(self, prompt: str, max_tokens: int = 2000) -> str:
        """Single generation attempt (called by retry logic).

        Args:
            prompt: Input prompt for generation
            max_tokens: Maximum tokens to generate in response

        Returns:
            Generated text from the model

        Raises:
            RateLimitError, APIConnectionError: Transient errors (will be retried)
            LLMAPIError: If generation fails
            LLMAuthenticationError: For authentication errors
            ValueError: If prompt is empty or max_tokens is invalid
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty")
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens}")

        try:
            logger.debug(
                f"Sending request to Anthropic: model={self.model}, max_tokens={max_tokens}"
            )

            response = self.client.messages.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt,
                                "cache_control": {"type": "ephemeral"},
                            }
                        ],
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.0,  # Deterministic for consistency
            )

            # Track token usage (including cache metrics)
            usage = response.usage
            if usage:
                # Standard tokens
                self.total_input_tokens += usage.input_tokens
                self.total_output_tokens += usage.output_tokens

                # Cache tokens (may be 0 if caching not used)
                cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
                cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
                self.total_cache_write_tokens += cache_write
                self.total_cache_read_tokens += cache_read

                cost = self._calculate_cost(
                    usage.input_tokens, usage.output_tokens, cache_write, cache_read
                )
                logger.debug(
                    f"Anthropic API call: {usage.input_tokens} input + "
                    f"{usage.output_tokens} output + "
                    f"{cache_write} cache_write + "
                    f"{cache_read} cache_read tokens "
                    f"(${cost:.4f})"
                )

            # Extract generated text from all content blocks
            text_parts = []
            if response.content:
                for block in response.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)

            generated_text = "".join(text_parts)

            if not generated_text:
                raise LLMAPIError(
                    "Anthropic returned empty response", details={"model": self.model}
                )

            return generated_text

        except (RateLimitError, APIConnectionError, APITimeoutError) as e:
            # Let these bubble up for retry - tenacity will handle them
            # Don't wrap them here, or retry won't work
            logger.warning(f"Anthropic transient error (will retry): {type(e).__name__}: {e}")
            raise

        except AuthenticationError as e:
            # Explicit auth error handling - don't retry
            logger.error(f"Anthropic authentication error: {e}")
            raise LLMAuthenticationError(
                "Anthropic API authentication failed - check API key",
                details={"model": self.model},
            ) from e

        except (APIError, APIStatusError) as e:
            # Other Anthropic errors (invalid requests, etc.) - don't retry
            logger.error(f"Anthropic API error: {e}")
            raise LLMAPIError(f"Anthropic API error: {e}", details={"model": self.model}) from e

        except Exception as e:
            # Unexpected errors
            logger.error(f"Unexpected error in Anthropic generation: {e}")
            raise LLMAPIError(
                f"Unexpected error during Anthropic generation: {e}",
                details={"model": self.model},
            ) from e

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using Anthropic's tokenizer.

        This method uses Anthropic's official token counting API to count tokens
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
            Token counts are exact for Anthropic models using their counting API.
            Falls back to rough estimation (chars / 4) if API call fails.
        """
        if text is None:
            raise ValueError("Text cannot be None")

        try:
            count_response = self.client.messages.count_tokens(
                model=self.model, messages=[{"role": "user", "content": text}]
            )
            return int(count_response.input_tokens)
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            # Fallback to rough estimation (Anthropic uses ~4 chars per token)
            return len(text) // 4

    def get_total_cost(self) -> float:
        """Calculate total cost of all API calls made by this provider.

        Returns:
            Total cost in USD based on tracked token usage (including cache costs)

        Note:
            Cost is calculated using MODEL_PRICING table. If model is not
            found, returns 0.0. Pricing is current as of Nov 2025.
        """
        return self._calculate_cost(
            self.total_input_tokens,
            self.total_output_tokens,
            self.total_cache_write_tokens,
            self.total_cache_read_tokens,
        )

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> float:
        """Calculate cost for given token counts.

        Args:
            input_tokens: Number of regular input tokens
            output_tokens: Number of completion tokens
            cache_write_tokens: Number of tokens written to cache
            cache_read_tokens: Number of tokens read from cache

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
        cache_write_cost = (cache_write_tokens / 1_000_000) * pricing["cache_write"]
        cache_read_cost = (cache_read_tokens / 1_000_000) * pricing["cache_read"]

        return input_cost + output_cost + cache_write_cost + cache_read_cost

    def reset_usage_tracking(self) -> None:
        """Reset token usage counters to zero.

        Useful for:
        - Starting fresh cost tracking for a new session
        - Testing scenarios that need clean state
        - Per-request cost tracking by resetting before each call
        """
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_write_tokens = 0
        self.total_cache_read_tokens = 0
        logger.debug("Reset token usage tracking")
