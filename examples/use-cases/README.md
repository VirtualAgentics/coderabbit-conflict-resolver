# Example Use Cases

This directory contains example scripts demonstrating common use cases for the Review Bot Automator.

## Available Scripts

| Script | Purpose | Description |
|--------|---------|-------------|
| `benchmark.sh` | Performance testing | Run LLM provider benchmarks |
| `smart-apply.py` | Intelligent application | Apply changes with conflict detection |
| `staged-application.sh` | Staged rollout | Apply changes in phases |

## Script Details

### benchmark.sh

Benchmarks LLM provider performance:

```bash
./examples/use-cases/benchmark.sh
```

What it does:

* Tests each configured provider
* Measures latency and throughput
* Reports cost estimates
* Exports results to JSON

### smart-apply.py

Intelligent change application with conflict detection:

```bash
python examples/use-cases/smart-apply.py --pr 123 --owner myorg --repo myrepo
```

Features:

* Pre-analyzes changes for conflicts
* Groups changes by file
* Applies non-conflicting first
* Reports conflicts for manual review

### staged-application.sh

Applies changes in phases for safer rollout:

```bash
./examples/use-cases/staged-application.sh 123 myorg myrepo
```

Phases:

1. **Dry run**: Analyze without changes
2. **Non-conflicts**: Apply safe changes
3. **Conflicts**: Apply with confirmation

## Common Use Cases

### CI/CD Integration

Add to your GitHub Actions workflow:

```yaml
- name: Apply CodeRabbit Suggestions
  run: |
    pr-resolve apply ${{ github.event.pull_request.number }} \
      --config .pr-resolve/ci-config.yaml \
      --show-metrics
```

### Batch Processing

Process multiple PRs:

```bash
for pr in 123 124 125; do
  pr-resolve apply $pr --config prod-config.yaml
done
```

### Cost-Controlled Development

Run with budget limits:

```bash
pr-resolve apply 123 \
  --llm-enabled \
  --llm-provider ollama \
  --show-metrics
```

### Quality Assurance

High-confidence only:

```bash
pr-resolve apply 123 \
  --llm-confidence-threshold 0.8 \
  --mode dry-run
```

## Creating Custom Scripts

### Template

```python
#!/usr/bin/env python3
"""Custom use case script template."""

from review_bot_automator import ConflictResolver
from review_bot_automator.config import PresetConfig

def main():
    resolver = ConflictResolver(config=PresetConfig.BALANCED)

    results = resolver.resolve_pr_conflicts(
        owner="myorg",
        repo="myrepo",
        pr_number=123
    )

    print(f"Applied: {results.applied_count}")
    print(f"Conflicts: {results.conflict_count}")

if __name__ == "__main__":
    main()
```

### Best Practices

1. **Use config files**: Store settings in YAML/TOML
2. **Enable metrics**: Track performance and costs
3. **Handle errors**: Use try/except for robustness
4. **Log output**: Use `--log-level INFO` for visibility

## See Also

* [Getting Started](../../docs/getting-started.md) - Basic usage guide
* [Configuration](../../docs/configuration.md) - Configuration reference
* [API Reference](../../docs/api-reference.md) - Python API documentation
