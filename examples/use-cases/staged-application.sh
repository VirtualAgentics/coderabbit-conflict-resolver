#!/bin/bash
# Staged application - apply changes in stages for maximum safety
# Usage: ./staged-application.sh PR_NUMBER OWNER REPO

set -euo pipefail

if [ $# -ne 3 ]; then
    echo "Usage: $0 PR_NUMBER OWNER REPO"
    echo "Example: $0 123 myorg myrepo"
    exit 1
fi

PR_NUMBER=$1
OWNER=$2
REPO=$3

echo "Staged Application for PR #$PR_NUMBER"
echo "======================================"
echo ""

# Stage 1: Analyze conflicts
echo "Stage 1: Analyzing conflicts..."
pr-resolve analyze --pr "$PR_NUMBER" --owner "$OWNER" --repo "$REPO"
echo ""

# Stage 2: Apply non-conflicting changes (safe, fast, high parallelism)
echo "Stage 2: Applying non-conflicting changes..."
echo "  - High parallelism (16 workers)"
echo "  - Validation disabled for speed"
echo "  - Rollback enabled for safety"
pr-resolve apply --pr "$PR_NUMBER" --owner "$OWNER" --repo "$REPO" \
    --mode non-conflicts-only \
    --parallel --max-workers 16 \
    --no-validation \
    --rollback
echo ""

# Stage 3: Apply conflicting changes (careful, moderate parallelism)
echo "Stage 3: Applying conflicting changes..."
echo "  - Moderate parallelism (8 workers)"
echo "  - Validation enabled"
echo "  - Rollback enabled"
pr-resolve apply --pr "$PR_NUMBER" --owner "$OWNER" --repo "$REPO" \
    --mode conflicts-only \
    --parallel --max-workers 8 \
    --validation \
    --rollback
echo ""

echo "======================================"
echo "Staged application complete!"
echo ""
echo "Benefits of staged application:"
echo "  - Non-conflicts applied quickly with high parallelism"
echo "  - Conflicts handled carefully with validation"
echo "  - If stage 2 fails, no changes applied"
echo "  - If stage 3 fails, stage 2 changes remain"
