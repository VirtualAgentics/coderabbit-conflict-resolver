# Optimization Guide

**Last Updated**: November 19, 2025
**Applies To**: v2.0+ (Phase 5: Optimization & Production Readiness)

This guide provides comprehensive strategies for optimizing the performance, cost, and reliability of the PR Conflict Resolver with LLM-powered comment parsing.

## Table of Contents

- [Quick Start: Optimization Checklist](#quick-start-optimization-checklist)
- [Performance Optimization](#performance-optimization)
- [Cost Optimization](#cost-optimization)
- [Reliability Optimization](#reliability-optimization)
- [Resource Management](#resource-management)
- [Monitoring & Observability](#monitoring--observability)
- [Production Deployment Best Practices](#production-deployment-best-practices)

---

## Quick Start: Optimization Checklist

### For Development & Testing

- [ ] Use free providers: `codex-cli-free` or `ollama-local`
- [ ] Enable prompt caching: `--cache-enabled`
- [ ] Use small models: `llama3.2:1b` (Ollama) or `gpt-4o-mini` (OpenAI)
- [ ] Set conservative cost budgets: `--cost-budget 1.0`

### For Production

- [ ] Enable all optimizations: `--parallel --cache-enabled`
- [ ] Configure circuit breaker: `--circuit-breaker-threshold 5`
- [ ] Set appropriate cost budgets: `--cost-budget 10.0`
- [ ] Monitor metrics: Review costs and latencies after each run
- [ ] Use balanced providers: Claude Haiku or GPT-4o-mini

### For High-Volume Usage

- [ ] Use local models: Ollama with GPU acceleration
- [ ] Maximize cache hit rate: Warm cache with common patterns
- [ ] Increase parallelism: `--max-workers 8`
- [ ] Pre-warm models: Download Ollama models in advance

---

## Performance Optimization

### 1. Parallel Processing

**What It Does**: Processes multiple PR comments concurrently instead of sequentially.

#### When to Use

- ✅ PRs with 5+ comments
- ✅ High-performance environments (multiple CPU cores)
- ✅ Providers with good API rate limits (Ollama, Claude, GPT-4)

#### When NOT to Use

- ❌ Single-comment PRs (overhead > benefit)
- ❌ Rate-limited API providers (will hit limits faster)
- ❌ Memory-constrained environments

#### Configuration

```bash
# Enable with default workers (4)
pr-resolve apply --pr 123 --parallel

# Customize worker count
pr-resolve apply --pr 123 --parallel --max-workers 8

# Config file (YAML)
parallel: true
max_workers: 8
```

#### Performance Impact

| PR Comments | Sequential | Parallel (4 workers) | Speedup |
| ----------- | ---------- | -------------------- | ------- |
| 2 comments | 2.0s | 2.1s | 0.95x |
| 5 comments | 5.0s | 1.5s | 3.3x |
| 10 comments | 10.0s | 3.0s | 3.3x |
| 20 comments | 20.0s | 6.0s | 3.3x |

#### Optimal Worker Count

- **CPU-bound (Ollama local)**: `workers = CPU cores`
- **I/O-bound (API providers)**: `workers = 4-8`
- **Memory-limited**: `workers = 2-4`

#### Trade-offs

- ✅ **Pro**: 2-4x faster for multi-comment PRs
- ✅ **Pro**: Better resource utilization
- ❌ **Con**: Slightly higher memory usage
- ❌ **Con**: May hit API rate limits faster

### 2. Prompt Caching

**What It Does**: Caches LLM responses for identical prompts to avoid redundant API calls.

#### When to Use

- ✅ **Always** - No downside, significant benefits
- ✅ Repeated runs on same PR
- ✅ Multiple PRs with similar comments
- ✅ Testing and development workflows

#### Configuration

```bash
# Enable caching (recommended)
pr-resolve apply --pr 123 --cache-enabled

# Customize cache settings
pr-resolve apply --pr 123 \
  --cache-enabled \
  --cache-max-size 5000 \
  --cache-ttl 7200  # 2 hours

# Config file (YAML)
cache:
  enabled: true
  max_size: 5000
  ttl: 7200
```

#### Cache Hit Rate Optimization

1. **Warm the cache** with common patterns:

   ```python
   from pr_conflict_resolver.llm.cache import CacheOptimizer

   optimizer = CacheOptimizer()
   optimizer.warm_cache(common_comments=[
       "LGTM",
       "Please fix the linting errors",
       "Add tests for this feature"
   ])

```bash

2. **Increase TTL** for stable codebases:
   - Development: 1 hour (default)
   - Staging: 4 hours
   - Production: 24 hours

3. **Increase max_size** for high-volume usage:
   - Low volume: 1,000 entries (default)
   - Medium volume: 5,000 entries
   - High volume: 10,000 entries

#### Performance Impact

- **Cache Hit**: ~0.01s (vs 0.5-2.0s for API call)
- **Cost Savings**: 100% (no API call made)
- **Memory Usage**: ~5 KB per cached entry

**Anthropic-Specific**: Anthropic API has native prompt caching (50-90% cost reduction). Our cache layer provides **additional** benefits:

- Eliminates latency for exact matches
- Works across different API keys
- Persists across application restarts (optional)

### 3. Model Selection

**What It Does**: Choose faster/cheaper models based on your requirements.

#### Model Comparison

| Provider | Model | Speed | Cost | Quality | Use Case |
| ---------- | ------- | ------- | ------ | --------- | ---------- |
| Ollama | llama3.2:1b | ⚡⚡⚡ | 💰 Free | ⭐⭐⭐ | Development, testing |
| Ollama | llama3.2:3b | ⚡⚡ | 💰 Free | ⭐⭐⭐⭐ | General use |
| Ollama | llama3:8b | ⚡ | 💰 Free | ⭐⭐⭐⭐⭐ | Production (local) |
| OpenAI | gpt-4o-mini | ⚡⚡ | 💰💰 | ⭐⭐⭐⭐ | Cost-conscious production |
| OpenAI | gpt-4o | ⚡ | 💰💰💰 | ⭐⭐⭐⭐⭐ | High-quality needs |
| Anthropic | claude-haiku | ⚡⚡⚡ | 💰💰 | ⭐⭐⭐⭐ | Balanced prod (fastest) |
| Anthropic | claude-sonnet | ⚡⚡ | 💰💰💰 | ⭐⭐⭐⭐⭐ | High-quality prod |
| Codex CLI | gpt-4 | ⚡ | 💰 Free* | ⭐⭐⭐⭐⭐ | Copilot subscribers |
| Claude CLI | claude-sonnet | ⚡⚡ | 💰 Free* | ⭐⭐⭐⭐⭐ | Claude subscribers |

*Free with subscription

#### Recommendation

- **Development**: `ollama-local` preset with `llama3.2:1b`
- **Production (cost-conscious)**: `openai-api-mini` or `anthropic-api-balanced`
- **Production (quality-first)**: `anthropic-api-balanced` or `openai-api-smart`
- **Free production**: `codex-cli-free` or `claude-cli-sonnet`

### 4. GPU Acceleration (Ollama Only)

**What It Does**: Uses GPU for inference instead of CPU, providing 5-50x speedup.

#### Auto-Detection

```bash
# GPU automatically detected and used
pr-resolve apply --pr 123 --llm-preset ollama-local

# Verify GPU usage
pr-resolve apply --pr 123 --llm-preset ollama-local --log-level debug
# Look for: "GPU: NVIDIA GeForce RTX 3080 (10GB VRAM)"
```

#### GPU Performance

| Hardware | Model Size | Inference Time | Throughput |
| ---------- | ----------- | --------------- | ------------ |
| CPU (8-core) | 1B params | ~500ms | 2 req/s |
| CPU (8-core) | 8B params | ~2000ms | 0.5 req/s |
| GPU (RTX 3060) | 1B params | ~50ms | 20 req/s |
| GPU (RTX 3060) | 8B params | ~200ms | 5 req/s |
| GPU (RTX 4090) | 8B params | ~100ms | 10 req/s |

#### Optimization Tips

1. **Batch requests** to maximize GPU utilization
2. **Pre-load models** to avoid startup latency:

   ```bash
   ollama pull llama3.2:3b
   ```

3. **Use quantized models** if VRAM-limited:
   - `llama3:8b-q4_0` (4-bit, ~4GB VRAM)
   - `llama3:8b-q8_0` (8-bit, ~8GB VRAM)

---

## Cost Optimization

See [cost-optimization.md](cost-optimization.md) for comprehensive cost strategies.

### Quick Tips

1. Use free providers when possible (Ollama, Codex CLI, Claude CLI)
2. Enable prompt caching to avoid redundant API calls
3. Set cost budgets to prevent overruns: `--cost-budget 10.0`
4. Choose cost-effective models (GPT-4o-mini, Claude Haiku)
5. Monitor costs with `--llm-metrics` flag

---

## Reliability Optimization

### 1. Circuit Breaker Pattern

**What It Does**: Prevents cascading failures by temporarily blocking requests to failing providers.

#### States

- **CLOSED** (normal): All requests pass through
- **OPEN** (failing): Requests immediately rejected (fast-fail)
- **HALF_OPEN** (testing): Limited requests to test recovery

#### Configuration

```bash
# Enable with defaults (5 failures, 60s timeout)
pr-resolve apply --pr 123 --circuit-breaker-enabled

# Customize thresholds
pr-resolve apply --pr 123 \
  --circuit-breaker-enabled \
  --circuit-breaker-threshold 3 \
  --circuit-breaker-timeout 30

# Config file (YAML)
circuit_breaker:
  enabled: true
  failure_threshold: 3
  recovery_timeout: 30
  success_threshold: 2
```

#### When Circuit Opens

1. Error logged: `Circuit breaker OPEN after N failures`
2. Subsequent requests fail immediately (no API calls)
3. After timeout, enters HALF_OPEN state
4. If recovery succeeds → CLOSED
5. If recovery fails → OPEN again

#### Tuning Guidelines

| Scenario | Threshold | Timeout | Success Threshold |
| ---------- | ----------- | --------- | ------------------- |
| Development | 10 | 60s | 2 |
| Production (stable) | 5 | 60s | 2 |
| Production (unstable) | 3 | 30s | 3 |
| CI/CD | 2 | 15s | 1 |

### 2. Retry Logic

**What It Does**: Automatically retries failed requests with exponential backoff.

#### Built-in Retry Logic

- Transient errors (network, timeout): 3 retries
- Backoff: 2s, 4s, 8s
- Rate limits: Honors `Retry-After` headers

#### Not Retried

- Authentication errors (permanent)
- Invalid input (client errors)
- Circuit breaker open (fast-fail)

#### Configuration

```python
# Providers use tenacity for retry logic
# Customize in provider initialization (advanced)
from pr_conflict_resolver.llm.providers import OpenAIAPIProvider

provider = OpenAIAPIProvider(
    api_key=api_key,
    model="gpt-4o-mini",
    max_retries=5,  # Default: 3
    retry_backoff=1.5  # Default: 2.0
)
```

### 3. Cost Budgeting

**What It Does**: Prevents runaway API costs by enforcing spending limits.

#### Configuration

```bash
# Set budget (recommended for production)
pr-resolve apply --pr 123 --cost-budget 10.0

# Budget check before each request
# Raises CostBudgetExceededError if exceeded
```

#### Budget Calculation

```text
Estimated Cost = (input_tokens / 1000 * input_price) +
                 (output_tokens / 1000 * output_price)

Budget Check = current_cost + estimated_cost <= budget
```

#### Production Recommendations

| Usage Pattern | Recommended Budget |
| -------------- | ------------------- |
| Single PR | $1.00 |
| Daily automation (10 PRs) | $10.00 |
| Weekly automation (50 PRs) | $50.00 |
| High-volume (200+ PRs) | $200.00 |

#### Monitoring

```bash
# Check spending after run
pr-resolve apply --pr 123 --llm-metrics

# Output includes:
# Total Cost: $0.45
# Remaining Budget: $9.55
```

---

## Resource Management

### 1. Memory Usage

#### Memory Footprint

| Component | Base | With Cache (1K entries) | With Cache (10K entries) |
| ----------- | ------ | ------------------------ | -------------------------- |
| Application | ~50 MB | ~55 MB | ~100 MB |
| Ollama (1B) | ~1.5 GB | - | - |
| Ollama (8B) | ~8 GB | - | - |

#### Memory Optimization

1. **Limit cache size** if memory-constrained:

   ```bash
   --cache-max-size 500  # 500 entries (~2.5 MB)

```bash

2. **Use smaller models** (Ollama):
   - `llama3.2:1b` (~1.5 GB)
   - `qwen2.5:0.5b` (~500 MB)

3. **Reduce worker count**:

   ```bash
   --max-workers 2  # Instead of default 4
```

### 2. Thread Management

#### Thread Usage

- Main thread: 1
- Worker threads: `max_workers` (default: 4)
- Background threads: 1 (cache cleanup)

**Total**: ~6 threads by default

#### Thread Pool Cleanup

- Automatic via context managers
- No manual cleanup required
- Threads terminated on process exit

### 3. Network Connections

#### Connection Pooling

- API providers use `requests.Session()`
- Pool size: 10 connections per provider
- Keep-alive: Enabled for reuse

#### Optimization

```python
# Reuse provider instances across requests
provider = OpenAIAPIProvider(api_key=api_key)

# Good: Single provider for multiple requests
for pr in prs:
    result = provider.generate(pr.comment)

# Bad: New provider per request (recreates pool)
for pr in prs:
    provider = OpenAIAPIProvider(api_key=api_key)
    result = provider.generate(pr.comment)
```

---

## Monitoring & Observability

### 1. Built-in Metrics

#### Enable Metrics

```bash
pr-resolve apply --pr 123 --llm-metrics

# Output after completion:
=== LLM Metrics ===
Provider: anthropic (claude-haiku-20240307)
Requests: 10 total, 10 successful, 0 failed
Latency: p50=250ms, p95=500ms, p99=750ms
Tokens: 5,000 input, 2,500 output (7,500 total)
Cost: $0.45 total, $0.045 avg per request
Success Rate: 100.0%
Circuit Breaker: CLOSED

Provider: ollama (llama3.2:3b)
Requests: 5 total, 5 successful, 0 failed
Latency: p50=150ms, p95=300ms, p99=400ms
Cost: $0.00 (local model)
```

#### Metrics Available

- Total requests (per provider/model)
- Success/failure counts
- Latency percentiles (P50, P95, P99)
- Token usage (input/output/total)
- Cost breakdown by provider
- Circuit breaker state
- Cache hit rate

### 2. Logging

#### Log Levels

```bash
# Minimal (errors only)
pr-resolve apply --pr 123 --log-level error

# Normal (info + errors)
pr-resolve apply --pr 123 --log-level info

# Verbose (debug everything)
pr-resolve apply --pr 123 --log-level debug

# Save to file
pr-resolve apply --pr 123 --log-file pr-123.log
```

#### What's Logged

- `ERROR`: API failures, circuit breaker trips
- `WARNING`: Rate limits, cache misses, retries
- `INFO`: Request/response, cache hits
- `DEBUG`: Full prompts, tokens, costs

### 3. Exporting Metrics

#### JSON Export

```python
from pr_conflict_resolver.llm.metrics import MetricsAggregator

metrics = MetricsAggregator()
# ... run operations ...

# Export to JSON
import json
with open('metrics.json', 'w') as f:
    json.dump(metrics.to_dict(), f, indent=2)
```

**Prometheus Integration** (future):

```python
# Example for future monitoring integration
from pr_conflict_resolver.llm.metrics import MetricsAggregator
from prometheus_client import Gauge, Counter

requests_total = Counter('llm_requests_total', 'Total LLM requests', ['provider', 'model'])
latency_seconds = Gauge('llm_latency_seconds', 'LLM latency', ['provider', 'model', 'percentile'])
cost_usd = Gauge('llm_cost_usd', 'LLM cost', ['provider'])

def export_to_prometheus(metrics: MetricsAggregator):
    summary = metrics.get_summary()
    # Export metrics to Prometheus
    # ... implementation ...
```

---

## Production Deployment Best Practices

### 1. Configuration Management

#### Use Config Files (Not CLI Flags)

```yaml
# production.yaml
llm:
  preset: "anthropic-api-balanced"

optimization:
  parallel: true
  max_workers: 8
  cache:
    enabled: true
    max_size: 10000
    ttl: 86400  # 24 hours

resilience:
  circuit_breaker:
    enabled: true
    failure_threshold: 5
    recovery_timeout: 60
  cost_budget: 100.0  # $100/day

logging:
  level: "info"
  file: "/var/log/pr-resolver/pr-resolver.log"
```

#### Load Config

```bash
pr-resolve apply --pr 123 --config production.yaml
```

### 2. Environment Variables

#### Required

```bash
# API Keys (never commit!)
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export GITHUB_TOKEN="${GITHUB_TOKEN}"
```

#### Optional

```bash
# Override config file settings
export CR_LLM_PROVIDER="anthropic"
export CR_LLM_MODEL="claude-haiku-20240307"
export CR_PARALLEL="true"
export CR_MAX_WORKERS="8"
export CR_CACHE_ENABLED="true"
export CR_COST_BUDGET="100.0"
```

### 3. Health Checks

#### Provider Health Check

```bash
# Verify provider is accessible
pr-resolve check-provider --provider anthropic

# Output:
✓ Provider: anthropic
✓ Authentication: Valid
✓ Model: claude-haiku-20240307 available
✓ Circuit Breaker: CLOSED
✓ Latency: 250ms (healthy)
```

### 4. Graceful Degradation

#### Fallback Strategy

```yaml
# Config with fallback providers
llm:
  primary: "anthropic-api-balanced"
  fallback: "ollama-local"

  # If primary fails (circuit breaker open):
  # 1. Try fallback provider
  # 2. If fallback fails, use manual parsing
```

### 5. Rate Limiting

#### Respect Provider Limits

| Provider | Free Tier | Paid Tier | Recommendation |
| ---------- | ----------- | ----------- | ---------------- |
| OpenAI | 3 RPM | 3,500 RPM | Max 4 workers |
| Anthropic | 5 RPM | 50 RPM | Max 8 workers |
| Ollama | Unlimited | Unlimited | Max = CPU cores |
| Codex CLI | ~20 RPM | ~60 RPM | Max 4 workers |
| Claude CLI | ~20 RPM | ~60 RPM | Max 4 workers |

#### Configure Workers

```yaml
optimization:
  max_workers: 4  # Safe for most providers
```

### 6. Monitoring Alerts

#### Key Metrics to Alert On

1. **Circuit Breaker State**: Alert if OPEN for > 5 minutes
2. **Cost Threshold**: Alert at 80% of budget
3. **Error Rate**: Alert if > 5% failures
4. **Latency**: Alert if P95 > 2 seconds

#### Example (Prometheus AlertManager)

```yaml
# alerts.yml
groups:
  - name: llm_alerts
    rules:
      - alert: CircuitBreakerOpen
        expr: llm_circuit_breaker_state == 1
        for: 5m
        annotations:
          summary: "LLM circuit breaker open"

      - alert: HighCost
        expr: llm_cost_usd > (llm_budget_usd * 0.8)
        annotations:
          summary: "LLM costs at 80% of budget"
```

---

## Performance Benchmarks

### Real-World Performance

#### Scenario: 10-comment PR, OpenAI GPT-4o-mini

| Configuration | Time | Cost | Notes |
| -------------- | ------ | ------ | ------- |
| Baseline | 10.0s | $0.50 | Sequential, no cache |
| + Cache | 10.0s | $0.50 | First run (cold cache) |
| + Cache | 0.1s | $0.00 | Second run (warm cache) |
| + Parallel | 3.0s | $0.50 | 4 workers, no cache |
| + Parallel + Cache | 3.0s | $0.50 | First run |
| + Parallel + Cache | 0.1s | $0.00 | Second run |

#### Scenario: 10-comment PR, Ollama llama3.2:3b (GPU)

| Configuration | Time | Cost | Notes |
| -------------- | ------ | ------ | ------- |
| Baseline | 5.0s | $0.00 | Sequential |
| + Parallel (4 workers) | 1.5s | $0.00 | GPU utilization: 60% |
| + Parallel (8 workers) | 1.0s | $0.00 | GPU utilization: 95% |

### Optimization Impact Summary

| Optimization | Performance Gain | Cost Savings | Complexity |
| ------------- | ------------------ | -------------- | ------------ |
| Prompt Caching | 10-100x (warm) | 100% (hits) | Low |
| Parallel Processing | 2-4x | 0% | Low |
| GPU Acceleration | 5-50x (Ollama) | 100% (vs API) | Medium |
| Smaller Models | 2-5x | 50-90% | Low |
| Circuit Breaker | N/A | Prevents waste | Low |
| Cost Budgeting | N/A | Prevents overrun | Low |

---

## Troubleshooting Performance Issues

### Slow Performance

**Symptoms**: Requests taking > 5 seconds

#### Diagnosis

```bash
# Enable debug logging
pr-resolve apply --pr 123 --log-level debug

# Look for:
# - High latency per request (> 2s)
# - Cache misses
# - Sequential processing
```

#### Solutions

1. Enable parallel processing: `--parallel`
2. Use faster model: Switch to `claude-haiku` or `gpt-4o-mini`
3. Enable GPU (Ollama): Verify GPU detected in logs
4. Check network latency: Test API from same region

### High Memory Usage

**Symptoms**: OOM errors or > 1 GB memory usage

#### Diagnosis

```bash
# Monitor memory
top -p $(pgrep -f pr-resolve)
```

#### Solutions

1. Reduce cache size: `--cache-max-size 500`
2. Use smaller model (Ollama): `llama3.2:1b`
3. Reduce workers: `--max-workers 2`

### High Costs

**Symptoms**: Unexpected API bills

#### Diagnosis

```bash
# Check metrics
pr-resolve apply --pr 123 --llm-metrics
```

#### Solutions

1. Enable caching: `--cache-enabled`
2. Switch to cheaper model: `gpt-4o-mini` or `claude-haiku`
3. Set cost budget: `--cost-budget 10.0`
4. Use free provider: Ollama or CLI-based

### Circuit Breaker Stuck Open

**Symptoms**: All requests failing with `CircuitBreakerError`

#### Diagnosis

```bash
# Check circuit breaker state
pr-resolve check-provider --provider anthropic
```

#### Solutions

1. Wait for recovery timeout (default: 60s)
2. Check provider status (API outage?)
3. Reset circuit breaker: Restart application
4. Adjust thresholds: Lower `failure_threshold`

---

## Summary: Optimal Configuration

### For Cost-Conscious Users

```yaml
llm:
  preset: "ollama-local"  # Free
  model: "llama3.2:3b"

optimization:
  parallel: true
  max_workers: 4
  cache:
    enabled: true

resilience:
  circuit_breaker:
    enabled: true
  cost_budget: 1.0  # Safety net
```

### For Performance-Focused Users

```yaml
llm:
  preset: "anthropic-api-balanced"  # Fast
  model: "claude-haiku-20240307"

optimization:
  parallel: true
  max_workers: 8
  cache:
    enabled: true
    max_size: 10000

resilience:
  circuit_breaker:
    enabled: true
  cost_budget: 100.0
```

### For Balanced Users (Recommended)

```yaml
llm:
  preset: "openai-api-mini"  # Good balance
  model: "gpt-4o-mini"

optimization:
  parallel: true
  max_workers: 4
  cache:
    enabled: true
    max_size: 5000

resilience:
  circuit_breaker:
    enabled: true
  cost_budget: 10.0
```

---

## Additional Resources

- [Cost Optimization Guide](cost-optimization.md) - Detailed cost strategies
- [LLM Configuration Guide](llm-configuration.md) - Provider setup and configuration
- [Security Audit Report](security/phase5-security-audit.md) - Security best practices
- [API Documentation](api/) - Programmatic usage

---

*For questions or issues, please open an issue on GitHub or refer to the project documentation.*
