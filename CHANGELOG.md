# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Phase 1**: Core functionality to apply ALL suggestions (Issue #14)
  - `ConflictResolver.separate_changes_by_conflict_status()` - Separate conflicting vs non-conflicting changes
  - `ConflictResolver.apply_changes()` - Apply changes with validation and batch processing
  - `ConflictResolver.resolve_pr_conflicts()` - Enhanced with application mode support (`all`, `conflicts-only`, `non-conflicts-only`)
  - Enhanced `ResolutionResult` model with detailed counters for conflicting/non-conflicting changes
  - Unit tests for change separation and application logic (80%+ coverage achieved)
- **Phase 2**: Git-based rollback system for safe change application (Issue #14)
  - `RollbackManager` class for checkpoint/rollback functionality using git stash
  - `ConflictResolver.apply_changes_with_rollback()` - Apply changes with automatic rollback on failure
  - Comprehensive integration tests for RollbackManager (17 tests)
  - Support for empty checkpoints and untracked file cleanup
  - Context manager pattern for automatic rollback on exceptions
- Initial repository structure and architecture
- Comprehensive documentation framework
- GitHub Actions CI/CD pipeline
- Pre-commit hooks for code quality
- Test infrastructure and fixtures
- Issue templates for bug reports, feature requests, and conflict reports
- MIT License

### Changed
- Enhanced `ResolutionResult` to track conflicting vs non-conflicting changes separately
- Updated unit tests for change separation logic

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- **CodeRabbit Feedback**: Success rate metric now correctly counts non-conflicting failures/skips (resolver.py:958)
  - Prevents incorrect 100% success_rate when validation skips or failures occur in non-conflicting changes
  - Includes non_conflicting_failed + non_conflicting_skipped in total_conflicts for accurate metrics
- **CodeRabbit Critical**: Fixed git stash command in RollbackManager (rollback.py:176-204)
  - Changed from `git stash create --include-untracked` (unsupported flag) to `git stash push --include-untracked`
  - Now captures stash ref with `git rev-parse stash@{0}` and immediately reapplies to restore working directory
  - Properly drops stash on both commit() and rollback() for cleanup
  - Addresses CodeRabbit review feedback about silent failures when untracked files exist
- ClusterFuzzLite build script fixes:
  - Fixed all path references from `/src` to `/src/coderabbit-conflict-resolver` (build.sh:21, 26, 32, 39)
  - Added mdurl==0.1.2 dependency to requirements-py311.txt (required by markdown-it-py)
  - Documented security rationale for local package installation without --require-hashes (build.sh:25-29)
  - Fixes pr-fuzz (address) and pr-fuzz (undefined) CI failures
- OSError handling for symlink checks in path validation (resolver.py:580-582)
- Clarified rollback behavior comments for better code maintainability
- Improved variable naming for intentionally unused values

### Security
- Path validation in RollbackManager using defense-in-depth approach
- Separate validation layers for user input vs internal paths
- Prevents data loss during rollback operations by capturing all file states

## [0.1.0] - 2025-01-01

### Added
- Initial release
- Basic repository structure
- Documentation framework
- CI/CD pipeline setup
- Test infrastructure

[Unreleased]: https://github.com/VirtualAgentics/coderabbit-conflict-resolver/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/VirtualAgentics/coderabbit-conflict-resolver/releases/tag/v0.1.0
