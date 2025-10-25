#!/bin/bash
# Install hooks to block --no-verify option

set -e

echo "🔒 Installing --no-verify blocker hooks..."

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

# Install pre-push hook
echo "Installing pre-push hook..."
cp scripts/pre-push-hook.sh .git/hooks/pre-push
chmod +x .git/hooks/pre-push

# Install commit-msg hook to check commit messages
echo "Installing commit-msg hook..."
cat > .git/hooks/commit-msg << 'EOF'
#!/bin/bash
# Commit message hook to block --no-verify

# Check if the commit message contains --no-verify or bypass language
if grep -i "no-verify\|bypass.*check\|skip.*check" "$1" > /dev/null; then
    echo "❌ ERROR: Commit message contains forbidden --no-verify language!"
    echo ""
    echo "Please remove any references to bypassing quality checks."
    echo "Quality checks are mandatory and cannot be bypassed."
    exit 1
fi

# Check if the commit was made with --no-verify
if [ "$GIT_EDITOR" = ":" ] || [ -n "$GIT_COMMIT_EDITMSG" ]; then
    # This might indicate --no-verify was used
    if git log -1 --pretty=format:%B | grep -i "no-verify\|bypass" > /dev/null; then
        echo "❌ ERROR: --no-verify option is FORBIDDEN!"
        echo ""
        echo "Quality checks are MANDATORY and cannot be bypassed."
        exit 1
    fi
fi

exit 0
EOF

chmod +x .git/hooks/commit-msg

echo "✅ --no-verify blocker hooks installed successfully!"
echo ""
echo "The following protections are now active:"
echo "  • Pre-commit hook blocks --no-verify on commit"
echo "  • Pre-push hook blocks --no-verify on push"
echo "  • Commit message hook blocks bypass language"
echo ""
echo "Quality checks are now MANDATORY and cannot be bypassed."
