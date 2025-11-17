"""Benchmarking utilities for LLM provider performance comparison.

This package provides tools for benchmarking and comparing the performance
of different LLM providers across multiple metrics:

- Latency (mean, median, P95, P99)
- Throughput (requests per second)
- Accuracy (parsing success rate)
- Cost (per request and monthly estimates)
- GPU performance (for local models)

Main Components:
    BenchmarkResult: Dataclass for storing benchmark results
    benchmark_provider: Run benchmarks on a single provider
    calculate_percentile: Statistical percentile calculation
    load_test_dataset: Load test comments from JSON

Usage:
    from pr_conflict_resolver.benchmarks import (
        BenchmarkResult,
        benchmark_provider,
        calculate_percentile,
        load_test_dataset,
    )

    # Load test dataset
    dataset = load_test_dataset(Path("tests/benchmarks/sample_comments.json"))

    # Run benchmark
    result = benchmark_provider(
        provider_name="anthropic",
        model="claude-3-5-sonnet-20241022",
        test_comments=dataset["simple"],
        iterations=100,
    )

    # Analyze results
    print(f"Mean latency: {result.mean_latency:.2f}s")
    print(f"P95 latency: {result.p95_latency:.2f}s")
    print(f"Success rate: {result.success_rate:.1%}")

See Also:
    scripts/benchmark_llm.py: CLI tool for running benchmarks
    docs/performance-benchmarks.md: Comprehensive benchmarking guide
"""

from pr_conflict_resolver.benchmarks.utils import (
    BenchmarkResult,
    calculate_percentile,
    load_test_dataset,
)

__all__ = [
    "BenchmarkResult",
    "calculate_percentile",
    "load_test_dataset",
]
