# API Reference

Complete API reference for CodeRabbit Conflict Resolver.

## Core Classes

### ConflictResolver

Main class for conflict resolution operations.

```python
from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.config import PresetConfig

resolver = ConflictResolver(config=PresetConfig.BALANCED)
```

#### Methods

##### `__init__(config: dict[str, Any] | None = None) -> None`

Initialize the conflict resolver with optional configuration.

**Parameters:**
- `config` (dict, optional): Configuration dictionary for customizing resolver behavior

**Example:**
```python
resolver = ConflictResolver(config={
    "semantic_merging": True,
    "priority_system": True,
})
```

##### `detect_file_type(path: str) -> FileType`

Determine file type from path extension.

**Parameters:**
- `path` (str): File path

**Returns:**
- `FileType`: Detected file type enum

**Example:**
```python
file_type = resolver.detect_file_type("config.json")
# Returns: FileType.JSON
```

##### `generate_fingerprint(path: str, start: int, end: int, content: str) -> str`

Create unique fingerprint for a change.

**Parameters:**
- `path` (str): File path
- `start` (int): Start line number
- `end` (int): End line number
- `content` (str): Change content

**Returns:**
- `str`: 16-character hex fingerprint

**Example:**
```python
fingerprint = resolver.generate_fingerprint(
    "file.py", 10, 15, "def new_function():"
)
```

##### `extract_changes_from_comments(comments: list[dict[str, Any]]) -> list[Change]`

Extract Change objects from GitHub comment data.

**Parameters:**
- `comments` (list[dict]): GitHub comment objects

**Returns:**
- `list[Change]`: List of extracted Change objects

##### `analyze_conflicts(owner: str, repo: str, pr_number: int) -> list[Conflict]`

Analyze conflicts in a pull request without applying changes.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `pr_number` (int): Pull request number

**Returns:**
- `list[Conflict]`: List of detected conflicts

**Example:**
```python
conflicts = resolver.analyze_conflicts("myorg", "myrepo", 123)
for conflict in conflicts:
    print(f"Conflict in {conflict.file_path}: {conflict.conflict_type}")
```

##### `resolve_pr_conflicts(owner: str, repo: str, pr_number: int) -> ResolutionResult`

Resolve all conflicts in a pull request and return results.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `pr_number` (int): Pull request number

**Returns:**
- `ResolutionResult`: Complete resolution results with counts and details

**Example:**
```python
results = resolver.resolve_pr_conflicts("myorg", "myrepo", 123)
print(f"Applied: {results.applied_count}")
print(f"Conflicts: {results.conflict_count}")
print(f"Success rate: {results.success_rate}%")
```

## Data Models

### FileType

Enumeration of supported file types.

```python
from pr_conflict_resolver.core.models import FileType

FileType.JSON  # JSON files
FileType.YAML  # YAML files
FileType.TOML  # TOML files
FileType.PYTHON  # Python files
FileType.TYPESCRIPT  # TypeScript/JavaScript files
FileType.PLAINTEXT  # Plain text files
```

### Change

Represents a single change suggestion.

```python
@dataclass
class Change:
    path: str  # File path
    start_line: int  # Start line (1-indexed)
    end_line: int  # End line (1-indexed)
    content: str  # Replacement content
    metadata: dict[str, Any]  # Additional metadata
    fingerprint: str  # Unique identifier
    file_type: FileType  # Detected file type
```

**Example:**
```python
from pr_conflict_resolver.core.models import Change, FileType

change = Change(
    path="config.json",
    start_line=10,
    end_line=12,
    content='{"key": "value"}',
    metadata={"author": "user", "url": "https://..."},
    fingerprint="abc123def456",
    file_type=FileType.JSON
)
```

### Conflict

Represents a conflict between multiple changes.

```python
@dataclass
class Conflict:
    file_path: str  # Path to conflicted file
    line_range: tuple[int, int]  # (start, end) lines
    changes: list[Change]  # Conflicting changes
    conflict_type: str  # Type of conflict
    severity: str  # Severity level
    overlap_percentage: float  # Overlap percentage
```

**Example:**
```python
conflict = Conflict(
    file_path="config.json",
    line_range=(10, 20),
    changes=[change1, change2],
    conflict_type="exact",
    severity="high",
    overlap_percentage=100.0
)
```

### Resolution

Represents a resolution for a conflict.

```python
@dataclass
class Resolution:
    strategy: str  # Strategy used
    applied_changes: list[Change]  # Applied changes
    skipped_changes: list[Change]  # Skipped changes
    success: bool  # Success status
    message: str  # Result message
```

### ResolutionResult

Complete results of conflict resolution.

```python
@dataclass
class ResolutionResult:
    applied_count: int  # Number of changes applied
    conflict_count: int  # Total conflicts found
    success_rate: float  # Success rate percentage
    resolutions: list[Resolution]  # All resolutions
    conflicts: list[Conflict]  # All conflicts
```

## Handlers

### BaseHandler

Abstract base class for all file handlers.

```python
from pr_conflict_resolver.handlers.base import BaseHandler
```

#### Abstract Methods

##### `can_handle(file_path: str) -> bool`

Check if handler can process a file type.

##### `apply_change(path: str, content: str, start_line: int, end_line: int) -> bool`

Apply a change to a file.

##### `validate_change(path: str, content: str, start_line: int, end_line: int) -> tuple[bool, str]`

Validate a change without applying it.

##### `detect_conflicts(path: str, changes: list[Change]) -> list[Conflict]`

Detect conflicts in file changes.

#### Utility Methods

##### `backup_file(path: str) -> str`

Create backup of a file.

##### `restore_file(backup_path: str, original_path: str) -> bool`

Restore a file from backup.

### JsonHandler

Handler for JSON files.

```python
from pr_conflict_resolver.handlers.json_handler import JsonHandler

handler = JsonHandler()
```

Extends `BaseHandler` with JSON-specific logic:
- Duplicate key detection
- Key-level merging
- Structure validation

### YamlHandler

Handler for YAML files.

```python
from pr_conflict_resolver.handlers.yaml_handler import YamlHandler

handler = YamlHandler()
```

Extends `BaseHandler` with YAML-specific logic:
- Comment preservation
- Anchor/alias handling
- Structure-aware merging

### TomlHandler

Handler for TOML files.

```python
from pr_conflict_resolver.handlers.toml_handler import TomlHandler

handler = TomlHandler()
```

Extends `BaseHandler` with TOML-specific logic:
- Section merging
- Comment preservation
- Table array handling

## Strategies

### PriorityStrategy

Priority-based resolution strategy.

```python
from pr_conflict_resolver.strategies.priority_strategy import PriorityStrategy

strategy = PriorityStrategy(config={
    "priority_rules": {
        "user_selections": 100,
        "security_fixes": 90,
    }
})
```

#### Methods

##### `__init__(config: dict[str, Any] | None = None) -> None`

Initialize strategy with configuration.

##### `resolve(conflict: Conflict) -> Resolution`

Resolve a conflict using priority rules.

**Returns:**
- `Resolution`: Resolution with applied and skipped changes

## Integration

### GitHubCommentExtractor

Extract comments from GitHub PRs.

```python
from pr_conflict_resolver.integrations.github import GitHubCommentExtractor

extractor = GitHubCommentExtractor(token="your_token")
```

#### Methods

##### `__init__(token: str | None = None, base_url: str = "https://api.github.com") -> None`

Initialize with optional token.

**Parameters:**
- `token` (str, optional): GitHub personal access token
- `base_url` (str): GitHub API base URL

##### `fetch_pr_comments(owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]`

Fetch all comments for a PR.

**Parameters:**
- `owner` (str): Repository owner
- `repo` (str): Repository name
- `pr_number` (int): PR number

**Returns:**
- `list[dict]`: List of comment objects from GitHub API

**Example:**
```python
comments = extractor.fetch_pr_comments("myorg", "myrepo", 123)
for comment in comments:
    print(comment["body"])
```

## Configuration

### PresetConfig

Predefined configuration presets.

```python
from pr_conflict_resolver.config import PresetConfig

# Available presets
PresetConfig.CONSERVATIVE
PresetConfig.BALANCED
PresetConfig.AGGRESSIVE
PresetConfig.SEMANTIC
```

## Utilities

### Text Utilities

```python
from pr_conflict_resolver.utils.text import normalize_content

normalized = normalize_content("some  content\n\nwith   spaces")
```

#### `normalize_content(content: str) -> str`

Normalize whitespace in content for comparison.

## CLI Command Reference

### Analyze Command

```bash
pr-resolve analyze --pr <number> --owner <owner> --repo <repo> [--config <preset>]
```

Analyze conflicts in a PR without applying changes.

### Apply Command

```bash
pr-resolve apply --pr <number> --owner <owner> --repo <repo> [--strategy <strategy>] [--dry-run]
```

Apply conflict resolutions to a PR.

### Simulate Command

```bash
pr-resolve simulate --pr <number> --owner <owner> --repo <repo> [--config <preset>]
```

Simulate conflict resolution without applying changes.

## Examples

### Basic Usage

```python
from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.config import PresetConfig

# Initialize resolver
resolver = ConflictResolver(config=PresetConfig.BALANCED)

# Analyze conflicts
conflicts = resolver.analyze_conflicts("myorg", "myrepo", 123)
print(f"Found {len(conflicts)} conflicts")

# Resolve conflicts
results = resolver.resolve_pr_conflicts("myorg", "myrepo", 123)
print(f"Applied {results.applied_count} changes")
```

### Custom Configuration

```python
custom_config = {
    "semantic_merging": True,
    "priority_system": True,
    "priority_rules": {
        "user_selections": 100,
        "security_fixes": 95,
    }
}

resolver = ConflictResolver(config=custom_config)
```

### Custom Handler

```python
from pr_conflict_resolver.handlers.base import BaseHandler
from pr_conflict_resolver.core.models import Change, Conflict

class CustomHandler(BaseHandler):
    def can_handle(self, file_path: str) -> bool:
        return file_path.endswith(".custom")

    def apply_change(self, path: str, content: str, start_line: int, end_line: int) -> bool:
        # Implementation
        return True

    def validate_change(self, path: str, content: str, start_line: int, end_line: int) -> tuple[bool, str]:
        # Implementation
        return True, "Valid"

    def detect_conflicts(self, path: str, changes: list[Change]) -> list[Conflict]:
        # Implementation
        return []
```

### Custom Strategy

```python
from pr_conflict_resolver.core.models import Conflict, Resolution

class CustomStrategy:
    def resolve(self, conflict: Conflict) -> Resolution:
        # Custom resolution logic
        return Resolution(
            strategy="custom",
            applied_changes=[conflict.changes[0]],
            skipped_changes=conflict.changes[1:],
            success=True,
            message="Custom resolution applied"
        )
```

## Error Handling

All operations may raise standard Python exceptions:

- `IOError`: File operations fail
- `ValueError`: Invalid parameters or data
- `requests.RequestException`: GitHub API errors

## Type Hints

All functions are fully type-hinted for IDE support and type checking.

```python
from typing import Any, List, Dict, Tuple

def example_function(data: Dict[str, Any]) -> List[str]:
    """Fully typed function."""
    return []
```

## See Also

- [Getting Started](getting-started.md) - Installation and basic usage
- [Configuration](configuration.md) - Configuration options
- [Conflict Types](conflict-types.md) - Understanding conflicts
- [Resolution Strategies](resolution-strategies.md) - Strategy details
