#!/bin/bash
# Pre-push hook to block --no-verify option
# This hook prevents pushes that bypass quality checks

# Check if --no-verify was used in any recent commits
if git log --oneline -10 | grep -i "no-verify\|bypass" > /dev/null; then
    echo "❌ ERROR: --no-verify option is FORBIDDEN!"
    echo ""
    echo "Quality checks are MANDATORY and cannot be bypassed."
    echo "Please fix the issues instead of bypassing them:"
    echo ""
    echo "  • Fix linting errors: ruff check --fix"
    echo "  • Fix formatting: black src/ tests/"
    echo "  • Fix type errors: mypy src/ --strict"
    echo "  • Fix security issues: bandit -r src/"
    echo ""
    echo "All quality checks must pass before pushing."
    echo "This ensures code quality and prevents technical debt."
    exit 1
fi

# Run the pre-commit hook to ensure all quality checks pass
if ! pre-commit run --all-files; then
    echo "❌ ERROR: Quality checks failed!"
    echo ""
    echo "Please fix all quality issues before pushing."
    echo "Run 'pre-commit run --all-files' to see detailed errors."
    exit 1
fi

echo "✅ All quality checks passed. Push allowed."
exit 0
