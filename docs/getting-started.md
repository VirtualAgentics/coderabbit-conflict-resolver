# Getting Started with Review Bot Automator

This guide will help you get started with the Review Bot Automator, from installation to analyzing your first pull request.

## Installation

### From PyPI (Recommended)

```bash
pip install review-bot-automator

```

### From Source

```bash
git clone https://github.com/VirtualAgentics/review-bot-automator.git
cd review-bot-automator
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

```

### Verify Installation

```bash
pr-resolve --version

```

## Environment Setup

### GitHub Token

You'll need a GitHub personal access token with the following permissions:

* `repo` - Full control of private repositories
* `read:org` - Read org membership (if working with organization repos)

#### Create a token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Name it (e.g., "Review Bot Automator")
4. Select the required scopes
5. Click "Generate token"
6. Copy the token immediately (you won't be able to see it again)

#### Set the token

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN="your_token_here"

```

Or add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
echo 'export GITHUB_PERSONAL_ACCESS_TOKEN="your_token_here"' >> ~/.bashrc
source ~/.bashrc

```

**Note:** The tool also supports `GITHUB_TOKEN` for backward compatibility, but `GITHUB_PERSONAL_ACCESS_TOKEN` is preferred.

### LLM Provider Setup (Optional - ✅ ALL 5 PROVIDERS PRODUCTION-READY)

The resolver supports AI-powered features via multiple LLM providers. All 5 providers are production-ready with full feature support (Phase 2 Complete - Nov 9, 2025).

#### ✅ Supported Providers (Production Status)

* **openai**: OpenAI API (GPT-4o-mini, GPT-4) - ✅ Production-ready with retry logic & cost tracking
* **anthropic**: Anthropic API (Claude Sonnet 4.5, Haiku 4) - ✅ Production-ready, 50-90% cost savings with prompt caching
* **claude-cli**: Claude CLI - ✅ Production-ready, subscription-based (no API key needed)
* **codex-cli**: Codex CLI - ✅ Production-ready, GitHub Copilot subscription
* **ollama**: Local models - ✅ Production-ready with GPU acceleration (NVIDIA/AMD/Apple Silicon), auto-download, HTTP pooling

#### Quick Setup: Anthropic (Recommended)

Anthropic provides the best balance of cost and performance with prompt caching:

```bash
# 1. Get API key from https://console.anthropic.com/
# 2. Set environment variables
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="anthropic"
export CR_LLM_API_KEY="sk-ant-..."
export CR_LLM_MODEL="claude-sonnet-4-5"  # Optional, uses default if not set

# 3. Verify setup
pr-resolve apply --pr 123 --owner myorg --repo myrepo --mode dry-run

```

#### Quick Setup: OpenAI

```bash
# 1. Get API key from https://platform.openai.com/api-keys
# 2. Set environment variables
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="openai"
export CR_LLM_API_KEY="sk-..."
export CR_LLM_MODEL="gpt-4"  # Optional

```

#### Quick Setup: Ollama (Local, Free)

Ollama can be used directly via its API (no MCP server required):

```bash
# 1. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Pull a model
ollama pull llama3.3:70b

# 3. Set environment variables (no API key needed)
export CR_LLM_ENABLED="true"
export CR_LLM_PROVIDER="ollama"
export CR_LLM_MODEL="llama3.3:70b"
export OLLAMA_BASE_URL="http://localhost:11434"  # Optional, uses default if not set

# 4. Verify Ollama is running
curl http://localhost:11434/api/tags

```

**Note**: Ollama is accessed via direct API calls, not through MCP server integration.

#### See [Configuration Guide - LLM Provider Configuration](configuration.md#llm-provider-configuration) for all provider options, cost comparison, and detailed setup instructions

### Privacy Considerations

When using LLM providers with the Review Bot Automator, understanding the privacy implications is important for making informed decisions about which provider to use.

#### Privacy Spectrum

Different LLM providers offer different privacy tradeoffs:

* **Local-Only (Ollama)**: Reduces third-party LLM vendor exposure by running models locally
  * Code review comments are processed on your machine via localhost (127.0.0.1:11434)
  * No third-party LLM vendors (OpenAI, Anthropic) have access to your code
  * ⚠️ **Important**: Still requires internet access for GitHub API operations (fetching PR data, posting comments)
  * **NOT air-gapped**: Cannot operate in isolated/offline environments
  * Best for: Organizations with strict data residency requirements, GDPR/HIPAA compliance needs

* **Subscription-Based (Claude CLI, Codex CLI)**: Zero marginal cost, subscription privacy model
  * Code processed by Anthropic/GitHub respectively
  * Covered under existing subscription terms
  * Best for: Individual developers or teams already using these services

* **API-Based (OpenAI API, Anthropic API)**: Pay-per-use with third-party processing
  * Code sent to third-party LLM providers for processing
  * Subject to provider's data retention and privacy policies
  * Anthropic offers prompt caching (50-90% cost reduction)
  * Best for: Cost-conscious users, high-volume processing with caching benefits

#### Privacy Verification

For Ollama users, you can verify localhost-only operation using the included privacy verification script:

```bash
# Run privacy verification for Ollama
./scripts/verify_privacy.sh

# Generates detailed report confirming
# - All LLM requests go to localhost only (127.0.0.1:11434)
# - No connections to OpenAI/Anthropic/other third-party LLM vendors
# - GitHub API connections are allowed (required for PR operations)

```

#### Additional Resources

For comprehensive privacy information, see:

* **[Privacy Architecture](privacy-architecture.md)** - Complete privacy model, data flows, and compliance guidance
* **[Privacy FAQ](privacy-faq.md)** - Common questions about privacy, offline operation, and data handling
* **[Privacy Verification Script](../scripts/verify_privacy.sh)** - Automated network monitoring for Ollama

**Key Takeaway**: This tool **reduces third-party LLM vendor exposure** when using Ollama, but cannot operate in air-gapped or offline environments due to GitHub API requirements. Choose the provider that best matches your privacy, cost, and performance needs.

### Configuration

The resolver uses preset configurations. The default is `balanced`:

* **conservative**: Skip all conflicts, manual review required
* **balanced**: Priority system + semantic merging (default)
* **aggressive**: Maximize automation, user selections always win
* **semantic**: Focus on structure-aware merging for config files

See [Configuration Reference](configuration.md) for details.

### Runtime Configuration System

The resolver supports multiple configuration sources with a precedence chain:

#### CLI flags > Environment variables > Config file > Defaults

#### Configuration Files

Create a `config.yaml` or `config.toml` file:

#### YAML Example

```yaml
mode: conflicts-only
rollback:
  enabled: true
validation:
  enabled: true
parallel:
  enabled: true
  max_workers: 8
logging:
  level: INFO
  file: resolver.log

```

#### TOML Example

```toml
mode = "conflicts-only"

[rollback]
enabled = true

[validation]
enabled = true

[parallel]
enabled = true
max_workers = 8

[logging]
level = "INFO"
file = "resolver.log"

```

Load configuration from file:

```bash
pr-resolve apply --pr 123 --owner myorg --repo myproject --config config.yaml

```

#### Environment Variables

Set configuration using `CR_*` prefix environment variables:

```bash
export CR_MODE="conflicts-only"
export CR_ENABLE_ROLLBACK="true"
export CR_VALIDATE="true"
export CR_PARALLEL="true"
export CR_MAX_WORKERS="8"
export CR_LOG_LEVEL="INFO"
export CR_LOG_FILE="resolver.log"

```

See [`.env.example`](../.env.example) in the root directory for all available environment variables.

#### Application Modes

The resolver supports different application modes:

* **all** (default): Apply both conflicting and non-conflicting changes
* **conflicts-only**: Apply only changes that have conflicts
* **non-conflicts-only**: Apply only changes without conflicts
* **dry-run**: Analyze and report without applying any changes

Set via CLI:

```bash
pr-resolve apply --pr 123 --owner myorg --repo myproject --mode conflicts-only

```

Set via environment:

```bash
export CR_MODE="dry-run"

```

## First PR Analysis

Let's analyze conflicts in a pull request.

### Basic Analysis

```bash
pr-resolve analyze \
  --pr 123 \
  --owner VirtualAgentics \
  --repo my-repo

```

This will:

* Fetch comments from the PR
* Detect conflicts between suggestions
* Display a table with conflict details
* Show statistics

### Example Output

```text
Analyzing conflicts in PR #123 for VirtualAgentics/my-repo
Using configuration: balanced

╭─────────────────────────────────────────╮
│         Conflict Analysis               │
├──────────┬────────────┬─────────────────┤
│ File     │ Conflicts  │ Type            │
├──────────┼────────────┼─────────────────┤
│ package. │ 3          │ overlap         │
│ config.  │ 2          │ semantic-dup    │
╰──────────┴────────────┴─────────────────╯

📊 Found 2 conflicts

```

## CLI Commands

### Analyze Command

Analyze conflicts without applying changes:

```bash
pr-resolve analyze \
  --pr <number> \
  --owner <owner> \
  --repo <repo> \
  --config <preset>

```

#### Options

* `--pr`: Pull request number (required)
* `--owner`: Repository owner or organization (required)
* `--repo`: Repository name (required)
* `--config`: Configuration preset (default: `balanced`)

### Apply Command

Apply conflict resolution suggestions:

```bash
pr-resolve apply \
  --pr <number> \
  --owner <owner> \
  --repo <repo> \
  --mode <mode> \
  --strategy <strategy> \
  --config <file> \
  --parallel \
  --max-workers <n> \
  --rollback / --no-rollback \
  --validation / --no-validation \
  --log-level <level> \
  --log-file <path>

```

#### Options: (Analyze Command)

* `--pr`: Pull request number (required)
* `--owner`: Repository owner or organization (required)
* `--repo`: Repository name (required)
* `--mode`: Application mode (`all`, `conflicts-only`, `non-conflicts-only`, `dry-run`)
* `--strategy`: Resolution strategy (default: `priority`)
* `--config`: Load configuration from YAML/TOML file
* `--parallel`: Enable parallel processing
* `--max-workers`: Number of parallel workers (default: 4)
* `--rollback` / `--no-rollback`: Enable/disable automatic rollback (default: enabled)
* `--validation` / `--no-validation`: Enable/disable pre-application validation (default: enabled)
* `--log-level`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
* `--log-file`: Write logs to file

#### Application Modes

* `all` (default): Apply both conflicting and non-conflicting changes
* `conflicts-only`: Apply only changes that have conflicts
* `non-conflicts-only`: Apply only changes without conflicts
* `dry-run`: Analyze and report without applying any changes

#### Resolution Strategies

* `priority` (default): Priority-based resolution (user selections > security > syntax > regular)
* `skip`: Skip all conflicts (conservative)
* `override`: Override conflicts (aggressive)
* `merge`: Semantic merging for compatible changes

### Simulate Command

Simulate conflict resolution without making changes:

```bash
pr-resolve simulate \
  --pr <number> \
  --owner <owner> \
  --repo <repo> \
  --config <preset>

```

#### Options: (Apply Command)

* `--pr`: Pull request number (required)
* `--owner`: Repository owner or organization (required)
* `--repo`: Repository name (required)
* `--config`: Configuration preset (default: `balanced`)

## Python API

You can also use the resolver programmatically:

```python
from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig

# Initialize resolver with configuration
resolver = ConflictResolver(config=PresetConfig.BALANCED)

# Analyze conflicts
conflicts = resolver.analyze_conflicts(
    owner="VirtualAgentics",
    repo="my-repo",
    pr_number=123
)

# Apply resolution
results = resolver.resolve_pr_conflicts(
    owner="VirtualAgentics",
    repo="my-repo",
    pr_number=123
)

print(f"Applied: {results.applied_count}")
print(f"Conflicts: {results.conflict_count}")
print(f"Success rate: {results.success_rate}%")

```

See [API Reference](api-reference.md) for complete API documentation.

## Common Use Cases

### 1. Check PR for Conflicts

Before applying suggestions, analyze conflicts:

```bash
pr-resolve analyze --pr 456 --owner myorg --repo myproject

```

### 2. Dry Run Before Applying

Test what would change without making changes:

```bash
pr-resolve apply --pr 456 --owner myorg --repo myproject --dry-run

```

### 3. Aggressive Auto-Apply

Automatically resolve with aggressive strategy:

```bash
pr-resolve apply --pr 456 --owner myorg --repo myproject --strategy override

```

### 4. Conservative Review

Simulate with conservative config to see all conflicts:

```bash
pr-resolve simulate --pr 456 --owner myorg --repo myproject --config conservative

```

### 5. Apply Only Conflicting Changes

Focus on resolving conflicts only:

```bash
pr-resolve apply --pr 456 --owner myorg --repo myproject --mode conflicts-only

```

### 6. Parallel Processing for Large PRs

Speed up processing with parallel workers:

```bash
pr-resolve apply --pr 456 --owner myorg --repo myproject --parallel --max-workers 8

```

### 7. Safe Apply with Rollback

Apply changes with automatic rollback on failure (default):

```bash
pr-resolve apply --pr 456 --owner myorg --repo myproject --rollback

```

Disable rollback if you have your own backup:

```bash
pr-resolve apply --pr 456 --owner myorg --repo myproject --no-rollback

```

## Rollback System

The resolver includes an automatic rollback system using Git stash:

### How It Works

1. **Checkpoint Creation**: Before applying changes, creates a git stash checkpoint
2. **Change Application**: Applies resolved changes to files
3. **Automatic Rollback**: If any error occurs, automatically restores from checkpoint
4. **Cleanup**: Removes checkpoint after successful application

### Enabling/Disabling

Rollback is enabled by default. Control it via:

#### CLI

```bash
# Enable (default)
pr-resolve apply --pr 123 --owner myorg --repo myproject --rollback

# Disable
pr-resolve apply --pr 123 --owner myorg --repo myproject --no-rollback

```

#### Environment Variable

```bash
export CR_ENABLE_ROLLBACK="false"

```

#### Config File: (Config)

```yaml
rollback:
  enabled: false

```

See [Rollback System](rollback-system.md) for complete documentation.

## Parallel Processing

Process multiple files concurrently for faster resolution:

### When to Use

* **Large PRs**: 20+ files with changes
* **Multiple Independent Files**: Changes don't depend on each other
* **Performance Critical**: Time-sensitive resolutions

### When NOT to Use

* **Small PRs**: < 10 files (overhead not worth it)
* **Dependent Changes**: Changes across files that interact
* **Debugging**: Sequential processing easier to debug

### Configuration

#### CLI

```bash
pr-resolve apply --pr 123 --owner myorg --repo myproject \
  --parallel --max-workers 8

```

#### Environment

```bash
export CR_PARALLEL="true"
export CR_MAX_WORKERS="8"

```

#### Config File

```yaml
parallel:
  enabled: true
  max_workers: 8

```

### Performance Tips

* **2-4 workers**: Small to medium PRs (10-30 files)
* **4-8 workers**: Large PRs (30-100 files)
* **8-16 workers**: Very large PRs (100+ files)
* **CPU cores**: Don't exceed CPU core count

See [Parallel Processing](parallel-processing.md) for detailed tuning guide.

## Troubleshooting

### "Authentication failed" Error

**Problem:** GitHub API authentication fails.

#### Solution

* Verify your `GITHUB_PERSONAL_ACCESS_TOKEN` is set: `echo $GITHUB_PERSONAL_ACCESS_TOKEN`
* Check token has required permissions (`repo`, `read:org`)
* Regenerate token if expired
* Note: `GITHUB_TOKEN` is also supported for backward compatibility

### "Repository not found" Error

**Problem:** Cannot access repository.

#### Solution

* Verify repository name and owner are correct
* Check token has `repo` scope
* For organization repos, ensure token has `read:org` scope

### "No conflicts detected" but comments exist

**Problem:** Analyzer reports no conflicts but PR has comments.

#### Solution

* Check that comments are from CodeRabbit or supported format
* Verify comments contain change suggestions (not just reviews)
* Check if comments are on lines that match file content

### Performance Issues

**Problem:** Analysis takes too long for large PRs.

#### Solution

* PRs with 100+ comments may be slow
* Consider analyzing specific files instead of full PR
* Use `--dry-run` first to avoid re-running analysis

### Type Checking Errors

**Problem:** MyPy reports type errors during development.

#### Solution

* Run `source .venv/bin/activate && mypy src/ --strict`
* Fix type annotations
* Check `pyproject.toml` for MyPy configuration

## Next Steps

* Learn about [Conflict Types](conflict-types.md)
* Explore [Resolution Strategies](resolution-strategies.md)
* Customize [Configuration](configuration.md)
* Understand the [Rollback System](rollback-system.md)
* Optimize with [Parallel Processing](parallel-processing.md)
* Read the [API Reference](api-reference.md)
* Review [Migration Guide](migration-guide.md) for upgrading

## Getting Help

* **Issues:** [GitHub Issues](https://github.com/VirtualAgentics/review-bot-automator/issues)
* **Discussions:** [GitHub Discussions](https://github.com/VirtualAgentics/review-bot-automator/discussions)
* **CodeRabbit AI:** [coderabbit.ai](https://coderabbit.ai)
