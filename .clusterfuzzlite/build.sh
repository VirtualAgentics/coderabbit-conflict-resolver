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

# Install project with dependencies (standard installation, not editable mode)
# Dependencies from pyproject.toml will be installed (all pinned to exact versions)
echo "[*] Installing project package..."
python3 -m pip install .

# Install additional runtime dependencies explicitly
# ruamel.yaml is required by the yaml_handler
# PyYAML is required by input_validator and conflict_detector
echo "[*] Installing additional runtime dependencies..."
python3 -m pip install "ruamel.yaml==0.18.16" "PyYAML==6.0.3"

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
