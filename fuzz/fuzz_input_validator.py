#!/usr/bin/env python3
"""Atheris fuzz target for InputValidator security validation.

This fuzzer tests the InputValidator class which is critical for security.
It validates file paths, extensions, URLs, tokens, and content to prevent
injection attacks, path traversal, and other security vulnerabilities.

Coverage:
- validate_file_path(): Path traversal, null bytes, special characters
- validate_file_extension(): Extension bypasses, null bytes, double extensions
- validate_github_url(): URL spoofing, encoding bypasses
- validate_github_token(): Token format bypasses
- sanitize_content(): Null byte injection, control characters

Bugs to find:
- Path traversal bypasses (../, ../../, encoded variants)
- Null byte injection (\x00)
- URL spoofing attacks
- Token format validation bypasses
- Content sanitization bypasses
"""

import sys

import atheris

# Import InputValidator - wrapped in try/except for graceful failure
try:
    from review_bot_automator.security.input_validator import InputValidator
except ImportError as e:
    print(f"[-] Failed to import InputValidator: {e}")
    print("[!] Make sure review-bot-automator is installed: pip install -e .")
    sys.exit(1)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    """Fuzz InputValidator security methods with random inputs.

    Args:
        data: Raw fuzzed input from Atheris
    """
    # Create fuzzed data provider
    fdp = atheris.FuzzedDataProvider(data)

    # Choose which validator method to fuzz (0-4)
    validator_method = fdp.ConsumeIntInRange(0, 4)

    # Generate fuzzed input
    # Use ConsumeString for raw bytes (useful for null byte injection)
    # Use ConsumeUnicodeNoSurrogates for valid Unicode
    if fdp.ConsumeBool():
        fuzzed_input = fdp.ConsumeString(min(fdp.remaining_bytes(), 1024))
    else:
        fuzzed_input = fdp.ConsumeUnicodeNoSurrogates(min(fdp.remaining_bytes(), 1024))

    try:
        validator = InputValidator()

        if validator_method == 0:
            # Fuzz validate_file_path()
            # Look for path traversal bypasses
            result = validator.validate_file_path(fuzzed_input)
            assert isinstance(result, bool), "validate_file_path must return bool"

            # Note: Checking ".." in raw string is incorrect - validator checks Path.parts
            # A filename like "file..txt" is valid, only ".." as a path component is rejected
            # Let the fuzzer explore all edge cases without assertions on specific logic

        elif validator_method == 1:
            # Fuzz validate_file_extension()
            # Look for extension bypasses (double extensions, null bytes, etc.)
            result = validator.validate_file_extension(fuzzed_input)
            assert isinstance(result, bool), "validate_file_extension must return bool"

        elif validator_method == 2:
            # Fuzz validate_github_url()
            # Look for URL spoofing, homograph attacks
            result = validator.validate_github_url(fuzzed_input)
            assert isinstance(result, bool), "validate_github_url must return bool"

            # Note: Simple substring check is insufficient - validator does proper parsing
            # Cases like "https://github.com.evil.com" should be rejected despite substring
            # Let the fuzzer explore all edge cases without assumptions on logic

        elif validator_method == 3:
            # Fuzz validate_github_token()
            # Look for token format bypasses
            result = validator.validate_github_token(fuzzed_input)
            assert isinstance(result, bool), "validate_github_token must return bool"

        else:  # validator_method == 4
            # Fuzz sanitize_content()
            # Look for sanitization bypasses (null bytes, control chars)
            file_type = fdp.PickValueInList(["json", "yaml", "toml", "python", "text"])
            sanitized, warnings = validator.sanitize_content(fuzzed_input, file_type)

            # Verify return types
            assert isinstance(sanitized, str), "sanitize_content must return string"
            assert isinstance(warnings, list), "sanitize_content must return list of warnings"

            # Null bytes should always be removed
            assert "\x00" not in sanitized, "Null bytes must be removed by sanitization"

    except (ValueError, TypeError, AttributeError):
        # Expected exceptions for invalid inputs - not bugs
        pass
    except UnicodeDecodeError:
        # Expected for some byte sequences
        pass
    # Unexpected exceptions (crashes, assertions) will propagate to Atheris


def main() -> int:
    """Entry point for Atheris fuzzing.

    Returns:
        Exit code (0 for success)
    """
    # Set up Atheris with command-line arguments
    atheris.Setup(sys.argv, TestOneInput)

    # Start fuzzing
    atheris.Fuzz()

    return 0


if __name__ == "__main__":
    sys.exit(main())
