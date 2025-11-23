# Copyright 2025 VirtualAgentics
# Licensed under the MIT License
#
# Dockerfile for OSS-Fuzz and ClusterFuzzLite fuzzing
# Compatible with both continuous fuzzing (OSS-Fuzz) and CI fuzzing (ClusterFuzzLite)
#
# Python Version: 3.11.13 (OSS-Fuzz base image - Atheris doesn't support Python 3.12 yet)
# Atheris Version: 2.3.0 (pre-installed in base image)

FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:c6666c7f7479e6ee853ab30e07312cc9ef4f130ffa6a95658b6781cfd4c1c480

# Copy local repository (ClusterFuzzLite tests PR code directly)
# For OSS-Fuzz: Replace this with: RUN git clone --depth 1 https://github.com/VirtualAgentics/coderabbit-conflict-resolver
COPY . $SRC/coderabbit-conflict-resolver

# Set working directory
WORKDIR $SRC/coderabbit-conflict-resolver

# Copy build script and fuzz targets from parent directory
COPY .clusterfuzzlite/build.sh $SRC/build.sh
COPY fuzz/fuzz_*.py $SRC/
