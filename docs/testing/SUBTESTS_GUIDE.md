# pytest Subtests Guide

## Table of Contents

* [Introduction](#introduction)
* [When to Use Subtests](#when-to-use-subtests)
* [When NOT to Use Subtests](#when-not-to-use-subtests)
* [Basic Subtest Pattern](#basic-subtest-pattern)
* [Advanced Patterns](#advanced-patterns)
* [Best Practices](#best-practices)
* [Examples from Codebase](#examples-from-codebase)
* [Common Pitfalls](#common-pitfalls)
* [Migration Guide](#migration-guide)

## Introduction

**Subtests** are a pytest 9.0 feature that allows you to run multiple test cases within a single test method, with each case reported independently. They provide better test organization and failure reporting compared to traditional approaches.

### What are Subtests?

Subtests allow you to:

* Run multiple related test cases in a single test method
* Get independent failure reporting for each case
* Continue testing even if one case fails
* Share expensive setup/teardown across cases
* Provide contextual information for debugging

### Why Use Subtests?

**Traditional approach (separate test methods):**

```python
def test_validates_path_case1(self) -> None:
    assert validate("path1")

def test_validates_path_case2(self) -> None:
    assert validate("path2")

def test_validates_path_case3(self) -> None:
    assert validate("path3")

```

**Problems:**

* Lots of boilerplate
* Hard to add new test cases
* Unclear relationship between tests
* Expensive setup runs multiple times

**Subtest approach:**

```python
def test_validates_paths(self, subtests: pytest.Subtests) -> None:
    """Test path validation using subtests."""
    paths = ["path1", "path2", "path3"]

    for path in paths:
        with subtests.test(msg=f"Validating: {path}", path=path):
            assert validate(path)

```

**Benefits:**

* Less boilerplate
* Easy to add test cases
* Clear test organization
* Setup runs once
* All cases run even if one fails

## When to Use Subtests

### Decision Tree

```text
Is this a test with multiple similar test cases?
├─ NO → Use a single test method
└─ YES → Continue...
    │
    Are there ≥4 test cases?
    ├─ NO → Continue to next question
    │   │
    │   Are test cases dynamic (from file/API/etc)?
    │   ├─ YES → ✅ USE SUBTESTS
    │   └─ NO → ❌ USE PARAMETRIZE
    │
    └─ YES → Continue...
        │
        Do cases share expensive setup/teardown?
        ├─ YES → ✅ USE SUBTESTS
        └─ NO → Continue...
            │
            Do you want all cases to run even if one fails?
            ├─ YES → ✅ USE SUBTESTS
            └─ NO → ⚠️ USE PARAMETRIZE (or subtests if preferred)

```

### Use Cases

#### 1. Testing Multiple Input Variations

**When:** You have many similar inputs to test

```python
def test_rejects_invalid_paths(self, subtests: pytest.Subtests) -> None:
    """Test that various invalid paths are rejected."""
    invalid_paths = [
        ("Path traversal", "../../../etc/passwd"),
        ("Absolute path", "/etc/passwd"),
        ("Windows path", "C:\\Windows\\System32"),
        ("Null byte", "file\x00.txt"),
        ("Too long", "a" * 10000),
    ]

    for description, path in invalid_paths:
        with subtests.test(msg=f"{description}: {path}", path=path):
            assert not InputValidator.validate_file_path(path)

```

#### 2. Testing Multiple Implementations

**When:** Testing the same behavior across multiple implementations

```python
def test_handlers_reject_malicious_input(self, subtests: pytest.Subtests) -> None:
    """Test that all handlers reject malicious input."""
    handlers = [
        ("JSON", JsonHandler()),
        ("YAML", YamlHandler()),
        ("TOML", TomlHandler()),
    ]
    malicious_input = "../../../etc/passwd"

    for name, handler in handlers:
        with subtests.test(msg=f"Handler: {name}", handler=name):
            assert not handler.apply_change(malicious_input, "content", 1, 1)

```

#### 3. Testing Configuration Variants

**When:** Testing different configuration values

```python
def test_from_env_boolean_true_variants(self, subtests: pytest.Subtests) -> None:
    """Test various boolean true values."""
    true_values = ["true", "True", "TRUE", "1", "yes", "on"]

    for value in true_values:
        with (
            subtests.test(msg=f"Boolean value: {value}", value=value),
            patch.dict(os.environ, {"CONFIG_FLAG": value}),
        ):
            config = Config.from_env()
            assert config.flag is True

```

#### 4. Testing Platform-Specific Behavior

**When:** Testing behavior across different platforms/environments

```python
def test_path_validation_cross_platform(self, subtests: pytest.Subtests) -> None:
    """Test path validation for different platforms."""
    test_cases = [
        ("Unix absolute", "/etc/passwd", False),
        ("Windows absolute", "C:\\Windows", False),
        ("UNC path", "\\\\server\\share", False),
        ("Relative safe", "config.json", True),
    ]

    for description, path, should_validate in test_cases:
        with subtests.test(msg=description, path=path):
            result = validate_path(path)
            assert result == should_validate

```

#### 5. Testing Edge Cases

**When:** You have many edge cases to verify

```python
def test_handles_unicode_edge_cases(self, subtests: pytest.Subtests) -> None:
    """Test handling of Unicode edge cases."""
    edge_cases = [
        ("Empty string", ""),
        ("Null byte", "\x00"),
        ("Zero-width space", "\u200b"),
        ("RTL override", "\u202e"),
        ("Fullwidth dots", "\uff0e\uff0e"),
        ("Combining characters", "e\u0301"),  # é
    ]

    for description, text in edge_cases:
        with subtests.test(msg=f"Edge case: {description}", input=text):
            result = sanitize_input(text)
            assert is_safe(result)

```

## When NOT to Use Subtests

### Use `@pytest.mark.parametrize` Instead

#### 1. Small, Static Test Sets (< 4 cases)

**❌ Don't use subtests:**

```python
def test_boolean_parsing(self, subtests: pytest.Subtests) -> None:
    for value, expected in [("true", True), ("false", False)]:
        with subtests.test(value=value):
            assert parse_bool(value) == expected

```

**✅ Use parametrize:**

```python
@pytest.mark.parametrize("value,expected", [
    ("true", True),
    ("false", False),
])
def test_boolean_parsing(value: str, expected: bool) -> None:
    assert parse_bool(value) == expected

```

**Why:** Parametrize is clearer for small, static sets and shows each case as a separate test in reports.

#### 2. When You Want Separate Test Reports

**❌ Don't use subtests if:**

* You want each case to appear as a separate test in CI reports
* You're tracking test counts as a metric
* You need fine-grained test selection (e.g., `pytest -k case1`)

**✅ Use parametrize for:**

* Separate test entries in reports
* Better test discovery
* Individual test selection

### Use Separate Test Methods Instead

#### 1. Unrelated Test Logic

**❌ Don't use subtests:**

```python
def test_user_operations(self, subtests: pytest.Subtests) -> None:
    """Test various user operations."""
    with subtests.test("create"):
        user = create_user("alice")
        assert user.name == "alice"

    with subtests.test("delete"):
        delete_user(user_id=123)
        assert not user_exists(123)

    with subtests.test("update"):
        update_user(456, name="bob")
        assert get_user(456).name == "bob"

```

**✅ Use separate tests:**

```python
def test_create_user(self) -> None:
    user = create_user("alice")
    assert user.name == "alice"

def test_delete_user(self) -> None:
    delete_user(user_id=123)
    assert not user_exists(123)

def test_update_user(self) -> None:
    update_user(456, name="bob")
    assert get_user(456).name == "bob"

```

**Why:** These are independent test cases with different logic, not variations of the same test.

#### 2. Tests with Different Fixtures

**❌ Don't use subtests:**

```python
def test_with_different_setups(
    self,
    subtests: pytest.Subtests,
    tmp_path: Path,
    mock_api: Mock,
) -> None:
    with subtests.test("uses tmp_path"):
        # Only uses tmp_path
        file = tmp_path / "test.txt"
        assert file.exists()

    with subtests.test("uses mock_api"):
        # Only uses mock_api
        mock_api.return_value = "data"
        assert fetch_data() == "data"

```

**✅ Use separate tests:**

```python
def test_file_operations(tmp_path: Path) -> None:
    file = tmp_path / "test.txt"
    assert file.exists()

def test_api_operations(mock_api: Mock) -> None:
    mock_api.return_value = "data"
    assert fetch_data() == "data"

```

## Basic Subtest Pattern

### Minimal Example

```python
def test_with_subtests(self, subtests: pytest.Subtests) -> None:
    """Test description."""
    test_cases = [
        # (input, expected)
        ("input1", "expected1"),
        ("input2", "expected2"),
        ("input3", "expected3"),
    ]

    for input_val, expected in test_cases:
        with subtests.test(msg=f"Testing: {input_val}", input=input_val):
            result = function_under_test(input_val)
            assert result == expected

```

### Key Components

1. **Fixture Parameter:** `subtests: pytest.Subtests`
   * Injects the subtests fixture into your test

2. **Context Manager:** `with subtests.test(...)`
   * Creates an isolated subtest context

3. **Message:** `msg="Descriptive message"`
   * Shown in failure reports (required for clarity)

4. **Context Variables:** `**kwargs` (e.g., `input=input_val`)
   * Included in failure reports for debugging

### Complete Pattern

```python
def test_example(self, subtests: pytest.Subtests) -> None:
    """Test example showing complete pattern."""
    # 1. Define test cases
    test_cases = [
        ("case1", "expected1"),
        ("case2", "expected2"),
    ]

    # 2. Loop through test cases
    for case_input, expected_output in test_cases:
        # 3. Create subtest with descriptive message and context
        with subtests.test(
            msg=f"Testing case: {case_input}",  # Descriptive message
            input=case_input,                   # Context for debugging
            expected=expected_output            # More context
        ):
            # 4. Execute test logic
            result = function_to_test(case_input)

            # 5. Make assertion
            assert result == expected_output, \
                f"Expected {expected_output}, got {result}"

```

## Advanced Patterns

### Pattern 1: Multiple Context Managers

Combine subtests with other context managers using Python 3.10+ syntax:

```python
def test_with_multiple_contexts(self, subtests: pytest.Subtests) -> None:
    """Test with multiple context managers."""
    configs = [("dev", 8080), ("prod", 443)]

    for env, port in configs:
        with (
            subtests.test(msg=f"Environment: {env}", env=env, port=port),
            patch.dict(os.environ, {"ENV": env, "PORT": str(port)}),
            tempfile.TemporaryDirectory() as tmpdir,
        ):
            config = load_config()
            assert config.port == port
            assert Path(tmpdir).exists()

```

### Pattern 2: Nested Subtests

Test combinations of parameters:

```python
def test_handler_format_combinations(self, subtests: pytest.Subtests) -> None:
    """Test all handler-format combinations."""
    handlers = [JsonHandler(), YamlHandler(), TomlHandler()]
    formats = ["compact", "pretty", "minimal"]

    for handler in handlers:
        for fmt in formats:
            with subtests.test(
                msg=f"{handler.__class__.__name__} with {fmt} format",
                handler=handler.__class__.__name__,
                format=fmt
            ):
                result = handler.format_output(data, format=fmt)
                assert is_valid_format(result, fmt)

```

### Pattern 3: Subtests with Setup/Teardown

Share expensive setup across subtests:

```python
def test_database_operations(self, subtests: pytest.Subtests) -> None:
    """Test database operations with shared connection."""
    # Expensive setup (runs once)
    conn = create_database_connection()
    setup_test_data(conn)

    operations = [
        ("insert", lambda: insert_record(conn, {"id": 1})),
        ("update", lambda: update_record(conn, 1, {"name": "updated"})),
        ("delete", lambda: delete_record(conn, 1)),
    ]

    try:
        for op_name, op_func in operations:
            with subtests.test(msg=f"Operation: {op_name}", operation=op_name):
                result = op_func()
                assert result.success
    finally:
        # Cleanup (runs once)
        conn.close()

```

### Pattern 4: Conditional Subtests

Skip subtests based on conditions:

```python
def test_platform_specific_features(self, subtests: pytest.Subtests) -> None:
    """Test platform-specific features."""
    features = [
        ("symlinks", sys.platform != "win32", test_symlinks),
        ("permissions", sys.platform != "win32", test_permissions),
        ("unicode_paths", True, test_unicode_paths),
    ]

    for feature_name, supported, test_func in features:
        with subtests.test(msg=f"Feature: {feature_name}", feature=feature_name):
            if not supported:
                pytest.skip(f"{feature_name} not supported on this platform")

            result = test_func()
            assert result.passed

```

### Pattern 5: Subtests with Fixtures

Use fixtures within subtests:

```python
def test_handlers_with_files(
    self,
    subtests: pytest.Subtests,
    tmp_path: Path
) -> None:
    """Test handlers with temporary files."""
    handlers = [
        ("json", JsonHandler(), "test.json", '{"key": "value"}'),
        ("yaml", YamlHandler(), "test.yaml", "key: value"),
        ("toml", TomlHandler(), "test.toml", 'key = "value"'),
    ]

    for name, handler, filename, content in handlers:
        with subtests.test(msg=f"Handler: {name}", handler=name):
            # Each subtest gets same tmp_path but different file
            test_file = tmp_path / filename
            test_file.write_text(content)

            assert handler.can_handle(str(test_file))
            result = handler.parse(str(test_file))
            assert result["key"] == "value"

```

## Best Practices

### 1. Write Descriptive Messages

**❌ Poor:**

```python
with subtests.test(msg=f"Test {i}"):
    assert validate(data[i])

```

**✅ Good:**

```python
with subtests.test(
    msg=f"Validate user input: {data[i]['username']}",
    username=data[i]["username"],
    index=i
):
    assert validate(data[i])

```

### 2. Include Context Variables

Context variables appear in failure reports:

**❌ Minimal context:**

```python
with subtests.test(msg="Testing path"):
    assert validate(path)

```

**✅ Rich context:**

```python
with subtests.test(
    msg=f"Validating path: {path}",
    path=path,
    path_type=get_path_type(path),
    length=len(path)
):
    assert validate(path)

```

### 3. Keep Subtests Focused

Each subtest should test one thing:

**❌ Testing too much:**

```python
with subtests.test(msg="User operations"):
    user = create_user("alice")
    assert user.name == "alice"
    assert user.email == "alice@example.com"
    assert user.is_active
    update_user(user.id, name="bob")
    assert get_user(user.id).name == "bob"

```

**✅ Focused tests:**

```python
with subtests.test(msg="Create user"):
    user = create_user("alice")
    assert user.name == "alice"

with subtests.test(msg="User has email"):
    assert user.email == "alice@example.com"

with subtests.test(msg="User is active"):
    assert user.is_active

```

### 4. Use Type Hints

```python
def test_with_subtests(self, subtests: pytest.Subtests) -> None:
    """Always type-hint the subtests fixture."""
    # ...

```

### 5. Document Test Cases

```python
def test_input_validation(self, subtests: pytest.Subtests) -> None:
    """Test input validation for various edge cases.

    Tests cover:
    * Empty strings
    * Whitespace-only strings
    * Special characters
    * Unicode characters
    * Maximum length inputs
    """
    test_cases = [...]

```

### 6. Group Related Assertions

```python
with subtests.test(msg=f"User validation: {username}", user=username):
    # Group related assertions in same subtest
    user = get_user(username)
    assert user is not None
    assert user.is_valid()
    assert user.has_permissions()

```

### 7. Use Meaningful Variable Names

**❌ Unclear:**

```python
for x, y in cases:
    with subtests.test(msg=f"{x}"):
        assert f(x) == y

```

**✅ Clear:**

```python
for input_value, expected_output in test_cases:
    with subtests.test(msg=f"Input: {input_value}", input=input_value):
        assert function(input_value) == expected_output

```

## Examples from Codebase

### Example 1: Path Traversal Testing

From `tests/security/test_input_validation.py`:

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

**Why this works:**

* Clear test purpose (Unix path traversal)
* Descriptive messages
* Context variable (path) for debugging
* All cases run independently

### Example 2: Handler Validation

From `tests/security/test_path_traversal.py`:

```python
def test_handlers_reject_absolute_paths(
    self,
    setup_test_files: tuple[Path, Path, Path, str],
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

**Why this works:**

* Tests all handlers with same logic
* Expensive fixture setup shared
* Clear failure reporting per handler
* All handlers tested even if one fails

### Example 3: Configuration Variants

From `tests/unit/test_runtime_config.py`:

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

**Why this works:**

* Multiple context managers combined
* Each variant tested independently
* Easy to add new boolean values
* Clear which variant failed

## Common Pitfalls

### Pitfall 1: Forgetting the Fixture

**❌ Error:**

```python
def test_without_fixture(self) -> None:
    with subtests.test(msg="test"):  # NameError: subtests not defined
        assert True

```

**✅ Fix:**

```python
def test_with_fixture(self, subtests: pytest.Subtests) -> None:
    with subtests.test(msg="test"):
        assert True

```

### Pitfall 2: Not Providing Messages

**❌ Poor debugging:**

```python
with subtests.test():  # No context when it fails
    assert validate(path)

```

**✅ Clear debugging:**

```python
with subtests.test(msg=f"Validating: {path}", path=path):
    assert validate(path)

```

### Pitfall 3: Shared Mutable State

**❌ State leaks between subtests:**

```python
shared_list = []

for item in items:
    with subtests.test(msg=f"Item: {item}"):
        shared_list.append(item)  # Affects other subtests!
        assert len(shared_list) == 1  # Fails after first subtest

```

**✅ Isolated state:**

```python
for item in items:
    with subtests.test(msg=f"Item: {item}"):
        item_list = [item]  # Fresh list per subtest
        assert len(item_list) == 1

```

### Pitfall 4: Using Subtests for Unrelated Tests

**❌ Unrelated logic:**

```python
def test_everything(self, subtests: pytest.Subtests) -> None:
    with subtests.test("user"):
        assert create_user("alice")

    with subtests.test("file"):
        assert file_exists("test.txt")

    with subtests.test("network"):
        assert ping("example.com")

```

**✅ Separate tests:**

```python
def test_user_creation(self) -> None:
    assert create_user("alice")

def test_file_exists(self) -> None:
    assert file_exists("test.txt")

def test_network_connectivity(self) -> None:
    assert ping("example.com")

```

### Pitfall 5: Nested with Statements (Linter Violation)

**❌ Ruff SIM117 violation:**

```python
with subtests.test(msg="test"):
    with patch.dict(os.environ, {"KEY": "value"}):
        assert True

```

**✅ Combined context managers:**

```python
with (
    subtests.test(msg="test"),
    patch.dict(os.environ, {"KEY": "value"}),
):
    assert True

```

## Migration Guide

### Step 1: Identify Candidates

Look for:

* Multiple test methods with similar names/logic
* Tests with loops that don't use subtests
* Tests with many similar assertions
* Tests that could benefit from better failure reporting

### Step 2: Choose the Pattern

Use the decision tree to determine if subtests are appropriate.

### Step 3: Refactor

**Before:**

```python
def test_case_1(self) -> None:
    assert validate("input1")

def test_case_2(self) -> None:
    assert validate("input2")

def test_case_3(self) -> None:
    assert validate("input3")

```

**After:**

```python
def test_validation_cases(self, subtests: pytest.Subtests) -> None:
    """Test validation with various inputs."""
    inputs = ["input1", "input2", "input3"]

    for input_val in inputs:
        with subtests.test(msg=f"Validating: {input_val}", input=input_val):
            assert validate(input_val)

```

### Step 4: Add Context

Enhance with descriptive messages and context variables:

```python
def test_validation_cases(self, subtests: pytest.Subtests) -> None:
    """Test validation with various inputs."""
    test_cases = [
        ("Simple input", "input1"),
        ("Complex input", "input2"),
        ("Edge case", "input3"),
    ]

    for description, input_val in test_cases:
        with subtests.test(
            msg=f"{description}: {input_val}",
            description=description,
            input=input_val
        ):
            result = validate(input_val)
            assert result is True

```

### Step 5: Test

Run the migrated test to ensure:

* All subtests pass
* Failure messages are clear
* No regressions introduced

### Step 6: Document

Update docstrings to mention subtests:

```python
def test_validation_cases(self, subtests: pytest.Subtests) -> None:
    """Test validation with various inputs using subtests.

    Each input is tested independently to ensure comprehensive
    coverage and clear failure reporting.
    """

```

## Related Documentation

* [Testing Guide](TESTING.md) - Comprehensive testing documentation
* [pytest 9.0 Migration Guide](PYTEST_9_MIGRATION.md) - Migration overview
* [CONTRIBUTING.md](../../CONTRIBUTING.md) - Contribution guidelines
* [pytest Documentation](https://docs.pytest.org/) - Official pytest docs
