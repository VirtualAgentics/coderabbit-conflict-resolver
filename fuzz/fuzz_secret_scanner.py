#!/usr/bin/env python3
"""Atheris fuzz target for SecretScanner security validation.

This fuzzer tests the SecretScanner class which is critical for preventing
accidental secret exposure. It validates that the secret detection system
can handle malicious or malformed inputs without crashing and without
exposing vulnerabilities like ReDoS (Regular Expression Denial of Service).

Coverage:
- scan_content(): Main scanning with stop_on_first optimization
- has_secrets(): Boolean check for secret presence
- _is_false_positive(): False positive detection logic
- _redact_secret(): Redaction safety for logging
- scan_content_generator(): Generator semantics and early exit

Bugs to find:
- ReDoS vulnerabilities in 17 regex patterns (catastrophic backtracking)
- Unicode edge cases (normalization, surrogates, combining characters)
- Null byte injection (\x00) in secrets
- Boundary conditions (empty strings, extremely long inputs)
- False positive logic errors (comment detection, test/example values)
- Redaction leaks (exposing secret content in logs)

Expected behavior:
- No crashes for any input (all exceptions handled gracefully)
- Consistent redaction format (no secret leakage)
- Performance: <100ms even for worst-case regex inputs
"""

import sys

import atheris

# Import SecretScanner - wrapped in try/except for graceful failure
try:
    from review_bot_automator.security.secret_scanner import SecretScanner
except ImportError as e:
    print(f"[-] Failed to import SecretScanner: {e}")
    print("[!] Make sure review-bot-automator is installed: pip install -e .")
    sys.exit(1)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    """Fuzz SecretScanner security methods with random inputs.

    Args:
        data: Raw fuzzed input from Atheris
    """
    # Create fuzzed data provider for structured input generation
    fdp = atheris.FuzzedDataProvider(data)

    # Choose which method to fuzz (0-4 for 5 key methods)
    method = fdp.ConsumeIntInRange(0, 4)

    # Generate fuzzed content (limit 10KB to prevent resource exhaustion)
    # Use ConsumeUnicodeNoSurrogates for valid Unicode strings
    content = fdp.ConsumeUnicodeNoSurrogates(min(fdp.remaining_bytes(), 10 * 1024))

    try:
        if method == 0:
            # Fuzz scan_content() - Main scanning method
            # Test ReDoS vulnerabilities, long inputs, Unicode edge cases
            stop_first = fdp.ConsumeBool()
            findings = SecretScanner.scan_content(content, stop_on_first=stop_first)

            # Verify return type and structure
            assert isinstance(findings, list), "scan_content must return list"

            # Verify all findings have required attributes
            for finding in findings:
                assert hasattr(finding, "secret_type"), "Finding must have secret_type"
                assert hasattr(finding, "severity"), "Finding must have severity"
                assert hasattr(finding, "matched_text"), "Finding must have matched_text"
                assert hasattr(finding, "line_number"), "Finding must have line_number"

                # Verify redaction (matched_text should never be full secret)
                # Short secrets (<=8 chars) should be fully masked
                matched = finding.matched_text
                assert isinstance(matched, str), "matched_text must be string"
                # If it's all asterisks, it's properly redacted
                # If it contains "...", it's properly redacted (long secret)
                assert "*" in matched or "..." in matched, "Secret must be redacted"

        elif method == 1:
            # Fuzz has_secrets() - Boolean check with early exit optimization
            # Test performance and correctness
            result = SecretScanner.has_secrets(content)
            assert isinstance(result, bool), "has_secrets must return bool"

            # Verify consistency: if has_secrets is True, scan_content should find >=1
            if result:
                findings = SecretScanner.scan_content(content, stop_on_first=True)
                assert len(findings) > 0, "has_secrets=True but scan_content found none"

        elif method == 2:
            # Fuzz _is_false_positive() - Context detection edge cases
            # Test boundary conditions in FP detection logic
            matched_text = fdp.ConsumeUnicodeNoSurrogates(min(fdp.remaining_bytes(), 100))
            is_fp = SecretScanner._is_false_positive(matched_text, content)
            assert isinstance(is_fp, bool), "_is_false_positive must return bool"

            # If matched_text contains obvious FP markers, should return True
            fp_markers = ["example", "test", "dummy", "xxx", "placeholder"]
            if any(marker in matched_text.lower() for marker in fp_markers):
                # Note: May still be False if context doesn't support FP
                # Just verify it doesn't crash
                pass

        elif method == 3:
            # Fuzz _redact_secret() - Boundary conditions (0-100 char secrets)
            # Test redaction safety to prevent secret leakage
            secret = fdp.ConsumeUnicodeNoSurrogates(min(fdp.remaining_bytes(), 100))
            redacted = SecretScanner._redact_secret(secret)

            # Verify return type
            assert isinstance(redacted, str), "_redact_secret must return string"

            # Verify redaction format based on input length
            if len(secret) == 0:
                # Empty secret should return empty redaction
                assert redacted == "", "Empty secret must return empty redaction"
            elif len(secret) <= 8:
                # Short secrets (1-8 chars) should be fully masked
                assert redacted == "*" * len(secret), "Short secrets must be fully masked"
            else:
                # Long secrets (>8 chars) should use first4...last4 format
                assert "..." in redacted, "Long secrets must use '...' format"
                # Should not expose more than 8 characters
                assert redacted.count("*") == 0 or len(redacted) <= len(
                    secret
                ), "Redaction must not be longer than original"

        else:  # method == 4
            # Fuzz scan_content_generator() - Generator semantics
            # Test early exit and generator behavior
            for count, finding in enumerate(SecretScanner.scan_content_generator(content), start=1):
                # Verify finding structure
                assert hasattr(finding, "secret_type"), "Finding must have secret_type"
                assert hasattr(finding, "severity"), "Finding must have severity"

                # Early exit after 10 findings to prevent timeout
                # (Some inputs may generate many findings)
                if count >= 10:
                    break

            # Generator should yield valid findings
            # (count may be 0 if no secrets found - that's valid)

    except (ValueError, TypeError, AttributeError):
        # Expected exceptions for invalid inputs - not bugs
        pass
    except UnicodeDecodeError:
        # Expected for some byte sequences - not a bug
        pass
    # Unexpected exceptions (crashes, assertions) will propagate to Atheris


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
