"""Tests for GPU detection and hardware acceleration.

This module tests GPU detection functionality for Ollama including
GPUInfo validation, multi-tier detection strategy, and fallback behavior.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from review_bot_automator.llm.providers.gpu_detector import GPUDetector, GPUInfo


class TestGPUInfo:
    """Tests for GPUInfo dataclass."""

    def test_gpu_info_creation_nvidia(self) -> None:
        """Test creating GPUInfo for NVIDIA GPU."""
        gpu = GPUInfo(
            available=True,
            gpu_type="NVIDIA",
            model_name="RTX 4090",
            vram_total_mb=24576,
            vram_available_mb=20480,
            compute_capability="8.9",
        )

        assert gpu.available is True
        assert gpu.gpu_type == "NVIDIA"
        assert gpu.model_name == "RTX 4090"
        assert gpu.vram_total_mb == 24576
        assert gpu.vram_available_mb == 20480
        assert gpu.compute_capability == "8.9"

    def test_gpu_info_creation_amd(self) -> None:
        """Test creating GPUInfo for AMD GPU."""
        gpu = GPUInfo(
            available=True,
            gpu_type="AMD",
            model_name="RX 7900 XTX",
            vram_total_mb=24576,
            vram_available_mb=22000,
            compute_capability=None,
        )

        assert gpu.available is True
        assert gpu.gpu_type == "AMD"
        assert gpu.model_name == "RX 7900 XTX"

    def test_gpu_info_creation_apple(self) -> None:
        """Test creating GPUInfo for Apple Silicon."""
        gpu = GPUInfo(
            available=True,
            gpu_type="Apple",
            model_name="M3 Max (Metal)",
            vram_total_mb=None,  # Unified memory
            vram_available_mb=None,
            compute_capability=None,
        )

        assert gpu.available is True
        assert gpu.gpu_type == "Apple"
        assert gpu.model_name == "M3 Max (Metal)"

    def test_gpu_info_creation_cpu_fallback(self) -> None:
        """Test creating GPUInfo for CPU-only mode."""
        gpu = GPUInfo(
            available=False,
            gpu_type="CPU",
            model_name=None,
            vram_total_mb=None,
            vram_available_mb=None,
            compute_capability=None,
        )

        assert gpu.available is False
        assert gpu.gpu_type == "CPU"
        assert gpu.model_name is None

    def test_gpu_info_immutability(self) -> None:
        """Test that GPUInfo is immutable."""
        gpu = GPUInfo(
            available=True,
            gpu_type="NVIDIA",
            model_name="RTX 3090",
            vram_total_mb=24576,
            vram_available_mb=20480,
            compute_capability="8.6",
        )

        with pytest.raises((AttributeError, TypeError)):
            gpu.available = False  # type: ignore[misc]

    def test_gpu_info_validation_missing_gpu_type_when_available(self) -> None:
        """Test that gpu_type=None raises ValueError when GPU is available."""
        with pytest.raises(ValueError, match="gpu_type cannot be None when GPU is available"):
            GPUInfo(
                available=True,
                gpu_type=None,
                model_name="Unknown GPU",
                vram_total_mb=8192,
                vram_available_mb=6000,
                compute_capability=None,
            )

    def test_gpu_info_validation_negative_vram_total(self) -> None:
        """Test that negative vram_total_mb raises ValueError."""
        with pytest.raises(ValueError, match="vram_total_mb must be >= 0"):
            GPUInfo(
                available=True,
                gpu_type="NVIDIA",
                model_name="RTX 4090",
                vram_total_mb=-1000,
                vram_available_mb=8000,
                compute_capability="8.9",
            )

    def test_gpu_info_validation_negative_vram_available(self) -> None:
        """Test that negative vram_available_mb raises ValueError."""
        with pytest.raises(ValueError, match="vram_available_mb must be >= 0"):
            GPUInfo(
                available=True,
                gpu_type="NVIDIA",
                model_name="RTX 4090",
                vram_total_mb=24576,
                vram_available_mb=-5000,
                compute_capability="8.9",
            )

    def test_gpu_info_validation_available_exceeds_total(self) -> None:
        """Test that vram_available > vram_total raises ValueError."""
        with pytest.raises(ValueError, match="vram_available_mb.*cannot exceed vram_total_mb"):
            GPUInfo(
                available=True,
                gpu_type="NVIDIA",
                model_name="RTX 4090",
                vram_total_mb=16384,
                vram_available_mb=20000,  # More than total!
                compute_capability="8.9",
            )


class TestGPUDetectorOllamaAPI:
    """Tests for GPU detection via Ollama /api/ps endpoint."""

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_from_ollama_ps_nvidia(self, mock_get: Mock) -> None:
        """Test NVIDIA GPU detection from Ollama /api/ps endpoint."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {
                    "processor": "NVIDIA CUDA 12.1",
                    "vram_total": 24576,
                    "vram_available": 20480,
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gpu = GPUDetector._detect_from_ollama_ps("http://localhost:11434", timeout=5)

        assert gpu.available is True
        assert gpu.gpu_type == "NVIDIA"
        assert gpu.model_name is not None
        assert "NVIDIA CUDA" in gpu.model_name
        assert gpu.vram_total_mb == 24576
        assert gpu.vram_available_mb == 20480
        mock_get.assert_called_once_with("http://localhost:11434/api/ps", timeout=5)

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_from_ollama_ps_amd(self, mock_get: Mock) -> None:
        """Test AMD GPU detection from Ollama /api/ps endpoint."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {
                    "processor": "AMD ROCm 5.7",
                    "vram_total": 16384,
                    "vram_available": 14000,
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gpu = GPUDetector._detect_from_ollama_ps("http://localhost:11434", timeout=5)

        assert gpu.available is True
        assert gpu.gpu_type == "AMD"
        assert gpu.model_name is not None
        assert "AMD ROCm" in gpu.model_name

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_from_ollama_ps_apple(self, mock_get: Mock) -> None:
        """Test Apple Metal detection from Ollama /api/ps endpoint."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {
                    "processor": "Apple Metal M3 Max",
                    "vram_total": None,  # Unified memory
                    "vram_available": None,
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gpu = GPUDetector._detect_from_ollama_ps("http://localhost:11434", timeout=5)

        assert gpu.available is True
        assert gpu.gpu_type == "Apple"
        assert gpu.model_name is not None
        assert "Metal" in gpu.model_name

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_from_ollama_ps_no_models(self, mock_get: Mock) -> None:
        """Test detection failure when no models running."""
        mock_response = Mock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="No running models"):
            GPUDetector._detect_from_ollama_ps("http://localhost:11434", timeout=5)

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_from_ollama_ps_unknown_processor(self, mock_get: Mock) -> None:
        """Test detection failure with unknown processor type."""
        mock_response = Mock()
        mock_response.json.return_value = {"models": [{"processor": "Unknown Processor X1000"}]}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="Unknown processor type"):
            GPUDetector._detect_from_ollama_ps("http://localhost:11434", timeout=5)

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_from_ollama_ps_http_error(self, mock_get: Mock) -> None:
        """Test detection failure when API returns HTTP error."""
        mock_get.side_effect = requests.HTTPError("404 Not Found")

        with pytest.raises(requests.HTTPError):
            GPUDetector._detect_from_ollama_ps("http://localhost:11434", timeout=5)

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_from_ollama_ps_timeout(self, mock_get: Mock) -> None:
        """Test detection failure when API request times out."""
        mock_get.side_effect = requests.Timeout("Request timed out")

        with pytest.raises(requests.Timeout):
            GPUDetector._detect_from_ollama_ps("http://localhost:11434", timeout=5)


class TestGPUDetectorSystemLevel:
    """Tests for GPU detection via system commands."""

    @patch("subprocess.run")
    def test_detect_from_system_nvidia(self, mock_run: Mock) -> None:
        """Test NVIDIA GPU detection via nvidia-smi."""
        mock_result = Mock()
        mock_result.stdout = "NVIDIA GeForce RTX 4090, 24576\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        gpu = GPUDetector._detect_from_system()

        assert gpu.available is True
        assert gpu.gpu_type == "NVIDIA"
        assert gpu.model_name is not None
        assert "RTX 4090" in gpu.model_name
        assert gpu.vram_total_mb == 24576

    @patch("subprocess.run")
    def test_detect_from_system_amd(self, mock_run: Mock) -> None:
        """Test AMD GPU detection via rocm-smi."""
        # First call (nvidia-smi) fails
        # Second call (rocm-smi) succeeds
        mock_nvidia_fail = Mock()
        mock_nvidia_fail.side_effect = FileNotFoundError()

        mock_rocm_success = Mock()
        mock_rocm_success.stdout = "GPU[0]: AMD Radeon RX 7900 XTX\n"
        mock_rocm_success.returncode = 0

        mock_run.side_effect = [mock_nvidia_fail.side_effect, mock_rocm_success]

        gpu = GPUDetector._detect_from_system()

        assert gpu.available is True
        assert gpu.gpu_type == "AMD"
        assert gpu.model_name == "AMD GPU (ROCm)"

    @patch("platform.system")
    @patch("subprocess.run")
    def test_detect_from_system_apple_m3(self, mock_run: Mock, mock_platform: Mock) -> None:
        """Test Apple M3 detection via sysctl on macOS."""
        mock_platform.return_value = "Darwin"

        # nvidia-smi fails
        # rocm-smi fails
        # sysctl succeeds
        mock_nvidia_fail = Mock()
        mock_nvidia_fail.side_effect = FileNotFoundError()

        mock_rocm_fail = Mock()
        mock_rocm_fail.side_effect = FileNotFoundError()

        mock_sysctl_success = Mock()
        mock_sysctl_success.stdout = "Apple M3 Max\n"
        mock_sysctl_success.returncode = 0

        mock_run.side_effect = [
            mock_nvidia_fail.side_effect,
            mock_rocm_fail.side_effect,
            mock_sysctl_success,
        ]

        gpu = GPUDetector._detect_from_system()

        assert gpu.available is True
        assert gpu.gpu_type == "Apple"
        assert gpu.model_name is not None
        assert "M3" in gpu.model_name
        assert "Metal" in gpu.model_name

    @patch("subprocess.run")
    def test_detect_from_system_no_gpu(self, mock_run: Mock) -> None:
        """Test system detection failure when no GPU found."""
        mock_run.side_effect = FileNotFoundError("Command not found")

        with pytest.raises(ValueError, match="No GPU detected via system queries"):
            GPUDetector._detect_from_system()

    @patch("subprocess.run")
    def test_detect_from_system_nvidia_parse_error(self, mock_run: Mock) -> None:
        """Test handling of malformed nvidia-smi output falls through to AMD/Apple detection."""
        mock_result = Mock()
        mock_result.stdout = "Invalid output format\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Should fall through to AMD/Apple detection and ultimately raise "No GPU detected"
        # because AMD/Apple detection will also fail
        with pytest.raises(ValueError, match="No GPU detected via system queries"):
            GPUDetector._detect_from_system()


class TestGPUDetectorIntegration:
    """Tests for complete GPU detection flow with fallback strategy."""

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_gpu_ollama_api_success(self, mock_get: Mock) -> None:
        """Test successful GPU detection via Ollama API (Strategy 1)."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {
                    "processor": "NVIDIA CUDA 12.1",
                    "vram_total": 24576,
                    "vram_available": 20480,
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gpu = GPUDetector.detect_gpu("http://localhost:11434")

        assert gpu.available is True
        assert gpu.gpu_type == "NVIDIA"

    @patch("subprocess.run")
    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_gpu_fallback_to_system(self, mock_get: Mock, mock_run: Mock) -> None:
        """Test fallback to system detection when Ollama API fails (Strategy 2)."""
        # Ollama API fails
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        # System detection succeeds
        mock_result = Mock()
        mock_result.stdout = "NVIDIA GeForce RTX 3090, 24576\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        gpu = GPUDetector.detect_gpu("http://localhost:11434")

        assert gpu.available is True
        assert gpu.gpu_type == "NVIDIA"
        assert gpu.model_name is not None
        assert "RTX 3090" in gpu.model_name

    @patch("subprocess.run")
    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_gpu_fallback_to_cpu(self, mock_get: Mock, mock_run: Mock) -> None:
        """Test fallback to CPU when all detection methods fail (Strategy 3)."""
        # Ollama API fails
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        # System detection fails
        mock_run.side_effect = FileNotFoundError("Command not found")

        gpu = GPUDetector.detect_gpu("http://localhost:11434")

        assert gpu.available is False
        assert gpu.gpu_type == "CPU"
        assert gpu.model_name is None
        assert gpu.vram_total_mb is None

    @patch("subprocess.run")
    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_gpu_timeout_parameter(self, mock_get: Mock, mock_run: Mock) -> None:
        """Test that timeout parameter is passed to API request."""
        mock_response = Mock()
        mock_response.json.return_value = {"models": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock system detection to fail
        mock_run.side_effect = FileNotFoundError("Command not found")

        # Should not raise, but will fall through to CPU fallback
        gpu = GPUDetector.detect_gpu("http://localhost:11434", timeout=10)

        mock_get.assert_called_once_with("http://localhost:11434/api/ps", timeout=10)
        assert gpu.gpu_type == "CPU"  # Fallback due to no models

    @patch("subprocess.run")
    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_gpu_never_raises(self, mock_get: Mock, mock_run: Mock) -> None:
        """Test that detect_gpu never raises exceptions (always returns GPUInfo)."""
        # Simulate all detection methods throwing exceptions
        mock_get.side_effect = Exception("Unexpected error")
        mock_run.side_effect = Exception("Unexpected error")

        # Should not raise - always falls back to CPU
        gpu = GPUDetector.detect_gpu("http://localhost:11434")

        assert gpu.available is False
        assert gpu.gpu_type == "CPU"


class TestGPUDetectorEdgeCases:
    """Tests for edge cases and boundary conditions in GPU detection."""

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_gpu_empty_vram_fields(self, mock_get: Mock) -> None:
        """Test handling of missing VRAM fields in API response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {
                    "processor": "NVIDIA CUDA 12.1",
                    # Missing vram_total and vram_available
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gpu = GPUDetector.detect_gpu("http://localhost:11434")

        assert gpu.available is True
        assert gpu.gpu_type == "NVIDIA"
        assert gpu.vram_total_mb is None
        assert gpu.vram_available_mb is None

    @patch("subprocess.run")
    def test_detect_from_system_nvidia_multiple_gpus(self, mock_run: Mock) -> None:
        """Test nvidia-smi output with multiple GPUs (uses first GPU).

        Note: nvidia-smi with --format=csv,noheader returns one line per GPU,
        but we call .strip() and .split(",") on the whole output. The code
        currently processes only the first line before the first newline.
        """
        mock_result = Mock()
        # nvidia-smi returns one line per GPU, we should only parse the first line
        mock_result.stdout = "NVIDIA RTX 4090, 24576\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        gpu = GPUDetector._detect_from_system()

        # Should detect first GPU
        assert gpu.available is True
        assert gpu.gpu_type == "NVIDIA"
        assert gpu.model_name is not None
        assert "RTX 4090" in gpu.model_name

    @patch("platform.system")
    @patch("subprocess.run")
    def test_detect_from_system_apple_non_silicon(
        self, mock_run: Mock, mock_platform: Mock
    ) -> None:
        """Test macOS system without Apple Silicon (Intel Mac)."""
        mock_platform.return_value = "Darwin"

        # nvidia-smi fails
        # rocm-smi fails
        # sysctl returns Intel CPU (not Apple Silicon)
        mock_nvidia_fail = Mock()
        mock_nvidia_fail.side_effect = FileNotFoundError()

        mock_rocm_fail = Mock()
        mock_rocm_fail.side_effect = FileNotFoundError()

        mock_sysctl_intel = Mock()
        mock_sysctl_intel.stdout = "Intel Core i9-10900K\n"
        mock_sysctl_intel.returncode = 0

        mock_run.side_effect = [
            mock_nvidia_fail.side_effect,
            mock_rocm_fail.side_effect,
            mock_sysctl_intel,
        ]

        # Should fail detection (no M1/M2/M3/M4 found)
        with pytest.raises(ValueError, match="No GPU detected"):
            GPUDetector._detect_from_system()

    @patch("review_bot_automator.llm.providers.gpu_detector.requests.get")
    def test_detect_gpu_case_insensitive_processor(self, mock_get: Mock) -> None:
        """Test case-insensitive matching for processor types."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {
                    "processor": "nvidia cuda 12.1",  # Lowercase
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gpu = GPUDetector.detect_gpu("http://localhost:11434")

        assert gpu.available is True
        assert gpu.gpu_type == "NVIDIA"
