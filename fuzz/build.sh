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

# Install project dependencies (standard installation, not editable mode)
echo "[*] Installing project dependencies..."
pip3 install .

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
