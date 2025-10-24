#!/bin/bash
# get-action-sha.sh
# Script to get the correct SHA for any GitHub Action

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to print usage
usage() {
    echo "Usage: $0 <action-repo> <version>"
    echo ""
    echo "Arguments:"
    echo "  action-repo    GitHub repository in format owner/repo"
    echo "  version        Version tag (e.g., v5.0.0, main, latest)"
    echo ""
    echo "Examples:"
    echo "  $0 actions/checkout v5.0.0"
    echo "  $0 actions/setup-python v6.0.0"
    echo "  $0 github/codeql-action v4.31.0"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
}

# Function to get SHA for a specific tag
get_sha_for_tag() {
    local repo=$1
    local version=$2

    print_status "$BLUE" "Getting SHA for $repo@$version..."

    # Try to get SHA from GitHub API
    local sha
    sha=$(gh api "repos/$repo/git/refs/tags/$version" 2>/dev/null | jq -r '.object.sha' 2>/dev/null || echo "")

    if [ "$sha" = "null" ] || [ -z "$sha" ]; then
        print_status "$RED" "❌ Could not find version $version for $repo"
        print_status "$YELLOW" "Available versions:"
        gh api "repos/$repo/tags" | jq -r '.[].name' | head -10
        return 1
    fi

    echo "$sha"
}

# Function to get SHA for a specific branch
get_sha_for_branch() {
    local repo=$1
    local branch=$2

    print_status "$BLUE" "Getting SHA for $repo@$branch..."

    # Try to get SHA from GitHub API
    local sha
    sha=$(gh api "repos/$repo/git/refs/heads/$branch" 2>/dev/null | jq -r '.object.sha' 2>/dev/null || echo "")

    if [ "$sha" = "null" ] || [ -z "$sha" ]; then
        print_status "$RED" "❌ Could not find branch $branch for $repo"
        return 1
    fi

    echo "$sha"
}

# Function to get latest release SHA
get_latest_release_sha() {
    local repo=$1

    print_status "$BLUE" "Getting SHA for latest release of $repo..."

    # Try to get latest release
    local sha
    sha=$(gh api "repos/$repo/releases/latest" 2>/dev/null | jq -r '.target_commitish' 2>/dev/null || echo "")

    if [ "$sha" = "null" ] || [ -z "$sha" ]; then
        print_status "$RED" "❌ Could not find latest release for $repo"
        return 1
    fi

    echo "$sha"
}

# Function to validate SHA
validate_sha() {
    local sha=$1
    local length=$(echo "$sha" | wc -c)

    # Check length (should be 41: 40 chars + newline)
    if [ "$length" -ne 41 ]; then
        print_status "$RED" "❌ Invalid SHA length: $((length-1)) (should be 40)"
        return 1
    fi

    # Check format (should be 40 hex characters)
    if ! echo "$sha" | grep -qE '^[a-f0-9]{40}$'; then
        print_status "$RED" "❌ Invalid SHA format (should be 40 hex characters)"
        return 1
    fi

    return 0
}

# Function to verify SHA exists
verify_sha_exists() {
    local repo=$1
    local sha=$2

    print_status "$BLUE" "Verifying SHA exists in $repo..."

    # Check if commit exists
    if gh api "repos/$repo/commits/$sha" >/dev/null 2>&1; then
        print_status "$GREEN" "✅ SHA verified and exists"
        return 0
    else
        print_status "$RED" "❌ SHA does not exist in $repo"
        return 1
    fi
}

# Main function
main() {
    local repo="$1"
    local version="$2"
    local sha=""

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

    # Determine how to get the SHA
    case "$version" in
        "latest")
            sha=$(get_latest_release_sha "$repo")
            ;;
        "main"|"master"|"develop")
            sha=$(get_sha_for_branch "$repo" "$version")
            ;;
        *)
            sha=$(get_sha_for_tag "$repo" "$version")
            ;;
    esac

    if [ $? -ne 0 ] || [ -z "$sha" ]; then
        exit 1
    fi

    # Validate SHA format
    if ! validate_sha "$sha"; then
        exit 1
    fi

    # Verify SHA exists
    if ! verify_sha_exists "$repo" "$sha"; then
        exit 1
    fi

    # Output results
    echo
    print_status "$GREEN" "✅ Success! Here's the correct SHA:"
    echo
    print_status "$BLUE" "Repository: $repo"
    print_status "$BLUE" "Version: $version"
    print_status "$BLUE" "SHA: $sha"
    echo
    print_status "$GREEN" "Usage in workflow:"
    print_status "$YELLOW" "  uses: $repo@$sha # $version"
    echo
}

# Parse command line arguments
if [[ $# -eq 0 ]] || [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -ne 2 ]]; then
    print_status "$RED" "❌ Error: Exactly 2 arguments required"
    echo
    usage
    exit 1
fi

# Run main function
main "$1" "$2"
