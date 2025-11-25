"""Universal LLM-powered comment parser.

This module implements the core parsing logic that uses LLM providers to extract
code changes from CodeRabbit review comments. The parser:
- Accepts any comment format (diff blocks, suggestions, natural language)
- Uses prompt templates to guide the LLM
- Returns structured ParsedChange objects
- Handles errors gracefully with optional fallback
- Filters results by confidence threshold
- Supports cost budget enforcement

The parser is provider-agnostic and works with any LLMProvider implementation.
"""

from __future__ import annotations

import json
import logging

from pr_conflict_resolver.llm.base import LLMParser, ParsedChange
from pr_conflict_resolver.llm.cost_tracker import CostStatus, CostTracker
from pr_conflict_resolver.llm.exceptions import LLMCostExceededError, LLMSecretDetectedError
from pr_conflict_resolver.llm.prompts import PARSE_COMMENT_PROMPT
from pr_conflict_resolver.llm.providers.base import LLMProvider
from pr_conflict_resolver.security.secret_scanner import SecretScanner

logger = logging.getLogger(__name__)


class UniversalLLMParser(LLMParser):
    """LLM-powered universal comment parser.

    This parser uses LLM providers to extract code changes from any CodeRabbit
    comment format. It handles:
    - Diff blocks (```diff with @@ headers)
    - Suggestion blocks (```suggestion)
    - Natural language descriptions
    - Multi-option suggestions

    The parser validates LLM output against the ParsedChange schema and filters
    by confidence threshold to ensure quality results.

    Examples:
        >>> from pr_conflict_resolver.llm.providers.openai_api import OpenAIAPIProvider
        >>> provider = OpenAIAPIProvider(api_key="sk-...")
        >>> parser = UniversalLLMParser(provider, confidence_threshold=0.7)
        >>> changes = parser.parse_comment("Apply this fix: ...", file_path="test.py")

    Attributes:
        provider: LLM provider instance for text generation
        fallback_to_regex: If True, return empty list on failure (enables fallback)
        confidence_threshold: Minimum confidence score (0.0-1.0) to accept changes
    """

    def __init__(
        self,
        provider: LLMProvider,
        fallback_to_regex: bool = True,
        confidence_threshold: float = 0.5,
        max_tokens: int = 2000,
        cost_tracker: CostTracker | None = None,
        scan_for_secrets: bool = True,
    ) -> None:
        """Initialize universal LLM parser.

        Args:
            provider: LLM provider instance implementing LLMProvider protocol
            fallback_to_regex: If True, return empty list on failure to trigger
                regex fallback. If False, raise exception on parsing errors.
            confidence_threshold: Minimum confidence (0.0-1.0) to accept a change.
                Lower threshold accepts more changes but with potentially lower quality.
                Recommended: 0.5 for balanced results, 0.7 for high quality only.
            max_tokens: Maximum tokens for LLM response generation. Default 2000 is
                sufficient for most PR comments while keeping costs low. Increase for
                very long comments with many changes.
            cost_tracker: Optional CostTracker for budget enforcement. If provided,
                requests are blocked when budget is exceeded and LLMCostExceededError
                is raised.
            scan_for_secrets: Security setting (default: True - secure). When enabled,
                scans comment bodies for secrets before sending to external LLM APIs
                and raises LLMSecretDetectedError if any are found. Disable only for
                testing or trusted local-only LLMs.

        Raises:
            ValueError: If confidence_threshold is not in [0.0, 1.0]
        """
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError(
                f"confidence_threshold must be in [0.0, 1.0], got {confidence_threshold}"
            )

        self.provider = provider
        self.fallback_to_regex = fallback_to_regex
        self.confidence_threshold = confidence_threshold
        self.max_tokens = max_tokens
        self.cost_tracker = cost_tracker
        self.scan_for_secrets = scan_for_secrets

        logger.info(
            "Initialized UniversalLLMParser: fallback=%s, threshold=%s, max_tokens=%s, "
            "cost_tracker=%s, secret_scan=%s",
            fallback_to_regex,
            confidence_threshold,
            max_tokens,
            "enabled" if cost_tracker else "disabled",
            "enabled" if scan_for_secrets else "disabled",
        )

    def parse_comment(
        self,
        comment_body: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ) -> list[ParsedChange]:
        """Parse comment using LLM to extract code changes.

        This method:
        1. Builds a prompt with comment body and context
        2. Sends prompt to LLM provider
        3. Parses JSON response into ParsedChange objects
        4. Validates and filters by confidence threshold
        5. Returns structured changes or empty list on failure

        Args:
            comment_body: Raw comment text from GitHub (markdown format)
            file_path: Optional file path for context (helps LLM with ambiguous comments)
            line_number: Optional line number where comment was posted

        Returns:
            List of ParsedChange objects meeting confidence threshold.
            Empty list if:
            - No changes found in comment
            - LLM parsing failed and fallback_to_regex=True
            - All changes filtered out by confidence threshold

        Raises:
            RuntimeError: If parsing fails and fallback_to_regex=False
            ValueError: If comment_body is None or empty
            LLMSecretDetectedError: If secrets are detected in comment_body
                and scan_for_secrets=True (default)
            LLMCostExceededError: If cost budget is exceeded

        Note:
            The method logs all parsing failures for debugging. Check logs
            if you're not getting expected results.
        """
        if not comment_body:
            raise ValueError("comment_body cannot be None or empty")

        # Scan for secrets BEFORE sending to external LLM API
        if self.scan_for_secrets:
            findings = SecretScanner.scan_content(comment_body, stop_on_first=True)
            if findings:
                logger.error(
                    "Secret detected in comment body (%s), blocking LLM request - "
                    "refusing to send to external API",
                    findings[0].secret_type,
                )
                raise LLMSecretDetectedError(
                    f"Secret detected: {findings[0].secret_type}",
                    findings=findings,
                    details={"file_path": file_path, "line_number": line_number},
                )

        # Check budget before making LLM API call
        if self.cost_tracker and self.cost_tracker.should_block_request():
            # Cache values to avoid multiple lock acquisitions
            accumulated = self.cost_tracker.accumulated_cost
            budget = self.cost_tracker.budget or 0.0
            raise LLMCostExceededError(
                f"Cost budget exceeded: ${accumulated:.4f}/${budget:.4f}",
                accumulated_cost=accumulated,
                budget=budget,
            )

        try:
            # Build prompt with context
            prompt = PARSE_COMMENT_PROMPT.format(
                comment_body=comment_body,
                file_path=file_path or "unknown",
                line_number=line_number or "unknown",
            )

            logger.debug(
                f"Parsing comment: file={file_path}, line={line_number}, "
                f"body_length={len(comment_body)}"
            )

            # Track cost before call to calculate incremental cost
            previous_cost = self.provider.get_total_cost() if self.cost_tracker else 0.0

            # Generate response from LLM
            response = self.provider.generate(prompt, max_tokens=self.max_tokens)

            # Track cost after successful call
            if self.cost_tracker:
                current_cost = self.provider.get_total_cost()
                request_cost = current_cost - previous_cost
                status = self.cost_tracker.add_cost(request_cost)

                # Log warning at threshold (only once)
                if status == CostStatus.WARNING:
                    warning_msg = self.cost_tracker.get_warning_message()
                    if warning_msg:
                        logger.warning(warning_msg)

            logger.debug(f"LLM response length: {len(response)} characters")

            # Parse JSON response
            try:
                changes_data = json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(
                    f"LLM returned invalid JSON: {response[:200]}... "
                    f"(truncated, total {len(response)} chars)"
                )
                raise RuntimeError(f"Invalid JSON from LLM: {e}") from e

            # Validate response is a list
            if not isinstance(changes_data, list):
                logger.error(f"LLM returned non-list: {type(changes_data).__name__}")
                raise RuntimeError(f"LLM must return JSON array, got {type(changes_data).__name__}")

            # Convert to ParsedChange objects with validation
            parsed_changes = []
            for idx, change_dict in enumerate(changes_data):
                try:
                    # ParsedChange.__post_init__ validates all fields
                    change = ParsedChange(**change_dict)

                    # Filter by confidence threshold
                    if change.confidence < self.confidence_threshold:
                        logger.info(
                            f"Filtered change {idx+1}/{len(changes_data)}: "
                            f"confidence {change.confidence:.2f} < "
                            f"threshold {self.confidence_threshold}"
                        )
                        continue

                    parsed_changes.append(change)
                    logger.debug(
                        f"Parsed change {idx+1}/{len(changes_data)}: "
                        f"{change.file_path}:{change.start_line}-{change.end_line} "
                        f"(confidence={change.confidence:.2f}, risk={change.risk_level})"
                    )

                except (TypeError, ValueError) as e:
                    logger.warning(
                        f"Invalid change format from LLM at index {idx}: {change_dict}. "
                        f"Error: {e}"
                    )
                    continue

            logger.info(
                f"LLM parsed {len(parsed_changes)}/{len(changes_data)} changes "
                f"(threshold={self.confidence_threshold})"
            )

            return parsed_changes

        except LLMCostExceededError:
            # Handle cost budget exceeded explicitly - don't wrap in RuntimeError
            if self.fallback_to_regex:
                logger.info("Cost budget exceeded; returning empty list for regex fallback")
                return []
            else:
                raise

        except Exception as e:
            logger.error(f"LLM parsing failed: {type(e).__name__}: {e}")

            if self.fallback_to_regex:
                logger.info("Returning empty list to trigger regex fallback")
                return []
            else:
                raise RuntimeError(f"LLM parsing failed: {e}") from e

    def set_confidence_threshold(self, threshold: float) -> None:
        """Update confidence threshold dynamically.

        Useful for:
        - Adjusting quality requirements per file type
        - Lowering threshold for exploratory parsing
        - Raising threshold for production changes

        Args:
            threshold: New confidence threshold (0.0-1.0)

        Raises:
            ValueError: If threshold not in valid range
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be in [0.0, 1.0], got {threshold}")

        old_threshold = self.confidence_threshold
        self.confidence_threshold = threshold
        logger.info(f"Updated confidence threshold: {old_threshold} -> {threshold}")
