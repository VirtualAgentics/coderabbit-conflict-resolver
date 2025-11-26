# Cost Estimation Guide

This guide helps you estimate and control LLM costs before running the conflict resolver.

## Cost Overview

LLM costs depend on:

* **Provider**: API-based providers charge per token
* **Model**: Larger models cost more
* **Comment count**: More comments = more API calls
* **Cache hit rate**: Cached responses are free or cheaper

## Provider Cost Comparison

### Per-Comment Estimates (Typical)

| Provider | Model | Cost/Comment | Notes |
|----------|-------|--------------|-------|
| **Ollama** | qwen2.5-coder:7b | $0.0000 | Free (local) |
| **Claude CLI** | claude-sonnet-4-5 | $0.0000 | Subscription-based |
| **Codex CLI** | codex | $0.0000 | Subscription-based |
| **OpenAI API** | gpt-5-nano | ~$0.0001 | Cheapest API option |
| **OpenAI API** | gpt-5-mini | ~$0.0003 | Best value (Nov 2025) |
| **OpenAI API** | gpt-4o-mini | ~$0.0002 | Low-cost API |
| **Anthropic API** | claude-haiku-4-5 | ~$0.0008 | Low-cost API |
| **Anthropic API** | claude-sonnet-4-5 | ~$0.0030 | Balanced |
| **Anthropic API** | claude-opus-4-5 | ~$0.0050 | Flagship (67% cheaper than 4.1!) |
| **OpenAI API** | gpt-5.1 | ~$0.0015 | Latest flagship |

### Monthly Cost Projections

Assuming 100 PRs/month with 20 comments each (2,000 comments):

| Provider | Model | Monthly Cost |
|----------|-------|--------------|
| Ollama | qwen2.5-coder:7b | $0.00 |
| Claude CLI | claude-sonnet-4-5 | $0.00 (subscription) |
| OpenAI API | gpt-5-nano | ~$0.20 |
| OpenAI API | gpt-5-mini | ~$0.60 |
| OpenAI API | gpt-4o-mini | ~$0.40 |
| Anthropic API | claude-haiku-4-5 | ~$1.60 |
| OpenAI API | gpt-5.1 | ~$3.00 |
| Anthropic API | claude-sonnet-4-5 | ~$6.00 |
| Anthropic API | claude-opus-4-5 | ~$10.00 |

## Pre-Run Cost Estimation

### 1. Estimate Comment Count

```bash
# Count comments in a PR using GitHub CLI
gh pr view 123 --json comments --jq '.comments | length'
```

### 2. Calculate Estimated Cost

```text
estimated_cost = comment_count × cost_per_comment × (1 - expected_cache_hit_rate)
```

Example for 50 comments with Anthropic Haiku:

```text
estimated_cost = 50 × $0.0008 × (1 - 0.30) = $0.028
```

### 3. Use Dry-Run Mode

Run with `--mode dry-run` to analyze without making API calls:

```bash
pr-resolve apply 123 --mode dry-run --llm-enabled
```

This shows the comment count without incurring costs.

## Budget Configuration

### Setting a Budget

Prevent cost overruns with `CR_LLM_COST_BUDGET`:

```bash
# Limit to $5 per run
export CR_LLM_COST_BUDGET=5.0
```

Or in config:

```yaml
llm:
  cost_budget: 5.0
```

### Budget Status

The cost tracker has three states:

| Status | Description | Action |
|--------|-------------|--------|
| `OK` | Under 80% of budget | Continue normally |
| `WARNING` | 80-99% of budget | Log warning, continue |
| `EXCEEDED` | 100%+ of budget | Block new requests |

### Warning Threshold

Customize when warnings appear:

```yaml
llm:
  cost_budget: 5.0
  # Warn at 70% instead of default 80%
  # (configured in code, not yet exposed)
```

## Cost Optimization Strategies

### 1. Enable Prompt Caching

Cache identical prompts to avoid redundant API calls:

```yaml
llm:
  cache_enabled: true  # Default: true
```

**Impact**: 30-50% cost reduction typical

### 2. Use Cost-Effective Models

For most CodeRabbit comments, smaller models work well:

```yaml
# Anthropic: Use Haiku instead of Sonnet
llm:
  provider: anthropic
  model: claude-haiku-4-20250514

# OpenAI: Use GPT-4o-mini instead of GPT-4o
llm:
  provider: openai
  model: gpt-4o-mini
```

### 3. Use Free Providers

For development or cost-sensitive environments:

```yaml
# Local Ollama (completely free)
llm:
  provider: ollama
  model: qwen2.5-coder:7b

# Claude CLI (subscription, no per-use cost)
llm:
  provider: claude-cli
  model: claude-sonnet-4-5
```

### 4. Increase Confidence Threshold

Reject low-confidence parses to reduce follow-up calls:

```yaml
llm:
  confidence_threshold: 0.7  # Default: 0.5
```

### 5. Limit Parallel Workers

Reduce concurrent API calls:

```yaml
parallel:
  enabled: true
  max_workers: 2  # Default: 4
```

## Monitoring Costs

### Real-Time Tracking

Enable metrics to see costs after each run:

```bash
pr-resolve apply 123 --llm-enabled --show-metrics
```

Output includes:

```text
Total cost: $0.0523
Cache hit rate: 35.7%
```

### Export for Analysis

```bash
pr-resolve apply 123 --llm-enabled --show-metrics --metrics-output costs.json
```

Review in JSON:

```json
{
  "summary": {
    "total_cost": 0.0523,
    "cost_per_comment": 0.00124,
    "cache_savings": 0.0187
  }
}
```

## Cost Alerts

When budget reaches warning threshold (80% by default):

```text
WARNING: LLM cost budget warning: $4.12 of $5.00 used (82.4%)
```

When budget is exceeded:

```text
ERROR: LLM cost budget exceeded: $5.23 of $5.00 used
```

New requests are blocked until the run completes.

## Recommended Budgets

| Use Case | Budget | Rationale |
|----------|--------|-----------|
| Development/Testing | $1.00 | Low risk while iterating |
| CI/CD per-PR | $2.00 | Typical PR costs < $0.50 |
| Large Monorepo | $10.00 | Higher comment counts |
| Batch Processing | $50.00 | Multiple PRs in sequence |

## Cost Tracking API

For programmatic cost tracking:

```python
from review_bot_automator.llm.cost_tracker import CostTracker, CostStatus

# Initialize with budget
tracker = CostTracker(budget=5.00, warning_threshold=0.8)

# Before each API call
if tracker.should_block_request():
    raise Exception("Budget exceeded")

# After API call
status = tracker.add_cost(0.0012)
if status == CostStatus.WARNING:
    print(tracker.get_warning_message())
elif status == CostStatus.EXCEEDED:
    print("Budget exceeded!")

# Check current state
print(f"Remaining: ${tracker.remaining_budget:.4f}")
print(f"Utilization: {tracker.budget_utilization * 100:.1f}%")
```

## See Also

* [LLM Configuration](llm-configuration.md) - Full configuration reference
* [Metrics Guide](metrics-guide.md) - Understanding metrics output
* [Performance Tuning](performance-tuning.md) - Optimizing performance and cost
