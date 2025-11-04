#!/bin/bash -eu
# Copyright 2025 VirtualAgentics
# Licensed under the MIT License
#
# Build script for OSS-Fuzz and ClusterFuzzLite fuzzing
# Compiles Atheris fuzz targets for coverage-guided fuzzing
#
# Base image info:
#   - Python 3.11.13 (Atheris doesn't support Python 3.12 yet)
#   - Atheris 2.3.0 pre-installed
#   - pip already upgraded to latest version
#
# Security note: Using 'python3 -m pip' instead of 'pip3' ensures we invoke
# the pip module bundled with the Python interpreter, which is the security
# best practice followed throughout this project.

# Install project dependencies with hash verification (Python 3.11)
# Using requirements-py311.txt ensures correct wheel hashes for Python 3.11
# (different from requirements.txt which has Python 3.12 hashes)
echo "[*] Installing project dependencies..."
python3 -m pip install --require-hashes -r /src/.clusterfuzzlite/requirements-py311.txt

# Install project package without dependencies (standard installation, not editable mode)
# Path matches Dockerfile COPY destination: $SRC/coderabbit-conflict-resolver
echo "[*] Installing project package..."
python3 -m pip install --no-deps /src/coderabbit-conflict-resolver

# Install additional runtime dependencies with SHA256 hash pinning
# Dependencies defined in requirements-fuzz.txt with --require-hashes enforcement
# See requirements-fuzz.txt for package details and hash verification info
echo "[*] Installing additional runtime dependencies..."
python3 -m pip install --require-hashes -r /src/.clusterfuzzlite/requirements-fuzz.txt

# NOTE: Atheris is pre-installed in gcr.io/oss-fuzz-base/base-builder-python
# No need to install it separately

# Build each fuzz target using compile_python_fuzzer helper
echo "[*] Building fuzz targets..."
for fuzzer in $SRC/fuzz_*.py; do
    fuzzer_basename=$(basename -s .py "$fuzzer")
    echo "[*] Compiling $fuzzer_basename..."

    # compile_python_fuzzer handles all compilation and packaging
    compile_python_fuzzer "$fuzzer"
done

echo "[*] Build complete! Fuzz targets ready."
