# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Testing Infrastructure

* **pytest 9.0 Migration**: Upgraded to pytest 9.0.0 with native subtests support
  * Migrated 76 test cases across 14 test methods to use pytest 9.0 native subtests
  * Modified 6 test files: configuration, CLI validation, input validation, handlers, and security tests
  * Improved test organization and readability with descriptive subtest messages
  * Enhanced failure reporting with contextual information for easier debugging
  * All subtests run independently even if one fails, providing comprehensive test coverage
  * Maintained 86.92% test coverage (exceeds 80% minimum requirement)
  * All 1318 tests passing with zero regressions
  * Strict mode enabled for pytest configuration validation
  * **Documentation added:**
    * `docs/testing/TESTING.md` - Comprehensive testing guide
    * `docs/testing/PYTEST_9_MIGRATION.md` - Migration overview and benefits
    * `docs/testing/SUBTESTS_GUIDE.md` - Detailed subtests best practices
    * Updated `CONTRIBUTING.md` with subtests guidelines
    * Updated `README.md` with pytest 9.0 information
  * **Migration Timeline:** 6 weeks (Week 1: Security tests, Week 2-3: Config/CLI tests, Week 4-5: Handlers/validation tests, Week 6: Documentation)
  * **Benefits:** Better test isolation, improved failure reporting, easier test maintenance, reduced boilerplate code
  * See [pytest 9.0 Migration Guide](docs/testing/PYTEST_9_MIGRATION.md) for complete details

* **V2.0 Phase 0**: LLM Foundation - Data Models & Infrastructure (PR #121, Issue #114)
  * Core LLM data models: `LLMConfig`, `LLMRequest`, `LLMResponse`, `ParsedChange`
  * Universal `CommentParser` with LLM-powered parsing and regex fallback
  * LLM provider protocol (`LLMProvider`) for polymorphic provider support
  * Structured prompt engineering system with examples
  * Confidence threshold filtering (default: 0.7) for high-quality change extraction
  * Comprehensive test suite for LLM components (15+ tests)
  * New LLM package: `pr_conflict_resolver.llm` with modular architecture
* **V2.0 Phase 1**: LLM-Powered Comment Parsing with OpenAI Provider (PR #122, Issue #115)
  * `OpenAIAPIProvider` implementation with official OpenAI Python SDK
  * Automatic retry logic with exponential backoff for transient failures (3 retries: 2s, 4s, 8s)
  * Token counting using tiktoken for accurate cost estimation
  * Cost tracking per request and cumulative totals
  * JSON mode for structured output with temperature=0 for deterministic results
  * Model pricing table for gpt-4, gpt-4-turbo, gpt-3.5-turbo, gpt-4o, gpt-4o-mini
  * Comprehensive error handling (authentication, rate limits, timeouts, API errors)
  * Integration with `ConflictResolver` for LLM-powered comment parsing
  * 30+ unit tests for OpenAI provider (93% coverage)
  * New dependencies: `openai==2.8.1`, `tenacity==9.1.2`, `tiktoken==0.12.0`
* **V2.0 Phase 2**: Multi-Provider Support ✅ COMPLETE (Issue #116, Closed Nov 9, 2025)
  * **All 5 LLM Providers Implemented:**
    * OpenAI API (`openai_api.py`) - Production-ready with retry logic
    * Anthropic API (`anthropic_api.py`) - With 50-90% cost reduction via prompt caching
    * Claude CLI (`claude_cli.py`) - Subscription-based, zero marginal cost
    * Codex CLI (`codex_cli.py`) - GitHub Copilot integration
    * Ollama (`ollama.py`) - Local, privacy-first, offline-capable
  * **Provider Infrastructure:**
    * `LLMProviderFactory` for automatic provider selection based on configuration
    * HTTP connection pooling (10 connections per pool) for improved performance (PR #173, Issue #167)
    * Retry logic with exponential backoff for all providers
    * Provider health checks and validation before use
    * Cost tracking across all API-based providers
  * **GPU Acceleration Support:**
    * Multi-platform GPU detection (NVIDIA CUDA, AMD ROCm, Apple Metal)
    * Automatic GPU configuration for Ollama (PR #176, Issue #169)
    * Hardware metrics display in output (GPU model, VRAM, driver version)
    * `GPUDetector` class for cross-platform GPU discovery
  * **Model Management:**
    * Ollama model auto-download functionality (PR #175, Issue #168)
    * Model availability checking before inference
    * Interactive setup scripts: `setup_ollama.sh`, `download_ollama_models.sh`
  * **Testing & Quality:**
    * Comprehensive test coverage for all providers (93%+ per provider)
    * Integration tests with actual provider APIs
    * Mock testing for CI/CD environments
  * **New Dependencies:** `anthropic==0.74.0`, improved Ollama integration
* **V2.0 Phase 3**: CLI Integration Polish ✅ COMPLETE (Issue #117, Closed Nov 11, 2025)
  * **Zero-Config Presets:** 5 instant-setup presets via `--llm-preset` flag (PR #166)
    * `codex-cli-free` - GitHub Copilot subscription (free)
    * `ollama-local` - Local Ollama with GPU support (free, private)
    * `claude-cli-sonnet` - Claude subscription (free)
    * `openai-api-mini` - GPT-4o-mini pay-per-use (~$0.15/1M tokens)
    * `anthropic-api-balanced` - Claude Haiku balanced cost/performance (~$0.25/1M tokens)
  * **Configuration System:** (PR #158, Sub-Issue #117.2)
    * Configuration precedence chain: CLI flags > Environment variables > Config file > Presets > Defaults
    * Support for YAML and TOML configuration files
    * Environment variable interpolation with `${VAR}` syntax
    * Security: Direct API keys in config files rejected, must use `${VAR}` references
    * Configuration validation with helpful error messages
  * **Enhanced CLI Experience:** (PR #160, Issue #152)
    * Provider-specific error messages with actionable resolution steps
    * Cost tracking and metrics display after each run
    * Configuration summary display before execution
    * Provider authentication setup guides in documentation
  * **LLM Preset System:** (PR #156, Issue #150)
    * Preset configurations with sensible defaults per use case
    * Easy switching between providers via single flag
    * Automatic provider validation and health checks
  * **Documentation:**
    * `.env.example` updated with all LLM-related environment variables
    * Comprehensive preset documentation in `docs/llm-configuration.md`
    * Provider setup guides for each LLM provider
* **V2.0 Phase 4**: Documentation & Developer Experience ✅ COMPLETE (Issue #120, Closed Nov 19, 2025)
  * **All sub-issues completed (6/6):**
    * ✅ HTTP connection pooling and optimization (PR #173, Sub-Issue #167, Nov 12, 2025)
      * `requests.Session()` for connection reuse and keep-alive
      * 10 connections per pool for concurrent requests
      * Enhanced error handling and timeout configuration
    * ✅ Ollama model auto-download automation (PR #175, Sub-Issue #168, Nov 12, 2025)
      * Automatic model availability checking
      * Python API integration for model downloads
      * Setup scripts with interactive prompts
      * 350+ lines of comprehensive Ollama documentation
    * ✅ GPU acceleration support and detection (PR #176, Sub-Issue #169, Nov 14, 2025)
      * Multi-tier GPU detection (NVIDIA, AMD, Apple Silicon)
      * Automatic hardware capability discovery
      * GPU metrics integrated into output display
      * Cross-platform compatibility (Linux, macOS, Windows)
    * ✅ Performance benchmarking infrastructure (PR #199, Sub-Issue #170, Nov 10, 2025)
      * Standardized benchmarking framework for all 5 LLM providers
      * Performance metrics collection and analysis
      * Cost tracking and comparison across providers
      * Automated benchmarking scripts for consistent measurements
    * ✅ Privacy documentation for local LLM operation (PR #201, Sub-Issue #171, Nov 11, 2025)
      * Complete privacy architecture documentation (655 lines)
      * Privacy FAQ addressing common misconceptions (575 lines)
      * Privacy verification script with network monitoring (554 lines)
      * GDPR, HIPAA, SOC2 compliance guidance
      * Honest messaging: "reduces third-party LLM vendor exposure" (not air-gapped/offline)
      * Clarifies that GitHub API access is required for PR operations
    * ✅ Offline integration tests (Sub-Issue #172) - Closed as not feasible (air-gapped operation not possible due to GitHub API requirement)
* **V2.0 Phase 5**: Optimization & Production Readiness 🔄 IN PROGRESS (Issue #119, 75% Complete)
  * **Week 1: Parallel Processing (100% Complete)**
    * Concurrent LLM comment parsing with ThreadPoolExecutor
    * `parse_comments_parallel()` method in CommentParser (parallel_parser.py)
    * Thread-safe result collection and error handling
    * Configurable via `--parallel` and `--max-workers` flags
    * 42 comprehensive unit tests for parallel parsing functionality
    * Performance improvements for multi-comment PRs
  * **Week 2: Prompt Caching (100% Complete)**
    * `PromptCache` class for cross-request caching (cache.py)
    * SHA-256 based cache keys with collision detection
    * LRU eviction policy with configurable max size (default: 1000 entries)
    * TTL expiration (default: 1 hour) with automatic cleanup
    * Cache warming and preloading via `CacheOptimizer` (cache_optimizer.py)
    * Thread-safe operations with `threading.Lock()`
    * Integration with all 5 LLM providers
    * 35 integration tests for caching functionality
    * Significant cost reduction for repeated prompts (especially beneficial for Anthropic API with native prompt caching)
  * **Week 3: Circuit Breaker & Resilience (100% Complete)**
    * `CircuitBreaker` implementation with three-state machine (CLOSED/OPEN/HALF_OPEN)
    * Configurable failure thresholds and recovery timeouts
    * `MetricsAggregator` for centralized metrics tracking across all providers
    * Tracks costs, latency (P50/P95/P99), token usage, error rates per provider/model
    * `ResilientProvider` wrapper combining circuit breaker, metrics, and cost budgeting
    * Cost budget enforcement to prevent runaway expenses
    * Thread-safe metrics with reentrant locks (RLock)
    * 83 comprehensive tests (29 circuit breaker + 22 metrics aggregator + 15 resilient provider + 17 integration)
    * Deadlock bug fixed in metrics export functionality
  * **Week 4: Security & Documentation (0% Complete) - IN PROGRESS**
    * Comprehensive security audit
    * Optimization guides and cost optimization documentation
    * Updated CHANGELOG, README, and configuration documentation
    * Security test suite and acceptance criteria validation
* **Phase 1**: Core functionality to apply ALL suggestions (Issue #14)
  * `ConflictResolver.separate_changes_by_conflict_status()` - Separate conflicting vs non-conflicting changes
  * `ConflictResolver.apply_changes()` - Apply changes with validation and batch processing
  * `ConflictResolver.resolve_pr_conflicts()` - Enhanced with application mode support (`all`, `conflicts-only`, `non-conflicts-only`)
  * Enhanced `ResolutionResult` model with detailed counters for conflicting/non-conflicting changes
  * Unit tests for change separation and application logic (80%+ coverage achieved)
* **Phase 2**: Git-based rollback system for safe change application (Issue #14)
  * `RollbackManager` class for checkpoint/rollback functionality using git stash
  * `ConflictResolver.apply_changes_with_rollback()` - Apply changes with automatic rollback on failure
  * Comprehensive integration tests for RollbackManager (17 tests)
  * Support for empty checkpoints and untracked file cleanup
  * Context manager pattern for automatic rollback on exceptions
* **Phase 2: CLI Enhancements - Multiple Modes & Configuration** (Issue #15)
  * `RuntimeConfig` system for flexible configuration management (runtime_config.py)
    * Support for environment variables (`CR_*` prefix), config files (YAML/TOML), and CLI flags
    * Configuration precedence: CLI flags > env vars > config file > defaults
    * Immutable dataclass with `frozen=True` and `slots=True` for efficiency
  * `ApplicationMode` enum with four execution modes:
    * `all` - Apply both conflicting and non-conflicting changes (default)
    * `conflicts-only` - Apply only changes with conflicts after resolution
    * `non-conflicts-only` - Apply only non-conflicting changes
    * `dry-run` - Analyze conflicts without applying any changes
  * Parallel processing support for improved performance (experimental)
    * `ConflictResolver._apply_changes_parallel()` - Thread-safe parallel change application
    * ThreadPoolExecutor with configurable worker threads (default: 4, recommended: 4-8)
    * Thread-safe collections with locks for data integrity
    * Maintains result order across parallel execution
  * Enhanced CLI with comprehensive configuration flags:
    * `--mode` - Select application mode
    * `--config` - Load configuration from YAML/TOML file
    * `--parallel` / `--max-workers` - Enable and configure parallel processing
    * `--no-rollback` / `--no-validation` - Disable safety features (not recommended)
    * `--log-level` / `--log-file` - Configure logging
  * `.env.example` template with comprehensive documentation of all configuration options
  * Comprehensive unit tests for RuntimeConfig (54 tests, 79% coverage)
    * Tests for defaults, environment variables, file loading (YAML/TOML), validation, merging, precedence
  * Enhanced documentation in docs/configuration.md with runtime configuration examples
* Initial repository structure and architecture
* Comprehensive documentation framework
* GitHub Actions CI/CD pipeline
* Pre-commit hooks for code quality
* Test infrastructure and fixtures
* Issue templates for bug reports, feature requests, and conflict reports
* MIT License

### Changed

* **Dependency Updates** (PRs #203-209, Nov 2025):
  * Updated `openai` from 2.8.0 to 2.8.1 (PR #203)
  * Updated `hypothesis` from 6.148.1 to 6.148.2 (PR #204)
  * Updated `anthropic` from 0.73.0 to 0.74.0 (PR #206)
  * Updated Docker base images (PRs #205, #207)
  * Synchronized source files (requirements.in, requirements-dev.in, .pre-commit-config.yaml) with Renovate updates (PRs #208, #209)
  * Regenerated requirements.txt and requirements-dev.txt with updated hashes
* Enhanced `ResolutionResult` to track conflicting vs non-conflicting changes separately
* Updated unit tests for change separation logic
* **CLI Enhancement** (Issue #15):
  * Enhanced `ConflictResolver.apply_changes()` to support parallel processing with `parallel` and `max_workers` parameters
  * Updated `ConflictResolver.apply_changes_with_rollback()` to pass through parallel processing parameters
  * Enhanced `pr-resolve apply` command with comprehensive configuration options
  * Deprecated `--dry-run` flag in favor of `--mode=dry-run` (backwards compatible with deprecation warning)
  * Improved CLI output with configuration summary display

### Deprecated

* N/A

### Removed

* N/A

### Fixed

* **CodeRabbit Feedback**: Success rate metric now correctly counts non-conflicting failures/skips (resolver.py:958)
  * Prevents incorrect 100% success_rate when validation skips or failures occur in non-conflicting changes
  * Includes non_conflicting_failed + non_conflicting_skipped in total_conflicts for accurate metrics
* **CodeRabbit Critical**: Fixed git stash command in RollbackManager (rollback.py:176-204)
  * Changed from `git stash create --include-untracked` (unsupported flag) to `git stash push --include-untracked`
  * Now captures stash ref with `git rev-parse stash@{0}` and immediately reapplies to restore working directory
  * Properly drops stash on both commit() and rollback() for cleanup
  * Addresses CodeRabbit review feedback about silent failures when untracked files exist
* ClusterFuzzLite build script fixes:
  * Fixed all path references from `/src` to `/src/review-bot-automator` (build.sh:21, 26, 32, 39)
  * Added mdurl==0.1.2 dependency to requirements-py311.txt (required by markdown-it-py)
  * Documented security rationale for local package installation without --require-hashes (build.sh:25-29)
  * Fixes pr-fuzz (address) and pr-fuzz (undefined) CI failures
* OSError handling for symlink checks in path validation (resolver.py:580-582)
* Clarified rollback behavior comments for better code maintainability
* Improved variable naming for intentionally unused values

### Security

* Path validation in RollbackManager using defense-in-depth approach
* Separate validation layers for user input vs internal paths
* Prevents data loss during rollback operations by capturing all file states

## [0.1.0] - 2025-01-01

### Added (0.1.0)

* Initial release
* Basic repository structure
* Documentation framework
* CI/CD pipeline setup
* Test infrastructure

[Unreleased]: https://github.com/VirtualAgentics/review-bot-automator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/VirtualAgentics/review-bot-automator/releases/tag/v0.1.0
