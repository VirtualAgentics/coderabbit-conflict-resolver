#!/bin/bash
# verify-workflow-shas.sh
# Script to verify and optionally fix GitHub Actions SHAs in workflow files

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
WORKFLOW_DIR=".github/workflows"
FIX_MODE=false
VERBOSE=false

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -f, --fix        Automatically fix malformed SHAs"
    echo "  -v, --verbose    Enable verbose output"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Check all SHAs"
    echo "  $0 -f                 # Check and fix all SHAs"
    echo "  $0 -v                 # Check with verbose output"
}

# Function to get correct SHA for an action
get_correct_sha() {
    local repo=$1
    local version=$2

    if [ "$VERBOSE" = true ]; then
        print_status "$BLUE" "Getting SHA for $repo@$version..."
    fi

    # Try to get SHA from GitHub API
    local sha
    sha=$(gh api "repos/$repo/git/refs/tags/$version" 2>/dev/null | jq -r '.object.sha' 2>/dev/null || echo "")

    if [ "$sha" = "null" ] || [ -z "$sha" ]; then
        print_status "$RED" "❌ Could not find version $version for $repo"
        return 1
    fi

    echo "$sha"
}

# Function to verify SHA format
verify_sha_format() {
    local sha=$1
    local length=$(echo "$sha" | wc -c)

    # Check length (should be 41: 40 chars + newline)
    if [ "$length" -ne 41 ]; then
        return 1
    fi

    # Check format (should be 40 hex characters)
    if ! echo "$sha" | grep -qE '^[a-f0-9]{40}$'; then
        return 1
    fi

    return 0
}

# Function to check if SHA exists
verify_sha_exists() {
    local repo=$1
    local sha=$2

    if [ "$VERBOSE" = true ]; then
        print_status "$BLUE" "Verifying SHA $sha exists in $repo..."
    fi

    # Check if commit exists
    if gh api "repos/$repo/commits/$sha" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to extract action info from line
extract_action_info() {
    local line=$1
    local file=$2
    local line_num=$3

    # Extract repository and SHA
    local repo_sha
    repo_sha=$(echo "$line" | grep -o 'uses: [^@]*@[a-f0-9]*' | sed 's/uses: //' | sed 's/@/ /')

    if [ -z "$repo_sha" ]; then
        return 1
    fi

    local repo=$(echo "$repo_sha" | cut -d' ' -f1)
    local sha=$(echo "$repo_sha" | cut -d' ' -f2)

    # Extract version from comment if present
    local version
    version=$(echo "$line" | grep -o '# v[0-9.]*' | sed 's/# v//' || echo "")

    echo "$repo|$sha|$version"
}

# Function to fix malformed SHA
fix_sha() {
    local file=$1
    local line_num=$2
    local old_line=$3
    local repo=$4
    local version=$5

    if [ -z "$version" ]; then
        print_status "$YELLOW" "⚠️  No version found for $repo, skipping fix"
        return 1
    fi

    print_status "$BLUE" "Getting correct SHA for $repo@$version..."
    local correct_sha
    correct_sha=$(get_correct_sha "$repo" "$version")

    if [ $? -ne 0 ]; then
        return 1
    fi

    # Create new line with correct SHA
    local new_line
    new_line=$(echo "$old_line" | sed "s/@[a-f0-9]*/@$correct_sha/")

    # Replace in file
    sed -i "${line_num}s/.*/$(echo "$new_line" | sed 's/[[\.*^$()+?{|]/\\&/g')/" "$file"

    print_status "$GREEN" "✅ Fixed SHA for $repo@$version: $correct_sha"
    return 0
}

# Function to process a single workflow file
process_workflow_file() {
    local file=$1
    local issues_found=0
    local fixes_applied=0

    print_status "$BLUE" "=== Processing $file ==="

    # Find all action usage lines
    while IFS= read -r line; do
        local line_num=$(echo "$line" | cut -d: -f1)
        local content=$(echo "$line" | cut -d: -f2-)

        # Extract action info
        local action_info
        action_info=$(extract_action_info "$content" "$file" "$line_num")

        if [ $? -ne 0 ]; then
            continue
        fi

        local repo=$(echo "$action_info" | cut -d'|' -f1)
        local sha=$(echo "$action_info" | cut -d'|' -f2)
        local version=$(echo "$action_info" | cut -d'|' -f3)

        # Verify SHA format
        if ! verify_sha_format "$sha"; then
            print_status "$RED" "❌ MALFORMED: Line $line_num - $content"
            print_status "$RED" "   SHA length: $(echo "$sha" | wc -c) (should be 40)"
            issues_found=$((issues_found + 1))

            if [ "$FIX_MODE" = true ]; then
                if fix_sha "$file" "$line_num" "$content" "$repo" "$version"; then
                    fixes_applied=$((fixes_applied + 1))
                fi
            fi
            continue
        fi

        # Verify SHA exists
        if ! verify_sha_exists "$repo" "$sha"; then
            print_status "$RED" "❌ INVALID: Line $line_num - $content"
            print_status "$RED" "   SHA does not exist in $repo"
            issues_found=$((issues_found + 1))

            if [ "$FIX_MODE" = true ]; then
                if fix_sha "$file" "$line_num" "$content" "$repo" "$version"; then
                    fixes_applied=$((fixes_applied + 1))
                fi
            fi
            continue
        fi

        print_status "$GREEN" "✅ OK: Line $line_num - $content"

    done < <(grep -n "uses: .*@[a-f0-9]" "$file" 2>/dev/null || true)

    echo
    print_status "$BLUE" "Summary for $file:"
    print_status "$BLUE" "  Issues found: $issues_found"
    if [ "$FIX_MODE" = true ]; then
        print_status "$BLUE" "  Fixes applied: $fixes_applied"
    fi
    echo

    return $issues_found
}

# Main function
main() {
    local total_issues=0
    local total_files=0

    print_status "$BLUE" "GitHub Actions SHA Verification Tool"
    print_status "$BLUE" "====================================="
    echo

    # Check if GitHub CLI is available
    if ! command -v gh &> /dev/null; then
        print_status "$RED" "❌ GitHub CLI (gh) is not installed. Please install it first:"
        print_status "$YELLOW" "   https://cli.github.com/"
        exit 1
    fi

    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        print_status "$RED" "❌ jq is not installed. Please install it first:"
        print_status "$YELLOW" "   sudo apt install jq"
        exit 1
    fi

    # Check if we're authenticated
    if ! gh auth status &> /dev/null; then
        print_status "$RED" "❌ Not authenticated with GitHub. Please run:"
        print_status "$YELLOW" "   gh auth login"
        exit 1
    fi

    # Process all workflow files
    for file in "$WORKFLOW_DIR"/*.yml "$WORKFLOW_DIR"/*.yaml; do
        if [ -f "$file" ]; then
            total_files=$((total_files + 1))
            local file_issues
            process_workflow_file "$file"
            file_issues=$?
            total_issues=$((total_issues + file_issues))
        fi
    done

    # Final summary
    print_status "$BLUE" "=== FINAL SUMMARY ==="
    print_status "$BLUE" "Files processed: $total_files"
    print_status "$BLUE" "Total issues found: $total_issues"

    if [ "$FIX_MODE" = true ]; then
        if [ "$total_issues" -eq 0 ]; then
            print_status "$GREEN" "✅ All SHAs are valid!"
        else
            print_status "$YELLOW" "⚠️  Some issues were fixed. Please review the changes."
        fi
    else
        if [ "$total_issues" -eq 0 ]; then
            print_status "$GREEN" "✅ All SHAs are valid!"
        else
            print_status "$YELLOW" "⚠️  Issues found. Run with -f to fix them automatically."
        fi
    fi

    exit $total_issues
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--fix)
            FIX_MODE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_status "$RED" "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Run main function
main
