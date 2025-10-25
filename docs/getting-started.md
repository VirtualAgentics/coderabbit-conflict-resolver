# Getting Started with CodeRabbit Conflict Resolver

This guide will help you get started with the CodeRabbit Conflict Resolver, from installation to analyzing your first pull request.

## Installation

### From PyPI (Recommended)

```bash
pip install pr-conflict-resolver
```

### From Source

```bash
git clone https://github.com/VirtualAgentics/coderabbit-conflict-resolver.git
cd coderabbit-conflict-resolver
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

- `repo` - Full control of private repositories
- `read:org` - Read org membership (if working with organization repos)

**Create a token:**

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Name it (e.g., "CodeRabbit Conflict Resolver")
4. Select the required scopes
5. Click "Generate token"
6. Copy the token immediately (you won't be able to see it again)

**Set the token:**

```bash
export GITHUB_TOKEN="your_token_here"
```

Or add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
echo 'export GITHUB_TOKEN="your_token_here"' >> ~/.bashrc
source ~/.bashrc
```

### Configuration

The resolver uses preset configurations. The default is `balanced`:

- **conservative**: Skip all conflicts, manual review required
- **balanced**: Priority system + semantic merging (default)
- **aggressive**: Maximize automation, user selections always win
- **semantic**: Focus on structure-aware merging for config files

See [Configuration Reference](configuration.md) for details.

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
- Fetch comments from the PR
- Detect conflicts between suggestions
- Display a table with conflict details
- Show statistics

### Example Output

```
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

**Options:**
- `--pr`: Pull request number (required)
- `--owner`: Repository owner or organization (required)
- `--repo`: Repository name (required)
- `--config`: Configuration preset (default: `balanced`)

### Apply Command

Apply conflict resolution suggestions:

```bash
pr-resolve apply \
  --pr <number> \
  --owner <owner> \
  --repo <repo> \
  --strategy <strategy> \
  --dry-run
```

**Options:**
- `--pr`: Pull request number (required)
- `--owner`: Repository owner or organization (required)
- `--repo`: Repository name (required)
- `--strategy`: Resolution strategy (default: `priority`)
- `--dry-run`: Simulate without applying changes

**Strategies:**
- `priority`: Priority-based resolution (user selections > security > syntax > regular)
- `skip`: Skip all conflicts (conservative)
- `override`: Override conflicts (aggressive)
- `merge`: Semantic merging for compatible changes

### Simulate Command

Simulate conflict resolution without making changes:

```bash
pr-resolve simulate \
  --pr <number> \
  --owner <owner> \
  --repo <repo> \
  --config <preset>
```

**Options:**
- `--pr`: Pull request number (required)
- `--owner`: Repository owner or organization (required)
- `--repo`: Repository name (required)
- `--config`: Configuration preset (default: `balanced`)

## Python API

You can also use the resolver programmatically:

```python
from pr_conflict_resolver import ConflictResolver
from pr_conflict_resolver.config import PresetConfig

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

## Troubleshooting

### "Authentication failed" Error

**Problem:** GitHub API authentication fails.

**Solution:**
- Verify your `GITHUB_TOKEN` is set: `echo $GITHUB_TOKEN`
- Check token has required permissions
- Regenerate token if expired

### "Repository not found" Error

**Problem:** Cannot access repository.

**Solution:**
- Verify repository name and owner are correct
- Check token has `repo` scope
- For organization repos, ensure token has `read:org` scope

### "No conflicts detected" but comments exist

**Problem:** Analyzer reports no conflicts but PR has comments.

**Solution:**
- Check that comments are from CodeRabbit or supported format
- Verify comments contain change suggestions (not just reviews)
- Check if comments are on lines that match file content

### Performance Issues

**Problem:** Analysis takes too long for large PRs.

**Solution:**
- PRs with 100+ comments may be slow
- Consider analyzing specific files instead of full PR
- Use `--dry-run` first to avoid re-running analysis

### Type Checking Errors

**Problem:** MyPy reports type errors during development.

**Solution:**
- Run `source .venv/bin/activate && mypy src/ --strict`
- Fix type annotations
- Check `pyproject.toml` for MyPy configuration

## Next Steps

- Learn about [Conflict Types](conflict-types.md)
- Explore [Resolution Strategies](resolution-strategies.md)
- Customize [Configuration](configuration.md)
- Read the [API Reference](api-reference.md)

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/VirtualAgentics/coderabbit-conflict-resolver/issues)
- **Discussions:** [GitHub Discussions](https://github.com/VirtualAgentics/coderabbit-conflict-resolver/discussions)
- **CodeRabbit AI:** [coderabbit.ai](https://coderabbit.ai)
