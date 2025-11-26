#!/usr/bin/env python3
"""Atheris fuzz target for file handlers (JSON, YAML, TOML).

This fuzzer tests the validate_change() and apply_change() methods of all
file handlers to find crashes, hangs, and security vulnerabilities when
processing malformed or malicious inputs.

Coverage:
- JsonHandler: JSON parsing, validation, modification
- YamlHandler: YAML parsing, validation, modification
- TomlHandler: TOML parsing, validation, modification

Bugs to find:
- Parsing crashes on malformed input
- Injection attacks via special characters
- Path traversal attempts
- Resource exhaustion (large inputs, nested structures)
- Encoding issues (null bytes, surrogates)
"""

import sys
import tempfile
from pathlib import Path

import atheris

# Import handlers - wrapped in try/except for graceful failure
try:
    from review_bot_automator.handlers.json_handler import JsonHandler
    from review_bot_automator.handlers.toml_handler import TomlHandler
    from review_bot_automator.handlers.yaml_handler import YamlHandler
except ImportError as e:
    print(f"[-] Failed to import handlers: {e}")
    print("[!] Make sure review-bot-automator is installed: pip install -e .")
    sys.exit(1)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    """Fuzz all file handlers with randomly generated inputs.

    Args:
        data: Raw fuzzed input from Atheris
    """
    # Create fuzzed data provider for structured input generation
    fdp = atheris.FuzzedDataProvider(data)

    # Choose which handler to fuzz (0=JSON, 1=YAML, 2=TOML)
    handler_type = fdp.ConsumeIntInRange(0, 2)

    # Choose which method to fuzz
    test_validate = fdp.ConsumeBool()

    # Generate fuzzed content (Unicode with no surrogates to avoid codec issues)
    # Limit size to 10KB to prevent resource exhaustion in fuzzing
    content = fdp.ConsumeUnicodeNoSurrogates(min(fdp.remaining_bytes(), 10 * 1024))

    # Generate fuzzed line numbers (1-1000)
    start_line = fdp.ConsumeIntInRange(1, 1000)
    end_line = fdp.ConsumeIntInRange(start_line, start_line + 100)

    try:
        # Create temporary workspace for handler
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)

            # Select and instantiate handler
            if handler_type == 0:
                handler = JsonHandler(workspace_root=workspace)
                filename = "test.json"
            elif handler_type == 1:
                handler = YamlHandler(workspace_root=workspace)
                filename = "test.yaml"
            else:
                handler = TomlHandler(workspace_root=workspace)
                filename = "test.toml"

            # Test validation or application based on fuzzed boolean
            if test_validate:
                # Fuzz validate_change()
                is_valid, message = handler.validate_change(
                    filename=filename, content=content, start_line=start_line, end_line=end_line
                )
                # Validation should always return bool + string
                assert isinstance(is_valid, bool), "validate_change must return bool"
                assert isinstance(message, str), "validate_change must return string message"
            else:
                # Fuzz apply_change()
                # First create a valid file to modify
                test_file = workspace / filename
                if handler_type == 0:
                    test_file.write_text('{"test": "value"}')
                elif handler_type == 1:
                    test_file.write_text("test: value\n")
                else:
                    test_file.write_text('test = "value"\n')

                # Apply fuzzed change
                result_path = handler.apply_change(
                    original_path=test_file,
                    new_content=content,
                    start_line=start_line,
                    end_line=end_line,
                )
                # Should return a valid Path
                assert isinstance(result_path, Path), "apply_change must return Path"

    except (ValueError, TypeError, KeyError, AttributeError):
        # Expected exceptions for invalid inputs - not bugs
        pass
    except MemoryError:
        # Memory exhaustion - expected for some large inputs
        pass
    except RecursionError:
        # Stack overflow - expected for deeply nested structures
        pass
    # Unexpected exceptions (e.g., crashes) will propagate and be caught by Atheris


def main() -> int:
    """Entry point for Atheris fuzzing.

    Returns:
        Exit code (0 for success)
    """
    # Set up Atheris with command-line arguments
    atheris.Setup(sys.argv, TestOneInput)

    # Start fuzzing (runs indefinitely until stopped or crash found)
    atheris.Fuzz()

    return 0


if __name__ == "__main__":
    sys.exit(main())
