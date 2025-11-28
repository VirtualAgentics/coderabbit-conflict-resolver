# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Exception hierarchy for LLM-powered parsing module.

This module defines a clear exception hierarchy for LLM parsing errors,
enabling fine-grained error handling and better debugging.

Exception Hierarchy:
    LLMError (base)
    ├── LLMProviderError (provider-level failures)
    │   ├── LLMAPIError (API communication failures)
    │   ├── LLMAuthenticationError (authentication/authorization failures)
    │   ├── LLMRateLimitError (rate limiting)
    │   └── LLMTimeoutError (request timeouts)
    ├── LLMParsingError (parsing/response processing failures)
    │   ├── LLMInvalidResponseError (malformed LLM response)
    │   └── LLMValidationError (response doesn't match expected schema)
    ├── LLMConfigurationError (configuration issues)
    ├── LLMCostExceededError (cost budget exceeded)
    └── LLMSecretDetectedError (secrets detected in content before LLM call)

Usage Examples:
    >>> try:
    ...     changes = parser.parse_comment("Fix this bug")
    ... except LLMRateLimitError:
    ...     # Retry with exponential backoff
    ...     time.sleep(60)
    ... except LLMAuthenticationError:
    ...     # Alert admin - API key invalid
    ...     logger.critical("LLM API authentication failed")
    ... except LLMParsingError:
    ...     # Fall back to regex parsing
    ...     changes = regex_parser.parse_comment("Fix this bug")
    ... except LLMError as e:
    ...     # Generic LLM error - log and continue
    ...     logger.error(f"LLM error: {e}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from review_bot_automator.security.secret_scanner import SecretFinding


class LLMError(Exception):
    """Base exception for all LLM-related errors.

    This is the root of the exception hierarchy. Catch this to handle
    any LLM error generically.

    Attributes:
        message: Human-readable error message
        details: Optional dict with additional error context
    """

    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        """Initialize LLM error.

        Args:
            message: Error message describing what went wrong
            details: Optional dictionary with additional context (e.g., model name,
                request ID, error code)
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Format error with details for logging."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


# Provider-level exceptions


class LLMProviderError(LLMError):
    """Base exception for LLM provider errors.

    Raised when the LLM provider (API service) encounters an error.
    This includes network issues, API errors, and service unavailability.
    """


class LLMAPIError(LLMProviderError):
    """LLM API request failed.

    Raised when the LLM API returns an error response that isn't covered
    by more specific exceptions (auth, rate limit, timeout).

    Examples:
        - Internal server error (5xx)
        - Bad request (4xx) due to malformed parameters
        - Service maintenance
    """


class LLMAuthenticationError(LLMProviderError):
    """LLM API authentication or authorization failed.

    Raised when:
        - API key is invalid or expired
        - API key lacks required permissions
        - Token authentication fails

    This error typically requires manual intervention (updating API key).
    """


class LLMRateLimitError(LLMProviderError):
    """LLM API rate limit exceeded.

    Raised when the API returns a rate limit error. The error details may
    include:
        - retry_after: Seconds to wait before retrying
        - limit_type: Type of limit hit (requests, tokens, etc.)

    Example:
        >>> try:
        ...     response = provider.generate(prompt)
        ... except LLMRateLimitError as e:
        ...     retry_after = e.details.get("retry_after", 60)
        ...     time.sleep(retry_after)
    """


class LLMTimeoutError(LLMProviderError):
    """LLM API request timed out.

    Raised when the API doesn't respond within the configured timeout period.
    This is often transient and can be retried.
    """


# Parsing-level exceptions


class LLMParsingError(LLMError):
    """Base exception for LLM response parsing errors.

    Raised when the LLM returns a response, but it can't be parsed or
    validated according to the expected format.
    """


class LLMInvalidResponseError(LLMParsingError):
    """LLM returned malformed or invalid response.

    Raised when:
        - Response is not valid JSON (when JSON expected)
        - Response structure doesn't match expected format
        - Response is empty when content expected
        - Response contains unparseable data

    Example:
        >>> try:
        ...     data = json.loads(llm_response)
        ... except json.JSONDecodeError as e:
        ...     raise LLMInvalidResponseError(
        ...         "LLM returned invalid JSON",
        ...         details={"response_preview": llm_response[:100]}
        ...     ) from e
    """


class LLMValidationError(LLMParsingError):
    """LLM response failed validation against expected schema.

    Raised when the LLM response is structurally valid (e.g., valid JSON)
    but doesn't conform to the expected data schema or business rules.

    Examples:
        - Missing required fields
        - Field values out of valid range
        - Invalid enum values
        - Type mismatches

    Example:
        >>> if confidence < 0.0 or confidence > 1.0:
        ...     raise LLMValidationError(
        ...         "Confidence must be in [0.0, 1.0]",
        ...         details={"field": "confidence", "value": confidence}
        ...     )
    """


# Configuration exceptions


class LLMConfigurationError(LLMError):
    """LLM configuration is invalid or incomplete.

    Raised when:
        - Required configuration parameters are missing
        - Configuration values are invalid
        - Provider setup fails due to configuration
        - Model specified doesn't exist or isn't accessible

    Examples:
        - Missing API key
        - Invalid model name
        - Incompatible parameter combinations
        - Configuration file parsing errors

    Example:
        >>> if not api_key:
        ...     raise LLMConfigurationError(
        ...         "API key is required",
        ...         details={"provider": "openai"}
        ...     )
    """


# Budget/cost exceptions


class LLMCostExceededError(LLMError):
    """LLM cost budget has been exceeded.

    Raised when the accumulated cost of LLM API calls reaches or exceeds
    the configured budget limit. This enables graceful degradation to
    fallback parsing methods (e.g., regex) instead of hard failures.

    Attributes:
        accumulated_cost: Total cost accumulated before exceeding budget (USD)
        budget: Configured budget limit (USD)

    Example:
        >>> try:
        ...     changes = parser.parse_comment("Fix this bug")
        ... except LLMCostExceededError as e:
        ...     logger.warning(
        ...         "Budget exceeded: $%.4f of $%.4f",
        ...         e.accumulated_cost, e.budget
        ...     )
        ...     # Fall back to regex parsing
        ...     changes = regex_parser.parse_comment("Fix this bug")
    """

    def __init__(
        self,
        message: str,
        accumulated_cost: float = 0.0,
        budget: float = 0.0,
        details: dict[str, object] | None = None,
    ) -> None:
        """Initialize cost exceeded error.

        Args:
            message: Error message describing what went wrong
            accumulated_cost: Total cost accumulated (USD)
            budget: Budget limit that was exceeded (USD)
            details: Optional dictionary with additional context
        """
        super().__init__(message, details)
        self.accumulated_cost = accumulated_cost
        self.budget = budget

    def __str__(self) -> str:
        """Format error with cost details."""
        base_msg = super().__str__()
        return f"{base_msg} (accumulated=${self.accumulated_cost:.4f}, budget=${self.budget:.4f})"


# Security exceptions


class LLMSecretDetectedError(LLMError):
    """Secrets detected in content before sending to external LLM API.

    Raised when the SecretScanner detects potential secrets (API keys, tokens,
    credentials) in the content that would be sent to an external LLM API.
    This prevents accidental data exfiltration.

    Attributes:
        findings: List of SecretFinding objects describing detected secrets
        secret_types: Set of detected secret types for logging

    Example:
        >>> try:
        ...     changes = parser.parse_comment("Fix using key: ghp_abc123...")
        ... except LLMSecretDetectedError as e:
        ...     logger.error(
        ...         "Blocked %d secrets from external API: %s",
        ...         len(e.findings), e.secret_types
        ...     )
        ...     # Do not proceed with LLM parsing
    """

    def __init__(
        self,
        message: str,
        findings: list[SecretFinding] | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        """Initialize secret detected error.

        Args:
            message: Error message describing what went wrong
            findings: List of SecretFinding objects from SecretScanner
            details: Optional dictionary with additional context
        """
        super().__init__(message, details)
        self.findings: list[SecretFinding] = findings if findings is not None else []
        self.secret_types = {f.secret_type for f in self.findings}

    def __str__(self) -> str:
        """Format error with secret types (no actual secrets!)."""
        base_msg = super().__str__()
        types_str = ", ".join(sorted(self.secret_types)) if self.secret_types else "unknown"
        return f"{base_msg} (types: {types_str}, count: {len(self.findings)})"
