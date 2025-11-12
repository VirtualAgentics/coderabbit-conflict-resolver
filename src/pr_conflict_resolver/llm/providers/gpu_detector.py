"""GPU detection and hardware acceleration status for Ollama.

This module provides utilities to detect GPU availability, type, and VRAM
through Ollama API inspection and system-level queries. It implements a
multi-tier fallback strategy to maximize detection reliability across
different GPU platforms (NVIDIA CUDA, AMD ROCm, Apple Metal, Intel OneAPI).

Example:
    >>> from pr_conflict_resolver.llm.providers.gpu_detector import GPUDetector
    >>> gpu_info = GPUDetector.detect_gpu("http://localhost:11434")
    >>> if gpu_info.available:
    ...     print(f"GPU: {gpu_info.model_name} ({gpu_info.vram_total_mb}MB)")
    ... else:
    ...     print("Using CPU inference")
"""

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GPUInfo:
    """GPU hardware information for Ollama inference.

    This immutable dataclass contains GPU detection results including
    vendor, model, VRAM capacity, and compute capability.

    Attributes:
        available: Whether GPU acceleration is available
        gpu_type: GPU vendor/type (e.g., "NVIDIA", "AMD", "Apple", "CPU")
        model_name: GPU model name (e.g., "RTX 4090", "M3 Max")
        vram_total_mb: Total VRAM in megabytes
        vram_available_mb: Available VRAM in megabytes
        compute_capability: Compute capability (NVIDIA) or equivalent

    Example:
        >>> gpu = GPUInfo(
        ...     available=True,
        ...     gpu_type="NVIDIA",
        ...     model_name="RTX 4090",
        ...     vram_total_mb=24576,
        ...     vram_available_mb=20480,
        ...     compute_capability="8.9"
        ... )
        >>> print(f"GPU: {gpu.model_name} ({gpu.vram_total_mb // 1024}GB)")
        GPU: RTX 4090 (24GB)
    """

    available: bool
    gpu_type: str | None
    model_name: str | None
    vram_total_mb: int | None
    vram_available_mb: int | None
    compute_capability: str | None

    def __post_init__(self) -> None:
        """Validate GPU info fields."""
        if self.available and self.gpu_type is None:
            raise ValueError("gpu_type cannot be None when GPU is available")

        if self.vram_total_mb is not None and self.vram_total_mb < 0:
            raise ValueError(f"vram_total_mb must be >= 0, got {self.vram_total_mb}")

        if self.vram_available_mb is not None and self.vram_available_mb < 0:
            raise ValueError(f"vram_available_mb must be >= 0, got {self.vram_available_mb}")

        if (
            self.vram_total_mb is not None
            and self.vram_available_mb is not None
            and self.vram_available_mb > self.vram_total_mb
        ):
            raise ValueError(
                f"vram_available_mb ({self.vram_available_mb}) "
                f"cannot exceed vram_total_mb ({self.vram_total_mb})"
            )


class GPUDetector:
    """Detect GPU availability and configuration for Ollama inference.

    This class implements a multi-tier detection strategy:
    1. Query Ollama's /api/ps endpoint for running process info
    2. Parse /api/show model metadata for hardware hints
    3. System-level detection (nvidia-smi, rocm-smi, Metal)
    4. Graceful fallback to CPU-only if detection fails

    The detection is non-blocking and never fails - it always returns
    a valid GPUInfo object (potentially with available=False).
    """

    @staticmethod
    def detect_gpu(base_url: str, timeout: int = 5) -> GPUInfo:
        """Detect GPU from Ollama API and system queries.

        Attempts multiple detection strategies in order of reliability:
        1. Ollama /api/ps endpoint (if available)
        2. System-level GPU detection
        3. CPU fallback (always succeeds)

        Args:
            base_url: Ollama API base URL (e.g., "http://localhost:11434")
            timeout: Timeout in seconds for API requests (default: 5)

        Returns:
            GPUInfo object with detection results. Never raises exceptions.

        Example:
            >>> gpu = GPUDetector.detect_gpu("http://localhost:11434")
            >>> if gpu.available:
            ...     print(f"Using {gpu.gpu_type} GPU: {gpu.model_name}")
            ... else:
            ...     print("No GPU detected, using CPU")
        """
        # Strategy 1: Try Ollama /api/ps endpoint
        try:
            gpu_info = GPUDetector._detect_from_ollama_ps(base_url, timeout)
            if gpu_info.available:
                logger.debug(f"GPU detected via Ollama API: {gpu_info.model_name}")
                return gpu_info
        except Exception as e:
            logger.debug(f"Ollama /api/ps detection failed: {e}")

        # Strategy 2: Try system-level detection
        try:
            gpu_info = GPUDetector._detect_from_system()
            if gpu_info.available:
                logger.debug(f"GPU detected via system: {gpu_info.model_name}")
                return gpu_info
        except Exception as e:
            logger.debug(f"System-level GPU detection failed: {e}")

        # Strategy 3: CPU fallback (always succeeds)
        logger.debug("No GPU detected, using CPU inference")
        return GPUInfo(
            available=False,
            gpu_type="CPU",
            model_name=None,
            vram_total_mb=None,
            vram_available_mb=None,
            compute_capability=None,
        )

    @staticmethod
    def _detect_from_ollama_ps(base_url: str, timeout: int) -> GPUInfo:
        """Detect GPU from Ollama /api/ps endpoint.

        This endpoint may return information about running models and
        their GPU allocation. The exact schema is not officially documented.

        Args:
            base_url: Ollama API base URL
            timeout: Request timeout in seconds

        Returns:
            GPUInfo with detection results

        Raises:
            Exception: If detection fails (endpoint unavailable, parsing error, etc.)
        """
        response = requests.get(f"{base_url}/api/ps", timeout=timeout)
        response.raise_for_status()

        data = response.json()
        logger.debug(f"Ollama /api/ps response: {data}")

        # Try to parse GPU info from response
        # Note: Schema is not officially documented, this is best-effort
        models = data.get("models", [])
        if not models:
            raise ValueError("No running models in /api/ps response")

        # Check first model for GPU info
        model = models[0]
        processor = model.get("processor", "")

        if "nvidia" in processor.lower() or "cuda" in processor.lower():
            return GPUInfo(
                available=True,
                gpu_type="NVIDIA",
                model_name=processor,
                vram_total_mb=model.get("vram_total"),
                vram_available_mb=model.get("vram_available"),
                compute_capability=None,
            )
        elif "amd" in processor.lower() or "rocm" in processor.lower():
            return GPUInfo(
                available=True,
                gpu_type="AMD",
                model_name=processor,
                vram_total_mb=model.get("vram_total"),
                vram_available_mb=model.get("vram_available"),
                compute_capability=None,
            )
        elif "metal" in processor.lower() or "apple" in processor.lower():
            return GPUInfo(
                available=True,
                gpu_type="Apple",
                model_name=processor,
                vram_total_mb=model.get("vram_total"),
                vram_available_mb=model.get("vram_available"),
                compute_capability=None,
            )

        raise ValueError(f"Unknown processor type: {processor}")

    @staticmethod
    def _detect_from_system() -> GPUInfo:
        """Detect GPU from system-level queries.

        Attempts to detect GPU using system commands:
        - NVIDIA: nvidia-smi
        - AMD: rocm-smi
        - Apple: system_profiler (macOS)

        Returns:
            GPUInfo with detection results

        Raises:
            Exception: If no GPU detected or system commands fail
        """
        import platform
        import subprocess

        # Try NVIDIA first (most common)
        try:
            result = subprocess.run(
                [  # noqa: S607
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            )
            output = result.stdout.strip()
            if output:
                parts = output.split(",")
                model_name = parts[0].strip()
                vram_mb = int(float(parts[1].strip()))
                return GPUInfo(
                    available=True,
                    gpu_type="NVIDIA",
                    model_name=model_name,
                    vram_total_mb=vram_mb,
                    vram_available_mb=None,  # Would need separate query
                    compute_capability=None,  # Would need separate query
                )
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
            pass  # nvidia-smi not available or failed

        # Try AMD ROCm
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            )
            output = result.stdout.strip()
            if "GPU" in output:
                return GPUInfo(
                    available=True,
                    gpu_type="AMD",
                    model_name="AMD GPU (ROCm)",
                    vram_total_mb=None,  # Would need separate query
                    vram_available_mb=None,
                    compute_capability=None,
                )
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass  # rocm-smi not available or failed

        # Try Apple Metal (macOS only)
        if platform.system() == "Darwin":
            try:
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=True,
                )
                cpu_brand = result.stdout.strip()
                # Check for Apple Silicon (M1/M2/M3)
                if any(chip in cpu_brand for chip in ["M1", "M2", "M3", "M4"]):
                    return GPUInfo(
                        available=True,
                        gpu_type="Apple",
                        model_name=f"Apple {cpu_brand.split()[1]} (Metal)",
                        vram_total_mb=None,  # Unified memory, hard to determine
                        vram_available_mb=None,
                        compute_capability=None,
                    )
            except (FileNotFoundError, subprocess.CalledProcessError, IndexError):
                pass  # System query failed

        raise ValueError("No GPU detected via system queries")


__all__ = ["GPUDetector", "GPUInfo"]
