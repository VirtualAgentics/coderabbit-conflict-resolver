#!/bin/bash
# Benchmark parallel processing performance
# Usage: ./benchmark.sh PR_NUMBER OWNER REPO

set -euo pipefail

if [ $# -ne 3 ]; then
    echo "Usage: $0 PR_NUMBER OWNER REPO"
    echo "Example: $0 123 myorg myrepo"
    exit 1
fi

PR_NUMBER=$1
OWNER=$2
REPO=$3
RESULTS_FILE="benchmark-results-$(date +%Y%m%d-%H%M%S).csv"

echo "Benchmarking PR #$PR_NUMBER"
echo "Results will be saved to: $RESULTS_FILE"
echo "======================================"

# Create results file
echo "workers,duration_seconds" > "$RESULTS_FILE"

# Test different worker counts
for workers in 1 2 4 8 16; do
    echo -n "Testing with $workers workers... "

    # Measure execution time
    START=$(date +%s)
    pr-resolve apply --pr "$PR_NUMBER" --owner "$OWNER" --repo "$REPO" \
        --mode dry-run \
        --parallel \
        --max-workers "$workers" \
        --log-level WARNING \
        > /dev/null 2>&1 || true
    END=$(date +%s)

    DURATION=$((END - START))
    echo "${workers},${DURATION}" >> "$RESULTS_FILE"
    echo "${DURATION}s"
done

echo "======================================"
echo "Results saved to $RESULTS_FILE"
echo ""
echo "Summary:"
cat "$RESULTS_FILE"
echo ""
echo "Find the worker count with the lowest duration for optimal performance."
