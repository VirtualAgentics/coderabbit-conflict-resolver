#!/usr/bin/env bash
# Ollama Setup Script for pr-resolve
#
# This script automates the installation and setup of Ollama for local LLM inference.
# It handles OS detection, installation, service startup, and health verification.
#
# Usage:
#   ./scripts/setup_ollama.sh [--skip-install] [--skip-start]
#
# Options:
#   --skip-install  Skip Ollama installation (useful if already installed)
#   --skip-start    Skip starting the Ollama service
#
# Exit codes:
#   0 - Success
#   1 - Installation failed
#   2 - Service start failed
#   3 - Health check failed
#   4 - Unsupported OS

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
OLLAMA_API_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
HEALTH_CHECK_RETRIES=10
HEALTH_CHECK_DELAY=2

# Flags
SKIP_INSTALL=false
SKIP_START=false

# Parse command-line arguments
for arg in "$@"; do
    case $arg in
        --skip-install)
            SKIP_INSTALL=true
            shift
            ;;
        --skip-start)
            SKIP_START=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--skip-install] [--skip-start]"
            echo ""
            echo "Options:"
            echo "  --skip-install  Skip Ollama installation"
            echo "  --skip-start    Skip starting the Ollama service"
            echo "  -h, --help      Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $arg${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Print colored message
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Detect operating system
detect_os() {
    local os_type=""

    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        os_type="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        os_type="macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
        os_type="wsl"
    else
        os_type="unknown"
    fi

    echo "$os_type"
}

# Check if Ollama is already installed
check_existing() {
    if command -v ollama &> /dev/null; then
        local version
        version=$(ollama --version 2>&1 | head -n1 || echo "unknown")
        return 0  # Installed
    else
        return 1  # Not installed
    fi
}

# Install Ollama using official installer
install_ollama() {
    local os_type="$1"

    print_info "Installing Ollama for $os_type..."

    case "$os_type" in
        linux|wsl)
            # Official installation script for Linux/WSL
            # Download to temporary file for security (scorecard requirement)
            local install_script
            install_script=$(mktemp)
            if ! curl -fsSL https://ollama.ai/install.sh -o "$install_script"; then
                print_error "Failed to download Ollama installer"
                rm -f "$install_script"
                return 1
            fi
            # Execute from file
            if ! sh "$install_script"; then
                print_error "Failed to install Ollama"
                rm -f "$install_script"
                return 1
            fi
            rm -f "$install_script"
            print_success "Ollama installed successfully"
            ;;
        macos)
            # Official installation script for macOS
            # Download to temporary file for security (scorecard requirement)
            local install_script
            install_script=$(mktemp)
            if ! curl -fsSL https://ollama.ai/install.sh -o "$install_script"; then
                print_error "Failed to download Ollama installer"
                rm -f "$install_script"
                return 1
            fi
            # Execute from file
            if ! sh "$install_script"; then
                print_error "Failed to install Ollama"
                rm -f "$install_script"
                return 1
            fi
            rm -f "$install_script"
            print_success "Ollama installed successfully"
            ;;
        *)
            print_error "Unsupported operating system: $os_type"
            print_info "Please install Ollama manually from: https://ollama.ai/download"
            return 1
            ;;
    esac

    return 0
}

# Check if Ollama service is running
is_service_running() {
    if curl -f -s -o /dev/null "$OLLAMA_API_URL/api/tags" 2>/dev/null; then
        return 0  # Running
    else
        return 1  # Not running
    fi
}

# Start Ollama service
start_service() {
    local os_type="$1"

    # Check if already running
    if is_service_running; then
        print_success "Ollama service is already running"
        return 0
    fi

    print_info "Starting Ollama service..."

    case "$os_type" in
        linux|wsl)
            # Start as background service
            if command -v systemctl &> /dev/null && systemctl is-system-running &> /dev/null; then
                # Use systemd if available
                if ! sudo systemctl start ollama 2>/dev/null; then
                    # Fallback to manual start
                    print_warning "Could not start via systemd, starting manually..."
                    nohup ollama serve > /tmp/ollama.log 2>&1 &
                fi
            else
                # Manual start without systemd
                nohup ollama serve > /tmp/ollama.log 2>&1 &
            fi
            ;;
        macos)
            # Start as background service
            if ! open -a Ollama 2>/dev/null; then
                # Fallback to manual start
                nohup ollama serve > /tmp/ollama.log 2>&1 &
            fi
            ;;
        *)
            print_error "Cannot start service on unsupported OS: $os_type"
            return 1
            ;;
    esac

    # Wait a moment for service to initialize
    sleep 2
    print_success "Ollama service started"
    return 0
}

# Verify Ollama installation and availability
verify_installation() {
    print_info "Verifying Ollama installation..."

    # Check command availability
    if ! command -v ollama &> /dev/null; then
        print_error "Ollama command not found in PATH"
        return 1
    fi

    local version
    version=$(ollama --version 2>&1 | head -n1 || echo "unknown")
    print_success "Ollama command available: $version"

    # Health check with retries
    print_info "Checking Ollama API health (retries: $HEALTH_CHECK_RETRIES)..."

    local attempt=1
    while [ $attempt -le $HEALTH_CHECK_RETRIES ]; do
        if curl -f -s -o /dev/null "$OLLAMA_API_URL/api/tags" 2>/dev/null; then
            print_success "Ollama API is healthy at $OLLAMA_API_URL"
            return 0
        fi

        if [ $attempt -lt $HEALTH_CHECK_RETRIES ]; then
            print_warning "Attempt $attempt/$HEALTH_CHECK_RETRIES failed, retrying in ${HEALTH_CHECK_DELAY}s..."
            sleep $HEALTH_CHECK_DELAY
        fi

        ((attempt++))
    done

    print_error "Ollama API health check failed after $HEALTH_CHECK_RETRIES attempts"
    print_info "Check logs at: /tmp/ollama.log"
    print_info "Ensure Ollama is running: ollama serve"
    return 1
}

# Main setup function
main() {
    echo ""
    echo "================================="
    echo "  Ollama Setup for pr-resolve"
    echo "================================="
    echo ""

    # Detect OS
    local os_type
    os_type=$(detect_os)
    print_info "Detected OS: $os_type"

    if [[ "$os_type" == "unknown" ]]; then
        print_error "Unsupported operating system"
        print_info "Please install Ollama manually from: https://ollama.ai/download"
        exit 4
    fi

    # Check existing installation
    if check_existing; then
        local version
        version=$(ollama --version 2>&1 | head -n1 || echo "unknown")
        print_success "Ollama is already installed: $version"

        if [[ "$SKIP_INSTALL" == false ]]; then
            print_warning "Use --skip-install to skip reinstallation"
        fi
    else
        print_info "Ollama is not installed"

        if [[ "$SKIP_INSTALL" == true ]]; then
            print_error "Ollama not found and --skip-install specified"
            exit 1
        fi

        # Install Ollama
        if ! install_ollama "$os_type"; then
            exit 1
        fi
    fi

    # Start service
    if [[ "$SKIP_START" == false ]]; then
        if ! start_service "$os_type"; then
            exit 2
        fi
    else
        print_info "Skipping service start (--skip-start specified)"
    fi

    # Verify installation
    if ! verify_installation; then
        exit 3
    fi

    echo ""
    print_success "Ollama setup completed successfully!"
    echo ""
    print_info "Next steps:"
    echo "  1. Download a model: ./scripts/download_ollama_models.sh"
    echo "  2. Or manually: ollama pull qwen2.5-coder:7b"
    echo "  3. Use with pr-resolve: pr-resolve apply 123 --llm-preset ollama-local"
    echo ""

    exit 0
}

# Run main function
main
