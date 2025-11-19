# Cost Optimization Guide

**Last Updated**: November 19, 2025
**Applies To**: v2.0+ with LLM-powered comment parsing

This guide provides comprehensive strategies for minimizing the cost of using LLM providers while maintaining quality and performance.

## Table of Contents

- [Quick Cost Comparison](#quick-cost-comparison)
- [Free Provider Options](#free-provider-options)
- [Cost-Effective Paid Providers](#cost-effective-paid-providers)
- [Prompt Caching Strategy](#prompt-caching-strategy)
- [Cost Budgeting & Controls](#cost-budgeting--controls)
- [Model Selection Strategy](#model-selection-strategy)
- [Cost Monitoring](#cost-monitoring)
- [Real-World Cost Examples](#real-world-cost-examples)

---

## Quick Cost Comparison

### Provider Cost Comparison (per 1M tokens)

| Provider | Model | Input | Output | Total (1M in + 1M out) | Notes |
| -------- | ----- | ----- | ------ | ---------------------- | ----- |
| **Free Options** | | | | | |
| Ollama | llama3.2:1b | $0 | $0 | **$0** | Requires local GPU/CPU |
| Ollama | llama3:8b | $0 | $0 | **$0** | Best free quality |
| Codex CLI | gpt-4 | $0* | $0* | **$0*** | Requires Copilot subscription ($10/mo) |
| Claude CLI | claude-sonnet-4 | $0* | $0* | **$0*** | Requires Claude Pro ($20/mo) |
| **Paid API Options** | | | | | |
| OpenAI | gpt-4o-mini | $0.15 | $0.60 | **$0.75** | Best value API |
| Anthropic | claude-haiku | $0.25 | $1.25 | **$1.50** | Fast & cheap |
| OpenAI | gpt-4o | $2.50 | $10.00 | **$12.50** | High quality |
| Anthropic | claude-sonnet-4 | $3.00 | $15.00 | **$18.00** | Best quality |

*Included with subscription

### Typical PR Cost Estimates

#### Scenario: 10-comment PR, 500 tokens/comment average

| Provider | First Run | With Cache (80% hit rate) | Monthly (50 PRs) |
| -------- | --------- | ------------------------- | ---------------- |
| Ollama (local) | $0.00 | $0.00 | $0.00 |
| Codex/Claude CLI | $0.00* | $0.00* | $0.00* |
| GPT-4o-mini | $0.38 | $0.08 | $4.00 |
| Claude Haiku | $0.75 | $0.15 | $7.50 |
| GPT-4o | $6.25 | $1.25 | $62.50 |
| Claude Sonnet | $9.00 | $1.80 | $90.00 |

*Subscription cost not included ($10-20/mo)

---

## Free Provider Options

### 1. Ollama (100% Free, Local)

**Best For**: Development, testing, privacy-conscious users, unlimited usage

**Setup**:

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Download model (one-time)
ollama pull llama3.2:3b  # 2GB download

# Use with PR Conflict Resolver
pr-resolve apply --pr 123 --llm-preset ollama-local
```

**Cost Breakdown**:

- **Hardware**: One-time cost ($0 if existing, $500-2000 for GPU)
- **Electricity**: ~$0.10-0.30 per day (24/7 usage)
- **Maintenance**: $0
- **Per-request**: $0

**Monthly Cost for 1000 PRs**: **$3-9** (electricity only)

**Pros**:

- ✅ Zero marginal cost per request
- ✅ No rate limits
- ✅ Complete privacy (no data sent to third parties)
- ✅ Works offline (after model download)
- ✅ GPU acceleration for 10-50x speed

**Cons**:

- ❌ Requires hardware (8GB+ RAM, GPU recommended)
- ❌ Initial model download (2-8GB)
- ❌ Slightly lower quality than GPT-4/Claude Sonnet
- ❌ Setup complexity

**Recommended Models by Use Case**:

- **Development**: `llama3.2:1b` (1.5GB, fastest)
- **Testing**: `llama3.2:3b` (2GB, balanced)
- **Production**: `llama3:8b` (4.7GB, best quality)

### 2. Codex CLI (Free with GitHub Copilot)

**Best For**: GitHub Copilot subscribers, high-quality needs

**Requirements**: GitHub Copilot subscription ($10/mo or free for students/OSS maintainers)

**Setup**:

```bash
# Install GitHub CLI
gh auth login

# Use with PR Conflict Resolver
pr-resolve apply --pr 123 --llm-preset codex-cli-free

```

**Cost Breakdown**:

- **Subscription**: $10/mo (or $0 if already subscribed)
- **Per-request**: $0
- **Rate Limits**: ~20 requests/minute

**Monthly Cost for 1000 PRs**: **$10** (subscription only)

**Pros**:

- ✅ High quality (GPT-4 class)
- ✅ Zero marginal cost if already subscriber
- ✅ No hardware requirements
- ✅ Fast inference

**Cons**:

- ❌ Requires subscription ($10/mo)
- ❌ Rate limits (~20 RPM)
- ❌ Requires internet connection
- ❌ Not suitable for high-volume automation

**When to Use**: If you already have Copilot for development, use this for PR resolution at no additional cost.

### 3. Claude CLI (Free with Claude Pro)

**Best For**: Claude Pro subscribers, high-quality needs

**Requirements**: Claude Pro subscription ($20/mo)

**Setup**:

```bash
# Install Claude CLI
npm install -g @anthropics/claude-cli

# Use with PR Conflict Resolver
pr-resolve apply --pr 123 --llm-preset claude-cli-sonnet

```

**Cost Breakdown**:

- **Subscription**: $20/mo
- **Per-request**: $0
- **Rate Limits**: ~20 requests/minute

**Monthly Cost for 1000 PRs**: **$20** (subscription only)

**Pros**:

- ✅ Highest quality (Claude Sonnet 4)
- ✅ Zero marginal cost if already subscriber
- ✅ No hardware requirements
- ✅ Fast inference

**Cons**:

- ❌ Requires subscription ($20/mo)
- ❌ Rate limits (~20 RPM)
- ❌ Requires internet connection
- ❌ Not suitable for high-volume automation

---

## Cost-Effective Paid Providers

### 1. OpenAI GPT-4o-mini (Best Value API)

**Cost**: $0.15/1M input + $0.60/1M output = **$0.75/1M total**

**Best For**: Production use, high volume, balanced quality/cost

**Setup**:

```bash
export OPENAI_API_KEY="sk-..."
pr-resolve apply --pr 123 --llm-preset openai-api-mini

```

**Monthly Cost Examples**:

| PRs/Month | Avg Cost/PR | Total Monthly Cost |
| ----------- | ------------- | ------------------- |
| 10 | $0.38 | $3.80 |
| 50 | $0.38 | $19.00 |
| 100 | $0.38 | $38.00 |
| 500 | $0.38 | $190.00 |

**With 80% Cache Hit Rate**:

| PRs/Month | Avg Cost/PR | Total Monthly Cost |
| ----------- | ------------- | ------------------- |
| 10 | $0.08 | $0.80 |
| 50 | $0.08 | $4.00 |
| 100 | $0.08 | $8.00 |
| 500 | $0.08 | $40.00 |

**Cost Optimization Tips**:

1. **Enable caching**: `--cache-enabled` (saves 80%+)
2. **Use smaller context**: Limit PR comment history
3. **Batch similar PRs**: Better cache hit rate
4. **Set cost budgets**: `--cost-budget 50.0`

### 2. Anthropic Claude Haiku (Fast & Cheap)

**Cost**: $0.25/1M input + $1.25/1M output = **$1.50/1M total**

**Best For**: High-volume production, speed-critical applications

**Native Prompt Caching**: Additional 50-90% cost reduction on cached portions

**Setup**:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
pr-resolve apply --pr 123 --llm-preset anthropic-api-balanced

```

**Monthly Cost Examples** (with native caching):

| PRs/Month | Base Cost/PR | With Caching | With App Cache | Total Savings |
| ----------- | -------------- | -------------- | ---------------- | --------------- |
| 10 | $0.75 | $0.15 | $0.03 | 96% |
| 50 | $0.75 | $0.15 | $0.03 | 96% |
| 100 | $0.75 | $0.15 | $0.03 | 96% |
| 500 | $0.75 | $0.15 | $0.03 | 96% |

**Unique Benefits**:

- **Fastest inference**: ~250ms P50 latency
- **Native caching**: Automatic 5-minute cache
- **Combined savings**: Up to 96% with both caching layers

---

## Prompt Caching Strategy

### How Caching Saves Money

**Without Caching**: Every request = full API call = full cost

Request 1: "Fix linting errors" → API call → $0.38
Request 2: "Fix linting errors" → API call → $0.38
Request 3: "Fix linting errors" → API call → $0.38
Total: $1.14

**With Caching**: Identical requests = cache hit = $0 cost

Request 1: "Fix linting errors" → API call → $0.38
Request 2: "Fix linting errors" → CACHE HIT → $0.00
Request 3: "Fix linting errors" → CACHE HIT → $0.00
Total: $0.38 (67% savings)

### Maximizing Cache Hit Rate

#### 1. Enable Caching (Essential)

```bash
# Always enable caching
pr-resolve apply --pr 123 --cache-enabled

# Or in config file
cache:
  enabled: true
  max_size: 5000
  ttl: 3600  # 1 hour

```

#### 2. Increase TTL for Stable Codebases

```yaml
# Development: Short TTL (things change fast)
cache:
  ttl: 1800  # 30 minutes

# Production: Long TTL (stable patterns)
cache:
  ttl: 86400  # 24 hours
```

**Cost Impact**:

- 30 minutes TTL: ~60% hit rate → 60% savings
- 1 hour TTL: ~75% hit rate → 75% savings
- 24 hours TTL: ~90% hit rate → 90% savings

#### 3. Warm Cache with Common Patterns

```python
from pr_conflict_resolver.llm.cache import CacheOptimizer

optimizer = CacheOptimizer()

# Pre-populate cache with common comments
common_patterns = [
    "LGTM",
    "Please fix the linting errors",
    "Add tests for this feature",
    "Update documentation",
    "Address review comments",
    # Add your team's common phrases
]

optimizer.warm_cache(common_patterns)

```

**Cost Impact**: +20-30% hit rate improvement

#### 4. Standardize Comment Phrasing

**Bad** (every variation is a cache miss):

"pls fix lint"
"please fix linting"
"Fix the linting errors"
"could you fix lint errors?"

**Good** (consistent phrasing = cache hits):

"Please fix the linting errors"
"Please fix the linting errors"
"Please fix the linting errors"
"Please fix the linting errors"

**Cost Impact**: +10-15% hit rate improvement

### Cache ROI Calculator

**Assumptions**:

- 50 PRs/month
- 10 comments per PR average
- $0.38 per comment without cache
- 75% cache hit rate with caching

**Without Caching**:

50 PRs × 10 comments × $0.38 = $190/month

**With Caching**:

50 PRs × 10 comments × (0.25 × $0.38) = $47.50/month
Savings: $142.50/month (75%)
Annual savings: $1,710

---

## Cost Budgeting & Controls

### 1. Setting Cost Budgets

**Prevent Runaway Costs**:

```bash
# Set daily budget
pr-resolve apply --pr 123 --cost-budget 10.0

# Budget exceeded? Error before API call
Error: Request would exceed cost budget: $10.45 > $10.00

```

**Budget Recommendations**:

| Usage Pattern | Recommended Budget | Safety Margin |
| -------------- | ------------------- | --------------- |
| Single PR (manual) | $1.00 | 2.6x avg cost |
| Daily automation (10 PRs) | $5.00 | 1.3x avg cost |
| Weekly automation (50 PRs) | $25.00 | 1.3x avg cost |
| High-volume (200+ PRs) | $100.00 | 1.3x avg cost |

### 2. Cost Monitoring

**Enable Metrics Tracking**:

```bash
pr-resolve apply --pr 123 --llm-metrics

# Output shows:
Total Cost: $2.45
Remaining Budget: $7.55
Average Cost per Request: $0.24

```

**Set Up Alerts**:

```yaml
# config.yaml
cost_alerts:
  - threshold: 5.0
    action: "warn"
  - threshold: 8.0
    action: "email"
  - threshold: 10.0
    action: "block"

```

### 3. Rate Limiting

**Prevent Cost Spikes from Parallel Processing**:

```yaml
# Limit concurrent requests
optimization:
  parallel: true
  max_workers: 4  # Instead of 8 or 16

```

**Cost Impact**:

- 4 workers: Controlled costs, 3-4x speedup
- 8 workers: 2x cost rate, 6-8x speedup
- 16 workers: 4x cost rate, potential rate limit issues

---

## Model Selection Strategy

### Quality vs Cost Trade-off

Quality  │
   100% │                        ● Claude Sonnet 4
        │                    ● GPT-4o
    80% │              ● Claude Haiku
        │          ● GPT-4o-mini
    60% │      ● Llama 3:8b (local)
        │  ● Llama 3.2:3b
    40% │● Llama 3.2:1b
        └────────────────────────────────────► Cost
         $0    $1    $5   $10   $15   $20
              (per 1M tokens)

### Decision Matrix

| Use Case | Recommended Model | Why |
| ---------- | ------------------ | ----- |
| **Development & Testing** | Ollama llama3.2:1b | Free, fast, good enough |
| **CI/CD Automation** | GPT-4o-mini | Best value, reliable |
| **Production (cost-focused)** | Claude Haiku + caching | Fast + cheap + caching |
| **Production (quality-focused)** | GPT-4o | Balanced quality/cost |
| **Enterprise** | Claude Sonnet 4 | Best quality, worth cost |
| **Personal Projects** | Codex CLI / Ollama | Free options |

### When to Upgrade Models

**Start Cheap, Upgrade as Needed**:

1. **Phase 1: Development** - Ollama `llama3.2:1b`
   - Cost: $0
   - Goal: Fast iteration, testing

2. **Phase 2: Testing** - GPT-4o-mini
   - Cost: ~$4/month
   - Goal: Validate quality on real PRs

3. **Phase 3: Low-Volume Production** - GPT-4o-mini + caching
   - Cost: ~$8-15/month
   - Goal: Reliable, cost-effective

4. **Phase 4: High-Volume Production** - Claude Haiku + caching
   - Cost: ~$15-30/month
   - Goal: Scale with minimal cost increase

5. **Phase 5: Enterprise** - Claude Sonnet 4 (if needed)
   - Cost: ~$90+/month
   - Goal: Best possible quality

**Upgrade Triggers**:

- ❌ Quality complaints from users
- ❌ Too many parsing failures
- ❌ Cost not a concern
- ✅ Stay on current model if working well

---

## Cost Monitoring

### Built-in Cost Tracking

**Per-Request Tracking**:

```bash
pr-resolve apply --pr 123 --llm-metrics --log-level info

# Logs show:
INFO: Request 1: 1,234 tokens → $0.38
INFO: Request 2: 987 tokens → $0.30
INFO: Request 3: CACHE HIT → $0.00
INFO: Total Cost: $0.68

```

**Aggregate Metrics**:

```bash
# Summary after run
=== Cost Summary ===
Total Requests: 10
Cache Hits: 7 (70%)
API Calls: 3
Total Tokens: 5,432
Total Cost: $2.10
Average Cost per PR: $0.21

```

### Export Cost Data

**JSON Export for Analysis**:

```python
from pr_conflict_resolver.llm.metrics import MetricsAggregator

metrics = MetricsAggregator()
# ... process PRs ...

# Export metrics
import json
with open('cost-report.json', 'w') as f:
    json.dump(metrics.to_dict(), f, indent=2)
```

**Example Output**:

```json
{
  "summary": {
    "total_requests": 100,
    "total_cost": 38.50,
    "cost_by_provider": {
      "openai": 38.50
    }
  },
  "by_provider": {
    "openai/gpt-4o-mini": {
      "total_requests": 100,
      "total_cost": 38.50,
      "avg_cost_per_request": 0.385,
      "total_tokens": 125000
    }
  }
}

```

### Monthly Cost Reporting

**Track Spending Over Time**:

```bash
# Daily cron job
0 0 * * * pr-resolve export-metrics >> /var/log/pr-costs.jsonl

# Weekly report
pr-resolve cost-report --since 7d

# Output:
Week of Nov 12-19, 2025:
Total PRs: 42
Total Costs: $16.10
Average per PR: $0.38
Cheapest day: Monday ($1.20)
Most expensive day: Friday ($3.80)

```

---

## Real-World Cost Examples

### Scenario 1: Solo Developer (10 PRs/month)

**Setup**: Ollama local with llama3.2:3b

**Costs**:

- Hardware: $0 (existing laptop with 16GB RAM)
- Electricity: $3/month (24/7 server)
- API: $0
- **Total: $3/month**

**Comparison to Paid**:

- GPT-4o-mini: $19/month
- Claude Haiku: $37.50/month
- **Savings: $16-34.50/month** ($192-414/year)

### Scenario 2: Small Team (50 PRs/month)

**Setup**: GPT-4o-mini with prompt caching

**Costs**:

- No caching: $95/month
- With caching (75% hit rate): $23.75/month
- **Total: $23.75/month**

**ROI of Caching**: $71.25/month savings

### Scenario 3: Medium Team (200 PRs/month)

**Setup**: Claude Haiku with native + app caching

**Costs**:

- No caching: $750/month
- Native caching (50% reduction): $375/month
- - App caching (75% reduction): $93.75/month
- **Total: $93.75/month**

**ROI of Dual Caching**: $656.25/month savings ($7,875/year)

### Scenario 4: Enterprise (1000 PRs/month)

**Setup**: Hybrid approach

- 70% via Ollama (on-premises)
- 30% via Claude Sonnet (quality-critical)

**Costs**:

- Ollama (700 PRs): $0 (hardware already owned)
- Claude Sonnet (300 PRs): $135/month (with caching)
- **Total: $135/month**

**Comparison to All-Cloud**:

- All Claude Sonnet: $450/month
- **Savings: $315/month** ($3,780/year)

---

## Cost Optimization Strategies Summary

### Immediate Actions (Quick Wins)

1. ✅ **Enable Prompt Caching** - 60-90% cost reduction

   ```bash
   --cache-enabled
   ```

2. ✅ **Use GPT-4o-mini Instead of GPT-4o** - 95% cost reduction

   ```bash
   --llm-preset openai-api-mini
   ```

3. ✅ **Set Cost Budgets** - Prevent overruns

   ```bash
   --cost-budget 10.0
   ```

4. ✅ **Switch to Ollama for Development** - 100% API cost reduction

   ```bash
   --llm-preset ollama-local
   ```

### Medium-Term Actions

1. ✅ **Warm Cache with Common Patterns** - +20% cache hit rate

2. ✅ **Standardize Team Comment Phrasing** - +15% cache hit rate

3. ✅ **Increase Cache TTL** - +10-20% cache hit rate

4. ✅ **Use Anthropic Haiku for High Volume** - Native + app caching

### Long-Term Actions

1. ✅ **Deploy Ollama on Team Server** - Zero marginal cost

2. ✅ **Hybrid Cloud + Local Strategy** - Best of both worlds

3. ✅ **Monitor and Optimize** - Continuous improvement

---

## Cost Optimization Checklist

### Before First Use

- [ ] Decide: Free (Ollama/CLI) vs Paid (API)
- [ ] If Paid: Choose cheapest model that meets quality needs
- [ ] Enable prompt caching
- [ ] Set conservative cost budget
- [ ] Test on a few PRs to estimate costs

### After First Month

- [ ] Review actual costs vs estimates
- [ ] Check cache hit rate (aim for 70%+)
- [ ] Identify most expensive operations
- [ ] Consider switching providers if costs high
- [ ] Warm cache with common patterns

### Quarterly Review

- [ ] Total costs vs budget
- [ ] Cost per PR trend
- [ ] Cache effectiveness
- [ ] Provider comparison
- [ ] Consider Ollama if costs growing

---

## Additional Resources

- [Optimization Guide](optimization-guide.md) - Performance and cost optimization
- [LLM Configuration](llm-configuration.md) - Provider setup and pricing
- [Provider Comparison](providers.md) - Detailed provider analysis

---

## Cost Calculator

**Interactive Cost Estimator**: Coming soon - link will be added when available

**Quick Estimate Formula**:

Monthly Cost = (PRs/month × comments/PR × (1 - cache_hit_rate) × cost_per_comment)

Example:
50 PRs × 10 comments × (1 - 0.75) × $0.38 = $47.50/month

---

_Need help optimizing costs for your specific use case? Open an issue on GitHub with your usage pattern and we'll provide personalized recommendations._
