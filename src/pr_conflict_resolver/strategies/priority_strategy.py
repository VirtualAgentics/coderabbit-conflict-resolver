"""
Priority-based resolution strategy.

This module provides the PriorityStrategy class that resolves conflicts
based on priority levels and user preferences.
"""

from typing import Any, Dict, List, Optional

from ..core.resolver import Change, Conflict, Resolution


class PriorityStrategy:
    """Priority-based conflict resolution strategy."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the priority strategy."""
        self.config = config or {}
        self.priority_rules = self.config.get("priority_rules", {
            "user_selections": 100,
            "security_fixes": 90,
            "syntax_errors": 80,
            "regular_suggestions": 50,
            "formatting": 10
        })
    
    def resolve(self, conflict: Conflict) -> Resolution:
        """Resolve a conflict using priority-based strategy."""
        if not conflict.changes:
            return Resolution(
                strategy="skip",
                applied_changes=[],
                skipped_changes=[],
                success=False,
                message="No changes to resolve"
            )
        
        # Calculate priorities for all changes
        prioritized_changes = []
        for change in conflict.changes:
            priority = self._calculate_priority(change)
            prioritized_changes.append((priority, change))
        
        # Sort by priority (highest first)
        prioritized_changes.sort(key=lambda x: x[0], reverse=True)
        
        # Select highest priority change
        highest_priority = prioritized_changes[0][0]
        selected_changes = [change for priority, change in prioritized_changes if priority == highest_priority]
        
        # If multiple changes have same priority, use first one
        applied_change = selected_changes[0]
        skipped_changes = [change for priority, change in prioritized_changes if change != applied_change]
        
        return Resolution(
            strategy="priority",
            applied_changes=[applied_change],
            skipped_changes=skipped_changes,
            success=True,
            message=f"Applied highest priority change (priority: {highest_priority})"
        )
    
    def _calculate_priority(self, change: Change) -> int:
        """Calculate priority for a change."""
        base_priority = self.priority_rules.get("regular_suggestions", 50)
        
        # Check for user selections
        if change.metadata.get("option_label"):
            base_priority = self.priority_rules.get("user_selections", 100)
        
        # Check for security-related changes
        if self._is_security_related(change):
            base_priority = self.priority_rules.get("security_fixes", 90)
        
        # Check for syntax error fixes
        if self._is_syntax_error_fix(change):
            base_priority = self.priority_rules.get("syntax_errors", 80)
        
        # Check for formatting changes
        if self._is_formatting_change(change):
            base_priority = self.priority_rules.get("formatting", 10)
        
        # Adjust based on author
        author = change.metadata.get("author", "").lower()
        if "coderabbit" in author:
            base_priority += 10  # Slight boost for CodeRabbit
        elif "bot" in author:
            base_priority += 5   # Small boost for other bots
        
        return base_priority
    
    def _is_security_related(self, change: Change) -> bool:
        """Check if change is security-related."""
        content = change.content.lower()
        security_keywords = [
            "security", "vulnerability", "auth", "token", "key", "password",
            "secret", "credential", "permission", "access", "login"
        ]
        return any(keyword in content for keyword in security_keywords)
    
    def _is_syntax_error_fix(self, change: Change) -> bool:
        """Check if change fixes syntax errors."""
        content = change.content.lower()
        syntax_keywords = [
            "error", "fix", "bug", "issue", "syntax", "parse", "invalid",
            "missing", "undefined", "not defined", "import", "require"
        ]
        return any(keyword in content for keyword in syntax_keywords)
    
    def _is_formatting_change(self, change: Change) -> bool:
        """Check if change is primarily formatting."""
        content = change.content.lower()
        formatting_keywords = [
            "format", "style", "indent", "spacing", "whitespace", "line",
            "prettier", "eslint", "black", "autopep8"
        ]
        return any(keyword in content for keyword in formatting_keywords)
    
    def get_strategy_name(self) -> str:
        """Get the name of this strategy."""
        return "priority"
    
    def get_strategy_description(self) -> str:
        """Get a description of this strategy."""
        return "Resolves conflicts by selecting the highest priority change based on content analysis and user preferences."
    
    def get_priority_rules(self) -> Dict[str, int]:
        """Get the current priority rules."""
        return self.priority_rules.copy()
    
    def update_priority_rules(self, new_rules: Dict[str, int]) -> None:
        """Update the priority rules."""
        self.priority_rules.update(new_rules)
        self.config["priority_rules"] = self.priority_rules
