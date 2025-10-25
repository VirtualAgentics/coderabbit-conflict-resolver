#!/bin/bash
# Setup git override to block --no-verify

echo "🔒 Setting up git override to block --no-verify..."

# Create a git function that overrides the git command
cat > ~/.bashrc_git_override << 'EOF'
# Git override to block --no-verify
git() {
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
            return 1
        fi
    done

    # If no --no-verify found, call the real git command
    command git "$@"
}
EOF

# Add the override to bashrc if not already present
if ! grep -q "bashrc_git_override" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# Git override to block --no-verify" >> ~/.bashrc
    echo "source ~/.bashrc_git_override" >> ~/.bashrc
fi

echo "✅ Git override installed!"
echo ""
echo "To activate the override, run:"
echo "  source ~/.bashrc"
echo ""
echo "Or restart your terminal."
echo ""
echo "The override will block any git command with --no-verify."
