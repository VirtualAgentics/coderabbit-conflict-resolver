# Fuzzing with Atheris and ClusterFuzzLite

This directory contains coverage-guided fuzzing infrastructure for finding security vulnerabilities and crashes using [Atheris](https://github.com/google/atheris) and [ClusterFuzzLite](https://google.github.io/clusterfuzzlite/).

## Overview

**Fuzzing complements our Hypothesis property-based tests:**

- **Hypothesis**: Tests that properties hold for all inputs (business logic)
- **Atheris**: Finds crashes, hangs, and security bugs through coverage-guided mutation

Both run in CI and provide different security benefits.

### Python Version Note

**Fuzzing runs on Python 3.11 ONLY in Docker** (main project uses Python 3.12):

- **Main Project**: Python >=3.12 (development, CI, production)
- **Fuzzing Container**: Python 3.11.13 (isolated in Docker only)
- **Why?**: Atheris 2.3.0 (latest) only supports Python ≤3.11
- Python 3.12 support tracked in [Atheris issue #60](https://github.com/google/atheris/issues/60)
- Atheris is **NOT** installed in dev dependencies to avoid breaking Python 3.12 workflows
- Atheris comes pre-installed in the OSS-Fuzz base Docker image (`gcr.io/oss-fuzz-base/base-builder-python`)
- Complete isolation: Fuzzing environment does not affect main project tooling or CI

## Fuzz Targets

### `fuzz_handlers.py`

Tests file handlers (JSON/YAML/TOML) for:

- Parsing crashes on malformed input
- Injection attacks via special characters
- Resource exhaustion (large/nested structures)
- Encoding issues (null bytes, surrogates)

### `fuzz_input_validator.py`

Tests InputValidator (security-critical) for:

- Path traversal bypasses
- Null byte injection
- URL spoofing attacks
- Token format validation bypasses
- Content sanitization bypasses

## Running Locally

### Quick Test (Native - Requires Python 3.11)

```bash
# IMPORTANT: You need Python 3.11 for native execution
# Atheris does NOT work with Python 3.12

# Install Atheris (Python 3.11 only)
pip install atheris

# Run a fuzz target for 60 seconds
python fuzz/fuzz_handlers.py -max_total_time=60

# Run with specific seed for reproducing crashes
python fuzz/fuzz_handlers.py fuzz/testcases/crash-1234567890
```

### Docker Build (ClusterFuzzLite Compatible)

```bash
# Build fuzzing Docker image (Dockerfile is in .clusterfuzzlite/)
docker build -t local-fuzz -f .clusterfuzzlite/Dockerfile .

# Run fuzzer in container
docker run --rm -v $(pwd)/out:/out local-fuzz \
  run_fuzzer fuzz_handlers -max_total_time=300
```

## CI Integration

Fuzzing runs automatically via `.github/workflows/clusterfuzzlite.yml`:

- **PR Mode**: Quick 2-minute fuzz on code changes
- **Weekly Mode**: 30-minute deep fuzz every Sunday
- **Crash Reporting**: Uploads artifacts for triage

## Triaging Crashes

When fuzzing finds a crash:

1. **Download artifact** from GitHub Actions
2. **Reproduce locally**:

   ```bash
   python fuzz/fuzz_handlers.py crash-artifact-file
   ```

3. **Analyze** the crash (stack trace, input that caused it)
4. **Fix** the bug in the code
5. **Verify** fix by re-running fuzzer

## OSS-Fuzz Migration Path

This infrastructure is **OSS-Fuzz compatible**. To migrate (post-v0.2.0):

1. Copy files to `oss-fuzz/projects/review-bot-automator/`
2. Add `project.yaml` configuration
3. Submit PR to [google/oss-fuzz](https://github.com/google/oss-fuzz)

No rewrites needed - all fuzz targets reuse!

## Resources

- [Atheris Documentation](https://github.com/google/atheris)
- [ClusterFuzzLite Guide](https://google.github.io/clusterfuzzlite/)
- [OSS-Fuzz Integration](https://google.github.io/oss-fuzz/getting-started/new-project-guide/)
