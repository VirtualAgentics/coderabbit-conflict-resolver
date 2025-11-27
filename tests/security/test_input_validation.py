"""Tests for input validation and sanitization."""

import tempfile
from pathlib import Path

import pytest

from review_bot_automator.security.input_validator import InputValidator


class TestFilePathValidation:
    """Tests for file path validation."""

    def test_valid_relative_path(self) -> None:
        """Test validation of valid relative paths."""
        assert InputValidator.validate_file_path("src/file.py")
        assert InputValidator.validate_file_path("tests/test_file.py")
        assert InputValidator.validate_file_path("docs/guide.md")

        # Edge case: filenames containing literal ".." should be allowed
        assert InputValidator.validate_file_path("my..file.txt")
        assert InputValidator.validate_file_path("folder/..file.txt")
        assert InputValidator.validate_file_path("test..data.json")

    def test_path_traversal_unix(self, subtests: pytest.Subtests) -> None:
        """Test detection of Unix-style path traversal using subtests."""
        unix_paths = [
            "../../etc/passwd",
            "../../../root/.ssh/id_rsa",
            "./../../etc/shadow",
        ]
        for path in unix_paths:
            with subtests.test(msg=f"Unix path traversal: {path}", path=path):
                assert not InputValidator.validate_file_path(path)

    def test_path_traversal_windows(self, subtests: pytest.Subtests) -> None:
        """Test detection of Windows-style path traversal using subtests."""
        windows_paths = [
            "..\\..\\windows\\system32",
            "..\\..\\..\\boot.ini",
        ]
        for path in windows_paths:
            with subtests.test(msg=f"Windows path traversal: {path}", path=path):
                assert not InputValidator.validate_file_path(path)

    def test_absolute_path_without_base_dir(self) -> None:
        """Test that absolute paths are rejected without base_dir."""
        assert not InputValidator.validate_file_path("/etc/passwd")
        assert not InputValidator.validate_file_path("/var/log/secure")

        # Edge case: Windows drive absolute paths should be rejected
        assert not InputValidator.validate_file_path("C:\\Windows\\system32")
        assert not InputValidator.validate_file_path("C:/Windows/System32")
        assert not InputValidator.validate_file_path("D:\\Program Files\\App")
        assert not InputValidator.validate_file_path("E:/Users/Documents")

    def test_absolute_path_with_base_dir(self) -> None:
        """Test absolute paths with base directory constraint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")

            # Valid: file within base_dir (requires allow_absolute=True)
            assert InputValidator.validate_file_path(
                str(test_file), base_dir=tmpdir, allow_absolute=True
            )

            # Invalid: file outside base_dir
            outside_file = "/etc/passwd"
            assert not InputValidator.validate_file_path(
                outside_file, base_dir=tmpdir, allow_absolute=True
            )

    def test_absolute_path_rejected_when_disallowed(self) -> None:
        """Test that absolute paths are rejected when allow_absolute=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")

            # Should be rejected even with base_dir when allow_absolute=False (default)
            assert not InputValidator.validate_file_path(str(test_file), base_dir=tmpdir)

            # Should be rejected without base_dir when allow_absolute=False (default)
            assert not InputValidator.validate_file_path(str(test_file))

    def test_absolute_path_allow_absolute_true_no_base_dir(self) -> None:
        """Test that absolute paths are rejected when allow_absolute=True but no base_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")

            # Should be rejected when allow_absolute=True but no base_dir
            assert not InputValidator.validate_file_path(str(test_file), allow_absolute=True)

    def test_unsafe_characters(self, subtests: pytest.Subtests) -> None:
        """Test rejection of paths with unsafe characters using subtests."""
        unsafe_paths = [
            ("Semicolon command", "file;rm -rf"),
            ("Pipe command", "file|cat /etc/passwd"),
            ("Double ampersand", "file&&evil"),
            ("Backtick execution", "file`whoami`"),
            ("Command substitution", "file$(whoami)"),
        ]
        for char_type, path in unsafe_paths:
            with subtests.test(msg=f"{char_type}: {path}", unsafe_char=char_type):
                assert not InputValidator.validate_file_path(path)

    def test_null_bytes(self) -> None:
        """Test rejection of paths with null bytes."""
        assert not InputValidator.validate_file_path("file\x00.txt")
        assert not InputValidator.validate_file_path("\x00/etc/passwd")

    def test_empty_or_none_path(self) -> None:
        """Test validation of empty or None paths."""
        assert not InputValidator.validate_file_path("")
        # Test with None using type ignore since the method doesn't accept None
        assert not InputValidator.validate_file_path(None)  # type: ignore[arg-type]

    def test_unicode_normalization_attack(self) -> None:
        """Test rejection of Unicode normalization attacks."""
        # These characters can normalize to '..' in some contexts
        assert not InputValidator.validate_file_path("file\u2024\u2024/")
        assert not InputValidator.validate_file_path("\uff0e\uff0e/etc/passwd")


class TestFileSizeValidation:
    """Tests for file size validation."""

    def test_valid_file_size(self) -> None:
        """Test validation of files within size limits."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # Write 1MB file
            f.write(b"a" * (1024 * 1024))
            f.flush()

            try:
                assert InputValidator.validate_file_size(Path(f.name))
            finally:
                Path(f.name).unlink()

    def test_file_too_large(self) -> None:
        """Test rejection of files exceeding size limit."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # Write 11MB file (exceeds 10MB limit)
            f.write(b"a" * (11 * 1024 * 1024))
            f.flush()

            try:
                assert not InputValidator.validate_file_size(Path(f.name))
            finally:
                Path(f.name).unlink()

    def test_nonexistent_file(self) -> None:
        """Test handling of nonexistent files."""
        with pytest.raises(FileNotFoundError):
            InputValidator.validate_file_size(Path("/nonexistent/file.txt"))

    def test_directory_not_file(self) -> None:
        """Test rejection of directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert not InputValidator.validate_file_size(Path(tmpdir))


class TestFileExtensionValidation:
    """Tests for file extension validation."""

    def test_allowed_extensions(self) -> None:
        """Test validation of allowed file extensions."""
        assert InputValidator.validate_file_extension("file.py")
        assert InputValidator.validate_file_extension("file.ts")
        assert InputValidator.validate_file_extension("file.js")
        assert InputValidator.validate_file_extension("file.json")
        assert InputValidator.validate_file_extension("file.yaml")
        assert InputValidator.validate_file_extension("file.yml")
        assert InputValidator.validate_file_extension("file.toml")

    def test_disallowed_extensions(self) -> None:
        """Test rejection of disallowed file extensions."""
        assert not InputValidator.validate_file_extension("file.exe")
        assert not InputValidator.validate_file_extension("file.sh")
        assert not InputValidator.validate_file_extension("file.bat")
        assert not InputValidator.validate_file_extension("file.dll")

    def test_case_insensitive(self) -> None:
        """Test that extension validation is case-insensitive."""
        assert InputValidator.validate_file_extension("file.PY")
        assert InputValidator.validate_file_extension("file.JSON")
        assert InputValidator.validate_file_extension("file.YAML")

    def test_empty_or_none_path(self) -> None:
        """Test handling of empty or None paths."""
        assert not InputValidator.validate_file_extension("")
        # Test with None using type ignore since the method doesn't accept None
        assert not InputValidator.validate_file_extension(None)  # type: ignore[arg-type]


class TestContentSanitization:
    """Tests for content sanitization."""

    def test_remove_null_bytes(self) -> None:
        """Test removal of null bytes from content."""
        content = "data: value\x00\x00"
        clean, warnings = InputValidator.sanitize_content(content, "yaml")

        assert "\x00" not in clean
        assert "Removed null bytes" in warnings[0]

    def test_valid_json(self) -> None:
        """Test sanitization of valid JSON."""
        content = '{"key": "value"}'
        clean, warnings = InputValidator.sanitize_content(content, "json")

        assert "key" in clean
        assert len(warnings) == 0

    def test_invalid_json(self) -> None:
        """Test handling of invalid JSON."""
        content = '{"key": invalid}'
        _clean, warnings = InputValidator.sanitize_content(content, "json")

        assert len(warnings) > 0
        assert "Invalid JSON" in warnings[0]

    def test_valid_yaml(self) -> None:
        """Test sanitization of valid YAML."""
        content = "key: value\nnested:\n  inner: data"
        clean, warnings = InputValidator.sanitize_content(content, "yaml")

        assert "key" in clean
        assert len(warnings) == 0

    def test_invalid_yaml(self) -> None:
        """Test handling of invalid YAML."""
        # Use truly invalid YAML syntax
        content = "key: value: bad: syntax"
        _clean, warnings = InputValidator.sanitize_content(content, "yaml")

        assert len(warnings) > 0
        assert "Invalid YAML" in warnings[0]

    def test_yaml_code_execution_detection(self) -> None:
        """Test detection of Python object serialization in YAML."""
        content = "!!python/object/apply:os.system\nargs: ['rm -rf /']"
        _clean, warnings = InputValidator.sanitize_content(content, "yaml")

        assert len(warnings) > 0
        assert any("Python object serialization" in w for w in warnings)

    def test_eval_detection(self) -> None:
        """Test detection of eval() usage."""
        content = 'code = eval("malicious")'
        _clean, warnings = InputValidator.sanitize_content(content, "python")

        assert len(warnings) > 0
        assert any("eval()" in w for w in warnings)

    def test_exec_detection(self) -> None:
        """Test detection of exec() usage."""
        content = 'exec("malicious code")'
        _clean, warnings = InputValidator.sanitize_content(content, "python")

        assert len(warnings) > 0
        assert any("exec()" in w for w in warnings)

    def test_subprocess_detection(self) -> None:
        """Test detection of subprocess usage."""
        content = "import subprocess\nsubprocess.call(['ls'])"
        _clean, warnings = InputValidator.sanitize_content(content, "python")

        assert len(warnings) > 0
        assert any("subprocess" in w for w in warnings)

    def test_valid_toml(self) -> None:
        """Test sanitization of valid TOML."""
        content = '[section]\nkey = "value"'
        clean, warnings = InputValidator.sanitize_content(content, "toml")

        assert "section" in clean
        assert len(warnings) == 0

    def test_invalid_toml(self) -> None:
        """Test handling of invalid TOML."""
        content = "[section\nkey = value"
        _clean, warnings = InputValidator.sanitize_content(content, "toml")

        assert len(warnings) > 0
        assert "Invalid TOML" in warnings[0]


class TestLineRangeValidation:
    """Tests for line range validation."""

    def test_valid_line_range(self) -> None:
        """Test validation of valid line ranges."""
        assert InputValidator.validate_line_range(1, 10)
        assert InputValidator.validate_line_range(5, 15)
        assert InputValidator.validate_line_range(1, 1)

    def test_invalid_start_line(self) -> None:
        """Test rejection of invalid start lines."""
        assert not InputValidator.validate_line_range(0, 10)
        assert not InputValidator.validate_line_range(-1, 10)

    def test_invalid_end_line(self) -> None:
        """Test rejection of invalid end lines."""
        assert not InputValidator.validate_line_range(1, 0)
        assert not InputValidator.validate_line_range(1, -1)

    def test_start_greater_than_end(self) -> None:
        """Test rejection when start > end."""
        assert not InputValidator.validate_line_range(10, 5)
        assert not InputValidator.validate_line_range(100, 50)

    def test_line_range_with_max_lines(self) -> None:
        """Test validation against maximum line count."""
        assert InputValidator.validate_line_range(1, 10, max_lines=100)
        assert InputValidator.validate_line_range(90, 100, max_lines=100)
        assert not InputValidator.validate_line_range(1, 101, max_lines=100)
        assert not InputValidator.validate_line_range(95, 105, max_lines=100)


class TestGitHubURLValidation:
    """Tests for GitHub URL validation."""

    def test_valid_github_urls(self) -> None:
        """Test validation of legitimate GitHub URLs."""
        assert InputValidator.validate_github_url("https://github.com/user/repo")
        assert InputValidator.validate_github_url("https://api.github.com/repos/user/repo")
        assert InputValidator.validate_github_url(
            "https://raw.githubusercontent.com/user/repo/main/file.txt"
        )

        # Case variations should be accepted
        assert InputValidator.validate_github_url("https://GitHub.com/user/repo")
        assert InputValidator.validate_github_url("HTTPS://GITHUB.COM/user/repo")
        assert InputValidator.validate_github_url("https://API.GITHUB.COM/repos/user/repo")
        assert InputValidator.validate_github_url(
            "https://RAW.GITHUBUSERCONTENT.COM/user/repo/main/file.txt"
        )

    def test_github_urls_with_ports(self) -> None:
        """Test that URLs with ports are handled correctly using hostname."""
        # URLs with non-standard ports should still work
        assert InputValidator.validate_github_url("https://github.com:443/user/repo")
        assert InputValidator.validate_github_url("https://api.github.com:443/repos/user/repo")
        assert InputValidator.validate_github_url("https://GitHub.com:443/user/repo")

    def test_invalid_urls(self) -> None:
        """Test rejection of non-GitHub URLs."""
        assert not InputValidator.validate_github_url("https://evil.com/malicious")
        assert not InputValidator.validate_github_url("http://github.com/user/repo")  # HTTP
        assert not InputValidator.validate_github_url("ftp://github.com/file")

    def test_empty_or_none_url(self) -> None:
        """Test handling of empty or None URLs."""
        assert not InputValidator.validate_github_url("")
        # Test with None using type ignore since the method doesn't accept None
        assert not InputValidator.validate_github_url(None)  # type: ignore[arg-type]

    def test_github_lookalike_domains(self) -> None:
        """Test rejection of GitHub lookalike domains."""
        assert not InputValidator.validate_github_url("https://github.com.evil.com/repo")
        assert not InputValidator.validate_github_url("https://fakegithub.com/repo")
        assert not InputValidator.validate_github_url("https://github-evil.com/repo")

    def test_explicit_allowlist_only(self) -> None:
        """Test that only explicitly allowed domains are accepted."""
        # Explicitly allowed domains
        assert InputValidator.validate_github_url("https://github.com/user/repo")
        assert InputValidator.validate_github_url("https://api.github.com/repos/user/repo")
        assert InputValidator.validate_github_url(
            "https://raw.githubusercontent.com/user/repo/main/file.txt"
        )
        assert InputValidator.validate_github_url("https://gist.github.com/user/12345")

        # Subdomain spoofing attempts should be rejected
        assert not InputValidator.validate_github_url("https://malicious.github.com/repo")
        assert not InputValidator.validate_github_url("https://github.com.evil.com/repo")
        assert not InputValidator.validate_github_url("https://api.github.com.attacker.com/repo")

    def test_case_insensitive_allowlist(self) -> None:
        """Test that allowlist matching is case-insensitive."""
        assert InputValidator.validate_github_url("https://GITHUB.COM/user/repo")
        assert InputValidator.validate_github_url("https://API.GITHUB.COM/repos/user/repo")
        assert InputValidator.validate_github_url(
            "https://RAW.GITHUBUSERCONTENT.COM/user/repo/main/file.txt"
        )
        assert InputValidator.validate_github_url("https://GIST.GITHUB.COM/user/12345")

    def test_github_subdomains(self) -> None:
        """Test explicit coverage for GitHub subdomains - legitimate vs malicious."""
        # Test legitimate GitHub subdomains that should be allowed
        legitimate_subdomains = [
            "https://gist.github.com/user/12345",
            "https://codeload.github.com/user/repo/zip/refs/heads/main",
            "https://github.com/user/repo",  # Main domain
            "https://api.github.com/repos/user/repo",
            "https://raw.githubusercontent.com/user/repo/main/file.txt",
        ]

        for url in legitimate_subdomains:
            assert InputValidator.validate_github_url(
                url
            ), f"Legitimate GitHub URL should be allowed: {url}"

        # Test malicious/arbitrary subdomains that should be rejected
        malicious_subdomains = [
            "https://evil.github.com/malicious",
            "https://malicious.github.com/attack",
            "https://github.com.evil.com/repo",  # Subdomain spoofing
            "https://api.github.com.attacker.com/repo",  # Subdomain spoofing
            "https://gist.github.com.evil.com/user/12345",  # Subdomain spoofing
            "https://codeload.github.com.attacker.com/user/repo",  # Subdomain spoofing
            "https://raw.githubusercontent.com.malicious.com/user/repo",  # Subdomain spoofing
            "https://fake-github.com/repo",  # Lookalike domain
            "https://github-evil.com/repo",  # Lookalike domain
        ]

        for url in malicious_subdomains:
            assert not InputValidator.validate_github_url(
                url
            ), f"Malicious GitHub URL should be rejected: {url}"

        # Test case variations of legitimate subdomains
        case_variations = [
            "https://GIST.GITHUB.COM/user/12345",
            "https://CODELOAD.GITHUB.COM/user/repo/zip/refs/heads/main",
            "https://API.GITHUB.COM/repos/user/repo",
            "https://RAW.GITHUBUSERCONTENT.COM/user/repo/main/file.txt",
        ]

        for url in case_variations:
            assert InputValidator.validate_github_url(
                url
            ), f"Case variation of legitimate URL should be allowed: {url}"


class TestInputValidationLogging:
    """Tests for logging behavior in input validation."""

    def test_path_containment_check_failure_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging when path containment check fails."""
        caplog.set_level("WARNING")

        # Create a scenario where path containment check fails
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            # Create a symlink that points outside the base directory
            outside_file = base_dir.parent / "outside_file.txt"
            outside_file.write_text("test")

            # Create a symlink inside base_dir that points to the outside file
            symlink_path = base_dir / "symlink.txt"
            symlink_path.symlink_to(outside_file)

            try:
                # This should trigger the containment check failure logging
                # because the symlink resolves outside the base directory
                result = InputValidator.validate_file_path("symlink.txt", str(base_dir))
                assert not result

                # Verify warning was logged
                assert any(
                    "Path containment check failed" in record.message for record in caplog.records
                )
            finally:
                if symlink_path.exists():
                    symlink_path.unlink()
                outside_file.unlink()

    def test_path_validation_error_logging(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test logging when path validation encounters an error."""
        caplog.set_level("ERROR")

        # Test with a path that causes an OSError during resolution
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            test_path = "some_file.txt"

            # Monkeypatch Path.parts to raise OSError when accessed
            def mock_parts(self: Path) -> tuple[str, ...]:
                raise OSError("Simulated path parts access error")

            monkeypatch.setattr(Path, "parts", property(mock_parts))

            # Call validate_file_path with a real path so path validation is attempted
            result = InputValidator.validate_file_path(test_path, str(base_dir))
            assert not result

            # Verify error was logged
            assert any("Path validation error" in record.message for record in caplog.records)

    def test_file_extension_warning_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging when file extension is not allowed."""
        caplog.set_level("WARNING")

        # Test with a disallowed extension
        result = InputValidator.validate_file_extension("test.exe")
        assert not result

        # Verify warning was logged
        assert any("File extension not allowed" in record.message for record in caplog.records)
