# Ollama Setup Guide

This guide provides comprehensive instructions for setting up Ollama for local LLM inference with pr-resolve.

> **See Also**:
>
> * [LLM Configuration Guide](llm-configuration.md) for advanced configuration options and presets
> * [Privacy Architecture](privacy-architecture.md) for privacy benefits and compliance
> * [Local LLM Operation Guide](local-llm-operation-guide.md) for local LLM setup
> * [Privacy FAQ](privacy-faq.md) for common privacy questions

## Table of Contents

* [Why Ollama?](#why-ollama)
* [Quick Start](#quick-start)
* [Installation](#installation)
* [Model Selection](#model-selection)
* [Configuration Options](#configuration-options)
* [Auto-Download Feature](#auto-download-feature)
* [Troubleshooting](#troubleshooting)
* [Advanced Usage](#advanced-usage)

## Why Ollama?

Ollama provides several advantages for local LLM inference:

### Privacy & Local LLM Processing 🔒

* **🔒 Reduced Exposure**: Eliminates LLM vendor (OpenAI/Anthropic) from access chain
* **🌐 GitHub API Required**: Internet needed to fetch PR data (not offline/air-gapped)
* **✅ Simpler Compliance**: One fewer data processor for GDPR, HIPAA, SOC2
* **⚠️ Reality Check**: Code is on GitHub, CodeRabbit has access (required)
* **🔍 Verifiable**: Localhost-only LLM operation can be proven with network monitoring

### Performance & Cost

* **💰 Free**: No API costs - runs entirely on your hardware (zero ongoing fees)
* **⚡ Fast**: Local inference with GPU acceleration (NVIDIA, AMD, Apple Silicon)
* **📦 Simple**: Easy installation and model management

### Recommended For

* **Reducing third-party LLM vendor exposure** (eliminate OpenAI/Anthropic)
* **Regulated industries** (simpler compliance with one fewer data processor)
* **Organizations with policies against cloud LLM services**
* **Cost-conscious usage** (no per-request LLM fees)
* **Development and testing**

### Trade-offs

* Requires local compute resources (8-16GB RAM, 10-20GB disk)
* Slower than cloud APIs on CPU-only systems (fast with GPU)
* Model quality varies (improving rapidly, generally lower than GPT-4/Claude)

### Learn More About Privacy

For detailed information about Ollama's privacy benefits:

* [Privacy Architecture](privacy-architecture.md) - Comprehensive privacy analysis
* [Local LLM Operation Guide](local-llm-operation-guide.md) - Local LLM setup procedures
* [Privacy FAQ](privacy-faq.md) - Common questions about privacy and local LLM operation
* [Privacy Verification](local-llm-operation-guide.md#privacy-verification) - Verify localhost-only LLM operation

## Quick Start

The fastest way to get started with Ollama:

```bash
# 1. Install and setup Ollama
./scripts/setup_ollama.sh

# 2. Download recommended model
./scripts/download_ollama_models.sh

# 3. Use with pr-resolve
pr-resolve apply 123 --llm-preset ollama-local

```

That's it! The scripts handle everything automatically.

## Installation

### Automated Installation (Recommended)

Use the provided setup script for automatic installation:

```bash
./scripts/setup_ollama.sh

```

This script:

* Detects your operating system (Linux, macOS, Windows/WSL)
* Checks for existing Ollama installation
* Downloads and installs Ollama using the official installer
* Starts the Ollama service
* Verifies the installation with health checks

**Options**:

```bash
./scripts/setup_ollama.sh --help

```

* `--skip-install`: Skip installation if Ollama is already present
* `--skip-start`: Skip starting the Ollama service

### Manual Installation

#### Linux

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start service
ollama serve

```

#### macOS

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Or use Homebrew
brew install ollama

# Start service
ollama serve

```

#### Windows (WSL)

```bash
# In WSL terminal
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve

```

### Verifying Installation

Check that Ollama is running:

```bash
# Check version
ollama --version

# List models (should work even if empty)
ollama list

# Test API health
curl http://localhost:11434/api/tags

```

## Model Selection

### Interactive Model Download

Use the interactive script to download models with recommendations:

```bash
./scripts/download_ollama_models.sh

```

Features:

* Interactive menu with recommendations
* Model size and quality information
* Disk space checking
* Shows already downloaded models

### Direct Model Download

Download a specific model directly:

```bash
# Using script
./scripts/download_ollama_models.sh qwen2.5-coder:7b

# Using ollama CLI
ollama pull qwen2.5-coder:7b

```

### Recommended Models

For code conflict resolution, we recommend:

| Model | Size | Speed | Quality | Best For |
| ------- | ------ | ------- | --------- | ---------- |
| **qwen2.5-coder:7b** ⭐ | ~4GB | Fast | Good | **Default choice** - Best balance |
| qwen2.5-coder:14b | ~8GB | Medium | Better | Higher quality, more RAM |
| qwen2.5-coder:32b | ~18GB | Slow | Best | Maximum quality, powerful hardware |
| codellama:7b | ~4GB | Fast | Good | Alternative code-focused model |
| codellama:13b | ~7GB | Medium | Better | Larger CodeLlama variant |
| deepseek-coder:6.7b | ~4GB | Fast | Good | Code specialist |
| mistral:7b | ~4GB | Fast | Good | General-purpose alternative |

⭐ **Default preset**: `qwen2.5-coder:7b` - Excellent for code tasks with minimal resource usage.

### Model Comparison

**qwen2.5-coder:7b vs codellama:7b**:

* Qwen 2.5 Coder: Better at code understanding and multi-language support
* CodeLlama: Strong at Python and code generation
* **Recommendation**: Start with qwen2.5-coder:7b

**7B vs 14B vs 32B**:

* 7B: Fast, suitable for most conflicts, 8-16GB RAM
* 14B: Better quality, complex conflicts, 16-32GB RAM
* 32B: Best quality, very complex conflicts, 32GB+ RAM

### Hardware Requirements

| Model Size | RAM | Disk Space | Speed (Inference) |
| ------------ | ----- | ------------ | ------------------- |
| 7B | 8-16GB | ~5GB | ~1-3 tokens/sec (CPU) |
| 14B | 16-32GB | ~10GB | ~0.5-1 tokens/sec (CPU) |
| 32B | 32GB+ | ~20GB | ~0.2-0.5 tokens/sec (CPU) |

With GPU (NVIDIA):

* 7B: 6GB+ VRAM → 50-100 tokens/sec
* 14B: 12GB+ VRAM → 30-60 tokens/sec
* 32B: 24GB+ VRAM → 20-40 tokens/sec

## Configuration Options

### Using Ollama with pr-resolve

#### 1. Preset (Easiest)

```bash
pr-resolve apply 123 --llm-preset ollama-local

```

Uses default settings:

* Model: `qwen2.5-coder:7b`
* Base URL: `http://localhost:11434`
* Auto-download: Disabled

#### 2. Custom Model

```bash
pr-resolve apply 123 \
  --llm-preset ollama-local \
  --llm-model codellama:13b

```

#### 3. Configuration File

Create `config.yaml`:

```yaml
llm:
  enabled: true
  provider: ollama
  model: qwen2.5-coder:7b
  ollama_base_url: http://localhost:11434
  max_tokens: 2000
  cache_enabled: true
  fallback_to_regex: true

```

Use with:

```bash
pr-resolve apply 123 --config config.yaml

```

#### 4. Environment Variables

```bash
# Set Ollama configuration
export CR_LLM_PROVIDER=ollama
export CR_LLM_MODEL=qwen2.5-coder:7b
export OLLAMA_BASE_URL=http://localhost:11434

# Run pr-resolve
pr-resolve apply 123 --llm-enabled

```

### Remote Ollama Server

If Ollama is running on a different machine:

```bash
# Set base URL
export OLLAMA_BASE_URL=http://ollama-server:11434

# Or use config file
pr-resolve apply 123 --config config.yaml

```

**config.yaml**:

```yaml
llm:
  enabled: true
  provider: ollama
  model: qwen2.5-coder:7b
  ollama_base_url: http://ollama-server:11434

```

## Auto-Download Feature

The auto-download feature automatically downloads models when they're not available locally.

### Enabling Auto-Download

**Via Python API**:

```python
from review_bot_automator.llm.providers.ollama import OllamaProvider

# Auto-download enabled
provider = OllamaProvider(
    model="qwen2.5-coder:7b",
    auto_download=True  # Downloads model if not available
)

```

**Behavior**:

* When `auto_download=True`: Missing models are downloaded automatically (may take several minutes)
* When `auto_download=False` (default): Raises error with installation instructions

**Use Cases**:

* Automated CI/CD pipelines
* First-time setup automation
* Switching between models frequently

**Note**: Auto-download is not currently exposed via CLI flags. Use the interactive script or manual `ollama pull` for CLI usage.

### Model Information

Get information about a model:

```python
provider = OllamaProvider(model="qwen2.5-coder:7b")

# Get model info
info = provider._get_model_info("qwen2.5-coder:7b")
print(info)  # Dict with size, parameters, etc.

# Get recommended models
models = OllamaProvider.list_recommended_models()
for model in models:
    print(f"{model['name']}: {model['description']}")

```

## Troubleshooting

### Ollama Not Running

**Error**:

```text
LLMAPIError: Ollama is not running or not reachable. Start Ollama with: ollama serve

```

**Solution**:

```bash
# Start Ollama service
ollama serve

# Or use setup script
./scripts/setup_ollama.sh --skip-install

```

### Model Not Found

**Error**:

```text
LLMConfigurationError: Model 'qwen2.5-coder:7b' not found in Ollama.
Install it with: ollama pull qwen2.5-coder:7b

```

**Solution**:

```bash
# Download model
./scripts/download_ollama_models.sh qwen2.5-coder:7b

# Or use ollama CLI
ollama pull qwen2.5-coder:7b

# Or enable auto-download (Python API only)
provider = OllamaProvider(model="qwen2.5-coder:7b", auto_download=True)

```

### Slow Performance

**Symptoms**: Generation takes a very long time (>30 seconds per request).

**Solutions**:

1. **Use GPU acceleration** (NVIDIA):

   ```bash
   # Check GPU is detected
   ollama ps

   # Should show GPU info in output

   ```

2. **Use smaller model**:

   ```bash
   # Switch from 14B to 7B
   pr-resolve apply 123 \
     --llm-preset ollama-local \
     --llm-model qwen2.5-coder:7b

   ```

3. **Close other applications** to free up RAM

4. **Check CPU usage**: Ensure Ollama has CPU resources

### Out of Memory

**Error**:

```text
Ollama model loading failed: not enough memory

```

**Solutions**:

1. **Use smaller model**:

   ```bash
   ollama pull qwen2.5-coder:7b  # Instead of 14b or 32b

   ```

2. **Close other applications** to free up RAM

3. **Use quantized model** (if available):

   ```bash
   ollama pull qwen2.5-coder:7b-q4_0  # 4-bit quantization

   ```

### Connection Pool Exhausted

**Error**:

```text
LLMAPIError: Connection pool exhausted - too many concurrent requests

```

**Cause**: More than 10 concurrent requests to Ollama.

**Solutions**:

1. **Reduce concurrency**: Process fewer requests simultaneously
2. **Increase pool size** (Python API):

   ```python
   # Not currently configurable - requires code change
   # Pool size is hardcoded to 10 in HTTPAdapter

   ```

### Port Already in Use

**Error**:

```text
Error: listen tcp 127.0.0.1:11434: bind: address already in use

```

**Solutions**:

1. **Check existing Ollama process**:

   ```bash
   ps aux | grep ollama
   killall ollama  # Stop existing instance
   ollama serve    # Start new instance

   ```

2. **Use different port**:

   ```bash
   OLLAMA_HOST=0.0.0.0:11435 ollama serve

   # Update configuration
   export OLLAMA_BASE_URL=http://localhost:11435

   ```

### Model Download Failed

**Error**:

```text
Failed to download model: connection timeout

```

**Solutions**:

1. **Check internet connection**
2. **Retry with manual pull**:

   ```bash
   ollama pull qwen2.5-coder:7b

   ```

3. **Check disk space**:

   ```bash
   df -h  # Ensure at least 10GB free

   ```

## Advanced Usage

### Custom Ollama Configuration

**Change default model directory**:

```bash
# Set model storage location
export OLLAMA_MODELS=/path/to/models

# Start Ollama
ollama serve

```

**Enable debug logging**:

```bash
# Enable verbose output
export OLLAMA_DEBUG=1
ollama serve

```

### Multiple Models

Use different models for different tasks:

```bash
# Download multiple models
ollama pull qwen2.5-coder:7b
ollama pull codellama:13b
ollama pull mistral:7b

# Use specific model
pr-resolve apply 123 --llm-preset ollama-local --llm-model codellama:13b

```

### Model Management

```bash
# List downloaded models
ollama list

# Show model info
ollama show qwen2.5-coder:7b

# Remove model
ollama rm mistral:7b

# Copy model with custom name
ollama cp qwen2.5-coder:7b my-custom-model

```

### Running as System Service

**Linux (systemd)**:

```bash
# Create service file
sudo tee /etc/systemd/system/ollama.service > /dev/null <<EOF
[Unit]
Description=Ollama Service
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=/usr/local/bin/ollama serve
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable ollama
sudo systemctl start ollama

# Check status
sudo systemctl status ollama

```

**macOS (launchd)**:

```bash
# Ollama includes launchd service by default
# Check if running
launchctl list | grep ollama

# Start service
launchctl start com.ollama.ollama

```

### GPU Acceleration

GPU acceleration provides 10-60x speedup compared to CPU-only inference. The pr-resolve tool automatically detects and displays GPU information when using Ollama.

#### Automatic GPU Detection

Starting with version 0.3.0, pr-resolve automatically detects GPU availability when initializing Ollama:

```bash
# Run conflict resolution
pr-resolve apply 123 --llm-preset ollama-local

# GPU info displayed in metrics (if detected)
# ╭─ LLM Metrics ─────────────────────────╮
# │ Provider: ollama (qwen2.5-coder:7b)   │
# │ Hardware: NVIDIA RTX 4090 (24GB)      │
# │ Changes Parsed: 5                     │
# │ ...                                   │
# ╰───────────────────────────────────────╯

```

Detection supports multiple platforms:

* **NVIDIA GPUs**: CUDA 11.0+ (automatically detected via nvidia-smi)
* **AMD GPUs**: ROCm 5.0+ (automatically detected via rocm-smi)
* **Apple Silicon**: M1/M2/M3/M4 with Metal (automatically detected on macOS)
* **CPU Fallback**: Gracefully falls back if no GPU detected

#### NVIDIA GPU Setup (CUDA)

**Prerequisites**:

```bash
# 1. Verify NVIDIA driver
nvidia-smi

# Should show driver version and GPU info
# Recommended: Driver 525+ (CUDA 12+)

```

**Installation** (if nvidia-smi not found):

**Ubuntu/Debian**:

```bash
# Install NVIDIA drivers
sudo ubuntu-drivers autoinstall

# Reboot required
sudo reboot

# Verify
nvidia-smi

```

**Fedora/RHEL**:

```bash
# Install NVIDIA drivers
sudo dnf install akmod-nvidia

# Reboot required
sudo reboot

# Verify
nvidia-smi

```

**Verification**:

```bash
# Check Ollama GPU detection
ollama ps

# Should show
# NAME                   ID              SIZE     PROCESSOR
# qwen2.5-coder:7b      abc123...       4.7 GB   100% GPU

# Test with pr-resolve
pr-resolve apply 123 --llm-preset ollama-local

# Check metrics output for GPU info

```

**Performance Expectations**:

* **RTX 3060 (12GB)**: ~50-70 tokens/sec with 7B models
* **RTX 3090 (24GB)**: ~70-100 tokens/sec with 7B models, ~40-60 tokens/sec with 14B
* **RTX 4090 (24GB)**: ~100-150 tokens/sec with 7B models, ~60-90 tokens/sec with 14B

#### AMD GPU Setup (ROCm)

**Prerequisites**:

* AMD GPU with ROCm support (RX 6000/7000 series, MI series)
* ROCm 5.0 or newer

**Installation**:

```bash
# Follow AMD ROCm installation guide
# https://github.com/ollama/ollama/blob/main/docs/gpu.md

# Verify
rocm-smi --showproductname

# Should display AMD GPU info

```

**Verification**:

```bash
# Check Ollama GPU detection
ollama ps

# Test with pr-resolve
pr-resolve apply 123 --llm-preset ollama-local

```

#### Apple Silicon Setup (Metal)

**Automatic Detection**: No setup required - Ollama automatically uses Metal acceleration on Apple Silicon Macs.

**Supported Chips**:

* M1, M1 Pro, M1 Max, M1 Ultra
* M2, M2 Pro, M2 Max, M2 Ultra
* M3, M3 Pro, M3 Max
* M4, M4 Pro, M4 Max

**Verification**:

```bash
# Check chip
sysctl -n machdep.cpu.brand_string

# Should show "Apple M1/M2/M3/M4"

# Test with pr-resolve
pr-resolve apply 123 --llm-preset ollama-local

# Metrics will show
# Hardware: Apple M3 Max (Metal)

```

**Performance Notes**:

* M1/M2 8GB: Good for 7B models
* M1/M2 Pro/Max 16GB+: Excellent for 7B-14B models
* M1/M2 Ultra 64GB+: Handles 32B models well
* Unified memory shared between CPU and GPU

#### Troubleshooting GPU Detection

**GPU Not Detected** (Shows "Hardware: CPU"):

1. **Verify GPU is available**:

   ```bash
   # NVIDIA
   nvidia-smi

   # AMD
   rocm-smi --showproductname

   # Apple Silicon
   sysctl -n machdep.cpu.brand_string

   ```

2. **Check Ollama GPU usage**:

   ```bash
   ollama ps

   # PROCESSOR column should show "GPU" not "CPU"
   # If shows CPU, Ollama isn't using GPU

   ```

3. **Restart Ollama** to detect GPU:

   ```bash
   # Stop Ollama
   killall ollama

   # Start Ollama (GPU detection happens on startup)
   ollama serve

   # Reload model to use GPU
   ollama pull qwen2.5-coder:7b --force

   ```

4. **Check CUDA/ROCm installation**:

   ```bash
   # NVIDIA: Check CUDA
   nvcc --version

   # AMD: Check ROCm
   rocminfo

   ```

**GPU Detected but Slow Performance**:

1. **Check GPU memory**:

   ```bash
   # NVIDIA
   nvidia-smi

   # Look for "Memory-Usage" - should have enough free VRAM
   # 7B models need ~6GB, 14B need ~12GB

   ```

2. **Close competing GPU processes**:

   ```bash
   # NVIDIA: List GPU processes
   nvidia-smi

   # AMD: List processes
   rocm-smi --showpids

   ```

3. **Use smaller model** if out of VRAM:

   ```bash
   # 7B instead of 14B
   pr-resolve apply 123 \
     --llm-preset ollama-local \
     --llm-model qwen2.5-coder:7b

   ```

**Mixed CPU/GPU Usage**:

If model is too large for GPU VRAM, Ollama may split between GPU and CPU (slower):

```bash
# Check split in ollama ps
ollama ps

# May show: "50% GPU" instead of "100% GPU"
# Solution: Use smaller model

```

#### GPU Performance Monitoring

**During Resolution**:

```bash
# Terminal 1: Run pr-resolve
pr-resolve apply 123 --llm-preset ollama-local

# Terminal 2: Monitor GPU
watch -n 1 nvidia-smi  # NVIDIA
# OR
watch -n 1 rocm-smi    # AMD

```

**Check pr-resolve Metrics**:

```bash
# After resolution completes
# Look for metrics panel in output
╭─ LLM Metrics ─────────────────────────╮
│ Provider: ollama (qwen2.5-coder:7b)   │
│ Hardware: NVIDIA RTX 4090 (24GB)      │  ← GPU detected
│ Changes Parsed: 5                     │
│ Avg Confidence: 0.92                  │
│ Cache Hit Rate: 0%                    │
│ Total Cost: $0.00                     │
│ API Calls: 5                          │
│ Total Tokens: 12,450                  │
╰───────────────────────────────────────╯

```

**No GPU Info Displayed**:

* If GPU info is not shown in metrics, it means:
  * No GPU detected (CPU-only system)
  * GPU detection failed (non-fatal, falls back to CPU)
  * Using cloud LLM provider (GPU info only for Ollama)

#### GPU Acceleration Benefits

**Performance Comparison** (qwen2.5-coder:7b):

| Hardware | Tokens/sec | Time for 1000 tokens |
| ---------- | ------------ | --------------------- |
| CPU (i7-12700K) | 1-3 | 5-15 minutes |
| RTX 3060 (12GB) | 50-70 | 15-20 seconds |
| RTX 4090 (24GB) | 100-150 | 7-10 seconds |
| M2 Max (96GB) | 40-60 | 15-25 seconds |

**Cost Savings**:

* GPU: Free (local hardware)
* API (Claude/GPT-4): ~$0.01-0.05 per resolution

**Recommendation**: For frequent usage, a $300-500 GPU pays for itself in API savings within months.

### Performance Tuning

**Adjust context size**:

```yaml
# config.yaml
llm:
  max_tokens: 4000  # Increase for larger conflicts

```

**Adjust timeout**:

```python
provider = OllamaProvider(
    model="qwen2.5-coder:7b",
    timeout=300  # 5 minutes for slow systems
)

```

## See Also

* [LLM Configuration Guide](llm-configuration.md) - Advanced configuration options
* [Configuration Guide](configuration.md) - General configuration documentation
* [Getting Started Guide](getting-started.md) - Quick start guide
* [Ollama Documentation](https://github.com/ollama/ollama) - Official Ollama docs
