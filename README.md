# Review Bot Automator

<p align="center">
  <strong>Universal AI-powered automation for GitHub code review bots</strong>
  <br>
  Intelligent suggestion application and conflict resolution for <a href="https://coderabbit.ai">CodeRabbit</a>, <a href="https://github.com/features/copilot">GitHub Copilot</a>, and custom review bots
</p>

<p align="center">
  <!-- Build & Quality -->
  <a href="https://github.com/VirtualAgentics/review-bot-automator/actions"><img src="https://github.com/VirtualAgentics/review-bot-automator/workflows/CI/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/VirtualAgentics/review-bot-automator"><img src="https://codecov.io/gh/VirtualAgentics/review-bot-automator/graph/badge.svg?token=6Om8QAxoM7" alt="codecov"></a>
  <a href="https://github.com/VirtualAgentics/review-bot-automator/actions/workflows/security.yml"><img src="https://github.com/VirtualAgentics/review-bot-automator/workflows/Security/badge.svg" alt="Security"></a>
  <a href="https://virtualagentics.github.io/review-bot-automator/"><img src="https://github.com/VirtualAgentics/review-bot-automator/workflows/Documentation/badge.svg" alt="Documentation"></a>
  <br>
  <!-- Code Quality -->
  <a href="https://github.com/psf/black"><img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="http://mypy-lang.org/"><img src="https://img.shields.io/badge/mypy-checked-blue" alt="MyPy"></a>
  <a href="https://github.com/DavidAnson/markdownlint"><img src="https://img.shields.io/badge/markdown-linted-brightgreen" alt="Markdownlint"></a>
  <a href="https://github.com/pre-commit/pre-commit"><img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit" alt="pre-commit"></a>
  <br>
  <!-- Security & Compliance -->
  <a href="https://securityscorecards.dev/viewer/?uri=github.com/VirtualAgentics/review-bot-automator"><img src="https://api.securityscorecards.dev/projects/github.com/VirtualAgentics/review-bot-automator/badge" alt="OpenSSF Scorecard"></a>
  <a href="https://coderabbit.ai"><img src="https://img.shields.io/coderabbit/prs/github/VirtualAgentics/review-bot-automator?utm_source=oss&utm_medium=github&utm_campaign=VirtualAgentics%2Freview-bot-automator&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews" alt="CodeRabbit Reviews"></a>
  <br>
  <!-- Project Info -->
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Status: Alpha">
</p>

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Quick Start](#quick-start)
- [Features](#features)
- [Architecture](#architecture)
- [Use Cases](#use-cases)
- [Environment Variables](#environment-variables)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Project Status](#project-status)
- [License](#license)

---

## Problem Statement

When multiple PR review comments suggest overlapping changes to the same file, traditional automation tools either:

- Skip all conflicting changes (losing valuable suggestions)
- Apply changes sequentially without conflict awareness (potentially breaking code)
- Require tedious manual resolution for every conflict

**Review Bot Automator** provides intelligent, semantic-aware conflict resolution that:

- ✅ Understands code structure (JSON, YAML, TOML, Python, TypeScript)
- ✅ Uses priority-based resolution (user selections, security fixes, syntax errors)
- ✅ Supports semantic merging (combining non-conflicting changes automatically)
- ✅ Learns from your decisions to improve over time
- ✅ Provides detailed conflict analysis and actionable suggestions

## Quick Start

### Installation

```bash
pip install pr-conflict-resolver
```

### Basic Usage

```bash
# Set your GitHub token (required)
export GITHUB_PERSONAL_ACCESS_TOKEN="your_token_here"

# Analyze conflicts in a PR
pr-resolve analyze --owner VirtualAgentics --repo my-repo --pr 123

# Apply suggestions with conflict resolution
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 --strategy priority

# Apply only conflicting changes
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 --mode conflicts-only

# Simulate without applying changes (dry-run mode)
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 --mode dry-run

# Use parallel processing for large PRs
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 --parallel --max-workers 8

# 🚀 NEW: Phase 5 Optimizations - Production-ready performance & cost controls
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 \
  --llm-preset openai-api-mini \
  --parallel \                      # Concurrent LLM calls (up to 3-4x faster on large batches)
  --cache-enabled \                 # Prompt caching (up to 60-90% cost reduction with cache hits)
  --circuit-breaker-enabled \       # Automatic failure recovery
  --cost-budget 10.0                # Set $10 USD budget limit
# See docs/optimization-guide.md for benchmarks and optimization strategies

# Load configuration from file
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 --config config.yaml
```

### LLM Provider Setup (Optional)

Enable AI-powered features with your choice of LLM provider using **zero-config presets**:

```bash
# ✨ NEW: Zero-config presets for instant setup

# Option 1: Codex CLI (free with GitHub Copilot subscription)
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 \
  --llm-preset codex-cli-free

# Option 2: Local Ollama 🔒 (free, private) - REDUCES THIRD-PARTY LLM VENDOR EXPOSURE
./scripts/setup_ollama.sh          # One-time install
./scripts/download_ollama_models.sh  # Download model
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 \
  --llm-preset ollama-local
# 🔒 Reduces third-party LLM vendor exposure (OpenAI/Anthropic never see comments)
# ✅ Simpler compliance (one fewer data processor for GDPR, HIPAA, SOC2)
# ⚠️ Note: GitHub/CodeRabbit still have access (required for PR workflow)
# See docs/ollama-setup.md for setup | docs/privacy-architecture.md for privacy details

# Option 3: Claude CLI (requires Claude subscription)
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 \
  --llm-preset claude-cli-sonnet

# Option 4: OpenAI API (pay-per-use, ~$0.01 per PR)
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 \
  --llm-preset openai-api-mini \
  --llm-api-key sk-...

# Option 5: Anthropic API (balanced cost/performance)
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123 \
  --llm-preset anthropic-api-balanced \
  --llm-api-key sk-ant-...

**Available presets**: `codex-cli-free`, `ollama-local` 🔒, `claude-cli-sonnet`, `openai-api-mini`, `anthropic-api-balanced`

**Privacy Note**: Ollama (`ollama-local`) reduces third-party LLM vendor exposure by processing review comments locally. OpenAI/Anthropic never see your code, simplifying compliance. Note: GitHub and CodeRabbit still have access (required for PR workflow). See [Privacy Architecture](docs/privacy-architecture.md) for details.

### Alternative: Use environment variables

```bash
# Anthropic (recommended - 50-90% cost savings with caching)
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="anthropic"
export CR_LLM_API_KEY="sk-ant-..."  # Get from https://console.anthropic.com/

# OpenAI
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="openai"
export CR_LLM_API_KEY="sk-..."  # Get from https://platform.openai.com/api-keys

# Then use as normal
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123

**Documentation**:

- [LLM Configuration Guide](docs/llm-configuration.md) - All provider options and setup
- [Privacy Architecture](docs/privacy-architecture.md) - Privacy comparison and compliance
- [Local LLM Operation Guide](docs/local-llm-operation-guide.md) - Local LLM setup with Ollama
- [Privacy FAQ](docs/privacy-faq.md) - Common privacy questions

### Python API

```python
from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.config import PresetConfig

resolver = ConflictResolver(config=PresetConfig.BALANCED)
results = resolver.resolve_pr_conflicts(
    owner="VirtualAgentics",
    repo="my-repo",
    pr_number=123
)

print(f"Applied: {results.applied_count}")
print(f"Conflicts: {results.conflict_count}")
print(f"Success rate: {results.success_rate}%")
```

## Features

### Intelligent Conflict Analysis

- **Semantic Understanding**: Analyzes JSON, YAML, TOML structure, not just text
- **Conflict Categorization**: Exact, major, partial, minor, disjoint-keys, semantic-duplicate
- **Impact Assessment**: Evaluates scope, risk level, and criticality of changes
- **Actionable Suggestions**: Provides specific guidance for each conflict

### Smart Resolution Strategies

- **Priority-Based**: User selections > Security fixes > Syntax errors > Regular suggestions
- **Semantic Merging**: Combines non-conflicting changes in structured files
- **Sequential Application**: Applies compatible changes in optimal order
- **Defer to User**: Escalates complex conflicts for manual review

### File-Type Handlers

- **JSON**: Duplicate key detection, key-level merging
- **YAML**: Comment preservation, structure-aware merging
- **TOML**: Section merging, format preservation
- **Python/TypeScript**: AST-aware analysis (planned)

### Multi-Provider LLM Support ✅ (Phase 2 Complete - All 5 Providers Production-Ready)

- **5 Provider Types**: OpenAI API, Anthropic API, Claude CLI, Codex CLI, Ollama (all production-ready)
- **GPU Acceleration**: Ollama supports NVIDIA CUDA, AMD ROCm, Apple Metal with automatic detection
- **HTTP Connection Pooling**: Optimized for concurrent requests (10 connections per provider)
- **Auto-Download**: Ollama can automatically download models when not available
- **Cost Optimization**: Prompt caching reduces Anthropic costs by 50-90%
- **Retry Logic**: Exponential backoff for transient failures (all providers)
- **Flexible Deployment**: API-based, CLI-based, or local inference
- **Provider Selection**: Choose based on cost, privacy, or performance needs
- **Health Checks**: Automatic provider validation before use

### Learning & Optimization ✅ (Phase 5: Production-Ready)

**Performance Optimization:**

- **Parallel Processing**: Concurrent LLM calls with ThreadPoolExecutor (3-4x faster for large PRs)
- **Prompt Caching**: SHA-256-based caching with LRU eviction (60-90% cost reduction)
- **GPU Acceleration**: Automatic NVIDIA/AMD/Apple Metal detection for Ollama

**Cost Optimization:**

- **Cost Budgeting**: Prevent runaway expenses with configurable USD limits
- **Provider Selection**: Choose based on cost (free Ollama vs $0.07/1K comments with OpenAI)
- **Cache Hit Optimization**: Automatic cache warming and preloading

**Reliability & Resilience:**

- **Circuit Breaker**: Three-state protection (CLOSED/OPEN/HALF_OPEN) against cascading failures
- **Metrics Aggregation**: Track costs, latency (P50/P95/P99), token usage per provider/model
- **Automatic Recovery**: Half-open state testing for provider health recovery
- **Thread Safety**: Production-grade concurrency with reentrant locks

See [Optimization Guide](docs/optimization-guide.md) and [Cost Optimization Guide](docs/cost-optimization.md) for complete details.

### Configuration & Presets

- **Conservative**: Skip all conflicts, manual review required
- **Balanced**: Priority system + semantic merging (default)
- **Aggressive**: Maximize automation, user selections always win
- **Semantic**: Focus on structure-aware merging for config files

### Application Modes

- **all**: Apply both conflicting and non-conflicting changes (default)
- **conflicts-only**: Apply only changes that have conflicts
- **non-conflicts-only**: Apply only changes without conflicts
- **dry-run**: Analyze and report without applying any changes

### Rollback & Safety Features

- **Automatic Rollback**: Git-based checkpointing with automatic rollback on failure
- **Pre-Application Validation**: Validates changes before applying (optional)
- **File Integrity Checks**: Verifies file safety and containment
- **Detailed Logging**: Comprehensive logging for debugging and audit trails

### Runtime Configuration

Configure via multiple sources with precedence chain:
**CLI flags > Environment variables > Config file > Defaults**

- **Configuration Files**: Load settings from YAML or TOML files
- **Environment Variables**: Set options using `CR_*` prefix variables
- **CLI Overrides**: Override any setting via command-line flags

See [`.env.example`](.env.example) for available environment variables.

## Documentation

### User Guides

- [Getting Started Guide](docs/getting-started.md) - Installation, setup, and first steps
- [Configuration Reference](docs/configuration.md) - Complete configuration options
- [LLM Configuration Guide](docs/llm-configuration.md) - LLM providers, presets, and advanced configuration
- [Ollama Setup Guide](docs/ollama-setup.md) - Comprehensive Ollama installation and setup
- [Optimization Guide](docs/optimization-guide.md) - Performance, cost, and reliability optimization strategies
- [Cost Optimization Guide](docs/cost-optimization.md) - Minimize LLM costs with caching and provider selection
- [Rollback System](docs/rollback-system.md) - Automatic rollback and recovery
- [Parallel Processing](docs/parallel-processing.md) - Performance tuning guide
- [Migration Guide](docs/migration-guide.md) - Upgrading from earlier versions
- [Troubleshooting](docs/troubleshooting.md) - Common issues and solutions

### Reference Documentation

- [API Reference](docs/api-reference.md) - Python API documentation
- [Conflict Types Explained](docs/conflict-types.md) - Understanding conflict categories
- [Resolution Strategies](docs/resolution-strategies.md) - Strategy selection guide
- [Performance Benchmarks](docs/performance-benchmarks.md) - LLM provider performance comparison

### Architecture & Development

- [Architecture Overview](docs/architecture.md) - System design and components
- [Contributing Guide](CONTRIBUTING.md) - How to contribute

### Security

- [Security Policy](SECURITY.md) - Vulnerability reporting, security features
- [Security Architecture](docs/security-architecture.md) - Design principles, threat model
- [Threat Model](docs/security/threat-model.md) - STRIDE analysis, risk assessment
- [Incident Response](docs/security/incident-response.md) - Security incident procedures
- [Compliance](docs/security/compliance.md) - GDPR, OWASP, SOC2, OpenSSF
- [Security Testing](docs/security/security-testing.md) - Testing guide, fuzzing, SAST
- [Phase 5 Security Audit](docs/security/phase5-security-audit.md) - Optimization features security review

## Architecture

┌─────────────────────────────────────────────────────────────┐
│                    GitHub PR Comments                       │
│                   (CodeRabbit, Review Bot)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Comment Parser & Extractor                     │
│   (Suggestions, Diffs, Codemods, Multi-Options)            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Conflict Detection Engine                      │
│  • Fingerprinting  • Overlap Analysis  • Semantic Check    │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴──────────┐
         ▼                      ▼
┌──────────────────┐   ┌──────────────────┐
│  File Handlers   │   │  Priority System │
│  • JSON          │   │  • User Selected │
│  • YAML          │   │  • Security Fix  │
│  • TOML          │   │  • Syntax Error  │
│  • Python        │   │  • Regular       │
└─────────┬────────┘   └────────┬─────────┘
          │                     │
          └──────────┬──────────┘
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Resolution Strategy Selector                      │
│  • Skip  • Override  • Merge  • Sequential  • Defer        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Application Engine                             │
│  • Backup  • Apply  • Validate  • Rollback                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│        Reporting & Metrics                                  │
│  • Conflict Summary  • Visual Diff  • Success Rate         │
└─────────────────────────────────────────────────────────────┘

## Use Cases

### 1. CodeRabbit Multi-Option Selections

**Problem**: User selects "Option 2" but it conflicts with another suggestion
**Solution**: Priority system ensures user selections override lower-priority changes

### 2. Overlapping Configuration Changes

**Problem**: Two suggestions modify different keys in `package.json`
**Solution**: Semantic merging combines both changes automatically

### 3. Security Fix vs. Formatting

**Problem**: Security fix conflicts with formatting suggestion
**Solution**: Priority system applies security fix, skips formatting

### 4. Large PR with 50+ Comments

**Problem**: Manual conflict resolution is time-consuming
**Solution**: Parallel processing + caching resolves conflicts in seconds

### 5. High API Costs for Frequent PRs

**Problem**: LLM API costs add up with many PRs
**Solution**: Prompt caching (60-90% cost reduction) + cost budgeting + free local models (Ollama)

### 6. Unreliable LLM Providers

**Problem**: LLM APIs fail intermittently, cascading failures
**Solution**: Circuit breaker pattern with automatic provider recovery + metrics tracking

## Environment Variables

Configure the tool using environment variables (see [`.env.example`](.env.example) for all options):

| Variable | Description | Default |
| ---------- | ------------- | --------- |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | GitHub API token (required) | None |
| `CR_MODE` | Application mode (`all`, `conflicts-only`, `non-conflicts-only`, `dry-run`) | `all` |
| `CR_ENABLE_ROLLBACK` | Enable automatic rollback on failure | `true` |
| `CR_VALIDATE` | Enable pre-application validation | `true` |
| `CR_PARALLEL` | Enable parallel processing | `false` |
| `CR_MAX_WORKERS` | Number of parallel workers | `4` |
| `CR_CACHE_ENABLED` | Enable prompt caching | `true` |
| `CR_CACHE_MAX_SIZE` | Maximum cache entries | `1000` |
| `CR_CACHE_TTL` | Cache TTL in seconds | `3600` |
| `CR_CIRCUIT_BREAKER_ENABLED` | Enable circuit breaker for LLM resilience | `true` |
| `CR_COST_BUDGET_USD` | Maximum cost budget (USD) | None |
| `CR_LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `CR_LOG_FILE` | Log file path (optional) | None |

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/VirtualAgentics/review-bot-automator.git
cd review-bot-automator
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install

### Running Tests

This project uses **pytest 9.0** with native subtests support for comprehensive testing. We maintain **>80% test coverage** with 1,394 tests including unit, integration, security, and property-based fuzzing tests.

```bash
# Run standard tests with coverage
pytest tests/ --cov=src --cov-report=html

# Run property-based fuzzing tests
make test-fuzz              # Dev profile: 50 examples
make test-fuzz-ci           # CI profile: 100 examples
make test-fuzz-extended     # Extended: 1000 examples

# Run all tests (standard + fuzzing)
make test-all

**For more details, see:**

- [Testing Guide](docs/testing/TESTING.md) - Comprehensive testing documentation
- [Subtests Guide](docs/testing/SUBTESTS_GUIDE.md) - Writing tests with subtests
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines including testing practices

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Inspired by the sophisticated code review capabilities of [CodeRabbit AI](https://coderabbit.ai)
- Built with experience from [ContextForge Memory](https://github.com/VirtualAgentics/ConextForge_memory) project
- Community feedback and contributions

## Project Status

**Current Version**: 0.1.0 (Alpha)

**Roadmap**:

- ✅ **Phase 0: Security Foundation (COMPLETE)**
  - ✅ 0.1: Security Architecture Design
  - ✅ 0.2: Input Validation & Sanitization
  - ✅ 0.3: Secure File Handling
  - ✅ 0.4: Secret Detection (14+ patterns)
  - ✅ 0.5: Security Testing Suite (95%+ coverage)
  - ✅ 0.6: Security Configuration
  - ✅ 0.7: CI/CD Security Scanning (7+ tools)
  - ✅ 0.8: Security Documentation
- ✅ **Phase 1: Core Features (COMPLETE)**
  - ✅ Core conflict detection and analysis
  - ✅ File handlers (JSON, YAML, TOML)
  - ✅ Priority system
  - ✅ Rollback system with git-based checkpointing
- ✅ **Phase 2: CLI & Configuration (COMPLETE)**
  - ✅ CLI with comprehensive options
  - ✅ Runtime configuration system
  - ✅ Application modes (all, conflicts-only, non-conflicts-only, dry-run)
  - ✅ Parallel processing support
  - ✅ Multiple configuration sources (file, env, CLI)
- 🔄 **Phase 3: Documentation & Examples (IN PROGRESS)**
  - 🔄 Comprehensive documentation updates
  - 📅 Example configurations and use cases
- ✅ **V2.0 Phase 0: LLM Foundation (COMPLETE)** - PR #121
  - ✅ Core LLM data models and infrastructure
  - ✅ Universal comment parser with LLM + regex fallback
  - ✅ LLM provider protocol for polymorphic support
  - ✅ Structured prompt engineering system
  - ✅ Confidence threshold filtering
- ✅ **V2.0 Phase 1: LLM-Powered Parsing (COMPLETE)** - PR #122
  - ✅ OpenAI API provider implementation
  - ✅ Automatic retry logic with exponential backoff
  - ✅ Token counting and cost tracking
  - ✅ Comprehensive error handling
  - ✅ Integration with ConflictResolver
- ✅ **V2.0 Phase 2: Multi-Provider Support (COMPLETE)** - Closed Nov 9, 2025
  - ✅ All 5 LLM providers implemented: OpenAI API, Anthropic API, Claude CLI, Codex CLI, Ollama
  - ✅ Provider factory pattern with automatic selection
  - ✅ HTTP connection pooling and retry logic
  - ✅ Provider health checks and validation
  - ✅ Cost tracking across all API-based providers
- ✅ **V2.0 Phase 3: CLI Integration Polish (COMPLETE)** - Closed Nov 11, 2025
  - ✅ Zero-config presets for instant LLM setup (5 presets available)
  - ✅ Configuration precedence chain: CLI > Environment > File > Defaults
  - ✅ Enhanced error messages with actionable resolution steps
  - ✅ Support for YAML/TOML configuration files
  - ✅ Security: API keys must use ${VAR} syntax in config files
- ✅ **V2.0 Phase 4: Documentation & Developer Experience (COMPLETE)** - Closed Nov 19, 2025
  - ✅ Ollama provider with GPU acceleration (NVIDIA, AMD ROCm, Apple Metal)
  - ✅ Automatic GPU detection and hardware info display
  - ✅ HTTP connection pooling for concurrent requests
  - ✅ Model auto-download feature
  - ✅ Performance benchmarking infrastructure - PR #199, Issue #170
  - ✅ Privacy documentation (local LLM operation guide) - PR #201, Issue #171
  - ✅ Integration tests with privacy verification - Issue #172 (Closed as not feasible)
- 🔄 **V2.0 Phase 5: Optimization & Production Readiness (IN PROGRESS)** - Issue #119, 75% complete
  - ✅ Week 1: Parallel Processing (100% complete) - Concurrent LLM parsing with ThreadPoolExecutor
  - ✅ Week 2: Prompt Caching (100% complete) - SHA-256 caching with LRU eviction and TTL
  - ✅ Week 3: Circuit Breaker & Resilience (100% complete) - Three-state circuit breaker, metrics aggregation, cost budgeting
  - 🔄 Week 4: Security & Documentation (60% complete) - Security audit, optimization guides, documentation updates
- 📅 **V2.0 Phase 6: Documentation & Migration** - Not started

**V2.0 Milestone Progress**: 71% complete (Phases 0-4 closed, Phase 5 at 75%)

### Security Highlights

- **ClusterFuzzLite**: Continuous fuzzing (3 fuzz targets, ASan + UBSan)
- **Test Coverage**: 82.35% overall, 95%+ for security modules
- **Security Scanning**: CodeQL, Trivy, TruffleHog, Bandit, pip-audit, OpenSSF Scorecard
- **Secret Detection**: 14+ pattern types (GitHub tokens, AWS keys, API keys, etc.)
- **Documentation**: Comprehensive security documentation (threat model, incident response, compliance)

## LLM Features (v2.0 Architecture)

> **✅ Core v2.0 LLM features are production-ready!** Phases 0-3 complete (57% of v2.0 milestone). All 5 LLM providers fully functional. See [Roadmap](#-project-status) for current status.

**Vision**: Major architecture upgrade to parse **95%+** of CodeRabbit comments (up from 20%)

### The Problem We're Solving

Current system only parses **```suggestion** blocks, missing:

- ❌ Diff blocks (```diff) - **60% of CodeRabbit comments**
- ❌ Natural language suggestions - **20% of comments**
- ❌ Multi-option suggestions
- ❌ Multiple diff blocks per comment

**Result**: Only **1 out of 5** CodeRabbit comments are currently parsed.

### The Solution: LLM-First Parsing

┌─────────────────────────────────────────────────────────┐
│           LLM Parser (Primary - All Formats)            │
│  • Diff blocks        • Suggestion blocks              │
│  • Natural language   • Multi-options                   │
│  • 95%+ coverage      • Intelligent understanding       │
└──────────────────────────┬──────────────────────────────┘
                           │
                  ┌────────┴────────┐
                  │  Fallback if    │
                  │  LLM fails      │
                  └────────┬────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│       Regex Parser (Fallback - Suggestion Blocks)       │
│  • 100% reliable      • Zero cost                       │
│  • Legacy support     • Always available                │
└─────────────────────────────────────────────────────────┘

### Multi-Provider Support (User Choice)

Choose your preferred LLM provider:

| Provider | Cost Model | Best For | Est. Cost (1000 comments) |
| ---------- | ----------- | ---------- | --------------------------- |
| **Claude CLI** | Subscription ($20/mo) | Best quality + zero marginal cost | $0 (covered) |
| **Codex CLI** | Subscription ($20/mo) | Cost-effective, OpenAI quality | $0 (covered) |
| **Ollama** | Free (local) | Privacy, offline, no API costs | $0 |
| **OpenAI API** | Pay-per-token | Pay-as-you-go, low volume | $0.07 (with caching) |
| **Anthropic API** | Pay-per-token | Best quality, willing to pay | $0.22 (with caching) |

### Quick Preview

```bash
# Current (v1.x) - regex-only
pr-resolve apply --owner VirtualAgentics --repo my-repo --pr 123
# Parses: 1/5 comments (20%)

# v2.0 - LLM-powered (opt-in)
pr-resolve apply --llm --llm-provider claude-cli --owner VirtualAgentics --repo my-repo --pr 123
# Parses: 5/5 comments (100%)

# Use presets for quick config
pr-resolve apply --llm-preset claude-cli-sonnet --owner VirtualAgentics --repo my-repo --pr 123
pr-resolve apply --llm-preset ollama-local --owner VirtualAgentics --repo my-repo --pr 123  # Privacy-first
```

### Backward Compatibility Guarantee

✅ **Zero Breaking Changes** - All v1.x code works unchanged in v2.0

- LLM parsing **disabled by default** (opt-in via `--llm` flag)
- Automatic **fallback to regex** if LLM fails
- v1.x CLI commands **work identically**
- v1.x Python API **unchanged**

### Enhanced Change Metadata

```python
# v2.0: Changes include AI-powered insights
change = Change(
    path="src/module.py",
    start_line=10,
    end_line=12,
    content="new code",
    # NEW in v2.0 (optional fields)
    llm_confidence=0.95,  # How confident the LLM is
    llm_provider="claude-cli",  # Which provider parsed it
    parsing_method="llm",  # "llm" or "regex"
    change_rationale="Improves error handling",  # Why change was suggested
    risk_level="low"  # "low", "medium", "high"
)
```

### Documentation

Comprehensive planning documentation available:

- [LLM Refactor Roadmap](./docs/planning/LLM_REFACTOR_ROADMAP.md) (15K words) - Full implementation plan
- [LLM Architecture](./docs/planning/LLM_ARCHITECTURE.md) (8K words) - Technical specification
- [Migration Guide](./docs/planning/MIGRATION_GUIDE.md) (3K words) - v1.x → v2.0 upgrade path

### Timeline

- **Phase 0-6**: 10-12 weeks implementation
- **Estimated Release**: Q2 2025
- **GitHub Milestone**: [v2.0 - LLM-First Architecture](https://github.com/VirtualAgentics/review-bot-automator/milestone/2)
- **GitHub Issues**: #114-#120 (Phases 0-6)

---

## Related Projects

- [ContextForge Memory](https://github.com/VirtualAgentics/ConextForge_memory) - Original implementation
- [CodeRabbit AI](https://coderabbit.ai) - AI-powered code review

---

**Made with ❤️ by [VirtualAgentics](https://github.com/VirtualAgentics)**
