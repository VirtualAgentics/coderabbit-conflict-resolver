"""Unit tests for CostTracker and CostStatus.

Tests cost budget tracking, warning thresholds, and thread safety.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from review_bot_automator.llm.cost_tracker import CostStatus, CostTracker


class TestCostStatus:
    """Tests for CostStatus enum."""

    def test_enum_values(self) -> None:
        """Verify CostStatus enum has expected values."""
        assert CostStatus.OK.value == "ok"
        assert CostStatus.WARNING.value == "warning"
        assert CostStatus.EXCEEDED.value == "exceeded"


class TestCostTrackerInit:
    """Tests for CostTracker initialization."""

    def test_init_with_budget(self) -> None:
        """Tracker initializes with budget."""
        tracker = CostTracker(budget=5.00)
        assert tracker.budget == 5.00
        assert tracker.accumulated_cost == 0.0
        assert tracker.warning_threshold == 0.8

    def test_init_without_budget(self) -> None:
        """Tracker initializes without budget (unlimited)."""
        tracker = CostTracker()
        assert tracker.budget is None
        assert tracker.accumulated_cost == 0.0

    def test_init_custom_warning_threshold(self) -> None:
        """Tracker initializes with custom warning threshold."""
        tracker = CostTracker(budget=10.0, warning_threshold=0.9)
        assert tracker.warning_threshold == 0.9

    def test_init_invalid_budget_raises(self) -> None:
        """Negative budget raises ValueError."""
        with pytest.raises(ValueError, match="Budget must be non-negative"):
            CostTracker(budget=-1.0)

    def test_init_invalid_threshold_too_low_raises(self) -> None:
        """Warning threshold <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="Warning threshold must be in"):
            CostTracker(budget=5.0, warning_threshold=0.0)

    def test_init_invalid_threshold_too_high_raises(self) -> None:
        """Warning threshold > 1 raises ValueError."""
        with pytest.raises(ValueError, match="Warning threshold must be in"):
            CostTracker(budget=5.0, warning_threshold=1.1)

    def test_init_threshold_exactly_one_valid(self) -> None:
        """Warning threshold of exactly 1.0 is valid."""
        tracker = CostTracker(budget=5.0, warning_threshold=1.0)
        assert tracker.warning_threshold == 1.0


class TestAddCost:
    """Tests for add_cost method."""

    def test_add_cost_returns_ok(self) -> None:
        """Adding cost under threshold returns OK."""
        tracker = CostTracker(budget=10.0)
        status = tracker.add_cost(5.0)
        assert status == CostStatus.OK
        assert tracker.accumulated_cost == 5.0

    def test_add_cost_returns_warning_at_threshold(self) -> None:
        """Adding cost at threshold returns WARNING."""
        tracker = CostTracker(budget=10.0, warning_threshold=0.8)
        status = tracker.add_cost(8.0)  # 80% = threshold
        assert status == CostStatus.WARNING

    def test_add_cost_returns_warning_above_threshold(self) -> None:
        """Adding cost above threshold returns WARNING."""
        tracker = CostTracker(budget=10.0, warning_threshold=0.8)
        status = tracker.add_cost(9.0)  # 90% > threshold
        assert status == CostStatus.WARNING

    def test_add_cost_returns_exceeded_at_budget(self) -> None:
        """Adding cost at budget returns EXCEEDED."""
        tracker = CostTracker(budget=10.0)
        status = tracker.add_cost(10.0)  # 100% = budget
        assert status == CostStatus.EXCEEDED

    def test_add_cost_returns_exceeded_above_budget(self) -> None:
        """Adding cost above budget returns EXCEEDED."""
        tracker = CostTracker(budget=10.0)
        status = tracker.add_cost(12.0)  # > budget
        assert status == CostStatus.EXCEEDED

    def test_add_cost_unlimited_budget_always_ok(self) -> None:
        """Adding cost with unlimited budget always returns OK."""
        tracker = CostTracker()  # No budget
        status = tracker.add_cost(1000.0)
        assert status == CostStatus.OK
        assert tracker.accumulated_cost == 1000.0

    def test_add_cost_negative_raises(self) -> None:
        """Negative cost raises ValueError."""
        tracker = CostTracker(budget=10.0)
        with pytest.raises(ValueError, match="Cost must be non-negative"):
            tracker.add_cost(-1.0)

    def test_add_cost_cumulative(self) -> None:
        """Adding costs is cumulative."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(3.0)
        tracker.add_cost(4.0)
        assert tracker.accumulated_cost == 7.0


class TestShouldBlockRequest:
    """Tests for should_block_request method."""

    def test_should_block_request_false_under_budget(self) -> None:
        """Returns False when under budget."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(5.0)
        assert tracker.should_block_request() is False

    def test_should_block_request_true_at_budget(self) -> None:
        """Returns True when at budget."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(10.0)
        assert tracker.should_block_request() is True

    def test_should_block_request_true_over_budget(self) -> None:
        """Returns True when over budget."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(15.0)
        assert tracker.should_block_request() is True

    def test_should_block_request_false_unlimited(self) -> None:
        """Returns False when no budget set."""
        tracker = CostTracker()
        tracker.add_cost(1000.0)
        assert tracker.should_block_request() is False


class TestBudgetCalculations:
    """Tests for budget utilization and remaining calculations."""

    def test_budget_utilization_calculation(self) -> None:
        """Budget utilization calculated correctly."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(7.5)
        assert tracker.budget_utilization == 0.75

    def test_budget_utilization_unlimited(self) -> None:
        """Budget utilization is 0.0 when unlimited."""
        tracker = CostTracker()
        tracker.add_cost(100.0)
        assert tracker.budget_utilization == 0.0

    def test_budget_utilization_zero_budget(self) -> None:
        """Budget utilization is 0.0 when budget is zero and no cost accrued."""
        tracker = CostTracker(budget=0.0)
        assert tracker.budget_utilization == 0.0

    def test_budget_utilization_zero_budget_with_cost(self) -> None:
        """Budget utilization is infinity when budget is zero but cost accrued."""
        tracker = CostTracker(budget=0.0)
        tracker.add_cost(1.0)
        assert tracker.budget_utilization == float("inf")

    def test_remaining_budget_calculation(self) -> None:
        """Remaining budget calculated correctly."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(3.5)
        assert tracker.remaining_budget == 6.5

    def test_remaining_budget_negative_when_exceeded(self) -> None:
        """Remaining budget can be negative when exceeded."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(15.0)
        assert tracker.remaining_budget == -5.0

    def test_remaining_budget_none_when_unlimited(self) -> None:
        """Remaining budget is None when no budget set."""
        tracker = CostTracker()
        assert tracker.remaining_budget is None


class TestWarningMessage:
    """Tests for warning message generation."""

    def test_warning_message_at_threshold(self) -> None:
        """Warning message returned at threshold."""
        tracker = CostTracker(budget=10.0, warning_threshold=0.8)
        tracker.add_cost(8.5)  # 85%
        msg = tracker.get_warning_message()
        assert msg is not None
        assert "$8.5000" in msg
        assert "$10.0000" in msg
        assert "85.0%" in msg

    def test_warning_message_only_once(self) -> None:
        """Warning message returned only once."""
        tracker = CostTracker(budget=10.0, warning_threshold=0.8)
        tracker.add_cost(8.5)
        msg1 = tracker.get_warning_message()
        msg2 = tracker.get_warning_message()
        assert msg1 is not None
        assert msg2 is None  # Second call returns None

    def test_warning_message_none_under_threshold(self) -> None:
        """No warning message under threshold."""
        tracker = CostTracker(budget=10.0, warning_threshold=0.8)
        tracker.add_cost(5.0)  # 50%
        assert tracker.get_warning_message() is None

    def test_warning_message_none_unlimited(self) -> None:
        """No warning message when unlimited budget."""
        tracker = CostTracker()
        tracker.add_cost(1000.0)
        assert tracker.get_warning_message() is None


class TestCheckBudget:
    """Tests for check_budget method."""

    def test_check_budget_ok(self) -> None:
        """Check budget returns OK when under threshold."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(5.0)
        assert tracker.check_budget() == CostStatus.OK

    def test_check_budget_warning(self) -> None:
        """Check budget returns WARNING at threshold."""
        tracker = CostTracker(budget=10.0, warning_threshold=0.8)
        tracker.add_cost(8.5)
        assert tracker.check_budget() == CostStatus.WARNING

    def test_check_budget_exceeded(self) -> None:
        """Check budget returns EXCEEDED at budget."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(10.0)
        assert tracker.check_budget() == CostStatus.EXCEEDED


class TestReset:
    """Tests for reset method."""

    def test_reset_clears_accumulated_cost(self) -> None:
        """Reset clears accumulated cost."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(5.0)
        tracker.reset()
        assert tracker.accumulated_cost == 0.0

    def test_reset_clears_warning_logged(self) -> None:
        """Reset allows warning message again."""
        tracker = CostTracker(budget=10.0, warning_threshold=0.8)
        tracker.add_cost(8.5)
        _ = tracker.get_warning_message()  # Consume warning
        tracker.reset()
        tracker.add_cost(8.5)
        msg = tracker.get_warning_message()
        assert msg is not None  # Warning available again

    def test_reset_preserves_budget(self) -> None:
        """Reset preserves budget and threshold."""
        tracker = CostTracker(budget=10.0, warning_threshold=0.9)
        tracker.reset()
        assert tracker.budget == 10.0
        assert tracker.warning_threshold == 0.9


class TestThreadSafety:
    """Tests for thread safety."""

    def test_thread_safety_concurrent_adds(self) -> None:
        """Concurrent add_cost calls are thread-safe."""
        tracker = CostTracker(budget=1000.0)
        num_threads = 10
        adds_per_thread = 100
        cost_per_add = 0.01

        def add_costs() -> None:
            for _ in range(adds_per_thread):
                tracker.add_cost(cost_per_add)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(add_costs) for _ in range(num_threads)]
            for f in futures:
                f.result()

        expected_total = num_threads * adds_per_thread * cost_per_add
        # Use approximate comparison due to floating point
        assert abs(tracker.accumulated_cost - expected_total) < 0.0001

    def test_thread_safety_warning_only_once(self) -> None:
        """Warning message returned only once across threads.

        This test verifies the atomicity of get_warning_message() by spawning
        100 concurrent calls across 10 threads. The CostTracker uses a lock to
        ensure that _warning_logged is checked and set atomically, preventing
        multiple threads from receiving the warning. This is critical for
        avoiding log spam during parallel comment parsing.

        The assertion `len(warnings_received) == 1` is deterministic because:
        1. The lock in get_warning_message() makes read-check-set atomic
        2. Only the first thread to acquire the lock gets the warning
        3. All subsequent threads see _warning_logged=True and get None
        """
        tracker = CostTracker(budget=10.0, warning_threshold=0.5)
        tracker.add_cost(6.0)  # Already at warning level

        warnings_received: list[str] = []
        lock = threading.Lock()

        def get_warning() -> None:
            msg = tracker.get_warning_message()
            if msg is not None:
                with lock:
                    warnings_received.append(msg)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_warning) for _ in range(100)]
            for f in futures:
                f.result()

        # Only one thread should have received the warning
        assert len(warnings_received) == 1


class TestRepr:
    """Tests for __repr__ method."""

    def test_repr_with_budget(self) -> None:
        """Repr shows budget information."""
        tracker = CostTracker(budget=10.0)
        tracker.add_cost(5.0)
        repr_str = repr(tracker)
        assert "CostTracker" in repr_str
        assert "5.0000" in repr_str
        assert "10.0000" in repr_str
        assert "50.0%" in repr_str

    def test_repr_unlimited(self) -> None:
        """Repr shows unlimited for no budget."""
        tracker = CostTracker()
        tracker.add_cost(5.0)
        repr_str = repr(tracker)
        assert "unlimited" in repr_str
