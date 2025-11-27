# LLM Metrics Guide

This guide explains how to use the metrics system to monitor LLM performance, costs, and reliability.

## Overview

The metrics system tracks:

* **Request latency** (p50, p95, p99 percentiles)
* **Success/failure rates** per provider
* **Cost tracking** with budget enforcement
* **Cache hit rates** and savings
* **Fallback rate** (LLM vs regex parser)
* **Per-provider breakdown**

## CLI Options

### Displaying Metrics

Use `--show-metrics` to display aggregated metrics after processing:

```bash
pr-resolve apply 123 --llm-enabled --show-metrics
```

Output:

```text
=== LLM Metrics Summary ===
Total requests: 42
Success rate: 97.6%
Latency: p50=0.234s, p95=1.456s, p99=2.103s
Total cost: $0.0523
Cache hit rate: 35.7%
Fallback rate: 4.8% (2 fallbacks)

Per-provider breakdown:
  anthropic: 35 requests, p95=1.234s, $0.0412
  ollama: 7 requests, p95=0.567s, $0.0000
```

### Exporting Metrics

Export metrics to a file for analysis:

```bash
# Export to JSON
pr-resolve apply 123 --llm-enabled --show-metrics --metrics-output metrics.json

# Export to CSV (per-request data)
pr-resolve apply 123 --llm-enabled --show-metrics --metrics-output metrics.csv
```

## JSON Export Format

The JSON export includes:

```json
{
  "summary": {
    "total_requests": 42,
    "successful_requests": 41,
    "failed_requests": 1,
    "success_rate": 0.976,
    "latency_p50": 0.234,
    "latency_p95": 1.456,
    "latency_p99": 2.103,
    "latency_avg": 0.567,
    "total_cost": 0.0523,
    "cost_per_comment": 0.00124,
    "cache_hit_rate": 0.357,
    "cache_savings": 0.0187,
    "fallback_count": 2,
    "fallback_rate": 0.048
  },
  "provider_stats": {
    "anthropic": {
      "provider": "anthropic",
      "model": "claude-haiku-4-20250514",
      "total_requests": 35,
      "successful_requests": 34,
      "failed_requests": 1,
      "success_rate": 0.971,
      "total_cost": 0.0412,
      "total_tokens": 15234,
      "avg_latency": 0.678,
      "latency_p50": 0.456,
      "latency_p95": 1.234,
      "latency_p99": 1.567,
      "cache_hit_rate": 0.286,
      "error_counts": {"RateLimitError": 1}
    }
  },
  "pr_info": {
    "owner": "VirtualAgentics",
    "repo": "my-repo",
    "pr_number": 123
  }
}
```

## CSV Export Format

CSV exports per-request data for detailed analysis:

| Column | Description |
|--------|-------------|
| `request_id` | Unique request identifier |
| `provider` | Provider name (anthropic, openai, ollama) |
| `model` | Model identifier |
| `latency_seconds` | Request duration |
| `success` | True/False |
| `tokens_input` | Input tokens consumed |
| `tokens_output` | Output tokens generated |
| `cost` | Request cost in USD |
| `cache_hit` | True if served from cache |
| `error_type` | Error class name if failed |

## Key Metrics Explained

### Latency Percentiles

* **p50 (median)**: Typical request latency
* **p95**: 95% of requests complete within this time
* **p99**: Worst-case latency (excluding outliers)

**Interpretation:**

* High p95 vs p50 gap indicates inconsistent performance
* High p99 may indicate timeout issues or provider instability

### Success Rate

Percentage of requests that completed successfully.

**Targets:**

* \> 99%: Excellent
* 95-99%: Good
* < 95%: Investigate failures

### Cache Hit Rate

Percentage of requests served from prompt cache.

**Impact:**

* Higher hit rate = lower costs and latency
* Typical range: 20-50% for varied PRs

### Fallback Rate

Percentage of comments where LLM parsing failed and regex fallback was used.

**Impact:**

* Higher fallback rate = lower parsing accuracy
* Target: < 10%

### Cache Savings

Estimated cost saved by cache hits, calculated as:

```text
savings = cache_hits × avg_non_cache_cost
```

## Programmatic Access

Use the `MetricsAggregator` class for custom integrations:

```python
from review_bot_automator.llm.metrics_aggregator import MetricsAggregator
from pathlib import Path

# Create aggregator
aggregator = MetricsAggregator()
aggregator.set_pr_info("owner", "repo", 123)

# Track requests
request_id = aggregator.start_request("anthropic", "claude-haiku-4")
# ... make LLM call ...
aggregator.end_request(
    request_id,
    success=True,
    tokens_input=100,
    tokens_output=50,
    cost=0.0012
)

# Get aggregated metrics
metrics = aggregator.get_aggregated_metrics(comments_processed=10)
print(f"Total cost: ${metrics.total_cost:.4f}")
print(f"Cost per comment: ${metrics.cost_per_comment:.4f}")

# Export
aggregator.export_json(Path("metrics.json"))
aggregator.export_csv(Path("metrics.csv"))

# Human-readable summary
print(aggregator.get_summary_report())
```

## Analyzing Metrics

### Cost Analysis

```python
import json
from pathlib import Path

data = json.loads(Path("metrics.json").read_text())

# Cost breakdown by provider
for provider, stats in data["provider_stats"].items():
    print(f"{provider}: ${stats['total_cost']:.4f} "
          f"({stats['total_requests']} requests)")

# Cost efficiency
summary = data["summary"]
print(f"Cost per comment: ${summary['cost_per_comment']:.4f}")
print(f"Cache savings: ${summary['cache_savings']:.4f}")
```

### Performance Analysis

```python
# Identify slow providers
for provider, stats in data["provider_stats"].items():
    if stats["latency_p95"] > 2.0:
        print(f"Warning: {provider} p95 latency is {stats['latency_p95']:.2f}s")

# Check error patterns
for provider, stats in data["provider_stats"].items():
    if stats["error_counts"]:
        print(f"{provider} errors: {stats['error_counts']}")
```

## Best Practices

1. **Enable metrics in CI/CD**: Track performance trends over time
2. **Set cost budgets**: Use `CR_LLM_COST_BUDGET` to prevent surprises
3. **Monitor fallback rate**: High rates indicate parsing issues
4. **Review error counts**: Identify provider-specific problems
5. **Export for analysis**: Use JSON/CSV for historical tracking

## See Also

* [Cost Estimation](cost-estimation.md) - Pre-run cost estimation
* [LLM Configuration](llm-configuration.md) - Full configuration reference
* [Performance Tuning](performance-tuning.md) - Optimizing performance
