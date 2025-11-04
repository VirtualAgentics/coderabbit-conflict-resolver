# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Phase 1**: Core functionality to apply ALL suggestions (Issue #14)
  - `ConflictResolver.separate_changes_by_conflict_status()` - Separate conflicting vs non-conflicting changes
  - `ConflictResolver.apply_changes_batch()` - Apply changes in batches with mode support
  - `ConflictResolver.apply_non_conflicting_changes_only()` - Apply only non-conflicting suggestions
  - `ConflictResolver.apply_all_changes()` - Apply all suggestions (conflicting + non-conflicting)
  - Enhanced `ResolutionResult` model with detailed counters for conflicting/non-conflicting changes
  - Support for application modes: `all`, `conflicts-only`, `non-conflicts-only`
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
- OSError handling for symlink checks in path validation (resolver.py:580-582)
- Clarified rollback behavior comments for better code maintainability
- Improved variable naming for intentionally unused values

### Security
- Path validation in RollbackManager using defense-in-depth approach
- Separate validation layers for user input vs internal paths

## [0.1.0] - 2025-01-01

### Added
- Initial release
- Basic repository structure
- Documentation framework
- CI/CD pipeline setup
- Test infrastructure

[Unreleased]: https://github.com/VirtualAgentics/coderabbit-conflict-resolver/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/VirtualAgentics/coderabbit-conflict-resolver/releases/tag/v0.1.0
