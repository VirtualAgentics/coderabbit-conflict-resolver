# Ollama Setup Guide

This guide provides comprehensive instructions for setting up Ollama for local LLM inference with pr-resolve.

> **See Also**: [LLM Configuration Guide](llm-configuration.md) for advanced configuration options and presets.

## Table of Contents

- [Why Ollama?](#why-ollama)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Model Selection](#model-selection)
- [Configuration Options](#configuration-options)
- [Auto-Download Feature](#auto-download-feature)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

## Why Ollama?

Ollama provides several advantages for local LLM inference:

- **Free**: No API costs - runs entirely on your hardware
- **Private**: Data never leaves your machine
- **Offline**: Works without internet connection (after initial model download)
- **Fast**: Local inference with GPU acceleration (if available)
- **Simple**: Easy installation and model management

**Recommended for**:
- Privacy-sensitive codebases
- Offline development environments
- Cost-conscious usage
- Development and testing

**Trade-offs**:
- Requires local compute resources (RAM, disk space)
- Slower than cloud APIs on CPU-only systems
- Model quality varies (generally lower than GPT-4 or Claude)

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
- Detects your operating system (Linux, macOS, Windows/WSL)
- Checks for existing Ollama installation
- Downloads and installs Ollama using the official installer
- Starts the Ollama service
- Verifies the installation with health checks

**Options**:
```bash
./scripts/setup_ollama.sh --help
```

- `--skip-install`: Skip installation if Ollama is already present
- `--skip-start`: Skip starting the Ollama service

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
- Interactive menu with recommendations
- Model size and quality information
- Disk space checking
- Shows already downloaded models

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
|-------|------|-------|---------|----------|
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
- Qwen 2.5 Coder: Better at code understanding and multi-language support
- CodeLlama: Strong at Python and code generation
- **Recommendation**: Start with qwen2.5-coder:7b

**7B vs 14B vs 32B**:
- 7B: Fast, suitable for most conflicts, 8-16GB RAM
- 14B: Better quality, complex conflicts, 16-32GB RAM
- 32B: Best quality, very complex conflicts, 32GB+ RAM

### Hardware Requirements

| Model Size | RAM | Disk Space | Speed (Inference) |
|------------|-----|------------|-------------------|
| 7B | 8-16GB | ~5GB | ~1-3 tokens/sec (CPU) |
| 14B | 16-32GB | ~10GB | ~0.5-1 tokens/sec (CPU) |
| 32B | 32GB+ | ~20GB | ~0.2-0.5 tokens/sec (CPU) |

With GPU (NVIDIA):
- 7B: 6GB+ VRAM → 50-100 tokens/sec
- 14B: 12GB+ VRAM → 30-60 tokens/sec
- 32B: 24GB+ VRAM → 20-40 tokens/sec

## Configuration Options

### Using Ollama with pr-resolve

#### 1. Preset (Easiest)

```bash
pr-resolve apply 123 --llm-preset ollama-local
```

Uses default settings:
- Model: `qwen2.5-coder:7b`
- Base URL: `http://localhost:11434`
- Auto-download: Disabled

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
from pr_conflict_resolver.llm.providers.ollama import OllamaProvider

# Auto-download enabled
provider = OllamaProvider(
    model="qwen2.5-coder:7b",
    auto_download=True  # Downloads model if not available
)
```

**Behavior**:
- When `auto_download=True`: Missing models are downloaded automatically (may take several minutes)
- When `auto_download=False` (default): Raises error with installation instructions

**Use Cases**:
- Automated CI/CD pipelines
- First-time setup automation
- Switching between models frequently

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
```
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
```
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
```
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
```
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
```
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
```
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

**NVIDIA GPU** (CUDA):

Ollama automatically detects and uses NVIDIA GPUs. Verify:

```bash
# Check GPU detection
ollama ps

# Should show GPU info
# If not detected, ensure NVIDIA drivers and CUDA are installed
nvidia-smi
```

**AMD GPU** (ROCm):

```bash
# Install ROCm support
# Follow: https://github.com/ollama/ollama/blob/main/docs/gpu.md

# Verify GPU
ollama ps
```

**Apple Silicon** (Metal):

Ollama automatically uses Metal acceleration on M1/M2/M3 Macs.

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

- [LLM Configuration Guide](llm-configuration.md) - Advanced configuration options
- [Configuration Guide](configuration.md) - General configuration documentation
- [Getting Started Guide](getting-started.md) - Quick start guide
- [Ollama Documentation](https://github.com/ollama/ollama) - Official Ollama docs
