"""Unit tests for benchmark utility functions.

Tests statistical calculations, data loading, and benchmark result structures.
"""

import json
import statistics
from pathlib import Path

import pytest

from review_bot_automator.benchmarks import (
    BenchmarkResult,
    calculate_percentile,
    load_test_dataset,
)


class TestCalculatePercentile:
    """Test percentile calculation function."""

    def test_percentile_median(self) -> None:
        """Test p50 (median) calculation."""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = calculate_percentile(data, 50)
        assert result == 5.5

    def test_percentile_p95(self) -> None:
        """Test p95 calculation."""
        data = list(range(1, 101))  # 1-100
        result = calculate_percentile(data, 95)
        # quantiles uses linear interpolation, so 95th percentile is slightly above 95
        assert 95.0 <= result <= 96.0

    def test_percentile_p99(self) -> None:
        """Test p99 calculation."""
        data = list(range(1, 101))  # 1-100
        result = calculate_percentile(data, 99)
        # quantiles uses linear interpolation, so 99th percentile is slightly above 99
        assert 99.0 <= result <= 100.0

    def test_percentile_min(self) -> None:
        """Test p0 (minimum) calculation."""
        data = [5, 2, 8, 1, 9]
        result = calculate_percentile(data, 0)
        assert result == 1

    def test_percentile_max(self) -> None:
        """Test p100 (maximum) calculation."""
        data = [5, 2, 8, 1, 9]
        result = calculate_percentile(data, 100)
        assert result == 9

    def test_percentile_single_value(self) -> None:
        """Test percentile of single-value dataset."""
        data = [42]
        for percentile in [0, 25, 50, 75, 100]:
            result = calculate_percentile(data, percentile)
            assert result == 42

    def test_percentile_two_values(self) -> None:
        """Test percentile with two values."""
        data = [10, 20]
        assert calculate_percentile(data, 0) == 10
        assert calculate_percentile(data, 50) == 15
        assert calculate_percentile(data, 100) == 20

    def test_percentile_empty_data_raises(self) -> None:
        """Test that empty data raises ValueError."""
        with pytest.raises(ValueError, match="Cannot calculate percentile of empty data"):
            calculate_percentile([], 50)

    def test_percentile_invalid_range_raises(self) -> None:
        """Test that percentile out of range raises ValueError."""
        data = [1, 2, 3]

        with pytest.raises(ValueError, match="Percentile must be 0-100"):
            calculate_percentile(data, -1)

        with pytest.raises(ValueError, match="Percentile must be 0-100"):
            calculate_percentile(data, 101)

    def test_percentile_matches_statistics_module(self) -> None:
        """Test that results match Python's statistics module."""
        data = [1.2, 3.4, 5.6, 7.8, 9.0, 11.2, 13.4, 15.6, 17.8, 19.0]

        # Median should match
        assert calculate_percentile(data, 50) == statistics.median(data)

        # Other percentiles should be consistent with quantiles
        quantiles = statistics.quantiles(data, n=100)
        for p in [25, 75, 90, 95]:
            result = calculate_percentile(data, p)
            expected = quantiles[p - 1]
            assert abs(result - expected) < 1e-10

    def test_percentile_large_dataset(self) -> None:
        """Test percentile with large dataset."""
        data = list(range(1, 10001))  # 1-10000
        # quantiles uses linear interpolation
        assert 100.0 <= calculate_percentile(data, 1) <= 101.0
        assert calculate_percentile(data, 50) == 5000.5
        assert 9900.0 <= calculate_percentile(data, 99) <= 9901.0


class TestLoadTestDataset:
    """Test test dataset loading function."""

    def test_load_valid_dataset(self, tmp_path: Path) -> None:
        """Test loading a valid dataset."""
        dataset = {
            "simple": [{"body": "test1", "path": "file.py", "line": 1, "ground_truth": {}}],
            "medium": [{"body": "test2", "path": "file.py", "line": 2, "ground_truth": {}}],
            "complex": [{"body": "test3", "path": "file.py", "line": 3, "ground_truth": {}}],
        }

        dataset_file = tmp_path / "test_dataset.json"
        with open(dataset_file, "w") as f:
            json.dump(dataset, f)

        result = load_test_dataset(dataset_file)
        assert "simple" in result
        assert "medium" in result
        assert "complex" in result
        assert len(result["simple"]) == 1
        assert result["simple"][0]["body"] == "test1"

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        """Test that missing file raises FileNotFoundError."""
        nonexistent = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError, match="Dataset not found"):
            load_test_dataset(nonexistent)

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        """Test that invalid JSON raises error."""
        invalid_file = tmp_path / "invalid.json"
        with open(invalid_file, "w") as f:
            f.write("{invalid json")

        with pytest.raises(json.JSONDecodeError):
            load_test_dataset(invalid_file)

    def test_load_missing_keys_raises(self, tmp_path: Path) -> None:
        """Test that missing required keys raises ValueError."""
        incomplete_dataset: dict[str, list[dict[str, object]]] = {
            "simple": [],
            # Missing "medium" and "complex"
        }

        dataset_file = tmp_path / "incomplete.json"
        with open(dataset_file, "w") as f:
            json.dump(incomplete_dataset, f)

        with pytest.raises(ValueError, match="Dataset must contain keys"):
            load_test_dataset(dataset_file)

    def test_load_empty_categories(self, tmp_path: Path) -> None:
        """Test loading dataset with empty categories."""
        dataset: dict[str, list[dict[str, object]]] = {
            "simple": [],
            "medium": [],
            "complex": [],
        }

        dataset_file = tmp_path / "empty.json"
        with open(dataset_file, "w") as f:
            json.dump(dataset, f)

        result = load_test_dataset(dataset_file)
        assert len(result["simple"]) == 0
        assert len(result["medium"]) == 0
        assert len(result["complex"]) == 0

    def test_load_actual_benchmark_dataset(self) -> None:
        """Test loading the actual benchmark dataset.

        This test validates the structure and content of the real benchmark
        dataset (tests/benchmarks/sample_comments.json) if it exists. The test
        is skipped during early development or in environments where the
        dataset hasn't been created yet.

        The test ensures:
        - All three complexity categories (simple, medium, complex) are present
        - Each category contains at least 10 test comments
        - All comments have required fields (body, path, line, ground_truth)
        """
        dataset_path = Path(__file__).parent.parent / "benchmarks" / "sample_comments.json"

        # Skip if the benchmark dataset hasn't been created yet
        # This allows the test suite to pass during development before the dataset exists
        if not dataset_path.exists():
            pytest.skip("Benchmark dataset not yet created")

        result = load_test_dataset(dataset_path)

        # Validate structure
        assert "simple" in result
        assert "medium" in result
        assert "complex" in result

        # Validate counts (should have 10+ in each category)
        assert len(result["simple"]) >= 10
        assert len(result["medium"]) >= 10
        assert len(result["complex"]) >= 10

        # Validate comment structure
        for category in ["simple", "medium", "complex"]:
            for comment in result[category]:
                assert "body" in comment
                assert "path" in comment
                assert "line" in comment
                assert "ground_truth" in comment


class TestBenchmarkResult:
    """Test BenchmarkResult dataclass."""

    def test_benchmark_result_creation(self) -> None:
        """Test creating a BenchmarkResult instance."""
        result = BenchmarkResult(
            provider="openai",
            model="gpt-4o-mini",
            iterations=100,
            latencies=[1.0, 1.5, 2.0] + [1.5] * 97,
            mean_latency=1.5,
            median_latency=1.5,
            p95_latency=2.0,
            p99_latency=2.0,
            throughput=0.67,
            success_rate=1.0,
            avg_confidence=0.85,
            total_cost=0.50,
            cost_per_request=0.005,
            total_tokens=1000,
            avg_tokens_per_request=10.0,
            gpu_info=None,
            errors=0,
        )

        assert result.provider == "openai"
        assert result.model == "gpt-4o-mini"
        assert result.iterations == 100
        assert len(result.latencies) == 100
        assert result.success_rate == 1.0

    def test_benchmark_result_to_dict(self) -> None:
        """Test converting BenchmarkResult to dictionary."""
        result = BenchmarkResult(
            provider="anthropic",
            model="claude-haiku-4",
            iterations=50,
            latencies=[2.0, 2.5, 3.0] + [2.5] * 47,
            mean_latency=2.5,
            median_latency=2.5,
            p95_latency=3.0,
            p99_latency=3.0,
            throughput=0.40,
            success_rate=0.98,
            avg_confidence=0.90,
            total_cost=0.75,
            cost_per_request=0.015,
            total_tokens=2000,
            avg_tokens_per_request=40.0,
            gpu_info=None,
            errors=1,
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["provider"] == "anthropic"
        assert result_dict["model"] == "claude-haiku-4"
        assert result_dict["iterations"] == 50
        assert result_dict["success_rate"] == 0.98
        assert result_dict["errors"] == 1

    def test_benchmark_result_with_gpu_info(self) -> None:
        """Test BenchmarkResult with GPU information."""
        gpu_info = {
            "name": "NVIDIA RTX 4090",
            "total_memory": 24000000000,
            "driver_version": "535.104.05",
            "cuda_version": "12.2",
        }

        result = BenchmarkResult(
            provider="ollama",
            model="qwen2.5-coder:7b",
            iterations=100,
            latencies=[0.5, 0.6, 0.7] + [0.6] * 97,
            mean_latency=0.6,
            median_latency=0.6,
            p95_latency=0.7,
            p99_latency=0.7,
            throughput=1.67,
            success_rate=1.0,
            avg_confidence=0.80,
            total_cost=0.0,
            cost_per_request=0.0,
            total_tokens=500,
            avg_tokens_per_request=5.0,
            gpu_info=gpu_info,
            errors=0,
        )

        assert result.gpu_info is not None
        assert result.gpu_info["name"] == "NVIDIA RTX 4090"
        assert result.cost_per_request == 0.0  # Ollama is free

    def test_benchmark_result_json_serializable(self) -> None:
        """Test that BenchmarkResult can be JSON serialized."""
        result = BenchmarkResult(
            provider="test",
            model="test-model",
            iterations=10,
            latencies=[1.0, 2.0, 3.0] + [2.0] * 7,
            mean_latency=2.0,
            median_latency=2.0,
            p95_latency=3.0,
            p99_latency=3.0,
            throughput=0.5,
            success_rate=1.0,
            avg_confidence=0.8,
            total_cost=0.1,
            cost_per_request=0.01,
            total_tokens=100,
            avg_tokens_per_request=10.0,
            gpu_info=None,
            errors=0,
        )

        # Should not raise
        json_str = json.dumps(result.to_dict())
        assert isinstance(json_str, str)

        # Should be deserializable
        decoded = json.loads(json_str)
        assert decoded["provider"] == "test"
        assert decoded["model"] == "test-model"


class TestBenchmarkResultValidation:
    """Test BenchmarkResult field validation in __post_init__."""

    def test_success_rate_below_zero_raises(self) -> None:
        """Test that success_rate < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="success_rate must be between 0.0 and 1.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=-0.1,  # Invalid: negative
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_success_rate_above_one_raises(self) -> None:
        """Test that success_rate > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="success_rate must be between 0.0 and 1.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.5,  # Invalid: > 1.0
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_avg_confidence_below_zero_raises(self) -> None:
        """Test that avg_confidence < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="avg_confidence must be between 0.0 and 1.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=-0.5,  # Invalid: negative
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_avg_confidence_above_one_raises(self) -> None:
        """Test that avg_confidence > 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="avg_confidence must be between 0.0 and 1.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=2.0,  # Invalid: > 1.0
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_iterations_zero_raises(self) -> None:
        """Test that iterations = 0 raises ValueError."""
        with pytest.raises(ValueError, match="iterations must be >= 1"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=0,  # Invalid: must be >= 1
                latencies=[1.0],
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_iterations_negative_raises(self) -> None:
        """Test that iterations < 0 raises ValueError."""
        with pytest.raises(ValueError, match="iterations must be >= 1"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=-5,  # Invalid: negative
                latencies=[1.0],
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_errors_negative_raises(self) -> None:
        """Test that errors < 0 raises ValueError."""
        with pytest.raises(ValueError, match="errors must be >= 0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=-1,  # Invalid: negative
            )

    def test_total_cost_negative_raises(self) -> None:
        """Test that total_cost < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="total_cost must be >= 0.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=-5.0,  # Invalid: negative
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_cost_per_request_negative_raises(self) -> None:
        """Test that cost_per_request < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="cost_per_request must be >= 0.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=-0.01,  # Invalid: negative
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_total_tokens_negative_raises(self) -> None:
        """Test that total_tokens < 0 raises ValueError."""
        with pytest.raises(ValueError, match="total_tokens must be >= 0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=-100,  # Invalid: negative
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_avg_tokens_per_request_negative_raises(self) -> None:
        """Test that avg_tokens_per_request < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="avg_tokens_per_request must be >= 0.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=-10.0,  # Invalid: negative
                gpu_info=None,
                errors=0,
            )

    def test_mean_latency_negative_raises(self) -> None:
        """Test that mean_latency < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="mean_latency must be >= 0.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=-1.0,  # Invalid: negative
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_median_latency_negative_raises(self) -> None:
        """Test that median_latency < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="median_latency must be >= 0.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=-1.0,  # Invalid: negative
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_p95_latency_negative_raises(self) -> None:
        """Test that p95_latency < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="p95_latency must be >= 0.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=-1.0,  # Invalid: negative
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_p99_latency_negative_raises(self) -> None:
        """Test that p99_latency < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="p99_latency must be >= 0.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=-1.0,  # Invalid: negative
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_throughput_negative_raises(self) -> None:
        """Test that throughput < 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="throughput must be >= 0.0"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0] * 10,
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=-1.0,  # Invalid: negative
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_latencies_empty_raises(self) -> None:
        """Test that empty latencies list raises ValueError."""
        with pytest.raises(ValueError, match="latencies must not be empty"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[],  # Invalid: empty list
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_latencies_length_mismatch_raises(self) -> None:
        """Test that latencies length mismatch raises ValueError."""
        with pytest.raises(ValueError, match="latencies length .* must equal iterations"):
            BenchmarkResult(
                provider="test",
                model="test-model",
                iterations=10,
                latencies=[1.0, 2.0, 3.0],  # Invalid: length != iterations
                mean_latency=1.0,
                median_latency=1.0,
                p95_latency=1.0,
                p99_latency=1.0,
                throughput=1.0,
                success_rate=1.0,
                avg_confidence=0.8,
                total_cost=0.0,
                cost_per_request=0.0,
                total_tokens=100,
                avg_tokens_per_request=10.0,
                gpu_info=None,
                errors=0,
            )

    def test_latencies_matching_length_accepted(self) -> None:
        """Test that latencies with matching iterations length is accepted."""
        result = BenchmarkResult(
            provider="test",
            model="test-model",
            iterations=3,
            latencies=[1.0, 2.0, 3.0],  # Valid: length == iterations
            mean_latency=2.0,
            median_latency=2.0,
            p95_latency=3.0,
            p99_latency=3.0,
            throughput=0.5,
            success_rate=1.0,
            avg_confidence=0.8,
            total_cost=0.0,
            cost_per_request=0.0,
            total_tokens=100,
            avg_tokens_per_request=33.3,
            gpu_info=None,
            errors=0,
        )
        assert result.latencies == [1.0, 2.0, 3.0]
        assert result.iterations == 3

    def test_valid_edge_cases_accepted(self) -> None:
        """Test that valid edge case values are accepted."""
        # Test success_rate and avg_confidence at boundaries
        result = BenchmarkResult(
            provider="test",
            model="test-model",
            iterations=1,  # Minimum valid iterations
            latencies=[1.0],
            mean_latency=0.0,  # Edge: zero latency
            median_latency=0.0,
            p95_latency=0.0,
            p99_latency=0.0,
            throughput=0.0,  # Edge: zero throughput
            success_rate=0.0,  # Edge: 0% success
            avg_confidence=0.0,  # Edge: 0% confidence
            total_cost=0.0,  # Edge: free (Ollama)
            cost_per_request=0.0,
            total_tokens=0,  # Edge: no tokens
            avg_tokens_per_request=0.0,
            gpu_info=None,
            errors=0,
        )
        assert result.success_rate == 0.0
        assert result.avg_confidence == 0.0
        assert result.iterations == 1

    def test_valid_maximum_edge_cases_accepted(self) -> None:
        """Test that maximum valid edge case values are accepted."""
        result = BenchmarkResult(
            provider="test",
            model="test-model",
            iterations=1000,
            latencies=[1.0] * 1000,
            mean_latency=1.0,
            median_latency=1.0,
            p95_latency=1.0,
            p99_latency=1.0,
            throughput=1.0,
            success_rate=1.0,  # Edge: 100% success
            avg_confidence=1.0,  # Edge: 100% confidence
            total_cost=1000.0,
            cost_per_request=1.0,
            total_tokens=100000,
            avg_tokens_per_request=100.0,
            gpu_info=None,
            errors=0,
        )
        assert result.success_rate == 1.0
        assert result.avg_confidence == 1.0
        assert result.iterations == 1000

    def test_valid_typical_values_accepted(self) -> None:
        """Test that typical valid values are accepted."""
        result = BenchmarkResult(
            provider="openai",
            model="gpt-4o-mini",
            iterations=100,
            latencies=[1.2] * 100,
            mean_latency=1.3,
            median_latency=1.3,
            p95_latency=1.5,
            p99_latency=1.5,
            throughput=0.77,
            success_rate=0.98,  # 98% success rate
            avg_confidence=0.85,  # 85% confidence
            total_cost=0.50,
            cost_per_request=0.005,
            total_tokens=1000,
            avg_tokens_per_request=10.0,
            gpu_info=None,
            errors=2,
        )
        assert result.provider == "openai"
        assert 0.0 <= result.success_rate <= 1.0
        assert 0.0 <= result.avg_confidence <= 1.0
        assert result.iterations >= 1
        assert result.errors >= 0


class TestIntegration:
    """Integration tests for benchmark utilities."""

    def test_percentile_on_realistic_latencies(self) -> None:
        """Test percentile calculation on realistic latency data."""
        # Simulate 1000 requests with realistic latencies
        latencies = [
            1.2 + (i * 0.01) + (0.5 if i % 10 == 0 else 0) for i in range(1000)  # Some outliers
        ]

        p50 = calculate_percentile(latencies, 50)
        p95 = calculate_percentile(latencies, 95)
        p99 = calculate_percentile(latencies, 99)

        # Sanity checks
        assert p50 < p95 < p99
        assert p50 > min(latencies)
        assert p99 < max(latencies)

    def test_full_benchmark_result_workflow(self) -> None:
        """Test complete workflow of creating and exporting benchmark result."""
        # Simulate benchmark data
        latencies = [1.0 + (i * 0.1) for i in range(100)]

        result = BenchmarkResult(
            provider="test_provider",
            model="test_model",
            iterations=len(latencies),
            latencies=latencies,
            mean_latency=statistics.mean(latencies),
            median_latency=statistics.median(latencies),
            p95_latency=calculate_percentile(latencies, 95),
            p99_latency=calculate_percentile(latencies, 99),
            throughput=1.0 / statistics.mean(latencies),
            success_rate=0.99,
            avg_confidence=0.85,
            total_cost=5.0,
            cost_per_request=0.05,
            total_tokens=10000,
            avg_tokens_per_request=100.0,
            gpu_info=None,
            errors=1,
        )

        # Verify calculations
        assert result.mean_latency > 0
        assert result.p95_latency > result.median_latency
        assert result.p99_latency > result.p95_latency
        assert 0 <= result.success_rate <= 1.0
        assert result.throughput > 0

        # Verify JSON export
        result_dict = result.to_dict()
        json_str = json.dumps(result_dict)
        assert len(json_str) > 0

        # Verify roundtrip
        decoded = json.loads(json_str)
        assert decoded["provider"] == result.provider
        assert decoded["iterations"] == result.iterations
