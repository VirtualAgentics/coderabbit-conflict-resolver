# Architecture Overview

## System Design

The Review Bot Automator is designed as a modular, extensible system that can intelligently resolve conflicts in GitHub PR comments. The architecture follows a pipeline pattern with clear separation of concerns.

## Core Components

### 1. Comment Parser & Extractor

**Location**: `src/review_bot_automator/integrations/`

Responsible for:

* Fetching PR comments from GitHub API
* Parsing different comment formats (suggestions, diffs, codemods)
* Extracting multi-option selections
* Normalizing comment data

**Key Classes**:

* `GitHubCommentExtractor`: Fetches and parses GitHub comments
* `CodeRabbitParser`: Specialized parser for CodeRabbit format
* `CommentNormalizer`: Standardizes comment data

### 2. Conflict Detection Engine

**Location**: `src/review_bot_automator/analysis/`

Analyzes comments for potential conflicts:

* Line range overlap detection
* Semantic duplicate detection
* File-type specific conflict analysis
* Impact assessment

**Key Classes**:

* `ConflictDetector`: Main conflict detection logic
* `SemanticAnalyzer`: Analyzes structured file conflicts
* `ImpactAssessor`: Evaluates change impact and risk

### 3. File-Type Handlers

**Location**: `src/review_bot_automator/handlers/`

Specialized handlers for different file types:

* JSON: Duplicate key detection, key-level merging
* YAML: Comment preservation, structure-aware merging
* TOML: Section merging, format preservation
* Python/TypeScript: AST-aware analysis (planned)

**Key Classes**:

* `BaseHandler`: Abstract base class for all handlers
* `JsonHandler`: JSON-specific conflict resolution
* `YamlHandler`: YAML-specific conflict resolution
* `TomlHandler`: TOML-specific conflict resolution

### 4. Priority System

**Location**: `src/review_bot_automator/core/`

Determines priority levels for different change types:

* User selections (highest priority)
* Security fixes
* Syntax errors
* Regular suggestions
* Formatting changes (lowest priority)

**Key Classes**:

* `PriorityCalculator`: Calculates change priorities
* `PriorityLearner`: ML-assisted priority learning
* `DynamicPriorityAdjuster`: Context-aware priority adjustment

### 5. Resolution Strategies

**Location**: `src/review_bot_automator/strategies/`

Implements different conflict resolution strategies:

* Skip: Skip conflicting change
* Override: Override lower-priority change
* Merge: Semantic merging of compatible changes
* Sequential: Apply changes in sequence
* Defer: Escalate to user

**Key Classes**:

* `ResolutionStrategy`: Base strategy class
* `PriorityBasedStrategy`: Priority-based resolution
* `SemanticMergeStrategy`: Semantic merging
* `InteractiveStrategy`: User-guided resolution

### 6. Application Engine

**Location**: `src/review_bot_automator/core/`

Applies resolved changes to files:

* Backup creation
* Change application
* Validation
* Rollback on failure

**Key Classes**:

* `ChangeApplicator`: Applies changes to files
* `BackupManager`: Manages file backups
* `ValidationEngine`: Validates applied changes

### 7. Reporting & Metrics

**Location**: `src/review_bot_automator/core/`

Generates reports and tracks metrics:

* Conflict summaries
* Visual diffs
* Success rate tracking
* Performance metrics

**Key Classes**:

* `ReportGenerator`: Creates conflict reports
* `MetricsCollector`: Tracks resolution metrics
* `VisualDiffGenerator`: Creates visual diffs

## Data Flow

```text
GitHub PR Comments
        ↓
Comment Parser & Extractor
        ↓
Conflict Detection Engine
        ↓
    ┌─────────┴─────────┐
    ↓                   ↓
File Handlers      Priority System
    ↓                   ↓
    └─────────┬─────────┘
              ↓
Resolution Strategy Selector
              ↓
Application Engine
              ↓
Reporting & Metrics

```

## Configuration System

### Preset Configurations

* **Conservative**: Skip all conflicts, manual review required
* **Balanced**: Priority system + semantic merging (default)
* **Aggressive**: Maximize automation, user selections always win
* **Semantic**: Focus on structure-aware merging for config files

### Custom Configuration

Users can create custom configurations with:

* Priority rules
* Resolution strategies
* File-type specific settings
* Learning parameters

## Extension Points

### Custom Handlers

Implement `BaseHandler` to add support for new file types:

```python
class CustomHandler(BaseHandler):
    def can_handle(self, file_path: str) -> bool:
        return file_path.endswith('.custom')

    def apply_change(self, path: str, change: Change) -> bool:
        # Custom implementation
        pass

```

### Custom Strategies

Implement `ResolutionStrategy` for custom resolution logic:

```python
class CustomStrategy(ResolutionStrategy):
    def resolve(self, conflict: Conflict) -> Resolution:
        # Custom resolution logic
        pass

```

### Custom Integrations

Implement comment source integrations:

```python
class CustomCommentSource(CommentSource):
    def fetch_comments(self, pr: PullRequest) -> List[Comment]:
        # Custom comment fetching
        pass

```

## Performance Considerations

### Caching

* Conflict analysis results cached by fingerprint
* File content cached during processing
* Priority calculations cached by change signature

### Parallel Processing

* Multiple files processed in parallel
* Conflict analysis parallelized
* Large PRs processed in batches

### Memory Management

* Streaming processing for large files
* Lazy loading of file content
* Garbage collection of processed data

## Security Considerations

### Input Validation

* All file paths validated
* Content size limits enforced
* Malicious content detection

### Backup Management

* Secure backup storage
* Backup cleanup policies
* Rollback verification

### Access Control

* GitHub token scoping
* Repository permission checks
* User authorization validation

## Testing Strategy

### Unit Tests

* Individual component testing
* Mock external dependencies
* Edge case coverage

### Integration Tests

* End-to-end workflow testing
* Real GitHub API testing (with test repos)
* Performance benchmarking

### Test Fixtures

* Sample PR comments
* Test repositories
* Conflict scenarios
* Expected outcomes

## Deployment

### Package Distribution

* PyPI package distribution
* Docker container support
* GitHub Actions integration

### Configuration Management

* Environment-based configuration
* Secret management
* Configuration validation

### Monitoring

* Health checks
* Performance metrics
* Error tracking
* Usage analytics

## Future Enhancements

### ML-Assisted Learning

* Priority learning from user decisions
* Conflict pattern recognition
* Automatic strategy optimization

### Advanced Merging

* Three-way merge support
* Intelligent conflict resolution
* Context-aware merging

### Multi-Platform Support

* GitLab integration
* Bitbucket support
* Azure DevOps compatibility

### Enterprise Features

* Team-wide configuration
* Audit logging
* Compliance reporting
* Advanced security controls
