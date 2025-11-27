# API Reference

Complete API reference for Review Bot Automator.

## Core Classes

### ConflictResolver

Main class for conflict resolution operations.

```python
from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig

resolver = ConflictResolver(config=PresetConfig.BALANCED)

```

#### Methods

##### `__init__(config: dict[str, Any] | None = None) -> None`

Initialize the conflict resolver with optional configuration.

**Parameters:**

* `config` (dict, optional): Configuration dictionary for customizing resolver behavior

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

* `path` (str): File path

**Returns:**

* `FileType`: Detected file type enum

**Example:**

```python
file_type = resolver.detect_file_type("config.json")
# Returns: FileType.JSON

```

##### `generate_fingerprint(path: str, start: int, end: int, content: str) -> str`

Create unique fingerprint for a change.

**Parameters:**

* `path` (str): File path
* `start` (int): Start line number
* `end` (int): End line number
* `content` (str): Change content

**Returns:**

* `str`: 16-character hex fingerprint

**Example:**

```python
fingerprint = resolver.generate_fingerprint(
    "file.py", 10, 15, "def new_function():"
)

```

##### `extract_changes_from_comments(comments: list[dict[str, Any]]) -> list[Change]`

Extract Change objects from GitHub comment data.

**Parameters:**

* `comments` (list[dict]): GitHub comment objects

**Returns:**

* `list[Change]`: List of extracted Change objects

##### `analyze_conflicts(owner: str, repo: str, pr_number: int) -> list[Conflict]`

Analyze conflicts in a pull request without applying changes.

**Parameters:**

* `owner` (str): Repository owner
* `repo` (str): Repository name
* `pr_number` (int): Pull request number

**Returns:**

* `list[Conflict]`: List of detected conflicts

**Example:**

```python
conflicts = resolver.analyze_conflicts("myorg", "myrepo", 123)
for conflict in conflicts:
    print(f"Conflict in {conflict.file_path}: {conflict.conflict_type}")

```

##### `resolve_pr_conflicts(owner: str, repo: str, pr_number: int, mode: ApplicationMode = ApplicationMode.ALL, validate: bool = True, parallel: bool = False, max_workers: int = 4, enable_rollback: bool = True) -> ResolutionResult`

Resolve all conflicts in a pull request and return results.

**Parameters:**

* `owner` (str): Repository owner
* `repo` (str): Repository name
* `pr_number` (int): Pull request number
* `mode` (ApplicationMode, optional): Application mode (default: ALL)
  * `ApplicationMode.ALL`: Apply both conflicting and non-conflicting changes
  * `ApplicationMode.CONFLICTS_ONLY`: Apply only conflicting changes
  * `ApplicationMode.NON_CONFLICTS_ONLY`: Apply only non-conflicting changes
  * `ApplicationMode.DRY_RUN`: Analyze without applying
* `validate` (bool, optional): Enable pre-application validation (default: True)
* `parallel` (bool, optional): Enable parallel processing (default: False)
* `max_workers` (int, optional): Number of parallel workers (default: 4)
* `enable_rollback` (bool, optional): Enable automatic rollback on failure (default: True)

**Returns:**

* `ResolutionResult`: Complete resolution results with counts and details

**Example:**

```python
from review_bot_automator.config.runtime_config import ApplicationMode

# Apply only conflicting changes with rollback
results = resolver.resolve_pr_conflicts(
    "myorg", "myrepo", 123,
    mode=ApplicationMode.CONFLICTS_ONLY,
    enable_rollback=True
)

# Parallel processing for large PRs
results = resolver.resolve_pr_conflicts(
    "myorg", "myrepo", 456,
    parallel=True,
    max_workers=8
)

print(f"Applied: {results.applied_count}")
print(f"Conflicts: {results.conflict_count}")
print(f"Success rate: {results.success_rate}%")

```

##### `apply_changes(changes: list[Change], validate: bool = True, parallel: bool = False, max_workers: int = 4) -> tuple[list[Change], list[Change], list[tuple[Change, str]]]`

Apply changes to files with optional validation and parallel processing.

**Parameters:**

* `changes` (list[Change]): List of changes to apply
* `validate` (bool, optional): Validate changes before applying (default: True)
* `parallel` (bool, optional): Process files in parallel (default: False)
* `max_workers` (int, optional): Number of parallel workers (default: 4)

**Returns:**

* `tuple`: (applied_changes, skipped_changes, failed_changes_with_errors)

**Example:**

```python
applied, skipped, failed = resolver.apply_changes(
    changes,
    validate=True,
    parallel=True,
    max_workers=8
)

for change in applied:
    print(f"Applied: {change.path}:{change.start_line}")

for change, error in failed:
    print(f"Failed {change.path}: {error}")

```

##### `apply_changes_with_rollback(changes: list[Change], enable_rollback: bool = True, parallel: bool = False, max_workers: int = 4) -> tuple[int, int, int]`

Apply changes with automatic rollback on failure.

**Parameters:**

* `changes` (list[Change]): List of changes to apply
* `enable_rollback` (bool, optional): Enable rollback (default: True)
* `parallel` (bool, optional): Process files in parallel (default: False)
* `max_workers` (int, optional): Number of parallel workers (default: 4)

**Returns:**

* `tuple[int, int, int]`: (applied_count, skipped_count, failed_count)

**Example:**

```python
applied_count, skipped_count, failed_count = resolver.apply_changes_with_rollback(
    changes,
    enable_rollback=True,
    parallel=True,
    max_workers=8
)

print(f"Applied: {applied_count}, Skipped: {skipped_count}, Failed: {failed_count}")

```

##### `separate_changes_by_conflict_status(changes: list[Change]) -> tuple[list[Change], list[Change]]`

Separate changes into conflicting and non-conflicting groups.

**Parameters:**

* `changes` (list[Change]): List of changes to separate

**Returns:**

* `tuple[list[Change], list[Change]]`: (conflicting_changes, non_conflicting_changes)

**Example:**

```python
conflicting, non_conflicting = resolver.separate_changes_by_conflict_status(changes)

print(f"Conflicting: {len(conflicting)}")
print(f"Non-conflicting: {len(non_conflicting)}")

```

### RollbackManager

Manages git-based rollback checkpoints for safe change application.

```python
from review_bot_automator.core.rollback import RollbackManager

rollback_manager = RollbackManager(workspace_root="/path/to/repo")

```

#### Methods

##### `__init__(workspace_root: Path | str) -> None`

Initialize the rollback manager.

**Parameters:**

* `workspace_root` (Path | str): Path to git repository root

##### `create_checkpoint() -> str`

Create a rollback checkpoint using git stash.

**Returns:**

* `str`: Checkpoint identifier

**Example:**

```python
checkpoint_id = rollback_manager.create_checkpoint()
print(f"Created checkpoint: {checkpoint_id}")

```

##### `rollback(checkpoint_id: str) -> bool`

Restore from a checkpoint.

**Parameters:**

* `checkpoint_id` (str): Checkpoint identifier to restore

**Returns:**

* `bool`: True if rollback successful, False otherwise

**Example:**

```python
success = rollback_manager.rollback(checkpoint_id)
if success:
    print("Rollback successful")
else:
    print("Rollback failed")

```

##### Context Manager Usage

Use as a context manager for automatic rollback on exception:

```python
with RollbackManager(workspace_root="/path/to/repo") as rollback:
    # Apply changes here
    # Automatically rolls back if exception occurs
    apply_changes(changes)
# Cleanup happens automatically

```

### RuntimeConfig

Runtime configuration with multiple source support (defaults, file, env, CLI).

```python
from review_bot_automator.config.runtime_config import RuntimeConfig, ApplicationMode

# Load from defaults
config = RuntimeConfig.from_defaults()

# Load from file
config = RuntimeConfig.from_file("config.yaml")

# Load from environment variables
config = RuntimeConfig.from_env()

# Use preset configurations
config = RuntimeConfig.from_conservative()
config = RuntimeConfig.from_balanced()
config = RuntimeConfig.from_aggressive()
config = RuntimeConfig.from_semantic()

```

#### Attributes

* `mode` (ApplicationMode): Application mode
* `enable_rollback` (bool): Enable automatic rollback
* `validate_before_apply` (bool): Enable pre-application validation
* `parallel_processing` (bool): Enable parallel processing
* `max_workers` (int): Number of parallel workers
* `log_level` (str): Logging level
* `log_file` (str | None): Log file path

#### Class Methods

##### `from_defaults() -> RuntimeConfig`

Create configuration with default values.

**Returns:**

* `RuntimeConfig`: Configuration with defaults

##### `from_file(file_path: Path | str) -> RuntimeConfig`

Load configuration from YAML or TOML file.

**Parameters:**

* `file_path` (Path | str): Path to configuration file

**Returns:**

* `RuntimeConfig`: Loaded configuration

**Example:**

```python
config = RuntimeConfig.from_file("config.yaml")

```

##### `from_env() -> RuntimeConfig`

Load configuration from environment variables (CR_* prefix).

**Returns:**

* `RuntimeConfig`: Configuration from environment

**Example:**

```python
# Set environment: CR_MODE=conflicts-only, CR_PARALLEL=true
config = RuntimeConfig.from_env()

```

##### `from_conservative() -> RuntimeConfig`

Create conservative preset configuration.

**Returns:**

* `RuntimeConfig`: Conservative configuration

##### `from_balanced() -> RuntimeConfig`

Create balanced preset configuration (default).

**Returns:**

* `RuntimeConfig`: Balanced configuration

##### `from_aggressive() -> RuntimeConfig`

Create aggressive preset configuration.

**Returns:**

* `RuntimeConfig`: Aggressive configuration

##### `from_semantic() -> RuntimeConfig`

Create semantic preset configuration.

**Returns:**

* `RuntimeConfig`: Semantic configuration

#### Instance Methods

##### `merge_with_cli(**cli_overrides) -> RuntimeConfig`

Merge configuration with CLI overrides.

**Parameters:**

* `**cli_overrides`: CLI flag overrides (mode, enable_rollback, etc.)

**Returns:**

* `RuntimeConfig`: New configuration with CLI overrides applied

**Example:**

```python
config = RuntimeConfig.from_file("config.yaml")
config = config.merge_with_cli(
    mode="conflicts-only",
    parallel_processing=True,
    max_workers=8
)

```

### ApplicationMode

Enumeration of application modes.

```python
from review_bot_automator.config.runtime_config import ApplicationMode

ApplicationMode.ALL  # Apply both conflicting and non-conflicting changes (default)
ApplicationMode.CONFLICTS_ONLY  # Apply only conflicting changes
ApplicationMode.NON_CONFLICTS_ONLY  # Apply only non-conflicting changes
ApplicationMode.DRY_RUN  # Analyze without applying changes

```

**Usage:**

```python
from review_bot_automator import ConflictResolver
from review_bot_automator.config.runtime_config import ApplicationMode

resolver = ConflictResolver()
results = resolver.resolve_pr_conflicts(
    "myorg", "myrepo", 123,
    mode=ApplicationMode.CONFLICTS_ONLY
)

```

## Data Models

### FileType

Enumeration of supported file types.

```python
from review_bot_automator.core.models import FileType

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
from review_bot_automator.core.models import Change, FileType

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
from review_bot_automator.handlers.base import BaseHandler

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
from review_bot_automator.handlers.json_handler import JsonHandler

handler = JsonHandler()

```

Extends `BaseHandler` with JSON-specific logic:

* Duplicate key detection
* Key-level merging
* Structure validation

### YamlHandler

Handler for YAML files.

```python
from review_bot_automator.handlers.yaml_handler import YamlHandler

handler = YamlHandler()

```

Extends `BaseHandler` with YAML-specific logic:

* Comment preservation
* Anchor/alias handling
* Structure-aware merging

### TomlHandler

Handler for TOML files.

```python
from review_bot_automator.handlers.toml_handler import TomlHandler

handler = TomlHandler()

```

Extends `BaseHandler` with TOML-specific logic:

* Section merging
* Comment preservation
* Table array handling

## Strategies

### PriorityStrategy

Priority-based resolution strategy.

```python
from review_bot_automator.strategies.priority_strategy import PriorityStrategy

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

* `Resolution`: Resolution with applied and skipped changes

## Integration

### GitHubCommentExtractor

Extract comments from GitHub PRs.

```python
from review_bot_automator.integrations.github import GitHubCommentExtractor

extractor = GitHubCommentExtractor(token="your_token")

```

#### Methods

##### `__init__(token: str | None = None, base_url: str = "https://api.github.com") -> None`

Initialize with optional token.

**Parameters:**

* `token` (str, optional): GitHub personal access token
* `base_url` (str): GitHub API base URL

##### `fetch_pr_comments(owner: str, repo: str, pr_number: int) -> list[dict[str, Any]]`

Fetch all comments for a PR.

**Parameters:**

* `owner` (str): Repository owner
* `repo` (str): Repository name
* `pr_number` (int): PR number

**Returns:**

* `list[dict]`: List of comment objects from GitHub API

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
from review_bot_automator.config import PresetConfig

# Available presets
PresetConfig.CONSERVATIVE
PresetConfig.BALANCED
PresetConfig.AGGRESSIVE
PresetConfig.SEMANTIC

```

## Utilities

### Text Utilities

```python
from review_bot_automator.utils.text import normalize_content

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
from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig

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
from review_bot_automator.handlers.base import BaseHandler
from review_bot_automator.core.models import Change, Conflict

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
from review_bot_automator.core.models import Conflict, Resolution

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

## LLM Module (v2.0)

The LLM module provides AI-powered parsing of CodeRabbit review comments. This enables parsing of all comment formats (diff blocks, suggestion blocks, natural language) with 95%+ coverage.

### LLMProvider Protocol

Protocol defining the interface for all LLM providers. All 5 providers implement this protocol.

```python
from review_bot_automator.llm.providers.base import LLMProvider

```

#### Methods

##### `generate(prompt: str, max_tokens: int = 2000) -> str`

Generate text completion from prompt.

**Parameters:**

* `prompt` (str): Input prompt text for generation
* `max_tokens` (int): Maximum tokens to generate (default: 2000)

**Returns:**

* `str`: Generated text from the LLM

**Raises:**

* `RuntimeError`: If generation fails after retries
* `LLMAuthenticationError`: If API credentials are invalid

##### `count_tokens(text: str) -> int`

Count tokens in text using provider's tokenizer.

**Parameters:**

* `text` (str): Text to tokenize and count

**Returns:**

* `int`: Number of tokens

### Available Providers

All 5 providers are production-ready:

| Provider | Class | Cost | Requires |
|----------|-------|------|----------|
| OpenAI API | `OpenAIAPIProvider` | Pay-per-token | `OPENAI_API_KEY` |
| Anthropic API | `AnthropicAPIProvider` | Pay-per-token | `ANTHROPIC_API_KEY` |
| Claude CLI | `ClaudeCLIProvider` | $0 (subscription) | `claude` CLI installed |
| Codex CLI | `CodexCLIProvider` | $0 (subscription) | `codex` CLI installed |
| Ollama | `OllamaProvider` | $0 (local) | Ollama running |

**Example:**

```python
from review_bot_automator.llm.providers.ollama import OllamaProvider

provider = OllamaProvider(
    model="llama3.3:70b",
    base_url="http://localhost:11434"
)
response = provider.generate("Explain Python decorators", max_tokens=500)

```

### ParsedChange

Intermediate representation of a change parsed by an LLM.

```python
from review_bot_automator.llm.base import ParsedChange

@dataclass
class ParsedChange:
    file_path: str       # Path to file to be modified
    start_line: int      # Starting line (1-indexed)
    end_line: int        # Ending line (inclusive)
    new_content: str     # New content to apply
    change_type: str     # "addition", "modification", "deletion"
    confidence: float    # LLM confidence (0.0-1.0)
    rationale: str       # Why this change was suggested
    risk_level: str      # "low", "medium", "high"

```

**Example:**

```python
change = ParsedChange(
    file_path="src/example.py",
    start_line=10,
    end_line=12,
    new_content="def new_function():\n    pass",
    change_type="modification",
    confidence=0.95,
    rationale="Replace deprecated function with new API",
    risk_level="low"
)

```

### LLMParser ABC

Abstract base class for LLM-powered comment parsers.

```python
from review_bot_automator.llm.base import LLMParser

```

#### Methods

##### `parse_comment(body: str, file_path: str | None, line_number: int | None) -> list[ParsedChange]`

Parse a GitHub comment using the LLM provider.

**Parameters:**

* `body` (str): Raw comment text from GitHub
* `file_path` (str, optional): File path for context
* `line_number` (int, optional): Line number for context

**Returns:**

* `list[ParsedChange]`: List of extracted changes

### Provider Factory

Create providers using the factory function:

```python
from review_bot_automator.llm.factory import create_provider

# Create Ollama provider
provider = create_provider({
    "llm_provider": "ollama",
    "llm_model": "llama3.3:70b"
})

# Create Anthropic provider
provider = create_provider({
    "llm_provider": "anthropic-api",
    "llm_model": "claude-sonnet-4-20250514",
    "llm_api_key": "sk-ant-..."
})

```

### Prompt Cache

File-based caching system for LLM responses to reduce costs.

```python
from review_bot_automator.llm.cache.prompt_cache import PromptCache

cache = PromptCache(
    cache_dir=".llm-cache",
    ttl_seconds=604800,  # 7 days
    max_size_mb=100
)

# Check cache
response = cache.get(prompt="...", provider="anthropic", model="claude-sonnet-4")
if response is None:
    response = provider.generate(prompt)
    cache.set(prompt="...", provider="anthropic", model="claude-sonnet-4", response=response)

```

**Features:**

* SHA256 cache keys for collision-free lookups
* TTL-based expiration (default: 7 days)
* LRU eviction when size limit exceeded
* Thread-safe for concurrent access
* Secure file permissions (0600)

### Change Dataclass (v2.0 Fields)

The `Change` dataclass includes additional LLM metadata fields in v2.0:

```python
@dataclass
class Change:
    # Core fields (v1.x)
    path: str
    start_line: int
    end_line: int
    content: str
    metadata: dict[str, Any]
    fingerprint: str
    file_type: FileType

    # LLM metadata fields (v2.0)
    llm_confidence: float | None = None    # 0.0-1.0 confidence score
    llm_provider: str | None = None        # Provider used ("anthropic", "ollama", etc.)
    parsing_method: str = "regex"          # "regex" or "llm"
    change_rationale: str | None = None    # Why this change was suggested
    risk_level: str | None = None          # "low", "medium", "high"

```

## Error Handling

All operations may raise standard Python exceptions:

* `IOError`: File operations fail
* `ValueError`: Invalid parameters or data
* `requests.RequestException`: GitHub API errors

## Type Hints

All functions are fully type-hinted for IDE support and type checking.

```python
from typing import Any, List, Dict, Tuple

def example_function(data: Dict[str, Any]) -> List[str]:
    """Fully typed function."""
    return []

```

## See Also

* [Getting Started](getting-started.md) - Installation and basic usage
* [Configuration](configuration.md) - Configuration options
* [LLM Configuration](llm-configuration.md) - LLM provider setup and presets
* [Conflict Types](conflict-types.md) - Understanding conflicts
* [Resolution Strategies](resolution-strategies.md) - Strategy details
* [Privacy Architecture](privacy-architecture.md) - Local LLM privacy guarantees
