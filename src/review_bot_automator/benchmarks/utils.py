# SPDX-License-Identifier: MIT
# Copyright (c) 2025 VirtualAgentics
"""Core benchmarking utilities for LLM provider performance testing.

This module contains the core functionality for benchmarking LLM providers,
including statistical calculations, dataset loading, and provider testing.
"""

import json
import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


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

    def __post_init__(self) -> None:
        """Validate field constraints after initialization.

        Raises:
            ValueError: If any field violates its documented constraints
        """
        # Validate positive integer constraints first
        if self.iterations < 1:
            raise ValueError(f"iterations must be >= 1, got {self.iterations}")

        # Validate latencies list
        if not self.latencies:
            raise ValueError("latencies must not be empty")

        if len(self.latencies) != self.iterations:
            raise ValueError(
                f"latencies length ({len(self.latencies)}) must equal "
                f"iterations ({self.iterations})"
            )

        # Validate range constraints (0.0-1.0)
        if not 0.0 <= self.success_rate <= 1.0:
            raise ValueError(f"success_rate must be between 0.0 and 1.0, got {self.success_rate}")

        if not 0.0 <= self.avg_confidence <= 1.0:
            raise ValueError(
                f"avg_confidence must be between 0.0 and 1.0, got {self.avg_confidence}"
            )

        # Validate non-negative constraints
        if self.errors < 0:
            raise ValueError(f"errors must be >= 0, got {self.errors}")

        if self.total_cost < 0.0:
            raise ValueError(f"total_cost must be >= 0.0, got {self.total_cost}")

        if self.cost_per_request < 0.0:
            raise ValueError(f"cost_per_request must be >= 0.0, got {self.cost_per_request}")

        if self.total_tokens < 0:
            raise ValueError(f"total_tokens must be >= 0, got {self.total_tokens}")

        if self.avg_tokens_per_request < 0.0:
            raise ValueError(
                f"avg_tokens_per_request must be >= 0.0, got {self.avg_tokens_per_request}"
            )

        # Validate latency metrics are non-negative
        if self.mean_latency < 0.0:
            raise ValueError(f"mean_latency must be >= 0.0, got {self.mean_latency}")

        if self.median_latency < 0.0:
            raise ValueError(f"median_latency must be >= 0.0, got {self.median_latency}")

        if self.p95_latency < 0.0:
            raise ValueError(f"p95_latency must be >= 0.0, got {self.p95_latency}")

        if self.p99_latency < 0.0:
            raise ValueError(f"p99_latency must be >= 0.0, got {self.p99_latency}")

        if self.throughput < 0.0:
            raise ValueError(f"throughput must be >= 0.0, got {self.throughput}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


def calculate_percentile(data: Sequence[float], percentile: int) -> float:
    """Calculate specific percentile from data.

    Uses Python's statistics.quantiles() for consistent results with
    linear interpolation between data points.

    Args:
        data: List of numeric values
        percentile: Percentile to calculate (0-100)

    Returns:
        The value at the specified percentile

    Raises:
        ValueError: If data is empty or percentile is out of range

    Examples:
        >>> calculate_percentile([1, 2, 3, 4, 5], 50)
        3
        >>> calculate_percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95)
        9.55  # Linear interpolation between 9 and 10
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

    The dataset must contain three keys: "simple", "medium", and "complex",
    each containing a list of test comment objects with ground truth annotations.

    Args:
        path: Path to JSON file containing test comments

    Returns:
        Dictionary with keys "simple", "medium", "complex" containing comment lists

    Raises:
        FileNotFoundError: If dataset file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
        ValueError: If dataset is missing required keys

    Example Dataset Structure:
        {
            "simple": [
                {
                    "body": "Fix typo in variable name",
                    "path": "src/utils.py",
                    "line": 10,
                    "ground_truth": {"changes": 1, "confidence_threshold": 0.9}
                }
            ],
            "medium": [...],
            "complex": [...]
        }
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    with open(path, encoding="utf-8") as f:
        dataset: dict[str, list[dict[str, Any]]] = json.load(f)

    # Validate structure
    required_keys = {"simple", "medium", "complex"}
    if not required_keys.issubset(dataset.keys()):
        raise ValueError(f"Dataset must contain keys: {required_keys}")

    return dataset
