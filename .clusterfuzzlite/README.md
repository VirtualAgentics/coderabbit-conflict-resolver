# ClusterFuzzLite Fuzzing Setup

This directory contains the configuration and build scripts for continuous fuzzing using Google's ClusterFuzzLite framework.

## Overview

ClusterFuzzLite runs coverage-guided fuzzing on pull requests and scheduled workflows to detect crashes, memory issues, and edge cases in security-critical code.

**Base Image**: `gcr.io/oss-fuzz-base/base-builder-python`

- **Python Version**: 3.11.13 (Atheris doesn't support Python 3.12 yet)
- **Pre-installed**: Atheris 2.3.0, pip (latest)

## Files

- **`build.sh`**: Build script that installs dependencies and compiles fuzz targets
- **`requirements-py311.txt`**: Hash-pinned core dependencies for Python 3.11
- **`requirements-fuzz.txt`**: Hash-pinned additional runtime dependencies for fuzzing
- **`Dockerfile`**: Docker configuration (if present)

## Critical: Hash Pinning for OpenSSF Scorecard

### ⚠️ IMPORTANT: Use Requirements File, NOT Inline Hashes

OpenSSF Scorecard's `Pinned-Dependencies` check **does not recognize** inline `--hash` arguments in pip install commands.

**❌ WRONG (will trigger CodeQL alert #83)**:

```bash
python3 -m pip install \
  "PyYAML==6.0.3" \
    --hash=sha256:b8bb0864c5a28024fac8a632c443c87c5aa6f215c0b126c449ae1a150412f31d
```

**✅ CORRECT (recognized by Scorecard)**:

```bash
python3 -m pip install --require-hashes -r /src/.clusterfuzzlite/requirements-fuzz.txt
```

### Why This Matters

1. **Security**: Scorecard flags unpinned dependencies as a supply chain risk
2. **Compliance**: OpenSSF badge requirements demand hash pinning
3. **Detection**: Scorecard's static analysis only recognizes requirements files
4. **Enforcement**: `--require-hashes` flag ensures ALL dependencies have hashes

**Impact**:

- Without requirements file: Pinned-Dependencies score = 9/10 (CodeQL alert)
- With requirements file: Pinned-Dependencies score = 10/10 ✅

## Python Version Mismatch Issue

### ⚠️ CRITICAL: Generate Hashes for Python 3.11, NOT 3.12

The Docker image uses **Python 3.11.13**, but local development may use Python 3.12+.

**Problem**: Compiled packages (PyYAML, ruamel.yaml.clib) have different binary wheels per Python version:

- `pyyaml-6.0.3-cp311-cp311-manylinux2014_x86_64.whl` (Python 3.11)
- `pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.whl` (Python 3.12)

**Result**: Different binaries = different SHA256 hashes

### How to Generate Correct Hashes

**Method 1: Query PyPI JSON API** (Recommended)

```bash
# Get PyYAML 6.0.3 for Python 3.11 Linux x86_64
curl -s <https://pypi.org/pypi/PyYAML/json> | \
  jq -r '.releases["6.0.3"][] | select(.python_version == "cp311" and .filename | contains("manylinux2014_x86_64")) | "\(.filename)\n  --hash=sha256:\(.digests.sha256)"'
```

### Method 2: Download and Verify

```bash
# Download specific wheel for Python 3.11
pip download --python-version 3.11 --platform manylinux2014_x86_64 \
  --only-binary=:all: --no-deps "PyYAML==6.0.3"

# Generate SHA256 hash
sha256sum pyyaml-6.0.3-cp311-cp311-manylinux2014_x86_64.whl
```

### Method 3: pip-compile (for multiple dependencies)

```bash
# Install pip-tools
pip install pip-tools

# Create requirements.in
echo "PyYAML==6.0.3" > requirements.in

# Generate hashes (run inside Python 3.11 environment)
pip-compile --generate-hashes requirements.in -o requirements-fuzz.txt
```

### Universal vs. Platform-Specific Wheels

**Pure Python packages** (e.g., `ruamel.yaml`):

- Wheel: `ruamel.yaml-0.18.16-py3-none-any.whl`
- Tag: `py3-none-any` (universal, works on all Python 3.x versions)
- Hash: **Same across all Python versions** ✅

**Compiled packages** (e.g., `PyYAML`, `ruamel.yaml.clib`):

- Wheel: `pyyaml-6.0.3-cp311-cp311-manylinux2014_x86_64.whl`
- Tag: `cp311` (CPython 3.11), `manylinux2014_x86_64` (Linux x86_64)
- Hash: **Different per Python version** ⚠️

## Requirements Files

### `requirements-py311.txt` - Core Dependencies

Contains all core project dependencies (from `pyproject.toml`) with Python 3.11 hashes:

- click, requests, pydantic, ruamel.yaml, tomli-w, rich
- All transitive dependencies (annotated-types, certifi, charset-normalizer, etc.)
- Installed first in `build.sh` with `--require-hashes` flag
- Project is then installed with `--no-deps` to avoid dependency conflicts

### Why separate from `requirements.txt`?

- Root `requirements.txt` has Python 3.12 hashes
- Compiled packages (charset-normalizer, pydantic-core) have different wheel hashes per Python version
- ClusterFuzzLite Docker image uses Python 3.11.13 (Atheris limitation)

### `requirements-fuzz.txt` - Additional Runtime Dependencies

Contains additional dependencies needed only for fuzzing (not in core dependencies):

- PyYAML (if not already in core)
- ruamel.yaml runtime components

## Updating Dependencies

### Step 1: Update `requirements-py311.txt` and `requirements-fuzz.txt`

1. **Check current version on PyPI**: <https://pypi.org/project/><package>/
2. **Generate hash** for Python 3.11 (see methods above)
3. **Update** `requirements-fuzz.txt` with new version and hash
4. **Verify** transitive dependencies are included

### Step 2: Test Locally (if possible)

```bash
# Build Docker image locally
docker build -t clusterfuzzlite-test -f .clusterfuzzlite/Dockerfile .

# Run build script
docker run --rm -v $(pwd):/src clusterfuzzlite-test bash -c \
  "cd /src && ./.clusterfuzzlite/build.sh"
```

### Step 3: Verify in CI

- Create PR with dependency update
- Wait for ClusterFuzzLite build to pass
- Check Scorecard does not raise alerts

## Common Issues

### Issue 1: Hash Mismatch Error

**Error**:

```text
ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE
```

**Cause**: Wrong Python version hash (cp312 instead of cp311)

**Fix**: Regenerate hash using Python 3.11 wheel (see "How to Generate Correct Hashes")

### Issue 2: CodeQL Alert #83 "pipCommand not pinned by hash"

**Cause**: Using inline `--hash` arguments instead of requirements file

**Fix**: Move hashes to `requirements-fuzz.txt` and use `--require-hashes` flag

### Issue 3: Missing Transitive Dependencies

**Error**:

```text
ERROR: In --require-hashes mode, all requirements must have their versions pinned
```

**Cause**: Transitive dependency (e.g., `ruamel.yaml.clib`) not included with hash

**Fix**: Add all transitive dependencies to `requirements-fuzz.txt`:

```bash
# Find transitive dependencies
pip install --dry-run PyYAML==6.0.3 ruamel.yaml==0.18.16
# Add any additional packages to requirements-fuzz.txt
```

## Lessons Learned (Issue #94 / PR #96)

### Problem Timeline

1. **Initial attempt**: Added inline `--hash` arguments to `build.sh`
   - ✅ Build passed
   - ❌ CodeQL alert #83 triggered: "pipCommand not pinned by hash"
   - ❌ OpenSSF Scorecard did not recognize hash pinning

2. **First iteration**: Used wrong Python version
   - ❌ Generated hashes from local Python 3.12 environment
   - ❌ Docker uses Python 3.11.13
   - ❌ Would have caused hash mismatch error (but caught before deployment)

3. **Second iteration**: Correct Python 3.11 hashes, still inline
   - ✅ Build passed
   - ❌ CodeQL alert #83 still triggered
   - ❌ Scorecard still did not recognize pinning

4. **Final solution**: Requirements file approach
   - ✅ Created `requirements-fuzz.txt` with Python 3.11 hashes
   - ✅ Used `--require-hashes -r requirements-fuzz.txt`
   - ✅ Build passed
   - ✅ Scorecard detected hash pinning correctly
   - ✅ Alert #83 auto-closed after merge

### Key Takeaways

1. **Always use requirements files** for hash pinning (not inline hashes)
2. **Always match Docker Python version** when generating hashes
3. **Always include transitive dependencies** with hashes
4. **Always verify with Scorecard** that detection works
5. **Document immediately** to prevent future mistakes

## Security Controls

### Supply Chain Security

**Hash Pinning** (SHA256):

- ✅ Prevents package substitution attacks
- ✅ Ensures reproducible builds
- ✅ Complies with SLSA framework Level 2

**Dependency Scanning**:

- ✅ Trivy scans for CVEs
- ✅ pip-audit checks PyPI advisories
- ✅ Renovate auto-updates dependencies

**Scorecard Compliance**:

- ✅ Pinned-Dependencies: 10/10 (after PR #96)
- ✅ Dependency-Update-Tool: Renovate configured
- ✅ SBOM-Generation: Enabled

## Fuzz Targets

All fuzz targets are located in the `/fuzz` directory:

1. **`fuzz_input_validator.py`**: Tests input validation and sanitization
2. **`fuzz_secret_scanner.py`**: Tests secret detection (17 patterns, ReDoS)
3. **`fuzz_handlers.py`**: Tests JSON, YAML, TOML parsing

**Coverage**: Each target runs with Address Sanitizer (ASan) and Undefined Behavior Sanitizer (UBSan)

## CI/CD Integration

### PR Fuzzing (`.github/workflows/clusterfuzzlite.yml`)

- **Trigger**: Every pull request
- **Duration**: 600 seconds total
- **Sanitizers**: Address, Undefined Behavior
- **Purpose**: Catch crashes and memory issues before merge

### Scheduled Fuzzing (`.github/workflows/fuzz-extended.yml`)

- **Trigger**: Weekly on main branch
- **Duration**: 1 hour per target
- **Purpose**: Extended fuzzing for deep coverage

## References

- **ClusterFuzzLite Docs**: <https://google.github.io/clusterfuzzlite/>
- **OpenSSF Scorecard**: <https://github.com/ossf/scorecard>
- **Pip Hash Checking**: <https://pip.pypa.io/en/stable/topics/secure-installs/>
- **PyPI JSON API**: <https://warehouse.pypa.io/api-reference/json.html>
- **Issue #94**: OpenSSF Scorecard improvement
- **PR #96**: Hash pinning implementation
- **Alert #83**: pipCommand not pinned by hash

---

**Last Updated**: 2025-11-03
**Maintainer**: VirtualAgentics Security Team
**Version**: 1.0
