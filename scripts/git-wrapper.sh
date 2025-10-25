#!/bin/bash
# Git wrapper that blocks --no-verify option

# Check if --no-verify is in the arguments
for arg in "$@"; do
    if [[ "$arg" == "--no-verify" ]]; then
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
        echo "All quality checks must pass before committing."
        echo "This ensures code quality and prevents technical debt."
        exit 1
    fi
done

# If no --no-verify found, call the real git command
exec /usr/bin/git "$@"
