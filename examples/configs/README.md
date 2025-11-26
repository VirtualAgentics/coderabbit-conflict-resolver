# Example Configurations

This directory contains example configuration files for different deployment scenarios.

## Available Configurations

| File | Use Case | Description |
|------|----------|-------------|
| `ci-config.yaml` | CI/CD pipelines | Optimized for automated runs with cost limits |
| `dev-config.yaml` | Development | Fast iteration with local Ollama |
| `perf-config.yaml` | Performance testing | Maximum throughput settings |
| `prod-config.yaml` | Production | Balanced quality, cost, and reliability |

## Configuration Details

### ci-config.yaml

Optimized for CI/CD pipelines:

* **Cost budget**: Limited to prevent runaway costs
* **Parallel workers**: Moderate for balanced speed
* **Retry enabled**: Handle transient failures
* **Metrics export**: Track costs and performance

```yaml
llm:
  enabled: true
  provider: anthropic
  model: claude-haiku-4-20250514  # Fast + cost-effective
  cost_budget: 2.0
  cache_enabled: true

parallel:
  enabled: true
  max_workers: 4
```

### dev-config.yaml

Optimized for development:

* **Local Ollama**: No API costs
* **Fast model**: Quick iteration
* **Debug logging**: Easier troubleshooting

```yaml
llm:
  enabled: true
  provider: ollama
  model: qwen2.5-coder:7b

log_level: DEBUG
```

### perf-config.yaml

Optimized for performance testing:

* **High parallelism**: Maximum throughput
* **Fast provider**: Lowest latency
* **Metrics enabled**: Track performance

```yaml
llm:
  enabled: true
  provider: anthropic
  model: claude-haiku-4-20250514

parallel:
  enabled: true
  max_workers: 16
```

### prod-config.yaml

Optimized for production:

* **Quality model**: Higher accuracy
* **Cost controls**: Budget with warnings
* **Resilience**: Circuit breaker + retry
* **Conservative parallelism**: Rate limit safe

```yaml
llm:
  enabled: true
  provider: anthropic
  model: claude-sonnet-4-5
  confidence_threshold: 0.7
  cost_budget: 10.0
  circuit_breaker_enabled: true
  retry_on_rate_limit: true

parallel:
  enabled: true
  max_workers: 4
```

## Usage

```bash
# Use a specific config
pr-resolve apply 123 --config examples/configs/ci-config.yaml

# Override specific settings
pr-resolve apply 123 --config examples/configs/prod-config.yaml --max-workers 8
```

## Customization

1. Copy the closest matching config
2. Modify settings for your needs
3. Store in your repo's `.pr-resolve/` directory

```bash
mkdir -p .pr-resolve
cp examples/configs/ci-config.yaml .pr-resolve/config.yaml
```

## See Also

* [Configuration Guide](../../docs/configuration.md) - Full configuration reference
* [LLM Configuration](../../docs/llm-configuration.md) - LLM-specific settings
* [Performance Tuning](../../docs/performance-tuning.md) - Optimization strategies
