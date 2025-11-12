#!/usr/bin/env bash
# Ollama Model Download Script for pr-resolve
#
# This script provides an interactive menu for downloading recommended Ollama models
# with disk space checking and progress display.
#
# Usage:
#   ./scripts/download_ollama_models.sh [model_name]
#
# Options:
#   model_name  Optional model name to download directly (e.g., qwen2.5-coder:7b)
#
# Exit codes:
#   0 - Success
#   1 - Ollama not available
#   2 - Insufficient disk space
#   3 - Model download failed

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
OLLAMA_API_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
MIN_FREE_SPACE_GB=10  # Minimum free disk space in GB

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

print_header() {
    echo -e "${BOLD}${CYAN}$1${NC}"
}

# Check if Ollama is available
check_ollama_available() {
    if ! command -v ollama &> /dev/null; then
        print_error "Ollama command not found"
        print_info "Please install Ollama first: ./scripts/setup_ollama.sh"
        return 1
    fi

    if ! curl -f -s -o /dev/null "$OLLAMA_API_URL/api/tags" 2>/dev/null; then
        print_error "Ollama service is not running"
        print_info "Start Ollama: ollama serve"
        return 1
    fi

    return 0
}

# Check available disk space
check_disk_space() {
    local required_gb="$1"
    local available_gb

    # Get available space in GB (works on Linux and macOS)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: use df with blocks
        available_gb=$(df -g . | awk 'NR==2 {print $4}')
    else
        # Linux: use df with human-readable output
        available_gb=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    fi

    if (( available_gb < required_gb )); then
        print_error "Insufficient disk space: ${available_gb}GB available, ${required_gb}GB required"
        return 1
    fi

    print_success "Sufficient disk space: ${available_gb}GB available"
    return 0
}

# Get list of already downloaded models
get_downloaded_models() {
    ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' || echo ""
}

# Check if a model is already downloaded
is_model_downloaded() {
    local model_name="$1"
    local downloaded_models
    downloaded_models=$(get_downloaded_models)

    if echo "$downloaded_models" | grep -q "^${model_name}$"; then
        return 0  # Already downloaded
    else
        return 1  # Not downloaded
    fi
}

# Download a model with progress display
download_model() {
    local model_name="$1"

    # Check if already downloaded
    if is_model_downloaded "$model_name"; then
        print_success "Model '$model_name' is already downloaded"
        return 0
    fi

    print_info "Downloading model: $model_name"
    print_warning "This may take several minutes depending on model size and network speed..."
    echo ""

    # Download with progress
    if ollama pull "$model_name"; then
        echo ""
        print_success "Successfully downloaded: $model_name"
        return 0
    else
        echo ""
        print_error "Failed to download: $model_name"
        return 1
    fi
}

# Display model recommendations
display_recommendations() {
    print_header "Recommended Models for Code Conflict Resolution"
    echo ""
    echo "┌─────────────────────────────────────────────────────────────────────────────┐"
    echo "│ Model                    │ Size   │ Speed  │ Quality │ Description          │"
    echo "├─────────────────────────────────────────────────────────────────────────────┤"
    echo "│ 1. qwen2.5-coder:7b      │ ~4GB   │ Fast   │ Good    │ Best balance (default)│"
    echo "│ 2. qwen2.5-coder:14b     │ ~8GB   │ Medium │ Better  │ Higher quality       │"
    echo "│ 3. qwen2.5-coder:32b     │ ~18GB  │ Slow   │ Best    │ Maximum quality      │"
    echo "│ 4. codellama:7b          │ ~4GB   │ Fast   │ Good    │ Alternative option   │"
    echo "│ 5. codellama:13b         │ ~7GB   │ Medium │ Better  │ Larger CodeLlama     │"
    echo "│ 6. deepseek-coder:6.7b   │ ~4GB   │ Fast   │ Good    │ Code specialist      │"
    echo "│ 7. mistral:7b            │ ~4GB   │ Fast   │ Good    │ General purpose      │"
    echo "│ 8. Custom model name     │ Varies │ Varies │ Varies  │ Enter manually       │"
    echo "└─────────────────────────────────────────────────────────────────────────────┘"
    echo ""

    # Show already downloaded models
    local downloaded_models
    downloaded_models=$(get_downloaded_models)

    if [[ -n "$downloaded_models" ]]; then
        print_info "Already downloaded models:"
        while IFS= read -r model; do
            echo "  ✓ $model"
        done <<< "$downloaded_models"
        echo ""
    fi
}

# Interactive menu for model selection
interactive_menu() {
    while true; do
        display_recommendations

        print_info "Recommended for pr-resolve: qwen2.5-coder:7b (default preset)"
        echo ""
        echo -e "${BOLD}Select a model to download (or 'q' to quit):${NC}"
        read -r -p "> " choice

        case "$choice" in
            1)
                model="qwen2.5-coder:7b"
                ;;
            2)
                model="qwen2.5-coder:14b"
                ;;
            3)
                model="qwen2.5-coder:32b"
                ;;
            4)
                model="codellama:7b"
                ;;
            5)
                model="codellama:13b"
                ;;
            6)
                model="deepseek-coder:6.7b"
                ;;
            7)
                model="mistral:7b"
                ;;
            8)
                echo ""
                read -r -p "Enter model name (e.g., llama2:7b): " model
                if [[ -z "$model" ]]; then
                    print_error "Invalid model name"
                    continue
                fi
                ;;
            q|Q|quit|exit)
                print_info "Exiting..."
                exit 0
                ;;
            *)
                print_error "Invalid choice: $choice"
                continue
                ;;
        esac

        # Check disk space (estimate 10GB needed for safety)
        echo ""
        if ! check_disk_space $MIN_FREE_SPACE_GB; then
            print_warning "Consider freeing up disk space before downloading"
            read -r -p "Continue anyway? (y/N): " confirm
            if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
                continue
            fi
        fi

        # Download the model
        echo ""
        if download_model "$model"; then
            echo ""
            print_success "Model setup complete!"
            print_info "Use with pr-resolve:"
            echo "  pr-resolve apply 123 --llm-preset ollama-local --llm-model $model"
            echo ""

            # Ask if user wants to download another model
            read -r -p "Download another model? (y/N): " another
            if [[ ! "$another" =~ ^[Yy]$ ]]; then
                break
            fi
            echo ""
        else
            print_error "Model download failed"
            read -r -p "Try another model? (y/N): " retry
            if [[ ! "$retry" =~ ^[Yy]$ ]]; then
                exit 3
            fi
            echo ""
        fi
    done
}

# Main function
main() {
    echo ""
    echo "============================================="
    echo "  Ollama Model Download for pr-resolve"
    echo "============================================="
    echo ""

    # Check Ollama availability
    if ! check_ollama_available; then
        exit 1
    fi

    print_success "Ollama is available and running"
    echo ""

    # If model name provided as argument, download directly
    if [[ $# -gt 0 ]]; then
        local model="$1"
        print_info "Direct download requested: $model"
        echo ""

        # Check disk space
        if ! check_disk_space $MIN_FREE_SPACE_GB; then
            print_warning "Low disk space detected"
            read -r -p "Continue anyway? (y/N): " confirm
            if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
                exit 2
            fi
        fi

        # Download the model
        if download_model "$model"; then
            echo ""
            print_success "Model setup complete!"
            print_info "Use with pr-resolve:"
            echo "  pr-resolve apply 123 --llm-preset ollama-local --llm-model $model"
            echo ""
            exit 0
        else
            exit 3
        fi
    fi

    # Interactive menu
    interactive_menu

    echo ""
    print_success "All done!"
    echo ""
    exit 0
}

# Run main function
main "$@"
