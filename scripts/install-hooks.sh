#!/bin/bash
# Install git hooks for quality enforcement

HOOKS_DIR=".git/hooks"
HOOK_FILE="$HOOKS_DIR/pre-push"

# Create pre-push hook
cat > "$HOOK_FILE" << 'EOF'
#!/bin/bash
# Pre-push hook to enforce quality checks

# Activate virtual environment
source .venv/bin/activate || {
    echo "Error: Virtual environment not found"
    exit 1
}

# Initialize counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_TOTAL=5

# Function to run a check and track results
run_check() {
    local name="$1"
    local command="$2"

    echo "Running $name..."
    if eval "$command"; then
        echo "✅ $name passed"
        ((CHECKS_PASSED++))
    else
        echo "❌ $name failed"
        ((CHECKS_FAILED++))
    fi
}

# Run all checks
run_check "Black formatting" "black --check src/ tests/"
run_check "Ruff linting" "ruff check src/ tests/"
run_check "MyPy type checking" "mypy src/ tests/ --strict"
run_check "Bandit security" "bandit -r src/ --severity-level medium --confidence-level medium --quiet --exit-zero"
run_check "Test suite" "pytest tests/ --cov=src --cov-fail-under=80 --quiet"

# Display summary
echo ""
echo "===================="
echo "Quality Check Summary"
echo "===================="
echo "Passed: $CHECKS_PASSED/$CHECKS_TOTAL"
echo "Failed: $CHECKS_FAILED/$CHECKS_TOTAL"
echo ""

if [ $CHECKS_FAILED -gt 0 ]; then
    echo "❌ Pre-push checks failed!"
    echo ""
    echo "To fix issues:"
    echo "  • Format code: black src/ tests/"
    echo "  • Fix linting: ruff check src/ tests/ --fix"
    echo "  • Check types: mypy src/ --strict"
    echo "  • Run tests: pytest tests/"
    echo ""
    echo "Or use 'git push --no-verify' to skip checks (not recommended)"
    exit 1
fi

echo "✅ All pre-push checks passed!"
exit 0
EOF

# Make executable
chmod +x "$HOOK_FILE"

echo "✅ Pre-push hook installed successfully!"
echo ""
echo "The hook will run these checks before each push:"
echo "  • Black formatting"
echo "  • Ruff linting"
echo "  • MyPy type checking"
echo "  • Bandit security scanning"
echo "  • Test suite with coverage"
echo ""
echo "To bypass (not recommended): git push --no-verify"
