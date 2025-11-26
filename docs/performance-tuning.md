# Performance Tuning Guide

This guide covers optimization strategies for maximizing throughput and minimizing latency when using the Review Bot Automator.

## Overview

Performance depends on several factors:

* **Parallel processing**: Worker count and rate limiting
* **LLM provider**: Latency and throughput characteristics
* **Caching**: Hit rate and warm-up strategies
* **Network**: Connection pooling and timeouts

## Parallel Processing Optimization

### Worker Count Recommendations

| PR Size (Comments) | Recommended Workers | Rationale |
|-------------------|---------------------|-----------|
| 1-10 | 2-4 | Low overhead, minimal benefit from more workers |
| 10-50 | 4-8 | Good parallelization benefit |
| 50-100 | 8-12 | Higher throughput, watch for rate limits |
| 100+ | 12-16 | Maximum throughput, requires careful rate limiting |

### Configuration

```yaml
parallel:
  enabled: true
  max_workers: 8
```

Or via CLI:

```bash
pr-resolve apply 123 --parallel --max-workers 8
```

### Monitoring Parallel Performance

```bash
pr-resolve apply 123 --parallel --max-workers 8 --show-metrics
```

Check the metrics output:

* **Latency p95 vs p50**: Large gap indicates bottlenecks
* **Success rate**: Should be > 99%
* **Cache hit rate**: Higher is better for parallel workloads

## LLM Provider Optimization

### Provider Latency Comparison

| Provider | Typical p50 | Typical p95 | Best For |
|----------|-------------|-------------|----------|
| Ollama (local) | 0.5-2.0s | 2.0-5.0s | Privacy, no network latency |
| Claude CLI | 0.3-1.0s | 1.0-3.0s | Quality + speed balance |
| Anthropic API | 0.2-0.8s | 0.8-2.0s | Lowest latency |
| OpenAI API | 0.3-1.0s | 1.0-3.0s | Good balance |

### Model Selection for Speed

**Fastest models by provider:**

```yaml
# Anthropic - Use Haiku for speed
llm:
  provider: anthropic
  model: claude-haiku-4-20250514

# OpenAI - Use mini for speed
llm:
  provider: openai
  model: gpt-4o-mini

# Ollama - Use smaller model
llm:
  provider: ollama
  model: qwen2.5-coder:7b  # Faster than llama3.3:70b
```

## Cache Optimization

### Cache Hit Rate Targets

* **< 20%**: Consider warming the cache
* **20-40%**: Normal for varied PRs
* **40-60%**: Good cache effectiveness
* **\> 60%**: Excellent (common patterns)

### Cache Warming

Pre-populate the cache for cold start optimization:

```python
from review_bot_automator.llm.cache.prompt_cache import PromptCache

cache = PromptCache()

# Load from previous export
entries = json.loads(Path("cache_export.json").read_text())
loaded, skipped = cache.warm_cache(entries)
print(f"Loaded {loaded} entries, skipped {skipped} duplicates")
```

### Cache Configuration

```yaml
llm:
  cache_enabled: true
  # Cache automatically manages size with LRU eviction
```

## Rate Limit Handling

### Retry Configuration

```yaml
llm:
  retry_on_rate_limit: true
  retry_max_attempts: 5
  retry_base_delay: 2.0  # Exponential backoff
```

### Rate Limit Best Practices

1. **Reduce workers when hitting limits:**

   ```bash
   export CR_MAX_WORKERS=4  # Down from 8
   ```

2. **Use circuit breaker:**

   ```yaml
   llm:
     circuit_breaker_enabled: true
     circuit_breaker_threshold: 5
   ```

3. **Monitor rate limit errors:**

   ```bash
   pr-resolve apply 123 --show-metrics --log-level INFO
   # Watch for "Rate limit exceeded" in logs
   ```

## Network Optimization

### Connection Pooling

Connection pooling is enabled by default for all HTTP-based providers. This reduces connection overhead for multiple requests.

### Timeout Configuration

Timeouts are not currently user-configurable. Default timeouts:

* **Connect timeout**: 30 seconds
* **Read timeout**: 120 seconds

If experiencing timeouts:

1. Check network connectivity
2. Try a different provider
3. Reduce parallel workers

## GPU Acceleration (Ollama)

### Enabling GPU

GPU acceleration is automatic when:

1. CUDA/ROCm/Metal drivers are installed
2. Ollama detects the GPU

### Verifying GPU Usage

```bash
# NVIDIA
nvidia-smi  # Watch for ollama process

# AMD
rocm-smi

# Apple Silicon
# GPU usage is automatic
```

### GPU vs CPU Performance

| Model | CPU (tokens/s) | GPU (tokens/s) | Speedup |
|-------|---------------|----------------|---------|
| llama3.2:3b | ~20 | ~100 | 5x |
| llama3.1:8b | ~10 | ~80 | 8x |
| llama3.3:70b | ~2 | ~30 | 15x |

## Memory Optimization

### Reducing Memory Usage

1. **Use smaller models:**

   ```bash
   export CR_LLM_MODEL=llama3.2:3b  # Instead of 70b
   ```

2. **Reduce workers:**

   ```bash
   export CR_MAX_WORKERS=2
   ```

3. **Process sequentially:**

   ```bash
   export CR_PARALLEL=false
   ```

### Memory Requirements by Model

| Model | Minimum RAM | Recommended RAM |
|-------|-------------|-----------------|
| llama3.2:3b | 4 GB | 8 GB |
| llama3.1:8b | 8 GB | 16 GB |
| qwen2.5-coder:7b | 8 GB | 16 GB |
| codestral:22b | 24 GB | 32 GB |
| llama3.3:70b | 48 GB | 64 GB |

## Benchmarking

### Running Benchmarks

```bash
# Quick benchmark
python scripts/benchmark_llm.py --iterations 10

# Comprehensive benchmark
python scripts/benchmark_llm.py --iterations 100 --providers all
```

### Key Metrics to Track

* **Tokens per second**: Model inference speed
* **Time to first token**: Perceived latency
* **Request latency p95**: Worst-case performance
* **Success rate**: Reliability

## Performance Profiles

### Development (Fast Iteration)

```yaml
llm:
  provider: ollama
  model: llama3.2:3b  # Fastest local
  cache_enabled: true

parallel:
  enabled: true
  max_workers: 4
```

### CI/CD (Balanced)

```yaml
llm:
  provider: anthropic
  model: claude-haiku-4-20250514  # Fast + accurate
  cache_enabled: true
  cost_budget: 2.0

parallel:
  enabled: true
  max_workers: 8
```

### Production (Maximum Quality)

```yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-5  # Highest quality
  confidence_threshold: 0.7
  cache_enabled: true

parallel:
  enabled: true
  max_workers: 4  # Careful rate limiting
```

## Troubleshooting Performance

### Slow Processing

1. Check metrics: `--show-metrics`
2. Review p95 latency - if high, check provider
3. Check cache hit rate - if low, consider warming
4. Reduce workers if hitting rate limits

### High Memory Usage

1. Use smaller model
2. Reduce worker count
3. Process sequentially for very large PRs

### Rate Limit Errors

1. Reduce worker count
2. Increase retry delay
3. Consider using a different provider

## See Also

* [Parallel Processing](parallel-processing.md) - Detailed parallel configuration
* [LLM Configuration](llm-configuration.md) - Full LLM setup guide
* [Cost Estimation](cost-estimation.md) - Managing API costs
* [Troubleshooting](troubleshooting.md) - Common issues and solutions
