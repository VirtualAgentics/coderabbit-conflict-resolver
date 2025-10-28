"""Priority-based resolution strategy.

This module provides the PriorityStrategy class that resolves conflicts
based on priority levels and user preferences.
"""

from typing import Any

from pr_conflict_resolver.core.models import Change, Conflict, Resolution
from pr_conflict_resolver.strategies.base import ResolutionStrategy


class PriorityStrategy(ResolutionStrategy):
    """Priority-based conflict resolution strategy."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Create a PriorityStrategy and initialize its configuration and priority rules.

        If `config` contains a "priority_rules" mapping, those rules are used; otherwise a default
        set of priority scores is established for:
        - user_selections: 100
        - security_fixes: 90
        - syntax_errors: 80
        - regular_suggestions: 50
        - formatting: 10

        Args:
            config (dict[str, Any] | None): Optional configuration dictionary that may include a
                "priority_rules" key to override the defaults.
        """
        self.config = config or {}
        self.priority_rules = self.config.get(
            "priority_rules",
            {
                "user_selections": 100,
                "security_fixes": 90,
                "syntax_errors": 80,
                "regular_suggestions": 50,
                "formatting": 10,
            },
        )

    def resolve(self, conflict: Conflict) -> Resolution:
        """Selects the highest-priority change from a conflict.

        Args:
            conflict (Conflict): The conflict containing candidate changes to resolve.

        Returns:
            Resolution: A resolution describing the selected applied change and any skipped changes.
                If the conflict has no changes, returns a "skip" resolution with success `False`
                and message "No changes to resolve".
        """
        if not conflict.changes:
            return Resolution(
                strategy="skip",
                applied_changes=[],
                skipped_changes=[],
                success=False,
                message="No changes to resolve",
            )

        # Calculate priorities for all changes
        prioritized_changes: list[tuple[int, Change]] = []
        for change in conflict.changes:
            priority = self._calculate_priority(change)
            prioritized_changes.append((priority, change))

        # Sort by priority (highest first)
        prioritized_changes.sort(key=lambda x: x[0], reverse=True)

        # Select highest priority change
        highest_priority = prioritized_changes[0][0]
        selected_changes = [
            change for priority, change in prioritized_changes if priority == highest_priority
        ]

        # If multiple changes have same priority, use first one
        applied_change = selected_changes[0]
        skipped_changes = [
            change for priority, change in prioritized_changes if change is not applied_change
        ]

        return Resolution(
            strategy="priority",
            applied_changes=[applied_change],
            skipped_changes=skipped_changes,
            success=True,
            message=f"Applied highest priority change (priority: {highest_priority})",
        )

    def _calculate_priority(self, change: Change) -> int:
        """Compute the numeric priority for a Change based on configured rules.

        Args:
            change (Change): The change to evaluate. Uses change.metadata["option_label"] (if
                present) to prefer user selections and change.metadata["author"] to apply
                author-based adjustments.

        Returns:
            int: Priority value where higher numbers indicate higher precedence when resolving
                conflicts.
        """
        base_priority = self.priority_rules.get("regular_suggestions", 50)

        # Use if/elif chain to prevent priority overwriting
        if change.metadata.get("option_label"):
            # User selections have highest priority
            base_priority = self.priority_rules.get("user_selections", 100)
        elif self._is_security_related(change):
            # Security fixes have second highest priority
            base_priority = self.priority_rules.get("security_fixes", 90)
        elif self._is_syntax_error_fix(change):
            # Syntax error fixes have third highest priority
            base_priority = self.priority_rules.get("syntax_errors", 80)
        elif self._is_formatting_change(change):
            # Formatting changes have lowest priority
            base_priority = self.priority_rules.get("formatting", 10)

        # Apply author-based adjustments AFTER priority determination
        author_value = change.metadata.get("author", "")
        author = author_value.lower() if isinstance(author_value, str) else ""
        if "coderabbit" in author:
            base_priority += 10  # Slight boost for CodeRabbit
        elif "bot" in author:
            base_priority += 5  # Small boost for other bots

        return int(base_priority)

    def _is_security_related(self, change: Change) -> bool:
        """Determine whether a Change's content indicates a security-related modification.

        Args:
            change (Change): Change object whose content will be inspected for security-related
                keywords.

        Returns:
            bool: True if the change's content contains any security-related keywords, False
                otherwise.
        """
        content = change.content.lower()
        security_keywords = [
            "security",
            "vulnerability",
            "auth",
            "token",
            "key",
            "password",
            "secret",
            "credential",
            "permission",
            "access",
            "login",
        ]
        return any(keyword in content for keyword in security_keywords)

    def _is_syntax_error_fix(self, change: Change) -> bool:
        """Determine whether a change addresses a syntax-related error.

        Args:
            change (Change): The change to evaluate.

        Returns:
            bool: True if the change's content contains syntax-related keywords, False otherwise.
        """
        content = change.content.lower()
        syntax_keywords = [
            "error",
            "fix",
            "bug",
            "issue",
            "syntax",
            "parse",
            "invalid",
            "missing",
            "undefined",
            "not defined",
            "import",
            "require",
        ]
        return any(keyword in content for keyword in syntax_keywords)

    def _is_formatting_change(self, change: Change) -> bool:
        """Determine whether a change is a formatting-related edit.

        Scans the change's content for common formatting tool names and other formatting-related
            keywords.

        Args:
            change (Change): The change to evaluate.

        Returns:
            bool: True if the change appears to be formatting-related, False otherwise.
        """
        content = change.content.lower()
        formatting_keywords = [
            "format",
            "style",
            "indent",
            "spacing",
            "whitespace",
            "line",
            "prettier",
            "eslint",
            "black",
            "autopep8",
        ]
        return any(keyword in content for keyword in formatting_keywords)

    def get_strategy_name(self) -> str:
        """Get the strategy's name.

        Returns:
            The strategy identifier string (e.g., "priority").
        """
        return "priority"

    def get_strategy_description(self) -> str:
        """Describe the priority-based conflict resolution strategy.

        Returns:
            str: Human-readable description of the strategy.
        """
        return (
            "Resolves conflicts by selecting the highest priority change based on "
            "content analysis and user preferences."
        )

    def get_priority_rules(self) -> dict[str, int]:
        """Return a copy of the current priority rules mapping.

        Returns:
            dict[str, int]: A copy of the priority rules where keys are rule names and values
                are their integer priorities.
        """
        return dict(self.priority_rules)

    def update_priority_rules(self, new_rules: dict[str, int]) -> None:
        """Update the strategy's priority rules with the provided mapping.

        Args:
            new_rules (dict[str, int]): Mapping of priority rule names to integer priority
                values. Keys present in this mapping override the existing rules; other rules
                remain unchanged. The method also updates the strategy's internal configuration
                to reflect the new rules.
        """
        self.priority_rules.update(new_rules)
        self.config["priority_rules"] = self.priority_rules
