# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
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
    calculate_percentile: Statistical percentile calculation
    load_test_dataset: Load test comments from JSON

Note:
    For running actual benchmarks, use the CLI tool scripts/benchmark_llm.py
    which provides the complete benchmarking infrastructure.

Usage:
    from review_bot_automator.benchmarks import (
        BenchmarkResult,
        calculate_percentile,
        load_test_dataset,
    )

    # Load test dataset
    dataset = load_test_dataset(Path("tests/benchmarks/sample_comments.json"))

    # Calculate percentiles from latency data
    latencies = [1.2, 1.5, 2.0, 1.8, 2.2]
    p95 = calculate_percentile(latencies, 95)
    print(f"P95 latency: {p95:.2f}s")

    # Work with benchmark results
    result = BenchmarkResult(
        provider="anthropic",
        model="claude-3-5-sonnet",
        iterations=100,
        latencies=latencies,
        mean_latency=1.74,
        median_latency=1.8,
        p95_latency=p95,
        p99_latency=2.2,
        throughput=0.57,
        success_rate=0.98,
        avg_confidence=0.85,
        total_cost=0.50,
        cost_per_request=0.005,
        total_tokens=1000,
        avg_tokens_per_request=10.0,
        gpu_info=None,
        errors=2,
    )
    print(f"Mean latency: {result.mean_latency:.2f}s")
    print(f"Success rate: {result.success_rate:.1%}")

See Also:
    scripts/benchmark_llm.py: CLI tool for running benchmarks
    docs/performance-benchmarks.md: Comprehensive benchmarking guide
"""

from review_bot_automator.benchmarks.utils import (
    BenchmarkResult,
    calculate_percentile,
    load_test_dataset,
)

__all__ = [
    "BenchmarkResult",
    "calculate_percentile",
    "load_test_dataset",
]
