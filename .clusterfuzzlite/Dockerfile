# Copyright 2025 VirtualAgentics
# Licensed under the MIT License
#
# Dockerfile for OSS-Fuzz and ClusterFuzzLite fuzzing
# Compatible with both continuous fuzzing (OSS-Fuzz) and CI fuzzing (ClusterFuzzLite)
#
# Python Version: 3.11.13 (OSS-Fuzz base image - Atheris doesn't support Python 3.12 yet)
# Atheris Version: 2.3.0 (pre-installed in base image)

FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:6fc98ba9122e5392ec51909d14bcd5405e65af84d71a9f1a8f03003ab08cbc87

# Clone the repository
# For OSS-Fuzz: GitHub URL is used
# For ClusterFuzzLite: Local checkout is mounted
RUN git clone --depth 1 https://github.com/VirtualAgentics/coderabbit-conflict-resolver coderabbit-conflict-resolver

# Set working directory
WORKDIR coderabbit-conflict-resolver

# Copy build script and fuzz targets from parent directory
COPY .clusterfuzzlite/build.sh $SRC/build.sh
COPY fuzz/fuzz_*.py $SRC/
