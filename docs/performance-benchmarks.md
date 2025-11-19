# LLM Provider Performance Benchmarks

Comprehensive performance comparison of LLM providers for code review comment resolution.

## Overview

This benchmarking infrastructure allows you to systematically compare the performance of all supported LLM providers (Anthropic, OpenAI, Ollama, Claude CLI, Codex CLI) across multiple dimensions:

* **Latency**: Response time metrics (mean, median, P95, P99)
* **Throughput**: Requests per second
* **Accuracy**: Parsing success rate against ground truth
* **Cost**: Per-request and monthly estimates
* **GPU Performance**: Hardware utilization for local models

## Quick Start

### Prerequisites

* Python 3.12+ with virtual environment activated
* API keys configured for cloud providers (Anthropic, OpenAI)
* Ollama installed for local model testing (optional)

### Basic Usage

```bash
# Benchmark all providers with default settings (100 iterations)
python scripts/benchmark_llm.py --iterations 100

# Benchmark specific providers
python scripts/benchmark_llm.py --providers anthropic openai --iterations 50

# Use custom test dataset
python scripts/benchmark_llm.py --dataset my_comments.json --iterations 100

# Save report to custom location
python scripts/benchmark_llm.py --output reports/benchmark-2025-11-17.md

```

### Command-Line Options

```bash
python scripts/benchmark_llm.py --help

Options:
  --providers PROVIDERS [PROVIDERS ...]
                        LLM providers to benchmark (default: all)
                        Choices: anthropic, openai, ollama, claude-cli, codex-cli

  --iterations N        Number of iterations per provider (default: 100)
                        Recommended: 100+ for statistical significance

  --dataset PATH        Path to test dataset JSON file
                        (default: tests/benchmarks/sample_comments.json)

  --output PATH         Output markdown report path
                        (default: docs/performance-benchmarks.md)

  --warmup N           Number of warmup iterations (default: 5)
                        Warmup runs are not included in metrics

```

## Metrics Explained

### Latency Metrics

#### Mean Latency

* Average response time across all requests
* Good indicator of typical performance
* Affected by outliers

#### Median Latency (P50)

* Middle value when sorted by response time
* More robust to outliers than mean
* Better represents "typical" user experience

#### P95 Latency

* 95% of requests complete faster than this time
* Indicates worst-case performance for most users
* **Acceptance Criteria**: < 5 seconds for all providers

#### P99 Latency

* 99% of requests complete faster than this time
* Captures tail latency and outliers
* Important for SLA guarantees

### Throughput

#### Requests Per Second

* How many requests the provider can handle
* Calculated as: `1 / mean_latency`
* Higher is better for high-volume deployments

### Accuracy Metrics

#### Success Rate

* Percentage of requests that returned valid responses
* Calculated as: `successful_parses / total_requests`
* Target: > 95% for production use

#### Average Confidence

* Mean confidence score from parsed responses
* Range: 0.0 - 1.0 (higher is better)
* Indicates model certainty in suggestions

### Cost Analysis

#### Total Cost

* Sum of all API costs for the benchmark run
* Free for local models (Ollama, Claude CLI, Codex CLI)

#### Cost Per Request

* Average cost per API call
* Important for budgeting at scale

#### Monthly Estimates

* Projected costs at 1K and 10K requests/month
* Helps plan production deployment budgets

### GPU Information (Local Models Only)

For Ollama and local models, the benchmark captures:

* GPU name and model
* Total memory available
* Driver version
* CUDA version (NVIDIA GPUs)

## Test Dataset

The default benchmark dataset (`tests/benchmarks/sample_comments.json`) contains 30 realistic CodeRabbit-style review comments across three complexity levels:

### Simple Comments (10)

* Basic code suggestions
* Single-line fixes
* Simple formatting changes
* **Expected latency**: < 2s

### Medium Comments (10)

* Multi-line code changes
* Diff blocks with context
* Moderate refactoring suggestions
* **Expected latency**: 2-4s

### Complex Comments (10)

* Security vulnerability fixes
* Architecture refactoring
* Multi-file changes
* Multi-option recommendations
* **Expected latency**: 4-6s

### Ground Truth Annotations

Each comment includes ground truth data for accuracy validation:

```json
{
  "body": "```suggestion\ndef calculate_total(items):\n    return sum(item.price for item in items)\n```",
  "path": "src/cart.py",
  "line": 45,
  "ground_truth": {
    "changes": 1,
    "start_line": 45,
    "end_line": 46,
    "change_type": "modification",
    "confidence_threshold": 0.8
  }
}

```

### Creating Custom Datasets

To create your own benchmark dataset:

1. **Structure**: JSON file with three keys: `simple`, `medium`, `complex`
2. **Format**: Each category contains a list of comment objects
3. **Required fields**: `body`, `path`, `line`, `ground_truth`

Example custom dataset:

```json
{
  "simple": [
    {
      "body": "Fix typo: 'recieve' → 'receive'",
      "path": "src/utils.py",
      "line": 10,
      "ground_truth": {
        "changes": 1,
        "confidence_threshold": 0.9
      }
    }
  ],
  "medium": [...],
  "complex": [...]
}

```

## Provider Comparison

### Anthropic (Claude)

#### Strengths

* Excellent accuracy on complex code understanding
* Strong security vulnerability detection
* Prompt caching reduces costs by 50-90%

#### Considerations

* Slightly higher per-request cost than OpenAI
* API latency depends on region

#### Best For

* Production deployments with repeated prompts
* Security-critical code reviews
* Complex architectural refactoring

### OpenAI (GPT-4o, GPT-4o-mini)

#### Strengths: (GPT-4o-mini)

* Fast response times (1-3s typical)
* GPT-4o-mini offers excellent cost/performance ratio
* Wide model selection

#### Considerations: (GPT-4o-mini)

* No prompt caching (yet)
* Higher costs for GPT-4o at scale

#### Best For: (GPT-4o-mini)

* Speed-critical applications
* Cost-sensitive deployments (with mini model)
* High-volume production systems

### Ollama (Local Models)

#### Strengths: (Claude Sonnet)

* Zero per-request cost
* 100% privacy (no data leaves your infrastructure)
* GPU acceleration support

#### Considerations: (Claude Sonnet)

* Requires local hardware (GPU recommended)
* Higher latency than cloud APIs
* Model quality varies (qwen2.5-coder:7b recommended)

#### Best For: (Claude Sonnet)

* Privacy-first requirements (HIPAA, GDPR, confidential code)
* Cost-sensitive high-volume deployments
* Air-gapped environments

### Claude CLI

#### Strengths: (Qwen2.5-Coder)

* Free for development/testing
* Uses latest Claude models
* No API key management

#### Considerations: (Qwen2.5-Coder)

* Not suitable for production automation
* Rate limits apply
* Requires Claude desktop app

#### Best For: (Qwen2.5-Coder)

* Local development and testing
* Prototyping before API integration

### Codex CLI

#### Strengths: (Deepseek-Coder)

* Free for development/testing
* Direct integration with OpenAI Codex

#### Considerations: (Deepseek-Coder)

* Not suitable for production automation
* Limited to Codex model family

#### Best For: (Deepseek-Coder)

* Local development and testing
* Codex-specific workflows

## Interpreting Results

### Sample Benchmark Report

```markdown
## Latency Comparison

| Provider   | Model          | Mean   | Median | P95   | P99   | Throughput |
|------------|----------------|--------|--------|-------|-------|------------|
| anthropic  | claude-3-5     | 2.1s   | 2.0s   | 3.5s  | 4.2s  | 0.48 req/s |
| openai     | gpt-4o-mini    | 1.8s   | 1.7s   | 2.9s  | 3.5s  | 0.56 req/s |
| ollama     | qwen2.5:7b     | 4.5s   | 4.2s   | 7.1s  | 8.5s  | 0.22 req/s |

```

### What to Look For

#### Production Readiness

* ✅ P95 latency < 5s (all providers meet acceptance criteria)
* ✅ Success rate > 95%
* ✅ Average confidence > 0.7

#### Cost Optimization

* Compare monthly estimates at expected volume
* Consider Anthropic with prompt caching for repeated prompts
* Evaluate Ollama for high-volume scenarios

#### Performance vs Cost Trade-offs

* OpenAI gpt-4o-mini: Best cost/performance for cloud
* Anthropic: Best accuracy, cost-effective with caching
* Ollama: Best for privacy and zero ongoing costs

## Advanced Usage

### Benchmarking Specific Scenarios

```bash
# Benchmark only simple comments
python scripts/benchmark_llm.py --complexity simple --iterations 200

# Benchmark with custom warmup
python scripts/benchmark_llm.py --warmup 10 --iterations 100

# Benchmark with verbose output
python scripts/benchmark_llm.py --verbose

```

### Continuous Benchmarking

Integrate benchmarking into your CI/CD pipeline:

```yaml
# .github/workflows/benchmark.yml
name: LLM Benchmark
on:
  schedule:
    * cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      * uses: actions/checkout@v4
      * name: Run benchmarks
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python scripts/benchmark_llm.py --iterations 100
          git add docs/performance-benchmarks-results.md
          git commit -m "chore: update weekly benchmarks"
          git push

```

### Regression Detection

Monitor key metrics over time to detect performance regressions:

```bash
# Save benchmark results with timestamp
python scripts/benchmark_llm.py --output "reports/benchmark-$(date +%Y-%m-%d).md"

# Compare with previous results
diff reports/benchmark-2025-11-10.md reports/benchmark-2025-11-17.md

```

## Troubleshooting

### Low Success Rate (< 95%)

#### Possible Causes

* Invalid API keys
* Network connectivity issues
* Model timeout (increase timeout in config)
* Malformed test comments

#### Solutions

1. Check API key validity: `echo $ANTHROPIC_API_KEY`
2. Test network: `curl https://api.anthropic.com`
3. Increase timeout: `--timeout 60`
4. Validate test dataset JSON schema

### High P99 Latency (> 10s)

#### Possible Causes: (High Latency)

* Network congestion
* Provider rate limiting
* Cold start delays (first request)
* Complex comments exceeding context limits

#### Solutions: (High Latency)

1. Increase warmup iterations: `--warmup 10`
2. Reduce concurrent requests
3. Split complex comments into simpler chunks
4. Check provider status pages

### GPU Not Detected (Ollama)

#### Possible Causes: (Low Confidence)

* CUDA/ROCm drivers not installed
* GPU not accessible to Docker (if running in container)
* Ollama not configured for GPU

#### Solutions: (Low Confidence)

1. Verify GPU: `nvidia-smi` or `rocm-smi`
2. Check Ollama config: `ollama ps`
3. Reinstall with GPU support: See [Ollama Setup Guide](ollama-setup.md)

### Out of Memory (Local Models)

#### Possible Causes: (High Cost)

* Model too large for available VRAM
* Batch size too high
* Memory leak in long-running benchmarks

#### Solutions: (High Cost)

1. Use smaller model: `qwen2.5-coder:3b` instead of `7b`
2. Reduce iterations: `--iterations 50`
3. Restart Ollama between runs

## See Also

* [LLM Configuration Guide](llm-configuration.md) - Provider setup and configuration
* [Ollama Setup Guide](ollama-setup.md) - Local model installation
* [Main Configuration Guide](configuration.md) - General tool configuration
* [API Reference](api-reference.md) - Python API documentation
* [Getting Started Guide](getting-started.md) - Quick start tutorial

## Contributing

Found a performance issue or want to add benchmark scenarios?

1. Create a new test comment in `tests/benchmarks/sample_comments.json`
2. Add ground truth annotations
3. Run the benchmark: `python scripts/benchmark_llm.py`
4. Submit a PR with your findings

For questions or issues, see the [GitHub Issues](https://github.com/VirtualAgentics/review-bot-automator/issues) page.
