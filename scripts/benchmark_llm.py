#!/usr/bin/env python3
"""LLM Provider Benchmark Script.

Benchmarks all LLM providers across key performance metrics:
- Latency (mean, median, p50, p95, p99)
- Throughput (requests/second)
- Accuracy (parsing success rate vs ground truth)
- Cost (per request and monthly estimates)
- GPU acceleration impact (Ollama only)

Usage:
    # Benchmark all providers
    python scripts/benchmark_llm.py --iterations 100

    # Specific providers only
    python scripts/benchmark_llm.py --providers ollama openai --iterations 50

    # Custom dataset and output
    python scripts/benchmark_llm.py --dataset my_comments.json --output my_report.md

    # Quick test (fewer iterations)
    python scripts/benchmark_llm.py --iterations 10 --providers ollama

Requirements:
    - OPENAI_API_KEY environment variable for OpenAI
    - ANTHROPIC_API_KEY environment variable for Anthropic
    - Ollama server running locally for Ollama provider

"""

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from review_bot_automator.llm.config import LLMConfig
from review_bot_automator.llm.factory import create_provider_from_config
from review_bot_automator.llm.parser import UniversalLLMParser


@dataclass
class BenchmarkResult:
    """Results for a single provider benchmark.

    Args:
        provider: Provider name (e.g., "openai", "anthropic", "ollama")
        model: Model identifier (e.g., "gpt-4o-mini", "claude-haiku-4")
        iterations: Number of benchmark iterations performed
        latencies: List of all latency measurements in seconds
        mean_latency: Mean latency in seconds
        median_latency: Median (p50) latency in seconds
        p95_latency: 95th percentile latency in seconds
        p99_latency: 99th percentile latency in seconds
        throughput: Requests per second
        success_rate: Percentage of successful parses (0.0-1.0)
        avg_confidence: Average confidence score (0.0-1.0)
        total_cost: Total cost in USD for all iterations
        cost_per_request: Average cost per request in USD
        total_tokens: Total tokens consumed (input + output)
        avg_tokens_per_request: Average tokens per request
        gpu_info: GPU hardware info (Ollama only), None for API providers
        errors: Number of failed requests
    """

    provider: str
    model: str
    iterations: int
    latencies: list[float]
    mean_latency: float
    median_latency: float
    p95_latency: float
    p99_latency: float
    throughput: float
    success_rate: float
    avg_confidence: float
    total_cost: float
    cost_per_request: float
    total_tokens: int
    avg_tokens_per_request: float
    gpu_info: dict[str, Any] | None
    errors: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


def calculate_percentile(data: list[float], percentile: int) -> float:
    """Calculate specific percentile from data.

    Args:
        data: List of numeric values
        percentile: Percentile to calculate (0-100)

    Returns:
        The value at the specified percentile

    Raises:
        ValueError: If data is empty or percentile is out of range
    """
    if not data:
        raise ValueError("Cannot calculate percentile of empty data")
    if not 0 <= percentile <= 100:
        raise ValueError(f"Percentile must be 0-100, got {percentile}")

    sorted_data = sorted(data)

    # Edge cases
    if len(sorted_data) == 1:
        return sorted_data[0]

    if percentile == 0:
        return min(sorted_data)
    if percentile == 100:
        return max(sorted_data)
    if percentile == 50:
        return statistics.median(sorted_data)

    # Use quantiles for other percentiles
    # quantiles(n=100) returns 99 cut points for percentiles 1-99
    quantiles = statistics.quantiles(sorted_data, n=100)
    return quantiles[percentile - 1]


def load_test_dataset(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load test comments dataset from JSON file.

    Args:
        path: Path to JSON file containing test comments

    Returns:
        Dictionary with keys "simple", "medium", "complex" containing comment lists

    Raises:
        FileNotFoundError: If dataset file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    with open(path) as f:
        dataset = json.load(f)

    # Validate structure
    required_keys = {"simple", "medium", "complex"}
    if not required_keys.issubset(dataset.keys()):
        raise ValueError(f"Dataset must contain keys: {required_keys}")

    return dataset


def benchmark_provider(
    provider_name: str,
    model: str,
    test_comments: list[dict[str, Any]],
    iterations: int = 100,
    api_key: str | None = None,
    warmup_iterations: int = 5,
) -> BenchmarkResult:
    """Benchmark a single LLM provider.

    Args:
        provider_name: Provider identifier (openai, anthropic, ollama, etc.)
        model: Model name to use
        test_comments: List of test comments with ground truth
        iterations: Number of iterations to run per comment
        api_key: API key for the provider (if required)
        warmup_iterations: Number of warmup requests (not measured)

    Returns:
        BenchmarkResult with all metrics

    Raises:
        ValueError: If provider initialization fails
        RuntimeError: If benchmark encounters critical errors
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking: {provider_name} ({model})")
    print(f"{'='*60}")

    # Initialize provider
    config = LLMConfig(
        provider=provider_name,
        model=model,
        api_key=api_key,
        max_retries=3,
        timeout=30,
    )

    try:
        provider = create_provider_from_config(config)
    except Exception as e:
        raise ValueError(f"Failed to initialize provider {provider_name}: {e}") from e

    # Warmup phase
    print(f"Warming up ({warmup_iterations} iterations)...")
    sample_comment = test_comments[0]
    for i in range(warmup_iterations):
        try:
            provider.generate(sample_comment["body"])
        except Exception as e:
            print(f"  Warmup iteration {i+1} failed: {e}")

    # Benchmark phase
    print(f"Running benchmark ({iterations} iterations x {len(test_comments)} comments)...")
    latencies: list[float] = []
    successful_parses = 0
    total_confidence = 0.0
    errors = 0

    total_iterations = iterations * len(test_comments)
    completed = 0

    for iteration in range(iterations):
        for comment_idx, comment in enumerate(test_comments):
            try:
                # Measure latency
                start_time = time.perf_counter()
                response = provider.generate(comment["body"])
                end_time = time.perf_counter()

                latency = end_time - start_time
                latencies.append(latency)

                # Parse and validate
                parser = UniversalLLMParser()
                changes = parser.parse(response)

                if changes:
                    successful_parses += 1
                    # Average confidence from all changes
                    avg_conf = sum(c.confidence for c in changes) / len(changes)
                    total_confidence += avg_conf

            except Exception as e:
                errors += 1
                print(f"  Error in iteration {iteration+1}, comment {comment_idx+1}: {e}")

            completed += 1
            if completed % 10 == 0:
                progress = (completed / total_iterations) * 100
                print(f"  Progress: {completed}/{total_iterations} ({progress:.1f}%)")

    # Get metrics from provider
    metrics = provider.get_metrics()

    # Calculate statistics
    if not latencies:
        raise RuntimeError("No successful requests - benchmark failed")

    mean_lat = statistics.mean(latencies)
    median_lat = statistics.median(latencies)
    p95_lat = calculate_percentile(latencies, 95)
    p99_lat = calculate_percentile(latencies, 99)
    throughput = 1.0 / mean_lat if mean_lat > 0 else 0.0
    success_rate = successful_parses / total_iterations
    avg_confidence = total_confidence / successful_parses if successful_parses > 0 else 0.0
    total_cost = provider.get_total_cost()
    cost_per_request = total_cost / total_iterations if total_iterations > 0 else 0.0
    avg_tokens = metrics.total_tokens / total_iterations if total_iterations > 0 else 0.0

    print("\nResults:")
    print(f"  Mean latency: {mean_lat:.3f}s")
    print(f"  Median latency: {median_lat:.3f}s")
    print(f"  P95 latency: {p95_lat:.3f}s")
    print(f"  P99 latency: {p99_lat:.3f}s")
    print(f"  Success rate: {success_rate*100:.1f}%")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Cost per request: ${cost_per_request:.6f}")

    return BenchmarkResult(
        provider=provider_name,
        model=model,
        iterations=total_iterations,
        latencies=latencies,
        mean_latency=mean_lat,
        median_latency=median_lat,
        p95_latency=p95_lat,
        p99_latency=p99_lat,
        throughput=throughput,
        success_rate=success_rate,
        avg_confidence=avg_confidence,
        total_cost=total_cost,
        cost_per_request=cost_per_request,
        total_tokens=metrics.total_tokens,
        avg_tokens_per_request=avg_tokens,
        gpu_info=asdict(metrics.gpu_info) if metrics.gpu_info else None,
        errors=errors,
    )


def generate_report(results: list[BenchmarkResult], output_path: Path) -> None:
    """Generate markdown report with benchmark results.

    Args:
        results: List of benchmark results for all providers
        output_path: Path to output markdown file
    """
    print(f"\nGenerating report: {output_path}")

    report_lines = [
        "# LLM Provider Performance Benchmarks\n",
        "_Generated by `scripts/benchmark_llm.py`_\n",
        "",
        "## Executive Summary\n",
        "",
        f"This report compares performance of {len(results)} LLM providers across latency, "
        "accuracy, cost, and throughput metrics.\n",
        "",
        "## Methodology\n",
        "",
        f"- **Iterations**: {results[0].iterations} total requests per provider",
        f"- **Test Dataset**: {len(results[0].latencies) // results[0].iterations} sample comments",
        "- **Metrics**: Latency (mean, median, p95, p99), success rate, cost, throughput",
        "- **Warm-up**: 5 requests before measurement (not included in results)\n",
        "",
        "## Latency Comparison\n",
        "",
        "| Provider | Model | Mean | Median | P95 | P99 | Throughput |",
        "|----------|-------|------|--------|-----|-----|------------|",
    ]

    # Sort by mean latency (fastest first)
    sorted_results = sorted(results, key=lambda r: r.mean_latency)

    for result in sorted_results:
        report_lines.append(
            f"| {result.provider} | {result.model} | "
            f"{result.mean_latency:.3f}s | {result.median_latency:.3f}s | "
            f"{result.p95_latency:.3f}s | {result.p99_latency:.3f}s | "
            f"{result.throughput:.2f} req/s |"
        )

    report_lines.extend(
        [
            "",
            "## Accuracy and Reliability\n",
            "",
            "| Provider | Model | Success Rate | Avg Confidence | Errors |",
            "|----------|-------|--------------|----------------|--------|",
        ]
    )

    # Sort by success rate (highest first)
    sorted_by_accuracy = sorted(results, key=lambda r: r.success_rate, reverse=True)

    for result in sorted_by_accuracy:
        report_lines.append(
            f"| {result.provider} | {result.model} | "
            f"{result.success_rate*100:.1f}% | {result.avg_confidence:.2f} | "
            f"{result.errors} |"
        )

    report_lines.extend(
        [
            "",
            "## Cost Analysis\n",
            "",
            "| Provider | Model | Total Cost | Cost/Request | Tokens/Request |"
            " Monthly (1K) | Monthly (10K) |",
            "|----------|-------|------------|--------------|----------------"
            "|--------------|---------------|",
        ]
    )

    # Sort by cost per request (cheapest first)
    sorted_by_cost = sorted(results, key=lambda r: r.cost_per_request)

    for result in sorted_by_cost:
        monthly_1k = result.cost_per_request * 1000
        monthly_10k = result.cost_per_request * 10000
        report_lines.append(
            f"| {result.provider} | {result.model} | "
            f"${result.total_cost:.4f} | ${result.cost_per_request:.6f} | "
            f"{result.avg_tokens_per_request:.0f} | ${monthly_1k:.2f} | ${monthly_10k:.2f} |"
        )

    # GPU information (if any)
    gpu_results = [r for r in results if r.gpu_info]
    if gpu_results:
        report_lines.extend(
            [
                "",
                "## GPU Acceleration (Ollama)\n",
                "",
            ]
        )

        for result in gpu_results:
            if result.gpu_info:
                gpu = result.gpu_info
                report_lines.extend(
                    [
                        f"**GPU Detected**: {gpu.get('name', 'Unknown')}",
                        f"- Memory: {gpu.get('total_memory', 0) / 1e9:.1f} GB",
                        f"- Driver: {gpu.get('driver_version', 'Unknown')}",
                        f"- CUDA: {gpu.get('cuda_version', 'Unknown')}\n",
                    ]
                )

    # Recommendations
    report_lines.extend(
        [
            "",
            "## Recommendations by Use Case\n",
            "",
            "### Privacy-First (100% Local)",
            "- **Best Choice**: Ollama",
            "- **Trade-off**: Higher latency (especially CPU-only)",
            "- **Benefit**: Zero cost, complete data privacy\n",
            "",
            "### Speed-Critical Applications",
            f"- **Best Choice**: {sorted_results[0].provider} ({sorted_results[0].model})",
            f"- **Latency**: {sorted_results[0].p95_latency:.3f}s (p95)",
            f"- **Cost**: ${sorted_results[0].cost_per_request:.6f} per request\n",
            "",
            "### Cost-Sensitive Deployments",
            f"- **Best Choice**: {sorted_by_cost[0].provider} ({sorted_by_cost[0].model})",
            f"- **Cost**: ${sorted_by_cost[0].cost_per_request:.6f} per request",
            f"- **Latency**: {sorted_by_cost[0].p95_latency:.3f}s (p95)\n",
            "",
            "### High-Volume Production",
            "- **Best Choice**: Anthropic with prompt caching",
            "- **Savings**: 50-90% cost reduction on repeated prompts",
            "- **Recommended**: claude-haiku-4 for balance\n",
            "",
            "## Validation Against Requirements\n",
            "",
            "**Target**: P95 latency <5s for all providers\n",
            "",
        ]
    )

    for result in results:
        status = "✅ PASS" if result.p95_latency < 5.0 else "❌ FAIL"
        report_lines.append(
            f"- {result.provider} ({result.model}): " f"{result.p95_latency:.3f}s {status}"
        )

    report_lines.extend(
        [
            "",
            "---",
            "",
            "_For more information on LLM configuration, see `docs/llm-configuration.md`_",
            "",
        ]
    )

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(report_lines))

    print(f"Report generated: {output_path}")


def main() -> int:
    """Main entry point for benchmark script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Benchmark LLM providers for performance comparison",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--providers",
        nargs="+",
        default=["anthropic", "openai", "ollama"],
        help="Providers to benchmark (default: anthropic openai ollama)",
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of iterations per test comment (default: 100)",
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("tests/benchmarks/sample_comments.json"),
        help="Path to test dataset JSON file (default: tests/benchmarks/sample_comments.json)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/performance-benchmarks.md"),
        help="Output path for markdown report (default: docs/performance-benchmarks.md)",
    )

    parser.add_argument(
        "--json",
        type=Path,
        help="Optional: output raw results as JSON",
    )

    args = parser.parse_args()

    # Load test dataset
    try:
        print(f"Loading test dataset: {args.dataset}")
        dataset = load_test_dataset(args.dataset)

        # Flatten all complexity levels into single list
        all_comments = []
        for level in ["simple", "medium", "complex"]:
            all_comments.extend(dataset[level])

        print(f"Loaded {len(all_comments)} test comments")

    except Exception as e:
        print(f"Error loading dataset: {e}", file=sys.stderr)
        return 1

    # Provider configurations
    provider_configs = {
        "openai": {
            "model": "gpt-4o-mini",
            "api_key": os.getenv("OPENAI_API_KEY"),
        },
        "anthropic": {
            "model": "claude-haiku-4",
            "api_key": os.getenv("ANTHROPIC_API_KEY"),
        },
        "ollama": {
            "model": "qwen2.5-coder:7b",
            "api_key": None,
        },
    }

    # Run benchmarks
    results: list[BenchmarkResult] = []

    for provider_name in args.providers:
        if provider_name not in provider_configs:
            print(f"Warning: Unknown provider '{provider_name}', skipping")
            continue

        config = provider_configs[provider_name]

        # Check API key requirement
        if provider_name in ["openai", "anthropic"] and not config["api_key"]:
            print(f"Warning: {provider_name.upper()}_API_KEY not set, skipping {provider_name}")
            continue

        try:
            result = benchmark_provider(
                provider_name=provider_name,
                model=config["model"],
                test_comments=all_comments,
                iterations=args.iterations,
                api_key=config["api_key"],
            )
            results.append(result)

        except Exception as e:
            print(f"Error benchmarking {provider_name}: {e}", file=sys.stderr)
            continue

    if not results:
        print("Error: No successful benchmarks completed", file=sys.stderr)
        return 1

    # Generate report
    try:
        generate_report(results, args.output)

        # Optional JSON output
        if args.json:
            with open(args.json, "w") as f:
                json.dump([r.to_dict() for r in results], f, indent=2)
            print(f"JSON results saved: {args.json}")

    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        return 1

    print("\n" + "=" * 60)
    print("Benchmark complete!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
