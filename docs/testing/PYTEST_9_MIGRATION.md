# pytest 9.0 Migration Guide

## Executive Summary

This document chronicles the migration from pytest <9.0 to **pytest 9.0.0** with native subtests support. The migration was completed over 6 weeks, resulting in **76 subtests** across **14 test methods** in **6 test files**, while maintaining **86.92% test coverage** and all 1318 tests passing.

### Quick Stats

* **Timeline:** 6 weeks (phased migration)
* **Subtests Created:** 76 individual subtests
* **Test Methods Migrated:** 14 methods
* **Files Modified:** 6 test files
* **Code Changes:** +170 insertions, -143 deletions
* **Coverage:** 86.92% (maintained, exceeds 80% minimum)
* **All Tests:** ✅ Passing (1318 tests, 10 skipped)

## Migration Timeline

### Week 1: Foundation & Security Tests

**Branch:** `feature/pytest-9-subtests`
**Commit:** `1a4b057`

#### Changes

* Upgraded pytest to 9.0.0
* Enabled strict mode in pytest configuration
* Migrated security tests to native subtests
* Established subtest patterns and best practices

#### Impact

* Baseline subtests created
* Testing patterns established
* No regressions introduced

### Week 2-3: Configuration & CLI Tests

**Commits:** `a7f0b16`

#### Files Modified

1. `tests/unit/test_runtime_config.py` (22 changes)
   * 2 methods → 10 subtests
   * Boolean configuration value variants

2. `tests/unit/test_cli_validation.py` (49 changes)
   * 3 methods → 16 subtests
   * Path traversal and absolute path rejection tests

3. `tests/security/test_input_validation.py` (49 changes)
   * 3 methods → 10 subtests
   * Unix/Windows path traversal, unsafe character detection

#### Impact: (DeprecationWarning)

* +36 subtests created
* Improved CLI validation test coverage
* Better test isolation for configuration tests

#### Technical Achievement

* Resolved Ruff SIM117 linting issue (nested with statements)
* Adopted Python 3.10+ parenthesized context manager syntax:

  ```python
  with (
      subtests.test(msg=..., **context),
      patch.dict(os.environ, {...}),
  ):
      # Test code

  ```

### Week 4-5: Handlers & Validation Tests

**Commits:** `c9598f0`

#### Files Modified: (Phase 1)

1. `tests/unit/test_handlers.py` (7 changes)
   * 1 method → 5 subtests
   * TOML section extraction validation

2. `tests/security/test_path_traversal.py` (161 changes)
   * 3 methods → 9 subtests
   * Handler-level security validation
   * Absolute path rejection
   * Null byte rejection
   * Symlink attack prevention

#### Impact: (Migration Success)

* +14 subtests created (total: 76 subtests)
* Enhanced handler security validation
* Complex setup/teardown scenarios handled

#### Technical Achievement: (Subtests)

* Successfully migrated tests with complex fixtures
* Maintained test isolation in symlink attack tests
* Zero regression in handler validation

### Week 6: Documentation & Rollout

**Status:** ✅ Complete

#### Documentation Created

1. `docs/testing/TESTING.md` - Comprehensive testing guide
2. `docs/testing/PYTEST_9_MIGRATION.md` - This document
3. `docs/testing/SUBTESTS_GUIDE.md` - Subtests best practices

#### Documentation Updated

* `CONTRIBUTING.md` - Added subtests guidance
* `README.md` - Noted pytest 9.0 upgrade
* `CHANGELOG.md` - Documented migration

#### Validation

* All 1318 tests passing
* Coverage at 86.92%
* All pre-commit hooks passing
* CI/CD validation complete

## What Changed

### pytest Version

#### Before

```toml
[tool.poetry.dependencies]
pytest = "^8.3.0"  # Or earlier

```

#### After

```toml
[tool.poetry.dependencies]
pytest = "^9.0.0"  # Latest version with native subtests

```

### Configuration

#### pyproject.toml changes

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-config",      # NEW: Strict configuration validation
    "--strict-markers",     # NEW: Strict marker validation
    "-ra",
    "--cov=src",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=80"
]

```

### Test Patterns

#### Pattern 1: Multiple Similar Assertions → Subtests

##### Before: (Handler Tests)

```python
def test_path_traversal_unix_case1(self) -> None:
    """Test Unix path traversal case 1."""
    assert not InputValidator.validate_file_path("../../etc/passwd")

def test_path_traversal_unix_case2(self) -> None:
    """Test Unix path traversal case 2."""
    assert not InputValidator.validate_file_path("../../../root/.ssh/id_rsa")

def test_path_traversal_unix_case3(self) -> None:
    """Test Unix path traversal case 3."""
    assert not InputValidator.validate_file_path("./../../etc/shadow")

```

#### After

```python
def test_path_traversal_unix(self, subtests: pytest.Subtests) -> None:
    """Test detection of Unix-style path traversal using subtests."""
    unix_paths = [
        "../../etc/passwd",
        "../../../root/.ssh/id_rsa",
        "./../../etc/shadow",
    ]

    for path in unix_paths:
        with subtests.test(msg=f"Unix path traversal: {path}", path=path):
            assert not InputValidator.validate_file_path(path)

```

#### Benefits

* Reduced from 3 test methods to 1
* All cases run even if one fails
* Easy to add new test cases
* Better failure reporting with context

#### Pattern 2: Loop-Based Tests → Subtests with Context

##### Before: (Pattern 2)

```python
def test_handlers_reject_absolute_paths(
    self, setup_test_files: tuple[Path, Path, Path, str]
) -> None:
    """Test that handlers reject absolute paths."""
    base_path, _, outside_file, _file_type = setup_test_files
    handlers = [
        JsonHandler(workspace_root=str(base_path)),
        YamlHandler(workspace_root=str(base_path)),
        TomlHandler(workspace_root=str(base_path)),
    ]

    for handler in handlers:
        assert not handler.apply_change(
            str(outside_file), "test content", 1, 1
        ), f"{handler.__class__.__name__} should reject absolute paths"

```

#### After: (Pattern 2)

```python
def test_handlers_reject_absolute_paths(
    self, setup_test_files: tuple[Path, Path, Path, str],
    subtests: pytest.Subtests
) -> None:
    """Test that handlers reject absolute paths using subtests."""
    base_path, _, outside_file, _file_type = setup_test_files
    handlers = [
        JsonHandler(workspace_root=str(base_path)),
        YamlHandler(workspace_root=str(base_path)),
        TomlHandler(workspace_root=str(base_path)),
    ]

    for handler in handlers:
        with subtests.test(
            msg=f"Handler: {handler.__class__.__name__}",
            handler=handler.__class__.__name__
        ):
            assert not handler.apply_change(
                str(outside_file), "test content", 1, 1
            ), f"{handler.__class__.__name__} should reject absolute paths"

```

#### Benefits: (Pattern 2)

* Each handler tested independently
* Failure clearly indicates which handler failed
* Context variables aid debugging
* All handlers tested even if one fails

#### Pattern 3: Configuration Variants → Subtests with Environment Patching

##### Before: (Pattern 3)

```python
def test_from_env_enable_rollback_true(self) -> None:
    """Test enable_rollback=true."""
    with patch.dict(os.environ, {"CR_ENABLE_ROLLBACK": "true"}):
        config = RuntimeConfig.from_env()
        assert config.enable_rollback is True

def test_from_env_enable_rollback_1(self) -> None:
    """Test enable_rollback=1."""
    with patch.dict(os.environ, {"CR_ENABLE_ROLLBACK": "1"}):
        config = RuntimeConfig.from_env()
        assert config.enable_rollback is True

# ... more variants

```

#### After: (Pattern 3)

```python
def test_from_env_enable_rollback_true_variants(
    self, subtests: pytest.Subtests
) -> None:
    """Test various true values using subtests."""
    for value in ["true", "True", "1", "yes", "on"]:
        with (
            subtests.test(msg=f"Boolean true variant: {value}", value=value),
            patch.dict(os.environ, {"CR_ENABLE_ROLLBACK": value}),
        ):
            config = RuntimeConfig.from_env()
            assert config.enable_rollback is True

```

#### Benefits: (Pattern 3)

* Reduced 5 test methods to 1
* Easy to test additional boolean variants
* Combined context managers (Python 3.10+)
* Clear which variant failed

## Benefits Achieved

### 1. Improved Test Organization

#### Metrics

* **Before:** 20+ scattered test methods for similar scenarios
* **After:** 14 consolidated test methods with 76 subtests
* **Reduction:** ~30% fewer test methods
* **Clarity:** Related test cases grouped logically

### 2. Better Failure Reporting

#### Before

```text
FAILED tests/security/test_input_validation.py::test_path_traversal_unix_case2

```

#### After

```text
SUBFAIL tests/security/test_input_validation.py::test_path_traversal_unix
[Unix path traversal: ../../../root/.ssh/id_rsa] (path='../../../root/.ssh/id_rsa')

```

#### Benefits

* Immediate context about what failed
* Debugging variables included
* Descriptive failure messages
* Easier to reproduce failures

### 3. Enhanced Test Coverage

#### Comprehensive Testing

* All test cases run even if one fails
* Easier to add edge cases
* No test omission due to early failures

#### Example Impact

```python
# If case 2 fails with parametrize, cases 3-5 might not run
# With subtests, all 5 cases always run and report independently

```

### 4. Developer Experience

#### Writing Tests

* Less boilerplate code
* Consistent patterns across codebase
* Easy to extend existing tests

#### Maintaining Tests

* Fewer files to update when patterns change
* Clear test organization
* Self-documenting test structure

#### Debugging Tests

* Contextual failure information
* Clear test case identification
* Easier to isolate failures

## Breaking Changes & Compatibility

### No Breaking Changes

This migration **does not** introduce breaking changes:

* ✅ All existing tests remain compatible
* ✅ Production code unchanged
* ✅ Public APIs unchanged
* ✅ CLI interface unchanged
* ✅ Configuration format unchanged

### pytest 9.0 Compatibility

#### Compatible with

* Python 3.8+
* All pytest plugins used in this project
* Existing parametrize decorators (can coexist with subtests)
* Existing fixtures and markers

#### Behavior Changes

* Strict mode catches configuration/marker errors earlier
* Subtest failures report differently (more detailed)
* Test execution order unchanged

## Migration Statistics by File

### Detailed Changes

| File | Methods Changed | Subtests Added | Lines Modified | Primary Focus |
| ------ | ---------------- | ---------------- | ---------------- | --------------- |
| `test_runtime_config.py` | 2 | 10 | 22 | Boolean config variants |
| `test_cli_validation.py` | 3 | 16 | 49 | Path validation |
| `test_input_validation.py` | 3 | 10 | 49 | Security validation |
| `test_path_traversal.py` | 3 | 9 | 161 | Handler security |
| `test_handlers.py` | 1 | 5 | 7 | Section extraction |
| `test_cli_security.py` | 2 | 26 | 25 | CLI security |
| **TOTAL** | **14** | **76** | **313** | **All aspects** |

### Coverage Impact

#### Coverage Stability

* **Before migration:** 86.98%
* **After migration:** 86.92%
* **Change:** -0.06% (negligible, within normal variance)
* **Status:** ✅ Exceeds 80% minimum requirement

#### Test Count

* **Total tests:** 1318 passing
* **Skipped tests:** 10 (platform-specific, permissions-based)
* **Subtests:** 76 (reported separately)
* **Execution time:** ~66-68 seconds (local)

## Lessons Learned

### Technical Insights

#### 1. Context Manager Combining (Python 3.10+)

Lesson: Use parenthesized syntax for multiple context managers to satisfy Ruff SIM117.

```python
# ✅ Good - Combined with parentheses
with (
    subtests.test(msg=..., **context),
    patch.dict(os.environ, {...}),
):
    # Test code

# ❌ Bad - Nested (Ruff SIM117 violation)
with subtests.test(msg=..., **context):
    with patch.dict(os.environ, {...}):
        # Test code

```

#### 2. Subtest Naming Strategy

Lesson: Include both descriptive message and context variables.

```python
# ✅ Good - Descriptive + context
with subtests.test(
    msg=f"Unix path traversal: {path}",
    path=path,
    category="security"
):
    assert not validate(path)

# ❌ Less useful - Only message
with subtests.test(msg=f"Test {path}"):
    assert not validate(path)

```

#### 3. Decision Matrix for Subtests vs Parametrize

Lesson: Not all loops should become subtests.

#### Use subtests when

* ≥4 test cases
* Dynamic test data
* Expensive setup/teardown shared
* Want all cases to run on failure

#### Use parametrize when

* <4 static test cases
* Want separate test per case in reports
* No shared expensive setup

### Process Insights

#### 1. Phased Migration Approach

✅ **What worked well:**

* Week-by-week migration prevented overwhelming changes
* Clear focus areas (security → config → handlers)
* Easy to review and validate each phase
* Minimal disruption to ongoing development

#### 2. Documentation-First Planning

✅ **What worked well:**

* Documented decision matrix before migration
* Established patterns early
* Created examples for team reference
* Reduced questions and inconsistencies

#### 3. Continuous Validation

✅ **What worked well:**

* Ran full test suite after each change
* Maintained coverage throughout
* Pre-commit hooks caught issues early
* CI validation on every commit

### Recommendations for Future Migrations

#### 1. Start Small

* Begin with 1-2 files to establish patterns
* Get team feedback before scaling
* Document patterns as you discover them

#### 2. Automate Where Possible

* Use linters to catch common issues
* Pre-commit hooks enforce consistency
* CI validation catches regressions

#### 3. Prioritize High-Value Areas

* Migrate tests with many similar methods first
* Focus on tests that fail often
* Target areas with poor failure reporting

#### 4. Communicate Changes

* Update documentation alongside code
* Provide examples in CONTRIBUTING.md
* Host knowledge-sharing sessions

## Migration Checklist

For teams performing similar migrations:

### Preparation

* [ ] Audit current test suite
* [ ] Identify tests suitable for subtests
* [ ] Document migration plan
* [ ] Establish patterns and examples
* [ ] Get team buy-in

### Execution

* [ ] Upgrade pytest to 9.0.0
* [ ] Enable strict mode
* [ ] Migrate tests in phases
* [ ] Run full test suite after each phase
* [ ] Monitor coverage
* [ ] Address linter feedback

### Documentation

* [ ] Update testing guide
* [ ] Document migration journey
* [ ] Create subtests best practices guide
* [ ] Update CONTRIBUTING.md
* [ ] Update CHANGELOG.md

### Validation

* [ ] All tests passing
* [ ] Coverage maintained/improved
* [ ] CI/CD passing
* [ ] Team training complete
* [ ] Documentation reviewed

### Rollout

* [ ] Create PR with comprehensive description
* [ ] Get peer review
* [ ] Merge to main
* [ ] Monitor for issues
* [ ] Gather feedback

## Conclusion

The pytest 9.0 migration was **highly successful**, achieving all objectives:

✅ **76 subtests** created across 14 test methods
✅ **86.92% coverage** maintained (exceeds 80% minimum)
✅ **All 1318 tests** passing
✅ **Zero breaking changes**
✅ **Improved test organization** and readability
✅ **Better failure reporting** with context
✅ **Enhanced developer experience**

The migration provides a **solid foundation** for future testing improvements and sets a **high standard** for test quality in the project.

## Related Documentation

* [Testing Guide](TESTING.md) - Comprehensive testing documentation
* [Subtests Guide](SUBTESTS_GUIDE.md) - Detailed subtests best practices
* [CONTRIBUTING.md](../../CONTRIBUTING.md) - Contribution guidelines
* [Security Testing](../security/security-testing.md) - Security testing practices

## Support

For questions or issues related to the pytest 9.0 migration:

* Check the [Subtests Guide](SUBTESTS_GUIDE.md) for patterns and examples
* Review existing migrated tests for reference
* Consult the team's testing documentation
* Open an issue on GitHub for bugs or improvements
