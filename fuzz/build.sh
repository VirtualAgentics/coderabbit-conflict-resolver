#!/bin/bash -eu
# Copyright 2025 VirtualAgentics
# Licensed under the MIT License
#
# Build script for OSS-Fuzz and ClusterFuzzLite fuzzing
# Compiles Atheris fuzz targets for coverage-guided fuzzing

# Install project dependencies
echo "[*] Installing project dependencies..."
pip3 install -e .

# Install Atheris fuzzing engine
echo "[*] Installing Atheris..."
pip3 install atheris

# Build each fuzz target
echo "[*] Building fuzz targets..."
for fuzzer in $SRC/fuzz_*.py; do
    fuzzer_basename=$(basename -s .py "$fuzzer")
    echo "[*] Compiling $fuzzer_basename..."

    # compile_python_fuzzer creates a standalone fuzzing binary
    # --add-binary includes Python dependencies in the binary
    compile_python_fuzzer "$fuzzer" \
        --add-binary=/usr/local/lib/python3.*/site-packages:site-packages
done

echo "[*] Build complete! Fuzz targets ready."
