# Copyright 2025 VirtualAgentics
# Licensed under the MIT License
#
# Dockerfile for OSS-Fuzz and ClusterFuzzLite fuzzing
# Compatible with both continuous fuzzing (OSS-Fuzz) and CI fuzzing (ClusterFuzzLite)
#
# Python Version: 3.11.13 (OSS-Fuzz base image - Atheris doesn't support Python 3.12 yet)
# Atheris Version: 2.3.0 (pre-installed in base image)

FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:becec2ed4843c1aabb573d1b28b11661a8c1ee1bc2ee2b49f65816a39ac0a696

# Copy local repository (ClusterFuzzLite tests PR code directly)
# For OSS-Fuzz: Replace this with: RUN git clone --depth 1 https://github.com/VirtualAgentics/coderabbit-conflict-resolver
COPY . $SRC/coderabbit-conflict-resolver

# Set working directory
WORKDIR $SRC/coderabbit-conflict-resolver

# Copy build script and fuzz targets from parent directory
COPY .clusterfuzzlite/build.sh $SRC/build.sh
COPY fuzz/fuzz_*.py $SRC/
