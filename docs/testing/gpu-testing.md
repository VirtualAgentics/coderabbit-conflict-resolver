# GPU Detection Testing Guide

This guide provides manual testing procedures for verifying GPU detection functionality in pr-resolve with Ollama.

## Overview

The GPU detection feature automatically identifies hardware acceleration capabilities when using Ollama for local LLM inference. This guide helps you verify that detection works correctly across different GPU platforms.

**Supported Platforms**:

* NVIDIA GPUs (CUDA)
* AMD GPUs (ROCm)
* Apple Silicon (Metal)
* CPU Fallback

## Pre-Test Setup

### 1. Install Ollama

```bash
# Automated installation
./scripts/setup_ollama.sh

# Or manual installation
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve

```

### 2. Download Test Model

```bash
# Download recommended test model
ollama pull qwen2.5-coder:7b

# Verify download
ollama list

```

### 3. Install pr-resolve

```bash
# Install in development mode
pip install -e ".[dev]"

# Verify installation
pr-resolve --version

```

## Test Suite

### Test 1: GPU Detection Logging

**Objective**: Verify GPU detection logs appear during OllamaProvider initialization.

**Test Steps**:

1. Run with debug logging:

   ```bash
   export PYTHONLOGLEVEL=DEBUG
   python -c "
   from review_bot_automator.llm.providers.ollama import OllamaProvider
   provider = OllamaProvider(model='qwen2.5-coder:7b')
   "

   ```

2. Check output for GPU detection logs

**Expected Results**:

**With GPU**:

```text
INFO:review_bot_automator.llm.providers.ollama:GPU detected: NVIDIA RTX 4090 (24GB VRAM)

```

**Without GPU**:

```text
INFO:review_bot_automator.llm.providers.ollama:GPU not detected, using CPU inference

```

**Pass Criteria**:

* ✅ Log message appears
* ✅ Correct GPU type detected (NVIDIA/AMD/Apple/CPU)
* ✅ VRAM displayed if available

### Test 2: Metrics Display

**Objective**: Verify GPU information appears in CLI metrics output.

**Test Steps**:

1. Create test conflict (or use existing PR):

   ```bash
   # Example with test repository
   pr-resolve apply 123 --llm-preset ollama-local

   ```

2. Look for metrics panel in output

**Expected Results**:

**With GPU**:

```text
╭─ LLM Metrics ─────────────────────────╮
│ Provider: ollama (qwen2.5-coder:7b)   │
│ Hardware: NVIDIA RTX 4090 (24GB)      │  ← GPU info displayed
│ Changes Parsed: X                     │
│ Avg Confidence: X.XX                  │
│ ...                                   │
╰───────────────────────────────────────╯

```

**Without GPU** (CPU fallback):

```text
╭─ LLM Metrics ─────────────────────────╮
│ Provider: ollama (qwen2.5-coder:7b)   │
│ Hardware: CPU (No GPU detected)       │  ← CPU fallback
│ ...                                   │
╰───────────────────────────────────────╯

```

**Pass Criteria**:

* ✅ Metrics panel appears
* ✅ Hardware row shows correct GPU or CPU
* ✅ VRAM displayed for GPU (if available)
* ✅ Formatting matches expected output

### Test 3: NVIDIA GPU Detection

**Objective**: Verify NVIDIA GPU detection via nvidia-smi.

**Prerequisites**: NVIDIA GPU with drivers installed.

**Test Steps**:

1. Verify nvidia-smi works:

   ```bash
   nvidia-smi

   ```

2. Run GPU detector test:

   ```bash
   python -c "
   from review_bot_automator.llm.providers.gpu_detector import GPUDetector
   gpu = GPUDetector.detect_gpu('http://localhost:11434')
   print(f'Available: {gpu.available}')
   print(f'Type: {gpu.gpu_type}')
   print(f'Model: {gpu.model_name}')
   print(f'VRAM Total: {gpu.vram_total_mb}MB')
   "

   ```

**Expected Results**:

```text
Available: True
Type: NVIDIA
Model: NVIDIA GeForce RTX 4090
VRAM Total: 24576MB

```

**Pass Criteria**:

* ✅ `available` is `True`
* ✅ `gpu_type` is `"NVIDIA"`
* ✅ `model_name` contains GPU name from nvidia-smi
* ✅ `vram_total_mb` matches nvidia-smi output

### Test 4: AMD GPU Detection

**Objective**: Verify AMD GPU detection via rocm-smi.

**Prerequisites**: AMD GPU with ROCm installed.

**Test Steps**:

1. Verify rocm-smi works:

   ```bash
   rocm-smi --showproductname

   ```

2. Run GPU detector test:

   ```bash
   python -c "
   from review_bot_automator.llm.providers.gpu_detector import GPUDetector
   gpu = GPUDetector.detect_gpu('http://localhost:11434')
   print(f'Available: {gpu.available}')
   print(f'Type: {gpu.gpu_type}')
   print(f'Model: {gpu.model_name}')
   "

   ```

**Expected Results**:

```text
Available: True
Type: AMD
Model: AMD GPU (ROCm)

```

**Pass Criteria**:

* ✅ `available` is `True`
* ✅ `gpu_type` is `"AMD"`
* ✅ `model_name` contains "AMD" or "ROCm"

### Test 5: Apple Silicon Detection

**Objective**: Verify Apple M-series chip detection via sysctl.

**Prerequisites**: Mac with Apple Silicon (M1/M2/M3/M4).

**Test Steps**:

1. Verify chip:

   ```bash
   sysctl -n machdep.cpu.brand_string

   ```

2. Run GPU detector test:

   ```bash
   python -c "
   from review_bot_automator.llm.providers.gpu_detector import GPUDetector
   gpu = GPUDetector.detect_gpu('http://localhost:11434')
   print(f'Available: {gpu.available}')
   print(f'Type: {gpu.gpu_type}')
   print(f'Model: {gpu.model_name}')
   "

   ```

**Expected Results**:

```text
Available: True
Type: Apple
Model: Apple M3 Max (Metal)

```

**Pass Criteria**:

* ✅ `available` is `True`
* ✅ `gpu_type` is `"Apple"`
* ✅ `model_name` contains "M1", "M2", "M3", or "M4"
* ✅ `model_name` contains "Metal"

### Test 6: CPU Fallback

**Objective**: Verify graceful CPU fallback when no GPU is available.

**Test Steps**:

1. **Mock no GPU** (temporarily rename GPU command):

   ```bash
   # NVIDIA systems
   sudo mv /usr/bin/nvidia-smi /usr/bin/nvidia-smi.bak

   # Restore after test:
   # sudo mv /usr/bin/nvidia-smi.bak /usr/bin/nvidia-smi

   ```

2. Run GPU detector test:

   ```bash
   python -c "
   from review_bot_automator.llm.providers.gpu_detector import GPUDetector
   gpu = GPUDetector.detect_gpu('http://localhost:11434')
   print(f'Available: {gpu.available}')
   print(f'Type: {gpu.gpu_type}')
   print(f'Model: {gpu.model_name}')
   "

   ```

3. **Restore GPU command** (important!):

   ```bash
   sudo mv /usr/bin/nvidia-smi.bak /usr/bin/nvidia-smi

   ```

**Expected Results**:

```text
Available: False
Type: CPU
Model: None

```

**Pass Criteria**:

* ✅ `available` is `False`
* ✅ `gpu_type` is `"CPU"`
* ✅ `model_name` is `None`
* ✅ No exceptions raised (graceful fallback)

### Test 7: Ollama API Detection

**Objective**: Verify GPU detection via Ollama /api/ps endpoint.

**Prerequisites**: Ollama running with a loaded model.

**Test Steps**:

1. Load model in Ollama:

   ```bash
   # Load model to trigger /api/ps detection
   ollama run qwen2.5-coder:7b "print('hello')"

   ```

2. Check /api/ps endpoint:

   ```bash
   curl http://localhost:11434/api/ps

   ```

3. Run GPU detector test:

   ```bash
   python -c "
   from review_bot_automator.llm.providers.gpu_detector import GPUDetector
   gpu = GPUDetector._detect_from_ollama_ps('http://localhost:11434', timeout=5)
   print(f'GPU Type: {gpu.gpu_type}')
   print(f'Model: {gpu.model_name}')
   "

   ```

**Expected Results**:

* Should detect GPU via Ollama API if model is loaded
* Falls through to system detection if /api/ps unavailable

**Pass Criteria**:

* ✅ Either detects via /api/ps or gracefully falls through
* ✅ No exceptions raised

### Test 8: Multi-Tier Fallback Strategy

**Objective**: Verify the detection fallback chain works correctly.

**Test Steps**:

1. Run with all detection methods available:

   ```bash
   python -c "
   from review_bot_automator.llm.providers.gpu_detector import GPUDetector
   import logging
   logging.basicConfig(level=logging.DEBUG)

   gpu = GPUDetector.detect_gpu('http://localhost:11434')
   print(f'Final result: {gpu.gpu_type} - {gpu.model_name}')
   "

   ```

2. Observe logs to see which detection method succeeded

**Expected Behavior**:

* Strategy 1: Try Ollama /api/ps (may fail if no model loaded)
* Strategy 2: Try system-level detection (nvidia-smi/rocm-smi/sysctl)
* Strategy 3: CPU fallback (always succeeds)

**Pass Criteria**:

* ✅ Tries Ollama API first (logged)
* ✅ Falls back to system detection if API fails
* ✅ Falls back to CPU if all fail
* ✅ Always returns valid GPUInfo object

### Test 9: Detection Performance

**Objective**: Verify GPU detection completes quickly (non-blocking).

**Test Steps**:

```bash
python -c "
import time
from review_bot_automator.llm.providers.gpu_detector import GPUDetector

start = time.time()
gpu = GPUDetector.detect_gpu('http://localhost:11434')
duration = time.time() - start

print(f'Detection took: {duration:.3f} seconds')
print(f'GPU Type: {gpu.gpu_type}')
"

```

**Expected Results**:

```text
Detection took: 0.XXX seconds  (should be < 5 seconds)
GPU Type: NVIDIA  (or AMD/Apple/CPU)

```

**Pass Criteria**:

* ✅ Detection completes in < 5 seconds
* ✅ Does not block OllamaProvider initialization
* ✅ Timeouts work correctly

### Test 10: Integration with OllamaProvider

**Objective**: Verify GPU detection integrates correctly with OllamaProvider.

**Test Steps**:

```bash
python -c "
from review_bot_automator.llm.providers.ollama import OllamaProvider

# Initialize provider
provider = OllamaProvider(model='qwen2.5-coder:7b')

# Check GPU info
if provider.gpu_info:
    print(f'GPU Available: {provider.gpu_info.available}')
    print(f'GPU Type: {provider.gpu_info.gpu_type}')
    print(f'GPU Model: {provider.gpu_info.model_name}')
else:
    print('No GPU info available')
"

```

**Expected Results**:

```text
GPU Available: True
GPU Type: NVIDIA
GPU Model: NVIDIA GeForce RTX 4090

```

**Pass Criteria**:

* ✅ `provider.gpu_info` is not None
* ✅ GPU info matches system
* ✅ Provider initializes successfully even if GPU detection fails

## Automated Test Suite

Run the full automated test suite:

```bash
# All GPU detector tests
pytest tests/unit/llm/test_gpu_detector.py -v

# All Ollama provider tests (including GPU integration)
pytest tests/unit/llm/test_ollama_provider.py -v

# Full test suite
pytest tests/ -v

```

**Expected Results**:

* All GPU detector tests pass (30 tests)
* All Ollama provider tests pass (68 tests, 2 skipped)

## Platform-Specific Checklists

### NVIDIA GPU Systems

* [ ] nvidia-smi command works
* [ ] GPU detected via system detection
* [ ] VRAM total is reported correctly
* [ ] GPU model name appears in metrics
* [ ] Performance shows GPU acceleration (50-150 tokens/sec)

### AMD GPU Systems

* [ ] rocm-smi command works
* [ ] GPU detected via system detection
* [ ] GPU type is "AMD"
* [ ] Model name contains "AMD" or "ROCm"
* [ ] Performance shows GPU acceleration

### Apple Silicon Systems

* [ ] sysctl shows M1/M2/M3/M4 chip
* [ ] GPU detected via system detection
* [ ] GPU type is "Apple"
* [ ] Model name contains "Metal"
* [ ] Performance shows Metal acceleration

### CPU-Only Systems

* [ ] Detection gracefully falls back to CPU
* [ ] No errors or exceptions raised
* [ ] Metrics show "Hardware: CPU (No GPU detected)"
* [ ] OllamaProvider still works correctly

## Troubleshooting Test Failures

### GPU Not Detected (False Negative)

1. **Verify GPU drivers**:

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
   # PROCESSOR column should show "GPU"

   ```

3. **Restart Ollama**:

   ```bash
   killall ollama
   ollama serve

   ```

### Tests Timeout

1. **Increase timeout** in test:

   ```python
   GPUDetector.detect_gpu('http://localhost:11434', timeout=10)

   ```

2. **Check Ollama is running**:

   ```bash
   curl http://localhost:11434/api/tags

   ```

### Inconsistent Detection

1. **Clear Ollama cache**:

   ```bash
   killall ollama
   rm -rf ~/.ollama/models/*
   ollama pull qwen2.5-coder:7b

   ```

2. **Check system commands** are in PATH:

   ```bash
   which nvidia-smi  # Should return path
   which rocm-smi
   which sysctl

   ```

## Manual Smoke Test Checklist

Quick manual verification (5 minutes):

* [ ] Ollama is running (`ollama ps`)
* [ ] Model downloaded (`ollama list`)
* [ ] Run pr-resolve with Ollama preset
* [ ] Metrics panel appears
* [ ] Hardware row shows GPU or CPU
* [ ] No errors in logs
* [ ] Performance is acceptable

## Reporting Issues

If GPU detection fails, collect this information:

```bash
# System info
uname -a
python --version

# GPU info
nvidia-smi 2>&1 || echo "No NVIDIA GPU"
rocm-smi --showproductname 2>&1 || echo "No AMD GPU"
sysctl -n machdep.cpu.brand_string 2>&1 || echo "Not macOS"

# Ollama info
ollama --version
ollama ps
curl http://localhost:11434/api/ps

# pr-resolve version
pr-resolve --version

# Run with debug logs
PYTHONLOGLEVEL=DEBUG python -c "
from review_bot_automator.llm.providers.ollama import OllamaProvider
provider = OllamaProvider(model='qwen2.5-coder:7b')
print(f'GPU Info: {provider.gpu_info}')
"

```

Include this output when reporting GPU detection issues.

## See Also

* [Ollama Setup Guide](../ollama-setup.md) - Complete Ollama setup documentation
* [LLM Configuration Guide](../llm-configuration.md) - LLM provider configuration
* [Testing Guide](TESTING.md) - General testing documentation
