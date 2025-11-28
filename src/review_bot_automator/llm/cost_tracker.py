# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Cost tracking and budget enforcement for LLM operations.

This module provides thread-safe cost tracking with configurable budget
limits and warning thresholds. It integrates with the LLM provider
cost tracking infrastructure to enforce spending limits.

Key Features:
- Thread-safe cost accumulation (supports parallel parsing)
- Configurable budget with warning threshold (default 80%)
- Clear status reporting (OK, WARNING, EXCEEDED)
- Graceful degradation support (check before blocking)

Usage Example:
    >>> tracker = CostTracker(budget=1.00, warning_threshold=0.8)
    >>> status = tracker.add_cost(0.50)
    >>> print(status)  # CostStatus.OK
    >>> status = tracker.add_cost(0.35)
    >>> print(status)  # CostStatus.WARNING (85% utilized)
    >>> tracker.should_block_request()  # False - still under budget
"""

import logging
import threading
from enum import Enum

logger = logging.getLogger(__name__)


class CostStatus(Enum):
    """Status of cost budget utilization.

    Used to communicate budget state after cost operations.

    Attributes:
        OK: Under warning threshold (< 80% by default)
        WARNING: At or above warning threshold, under budget
        EXCEEDED: At or above 100% budget utilization
    """

    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"


class CostTracker:
    """Thread-safe cost tracking and budget enforcement.

    This class tracks accumulated costs across LLM API calls and enforces
    budget limits. It is designed to be shared across multiple threads
    (e.g., parallel comment parsing) with proper synchronization.

    The tracker supports:
    - Optional budget (None = unlimited)
    - Warning threshold at configurable percentage (default 80%)
    - Hard stop at 100% budget utilization
    - Single warning log (avoids spam)

    Thread Safety:
        All state-modifying operations use a lock. Properties that read
        mutable state also acquire the lock for consistency.

    Attributes:
        budget: Maximum cost allowed in USD (None = unlimited)
        warning_threshold: Fraction of budget that triggers warning (0.0-1.0)

    Example:
        >>> tracker = CostTracker(budget=5.00)
        >>> # Before each LLM call
        >>> if tracker.should_block_request():
        ...     raise LLMCostExceededError(...)
        >>> # After successful LLM call
        >>> status = tracker.add_cost(provider.get_total_cost() - previous_cost)
        >>> if status == CostStatus.WARNING:
        ...     logger.warning(tracker.get_warning_message())
    """

    def __init__(
        self,
        budget: float | None = None,
        warning_threshold: float = 0.8,
    ) -> None:
        """Initialize cost tracker.

        Args:
            budget: Maximum cost in USD. None means unlimited (no enforcement).
            warning_threshold: Fraction of budget that triggers warning.
                Must be in range (0.0, 1.0]. Default is 0.8 (80%).

        Raises:
            ValueError: If budget is negative or warning_threshold is invalid.
        """
        if budget is not None and budget < 0:
            raise ValueError(f"Budget must be non-negative, got {budget}")
        if not (0.0 < warning_threshold <= 1.0):
            raise ValueError(f"Warning threshold must be in (0.0, 1.0], got {warning_threshold}")

        self._budget = budget
        self._warning_threshold = warning_threshold
        self._accumulated_cost: float = 0.0
        self._lock = threading.Lock()
        self._warning_logged: bool = False

        if budget is not None:
            logger.info(
                f"Cost tracker initialized: budget=${budget:.4f}, "
                f"warning_threshold={warning_threshold*100:.0f}%"
            )
        else:
            logger.debug("Cost tracker initialized: unlimited budget")

    @property
    def budget(self) -> float | None:
        """Get the configured budget (None if unlimited)."""
        return self._budget

    @property
    def warning_threshold(self) -> float:
        """Get the warning threshold as a fraction (0.0-1.0)."""
        return self._warning_threshold

    @property
    def accumulated_cost(self) -> float:
        """Get total accumulated cost in USD (thread-safe)."""
        with self._lock:
            return self._accumulated_cost

    @property
    def remaining_budget(self) -> float | None:
        """Get remaining budget in USD, or None if unlimited.

        Returns:
            Remaining budget (may be negative if exceeded), or None.
        """
        with self._lock:
            if self._budget is None:
                return None
            return self._budget - self._accumulated_cost

    @property
    def budget_utilization(self) -> float:
        """Get budget utilization as a fraction (0.0-1.0+).

        Returns:
            Fraction of budget used. Returns 0.0 if no budget set.
            Can exceed 1.0 if budget is exceeded.
            Returns infinity if budget is 0 and accumulated_cost > 0.
        """
        with self._lock:
            return self._compute_utilization_unlocked()

    def add_cost(self, cost: float) -> CostStatus:
        """Add cost and return current status.

        This method is thread-safe and should be called after each
        successful LLM API call to track spending.

        Args:
            cost: Cost to add in USD. Must be non-negative.

        Returns:
            Current budget status after adding cost:
            - OK: Under warning threshold
            - WARNING: At/above warning threshold, under budget
            - EXCEEDED: At/above 100% budget

        Raises:
            ValueError: If cost is negative.
        """
        if cost < 0:
            raise ValueError(f"Cost must be non-negative, got {cost}")

        with self._lock:
            self._accumulated_cost += cost
            logger.debug(f"Cost added: ${cost:.6f}, total: ${self._accumulated_cost:.4f}")
            return self._check_status_unlocked()

    def check_budget(self) -> CostStatus:
        """Check current budget status without adding cost.

        Thread-safe check of current budget utilization.

        Returns:
            Current budget status (OK, WARNING, or EXCEEDED).
        """
        with self._lock:
            return self._check_status_unlocked()

    def _compute_utilization_unlocked(self) -> float:
        """Compute budget utilization without acquiring lock (internal use).

        Must be called while holding self._lock.

        Returns:
            Fraction of budget used. Returns 0.0 if no budget set.
            Returns infinity if budget is 0 and accumulated_cost > 0.
        """
        if self._budget is None:
            return 0.0
        if self._budget == 0:
            return float("inf") if self._accumulated_cost > 0 else 0.0
        return self._accumulated_cost / self._budget

    def _check_status_unlocked(self) -> CostStatus:
        """Check status without acquiring lock (internal use).

        Must be called while holding self._lock.
        """
        if self._budget is None:
            return CostStatus.OK

        # Handle zero budget explicitly
        if self._budget == 0:
            return CostStatus.EXCEEDED if self._accumulated_cost > 0 else CostStatus.OK

        utilization = self._compute_utilization_unlocked()

        if utilization >= 1.0:
            return CostStatus.EXCEEDED
        elif utilization >= self._warning_threshold:
            return CostStatus.WARNING
        else:
            return CostStatus.OK

    def should_block_request(self) -> bool:
        """Check if new requests should be blocked due to budget.

        Call this BEFORE making an LLM API request to prevent
        exceeding the budget.

        Returns:
            True if budget is exceeded and requests should be blocked.
            Always False if no budget is set (unlimited).
        """
        with self._lock:
            if self._budget is None:
                return False
            return self._accumulated_cost >= self._budget

    def get_warning_message(self) -> str | None:
        """Get warning message if at/above warning threshold.

        Returns a message only once per tracker instance to avoid
        log spam during repeated checks.

        Returns:
            Warning message string, or None if:
            - Under warning threshold
            - Warning already logged
            - No budget set
        """
        with self._lock:
            if self._budget is None:
                return None

            if self._warning_logged:
                return None

            utilization = self._compute_utilization_unlocked()

            if utilization >= self._warning_threshold:
                self._warning_logged = True
                # Format utilization for display (handle infinity)
                util_display = "∞" if utilization == float("inf") else f"{utilization*100:.1f}%"
                return (
                    f"LLM cost budget warning: ${self._accumulated_cost:.4f} of "
                    f"${self._budget:.4f} used ({util_display})"
                )

            return None

    def reset(self) -> None:
        """Reset accumulated cost to zero.

        Useful for testing or per-session cost tracking.
        Does not modify budget or warning threshold.
        """
        with self._lock:
            self._accumulated_cost = 0.0
            self._warning_logged = False
            logger.debug("Cost tracker reset")

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        with self._lock:
            if self._budget is None:
                return f"CostTracker(accumulated=${self._accumulated_cost:.4f}, unlimited)"
            utilization = self._compute_utilization_unlocked()
            # Format utilization for display (handle infinity)
            util_display = "∞" if utilization == float("inf") else f"{utilization*100:.1f}%"
            return (
                f"CostTracker(accumulated=${self._accumulated_cost:.4f}, "
                f"budget=${self._budget:.4f}, "
                f"utilization={util_display})"
            )
