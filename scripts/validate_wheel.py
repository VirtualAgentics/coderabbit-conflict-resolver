#!/usr/bin/env python3
"""Validate built wheel package.

This script validates that the built wheel can be installed and imported correctly.
It performs import testing, version verification, and entry point validation.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def get_project_root() -> Path:
    """Get the project root directory.

    Returns:
        Path: Project root directory.
    """
    return Path(__file__).parent.parent


def find_wheel_file() -> Path:
    """Find the wheel file in the dist/ directory.

    Returns:
        Path: Path to the wheel file.

    Raises:
        FileNotFoundError: If no wheel file is found.
        ValueError: If multiple wheel files are found.
    """
    dist_dir = get_project_root() / "dist"
    if not dist_dir.exists():
        raise FileNotFoundError(f"dist/ directory not found at {dist_dir}")

    wheel_files = list(dist_dir.glob("*.whl"))

    if not wheel_files:
        raise FileNotFoundError(f"No wheel file found in {dist_dir}")

    if len(wheel_files) > 1:
        raise ValueError(
            f"Multiple wheel files found in {dist_dir}: {[f.name for f in wheel_files]}"
        )

    return wheel_files[0]


def load_metadata() -> dict[str, Any]:
    """Load metadata.json file.

    Returns:
        dict: Metadata dictionary.

    Raises:
        FileNotFoundError: If metadata.json not found.
    """
    metadata_path = get_project_root() / "dist" / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json not found at {metadata_path}")

    with metadata_path.open() as f:
        return json.load(f)


def install_wheel_isolated(wheel_path: Path, target_dir: Path) -> None:
    """Install wheel in an isolated directory.

    Args:
        wheel_path: Path to the wheel file.
        target_dir: Target installation directory.

    Raises:
        subprocess.CalledProcessError: If installation fails.
    """
    print(f"Installing wheel to isolated directory: {target_dir}")

    # Install wheel to target directory
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--target",
            str(target_dir),
            str(wheel_path),
        ],
        check=True,
        capture_output=True,
    )


def validate_import(install_dir: Path, expected_version: str) -> dict[str, Any]:
    """Validate package import and version.

    Args:
        install_dir: Directory where package is installed.
        expected_version: Expected version string.

    Returns:
        dict: Validation results.
    """
    results = {
        "import_successful": False,
        "version_matches": False,
        "version_found": None,
        "error": None,
    }

    # Create a test script to run in isolation
    test_script = f"""
import sys
sys.path.insert(0, {str(install_dir)!r})

try:
    import review_bot_automator
    print(f"VERSION:{{review_bot_automator.__version__}}")
    print("IMPORT:SUCCESS")
except Exception as e:
    print(f"ERROR:{{e}}")
    sys.exit(1)
"""

    try:
        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            check=False,
        )

        output = result.stdout.strip()

        if result.returncode == 0 and "IMPORT:SUCCESS" in output:
            results["import_successful"] = True

            # Extract version from output
            for line in output.split("\n"):
                if line.startswith("VERSION:"):
                    found_version = line.split(":", 1)[1]
                    results["version_found"] = found_version
                    results["version_matches"] = found_version == expected_version
                    break
        else:
            results["error"] = result.stderr or result.stdout

    except Exception as e:
        results["error"] = str(e)

    return results


def validate_entry_point(install_dir: Path) -> dict[str, Any]:
    """Validate that the CLI entry point exists and is callable.

    Args:
        install_dir: Directory where package is installed.

    Returns:
        dict: Entry point validation results.
    """
    results = {
        "entry_point_exists": False,
        "entry_point_callable": False,
        "error": None,
    }

    test_script = f"""
import sys
sys.path.insert(0, {str(install_dir)!r})

try:
    from review_bot_automator.cli.main import cli
    print("ENTRY_POINT:EXISTS")

    # Check if it's callable
    if callable(cli):
        print("ENTRY_POINT:CALLABLE")
except ImportError as e:
    print(f"ERROR:Entry point not found: {{e}}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR:{{e}}")
    sys.exit(1)
"""

    try:
        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            check=False,
        )

        output = result.stdout.strip()

        if "ENTRY_POINT:EXISTS" in output:
            results["entry_point_exists"] = True

        if "ENTRY_POINT:CALLABLE" in output:
            results["entry_point_callable"] = True

        if result.returncode != 0:
            results["error"] = result.stderr or result.stdout

    except Exception as e:
        results["error"] = str(e)

    return results


def main() -> int:
    """Main entry point for wheel validation.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    print("=" * 70)
    print("Validating Wheel Package")
    print("=" * 70)

    validation_results = {
        "wheel_found": False,
        "wheel_path": None,
        "install_successful": False,
        "import_validation": {},
        "entry_point_validation": {},
        "overall_success": False,
    }

    temp_dir = None

    try:
        # Find wheel file
        print("\n1. Finding wheel file...")
        wheel_path = find_wheel_file()
        validation_results["wheel_found"] = True
        validation_results["wheel_path"] = str(wheel_path)
        print(f"✓ Found wheel: {wheel_path.name}")

        # Load metadata
        print("\n2. Loading metadata...")
        metadata = load_metadata()
        expected_version = metadata["package"]["version"]
        print(f"✓ Expected version: {expected_version}")

        # Create temporary directory for isolated installation
        print("\n3. Installing wheel in isolated environment...")
        temp_dir = Path(tempfile.mkdtemp(prefix="wheel_validation_"))
        install_wheel_isolated(wheel_path, temp_dir)
        validation_results["install_successful"] = True
        print("✓ Installation successful")

        # Validate import
        print("\n4. Validating package import...")
        import_results = validate_import(temp_dir, expected_version)
        validation_results["import_validation"] = import_results

        if import_results["import_successful"]:
            print("✓ Package import successful")
        else:
            print(f"✗ Package import failed: {import_results.get('error', 'Unknown error')}")

        if import_results["version_matches"]:
            print(f"✓ Version matches: {import_results['version_found']}")
        else:
            print(
                f"✗ Version mismatch: expected {expected_version}, "
                f"found {import_results.get('version_found', 'None')}"
            )

        # Validate entry point
        print("\n5. Validating CLI entry point...")
        entry_point_results = validate_entry_point(temp_dir)
        validation_results["entry_point_validation"] = entry_point_results

        if entry_point_results["entry_point_exists"]:
            print("✓ Entry point exists")
        else:
            print(f"✗ Entry point not found: {entry_point_results.get('error', 'Unknown error')}")

        if entry_point_results["entry_point_callable"]:
            print("✓ Entry point is callable")
        else:
            print("✗ Entry point is not callable")

        # Determine overall success
        validation_results["overall_success"] = (
            validation_results["wheel_found"]
            and validation_results["install_successful"]
            and import_results["import_successful"]
            and import_results["version_matches"]
            and entry_point_results["entry_point_exists"]
            and entry_point_results["entry_point_callable"]
        )

        # Print summary
        print("\n" + "=" * 70)
        print("Validation Summary")
        print("=" * 70)
        print(f"Wheel Found:          {'✓' if validation_results['wheel_found'] else '✗'}")
        print(f"Install Successful:   {'✓' if validation_results['install_successful'] else '✗'}")
        print(f"Import Successful:    {'✓' if import_results['import_successful'] else '✗'}")
        print(f"Version Matches:      {'✓' if import_results['version_matches'] else '✗'}")
        print(f"Entry Point Exists:   {'✓' if entry_point_results['entry_point_exists'] else '✗'}")
        print(
            f"Entry Point Callable: {'✓' if entry_point_results['entry_point_callable'] else '✗'}"
        )
        print("=" * 70)

        if validation_results["overall_success"]:
            print("\n✓ All validations passed!")
            return 0
        else:
            print("\n✗ Some validations failed!")
            return 1

    except Exception as e:
        print(f"\n✗ Validation error: {e}", file=sys.stderr)
        return 1

    finally:
        # Clean up temporary directory
        if temp_dir and temp_dir.exists():
            print(f"\nCleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    sys.exit(main())
