# Copyright 2025 VirtualAgentics
# Licensed under the MIT License
#
# Dockerfile for OSS-Fuzz and ClusterFuzzLite fuzzing
# Compatible with both continuous fuzzing (OSS-Fuzz) and CI fuzzing (ClusterFuzzLite)

FROM gcr.io/oss-fuzz-base/base-builder-python

# Clone the repository
# For OSS-Fuzz: GitHub URL is used
# For ClusterFuzzLite: Local checkout is mounted
RUN git clone --depth 1 https://github.com/VirtualAgentics/coderabbit-conflict-resolver coderabbit-conflict-resolver

# Set working directory
WORKDIR coderabbit-conflict-resolver

# Copy build script and fuzz targets
COPY build.sh fuzz_*.py $SRC/
