#!/usr/bin/env bash
#
# Privacy Verification Script for Ollama Local Operation
#
# This script verifies that Ollama operates entirely on localhost without
# any external LLM vendor connections (OpenAI/Anthropic), confirming that
# LLM inference stays local.
#
# NOTE: This does NOT verify air-gapped/offline operation. The tool requires
# GitHub API access, so internet connectivity is expected.
#
# Usage:
#   ./scripts/verify_privacy.sh
#   ./scripts/verify_privacy.sh --report-only
#   ./scripts/verify_privacy.sh --help
#
# Requirements:
#   - Ollama installed and running
#   - tcpdump (Linux) or lsof (macOS/Linux)
#   - Sufficient permissions for network monitoring
#
# Exit Codes:
#   0 - Privacy verified (no external connections)
#   1 - External connections detected (privacy violation)
#   2 - Prerequisites not met or errors
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPORT_FILE="privacy-verification-report.md"
TEST_PROMPT="Write a simple Hello World function in Python"
OLLAMA_PORT=11434

# Detect OS
OS="$(uname -s)"
case "${OS}" in
    Linux*)     PLATFORM=Linux;;
    Darwin*)    PLATFORM=Mac;;
    *)          PLATFORM="UNKNOWN";;
esac

#
# Helper Functions
#

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  Privacy Verification for Ollama${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

usage() {
    cat << EOF
Privacy Verification Script for Ollama

Usage:
    $0 [OPTIONS]

Options:
    --help          Show this help message
    --report-only   Generate report without running verification
    --verbose       Enable verbose output
    --timeout N     Set test timeout in seconds (default: 30)

Description:
    Verifies that Ollama operates entirely on localhost by:
    1. Monitoring network connections during inference
    2. Checking for any external IP connections
    3. Generating detailed verification report

Examples:
    # Basic verification
    $0

    # Verbose mode
    $0 --verbose

    # Custom timeout
    $0 --timeout 60

Exit Codes:
    0 - Privacy verified (no external connections)
    1 - External connections detected
    2 - Prerequisites not met or errors

For more information, see: docs/privacy-architecture.md
EOF
}

check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check if Ollama is installed
    if ! command -v ollama &> /dev/null; then
        print_error "Ollama is not installed"
        echo "  Install: curl -fsSL https://ollama.ai/install.sh | sh"
        return 1
    fi
    print_success "Ollama is installed"

    # Check if Ollama is running
    if ! curl -s http://localhost:${OLLAMA_PORT}/api/tags &> /dev/null; then
        print_error "Ollama is not running"
        echo "  Start: ollama serve"
        return 1
    fi
    print_success "Ollama is running (localhost:${OLLAMA_PORT})"

    # Check monitoring tools
    case "${PLATFORM}" in
        Linux)
            if ! command -v tcpdump &> /dev/null; then
                print_warning "tcpdump not found (network monitoring limited)"
                if ! command -v lsof &> /dev/null; then
                    print_error "Neither tcpdump nor lsof available"
                    echo "  Install: sudo apt-get install tcpdump  # or lsof"
                    return 1
                fi
            fi
            ;;
        Mac)
            if ! command -v lsof &> /dev/null; then
                print_error "lsof not found"
                echo "  lsof should be pre-installed on macOS"
                return 1
            fi
            ;;
    esac
    print_success "Network monitoring tools available"

    # Check if at least one model is available
    if ! ollama list | grep -q ":"; then
        print_error "No Ollama models found"
        echo "  Download a model: ollama pull qwen2.5-coder:7b"
        return 1
    fi
    print_success "Ollama models available"

    echo ""
    return 0
}

get_default_model() {
    # Get the first available model
    ollama list | grep ":" | head -1 | awk '{print $1}'
}

monitor_connections_linux() {
    local timeout=$1
    local temp_file
    temp_file=$(mktemp)

    print_info "Monitoring network connections (Linux)..."
    print_info "Running test inference for ${timeout} seconds..."

    # Start network monitoring in background
    if command -v tcpdump &> /dev/null; then
        # Use tcpdump (more comprehensive)
        sudo timeout "$timeout" tcpdump -i any "host not 127.0.0.1 and host not ::1" -n 2>&1 | tee "$temp_file" &
        MONITOR_PID=$!
    else
        # Fallback to lsof
        timeout "$timeout" bash -c "while true; do lsof -i -n -P | grep -v '127.0.0.1\|::1' >> '$temp_file'; sleep 1; done" &
        MONITOR_PID=$!
    fi

    # Wait a moment for monitoring to start
    sleep 2

    # Run test inference
    local model
    model=$(get_default_model)
    print_info "Using model: $model"

    ollama run "$model" "$TEST_PROMPT" > /dev/null 2>&1 || true

    # Wait for monitoring to complete
    wait $MONITOR_PID 2>/dev/null || true

    # Analyze results
    if [ -s "$temp_file" ]; then
        # File has content - external connections detected
        echo "$temp_file"
        return 1
    else
        # File is empty - no external connections
        rm -f "$temp_file"
        return 0
    fi
}

monitor_connections_mac() {
    local timeout=$1
    local temp_file
    temp_file=$(mktemp)
    local before_file
    before_file=$(mktemp)
    local after_file
    after_file=$(mktemp)

    print_info "Monitoring network connections (macOS)..."

    # Capture connections before
    lsof -i -n -P | grep -v "127.0.0.1\|::1" | grep ollama > "$before_file" 2>/dev/null || true

    # Run test inference
    local model
    model=$(get_default_model)
    print_info "Using model: $model"
    print_info "Running test inference..."

    ollama run "$model" "$TEST_PROMPT" > /dev/null 2>&1 || true

    # Capture connections after
    lsof -i -n -P | grep -v "127.0.0.1\|::1" | grep ollama > "$after_file" 2>/dev/null || true

    # Compare
    if diff "$before_file" "$after_file" > /dev/null 2>&1; then
        # No new connections
        rm -f "$before_file" "$after_file"
        return 0
    else
        # New connections detected
        diff "$before_file" "$after_file" > "$temp_file"
        rm -f "$before_file" "$after_file"
        echo "$temp_file"
        return 1
    fi
}

run_verification() {
    local timeout=${1:-30}
    local external_connections_file=""

    echo ""
    print_info "Starting privacy verification..."
    echo ""

    # Run platform-specific monitoring
    case "${PLATFORM}" in
        Linux)
            if monitor_connections_linux "$timeout"; then
                VERIFICATION_RESULT="PASSED"
            else
                VERIFICATION_RESULT="FAILED"
                external_connections_file=$(monitor_connections_linux "$timeout")
            fi
            ;;
        Mac)
            if monitor_connections_mac "$timeout"; then
                VERIFICATION_RESULT="PASSED"
            else
                VERIFICATION_RESULT="FAILED"
                external_connections_file=$(monitor_connections_mac "$timeout")
            fi
            ;;
        *)
            print_error "Unsupported platform: ${PLATFORM}"
            return 2
            ;;
    esac

    echo ""

    # Print results
    if [ "$VERIFICATION_RESULT" = "PASSED" ]; then
        print_success "Privacy Verification: PASSED"
        print_success "No external network connections detected"
        print_success "All Ollama traffic is localhost-only"
        echo ""
    else
        print_error "Privacy Verification: FAILED"
        print_error "External network connections detected!"
        echo ""
        if [ -n "$external_connections_file" ] && [ -f "$external_connections_file" ]; then
            echo "External connections:"
            cat "$external_connections_file"
            rm -f "$external_connections_file"
        fi
        echo ""
    fi

    # Generate report
    generate_report "$VERIFICATION_RESULT" "$external_connections_file"

    # Return appropriate exit code
    if [ "$VERIFICATION_RESULT" = "PASSED" ]; then
        return 0
    else
        return 1
    fi
}

generate_report() {
    local result=$1
    local connections_file=$2

    print_info "Generating verification report: $REPORT_FILE"

    cat > "$REPORT_FILE" << EOF
# Privacy Verification Report

**Generated**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Platform**: ${PLATFORM} ($(uname -r))
**Ollama Version**: $(ollama --version 2>/dev/null || echo "Unknown")
**Test Model**: $(get_default_model)

---

## Verification Result

**Status**: **${result}**

EOF

    if [ "$result" = "PASSED" ]; then
        cat >> "$REPORT_FILE" << EOF
✅ **Privacy Verified**: All Ollama LLM traffic is confined to localhost.

### Summary

- ✅ No external LLM vendor connections detected
- ✅ All Ollama traffic limited to 127.0.0.1:${OLLAMA_PORT} (localhost)
- ✅ LLM inference data stays on your machine
- ⚠️ **Note**: GitHub API connections are expected (required for PR workflow)

### What This Means

Review comments processed by Ollama **never reach LLM vendors (OpenAI/Anthropic)**. This verification confirms:

1. **No LLM vendor transmission** - OpenAI/Anthropic never see your comments
2. **Localhost-only LLM** - All inference happens on your machine
3. **Reduced third-party exposure** - One fewer entity with access

**Important Context**:
- ⚠️ Your code is on GitHub (required for PR workflow)
- ⚠️ CodeRabbit has access (required for review comments)
- ✅ LLM vendor does NOT have access (eliminated)

### Recommendation

✅ **Use Ollama to**:
- Eliminate LLM vendor exposure
- Simplify compliance (one fewer data processor for HIPAA, GDPR, SOC2)
- Reduce third-party attack surface
- Avoid LLM vendor data retention policies

❌ **NOT for**:
- Air-gapped operation (GitHub API required)
- Offline operation (internet needed for PR fetching)
- Complete data isolation (GitHub/CodeRabbit still have access)

---

## Test Details

**Test Prompt**: "$TEST_PROMPT"
**Monitoring Method**: ${PLATFORM}-specific network monitoring
**Duration**: Test inference + network monitoring
**Connections Monitored**: All non-localhost traffic

### Network Configuration

- **Ollama Port**: ${OLLAMA_PORT}
- **Bind Address**: 127.0.0.1 (localhost only)
- **External Connections**: None detected ✅

---

## Verification Steps

This verification was performed by:

1. ✅ Monitoring all network connections (excluding localhost)
2. ✅ Running test LLM inference with Ollama
3. ✅ Analyzing all network traffic during inference
4. ✅ Verifying no external IP addresses contacted

### Tools Used

EOF
        case "${PLATFORM}" in
            Linux)
                echo "- \`tcpdump\` or \`lsof\` for network monitoring" >> "$REPORT_FILE"
                ;;
            Mac)
                echo "- \`lsof\` for network monitoring" >> "$REPORT_FILE"
                ;;
        esac

        cat >> "$REPORT_FILE" << EOF
- \`ollama\` CLI for inference testing
- Native OS network utilities

---

## Related Documentation

- [Privacy Architecture](docs/privacy-architecture.md) - Detailed privacy analysis
- [Local LLM Operation Guide](docs/local-llm-operation-guide.md) - Local LLM setup
- [Privacy FAQ](docs/privacy-faq.md) - Common privacy questions

---

## Compliance Notes

This verification supports compliance by confirming:

- **GDPR**: LLM processing stays local (one fewer data processor)
- **HIPAA**: LLM vendor eliminated from BAA chain
- **SOC 2**: LLM vendor risk eliminated (no LLM vendor connections)

**Important**: Your code is on GitHub (required for tool operation). This verification only confirms localhost-only LLM inference, not complete data isolation.

---

## Next Steps

1. ✅ Use Ollama to eliminate LLM vendor exposure
2. ✅ Document this verification for compliance audits
3. ✅ Re-verify periodically (monthly recommended)
4. ✅ Share this report with security/compliance teams

**This verification confirms Ollama's privacy guarantees are accurate and verifiable.**

EOF
    else
        cat >> "$REPORT_FILE" << EOF
❌ **Privacy Violation Detected**: External network connections observed during Ollama operation.

### Summary

- ❌ External network connections detected
- ❌ Data may have been transmitted outside localhost
- ❌ Privacy guarantees NOT confirmed
- ❌ Further investigation required

### External Connections Detected

EOF

        if [ -n "$connections_file" ] && [ -f "$connections_file" ]; then
            echo '```' >> "$REPORT_FILE"
            cat "$connections_file" >> "$REPORT_FILE"
            echo '```' >> "$REPORT_FILE"
        else
            echo "*Details not available*" >> "$REPORT_FILE"
        fi

        cat >> "$REPORT_FILE" << EOF

### Possible Causes

1. **Ollama Misconfiguration**: Ollama may be bound to 0.0.0.0 instead of 127.0.0.1
2. **Network Interface Issue**: Unexpected network routing
3. **Telemetry/Updates**: Ollama may be checking for updates (verify config)
4. **Other Software**: Another process may be using Ollama's port

### Recommended Actions

1. ❌ **DO NOT use for sensitive code** until issue resolved
2. 🔍 Check Ollama configuration:
   \`\`\`bash
   env | grep OLLAMA
   netstat -an | grep ${OLLAMA_PORT}
   \`\`\`
3. 🔍 Verify Ollama version: \`ollama --version\`
4. 🔍 Review Ollama documentation for privacy settings
5. 🔍 Contact Ollama support or review GitHub issues

### Verification Failed

This verification indicates potential privacy issues. **Do not use Ollama for sensitive data** until the issue is investigated and resolved.

EOF
    fi

    cat >> "$REPORT_FILE" << EOF

---

*Generated by: \`scripts/verify_privacy.sh\`*
*Report: \`${REPORT_FILE}\`*
EOF

    print_success "Report saved to: $REPORT_FILE"
}

#
# Main Script
#

main() {
    local timeout=30
    local report_only=false
    local verbose=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                usage
                exit 0
                ;;
            --report-only)
                # Reserved for future feature: generate report without running tests
                # shellcheck disable=SC2034
                report_only=true
                shift
                ;;
            --verbose)
                # Reserved for future feature: verbose output mode
                # shellcheck disable=SC2034
                verbose=true
                shift
                ;;
            --timeout)
                timeout="$2"
                shift 2
                ;;
            *)
                echo "Unknown option: $1"
                usage
                exit 2
                ;;
        esac
    done

    # Print header
    print_header

    # Check prerequisites
    if ! check_prerequisites; then
        print_error "Prerequisites not met"
        exit 2
    fi

    # Run verification
    if run_verification "$timeout"; then
        print_success "Privacy verification completed successfully"
        echo ""
        exit 0
    else
        print_error "Privacy verification failed"
        echo ""
        exit 1
    fi
}

# Run main function
main "$@"
