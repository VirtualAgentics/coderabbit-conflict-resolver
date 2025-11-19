# Examples

This directory contains practical examples for using the Review Bot Automator.

## Directory Structure

```text
examples/
├── configs/          # Configuration file examples
├── workflows/        # CI/CD workflow examples
├── use-cases/        # Real-world usage scripts
└── README.md         # This file
```

## Configuration Examples

See `configs/` for ready-to-use configuration files:

- **dev-config.yaml** - Development environment setup
- **prod-config.yaml** - Production environment with maximum safety
- **perf-config.yaml** - Performance-optimized for large PRs
- **ci-config.yaml** - CI/CD pipeline configuration

## Workflow Examples

See `workflows/` for CI/CD integration examples:

- **github-actions.yml** - GitHub Actions workflow
- **gitlab-ci.yml** - GitLab CI pipeline

## Use Case Examples

See `use-cases/` for practical scripts:

- **smart-apply.py** - Dynamic worker scaling based on PR size
- **benchmark.sh** - Performance benchmarking script
- **staged-application.sh** - Apply changes in stages

## Quick Start

### 1. Using a Configuration File

```bash
# Copy a config file to your project
cp examples/configs/prod-config.yaml .pr-resolver-config.yaml

# Apply with configuration
pr-resolve apply --pr 123 --owner myorg --repo myrepo --config .pr-resolver-config.yaml
```

### 2. Using a Workflow

```bash
# GitHub Actions: Copy to your repository
cp examples/workflows/github-actions.yml .github/workflows/pr-resolver.yml

# GitLab CI: Copy to your repository
cp examples/workflows/gitlab-ci.yml .gitlab-ci.yml
```

### 3. Running Use Case Scripts

```bash
# Make scripts executable
chmod +x examples/use-cases/*.sh examples/use-cases/*.py

# Run smart apply (auto-adjusts workers)
./examples/use-cases/smart-apply.py myorg myrepo 123

# Run benchmark
./examples/use-cases/benchmark.sh 123 myorg myrepo

# Staged application
./examples/use-cases/staged-application.sh 123 myorg myrepo
```

## Documentation

For detailed documentation, see:

- [Getting Started](../docs/getting-started.md)
- [Configuration Reference](../docs/configuration.md)
- [Rollback System](../docs/rollback-system.md)
- [Parallel Processing](../docs/parallel-processing.md)
