"""Test the priority strategy."""

from review_bot_automator import Change, Conflict, FileType, PriorityStrategy


class TestPriorityStrategy:
    """Test the priority strategy."""

    def test_init(self) -> None:
        """Test strategy initialization."""
        strategy = PriorityStrategy()
        assert strategy.config == {}
        assert "user_selections" in strategy.priority_rules
        assert "security_fixes" in strategy.priority_rules
        assert "syntax_errors" in strategy.priority_rules
        assert "regular_suggestions" in strategy.priority_rules
        assert "formatting" in strategy.priority_rules

    def test_init_with_config(self) -> None:
        """Test strategy initialization with custom config."""
        config = {"priority_rules": {"user_selections": 200, "security_fixes": 150}}
        strategy = PriorityStrategy(config)
        assert strategy.priority_rules["user_selections"] == 200
        assert strategy.priority_rules["security_fixes"] == 150

    def test_calculate_priority(self) -> None:
        """Test priority calculation."""
        strategy = PriorityStrategy()

        # Regular change
        regular_change = Change("test.py", 10, 15, "regular change", {}, "fp1", FileType.PYTHON)
        priority = strategy._calculate_priority(regular_change)
        assert priority == strategy.priority_rules["regular_suggestions"]

        # User selection
        user_change = Change(
            "test.py",
            10,
            15,
            "regular change",
            {"option_label": "Option 1"},
            "fp2",
            FileType.PYTHON,
        )
        priority = strategy._calculate_priority(user_change)
        assert priority == strategy.priority_rules["user_selections"]

        # Security-related change
        security_change = Change(
            "test.py", 10, 15, "security fix for vulnerability", {}, "fp3", FileType.PYTHON
        )
        priority = strategy._calculate_priority(security_change)
        assert priority == strategy.priority_rules["security_fixes"]

        # Syntax error fix
        syntax_change = Change("test.py", 10, 15, "fix syntax error", {}, "fp4", FileType.PYTHON)
        priority = strategy._calculate_priority(syntax_change)
        assert priority == strategy.priority_rules["syntax_errors"]

        # Formatting change
        formatting_change = Change(
            "test.py", 10, 15, "format code with prettier", {}, "fp5", FileType.PYTHON
        )
        priority = strategy._calculate_priority(formatting_change)
        assert priority == strategy.priority_rules["formatting"]

    def test_is_security_related(self) -> None:
        """Test security-related change detection."""
        strategy = PriorityStrategy()

        # Security-related changes
        security_changes = [
            "security fix",
            "vulnerability patch",
            "auth token update",
            "password hash",
            "secret key rotation",
            "credential management",
            "permission check",
            "access control",
            "login security",
        ]

        for content in security_changes:
            change = Change("test.py", 10, 15, content, {}, "fp1", FileType.PYTHON)
            assert strategy._is_security_related(change) is True

        # Non-security changes
        regular_changes = ["regular change", "bug fix", "feature addition", "code cleanup"]

        for content in regular_changes:
            change = Change("test.py", 10, 15, content, {}, "fp1", FileType.PYTHON)
            assert strategy._is_security_related(change) is False

    def test_is_syntax_error_fix(self) -> None:
        """Test syntax error fix detection."""
        strategy = PriorityStrategy()

        # Syntax error fixes
        syntax_fixes = [
            "fix error",
            "bug fix",
            "syntax error",
            "parse error",
            "invalid syntax",
            "missing import",
            "undefined variable",
            "not defined",
            "import error",
            "require statement",
        ]

        for content in syntax_fixes:
            change = Change("test.py", 10, 15, content, {}, "fp1", FileType.PYTHON)
            assert strategy._is_syntax_error_fix(change) is True

        # Non-syntax fixes
        regular_changes = [
            "regular change",
            "feature addition",
            "code cleanup",
            "performance improvement",
        ]

        for content in regular_changes:
            change = Change("test.py", 10, 15, content, {}, "fp1", FileType.PYTHON)
            assert strategy._is_syntax_error_fix(change) is False

    def test_is_formatting_change(self) -> None:
        """Test formatting change detection."""
        strategy = PriorityStrategy()

        # Formatting changes
        formatting_changes = [
            "format code",
            "style fix",
            "indent correction",
            "spacing update",
            "whitespace cleanup",
            "line formatting",
            "prettier format",
            "eslint fix",
            "black format",
            "autopep8 style",
        ]

        for content in formatting_changes:
            change = Change("test.py", 10, 15, content, {}, "fp1", FileType.PYTHON)
            assert strategy._is_formatting_change(change) is True

        # Non-formatting changes
        regular_changes = ["regular change", "bug fix", "feature addition", "security fix"]

        for content in regular_changes:
            change = Change("test.py", 10, 15, content, {}, "fp1", FileType.PYTHON)
            assert strategy._is_formatting_change(change) is False

    def test_resolve(self) -> None:
        """
        Verify PriorityStrategy selects the highest-priority change and skips the others when
            resolving a conflict.

        Creates three changes implying different priorities (security, regular, formatting),
            constructs a Conflict containing those changes, calls Strategy.resolve, and asserts
            that the resolution uses the "priority" strategy, succeeds, applies exactly the
            highest-priority change, and marks the other two changes as skipped.
        """
        strategy = PriorityStrategy()

        # Create changes with different priorities
        high_priority = Change("test.py", 10, 15, "security fix", {}, "fp1", FileType.PYTHON)
        medium_priority = Change("test.py", 10, 15, "regular change", {}, "fp2", FileType.PYTHON)
        low_priority = Change("test.py", 10, 15, "formatting change", {}, "fp3", FileType.PYTHON)

        conflict = Conflict(
            file_path="test.py",
            line_range=(10, 15),
            changes=[high_priority, medium_priority, low_priority],
            conflict_type="multiple",
            severity="medium",
            overlap_percentage=100.0,
        )

        resolution = strategy.resolve(conflict)

        assert resolution.strategy == "priority"
        assert resolution.success is True
        assert len(resolution.applied_changes) == 1
        assert resolution.applied_changes[0] == high_priority
        assert len(resolution.skipped_changes) == 2
        assert medium_priority in resolution.skipped_changes
        assert low_priority in resolution.skipped_changes

    def test_resolve_empty_conflict(self) -> None:
        """Test resolving empty conflict."""
        strategy = PriorityStrategy()

        conflict = Conflict(
            file_path="test.py",
            line_range=(10, 15),
            changes=[],
            conflict_type="none",
            severity="low",
            overlap_percentage=0.0,
        )

        resolution = strategy.resolve(conflict)

        assert resolution.strategy == "skip"
        assert resolution.success is False
        assert len(resolution.applied_changes) == 0
        assert len(resolution.skipped_changes) == 0
        assert "No changes to resolve" in resolution.message

    def test_get_strategy_name(self) -> None:
        """Test getting strategy name."""
        strategy = PriorityStrategy()
        assert strategy.get_strategy_name() == "priority"

    def test_get_strategy_description(self) -> None:
        """Test getting strategy description."""
        strategy = PriorityStrategy()
        description = strategy.get_strategy_description()
        assert "priority" in description.lower()
        assert "highest" in description.lower()

    def test_get_priority_rules(self) -> None:
        """Test getting priority rules."""
        strategy = PriorityStrategy()
        rules = strategy.get_priority_rules()
        assert isinstance(rules, dict)
        assert "user_selections" in rules
        assert "security_fixes" in rules

    def test_update_priority_rules(self) -> None:
        """Test updating priority rules."""
        strategy = PriorityStrategy()

        new_rules = {"user_selections": 200, "security_fixes": 150}

        strategy.update_priority_rules(new_rules)

        assert strategy.priority_rules["user_selections"] == 200
        assert strategy.priority_rules["security_fixes"] == 150
        assert strategy.config["priority_rules"]["user_selections"] == 200
