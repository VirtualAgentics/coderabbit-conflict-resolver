# Agent Plan: Upcoming Fixes (for Claude dry-run)

> This document outlines the exact edits to make, with acceptance criteria and test steps. Do not apply the edits yet; use this plan to simulate and review.

## 1) strategies/priority_strategy.py — Docstrings to Google Style

- Scope:
  - Line ~42–52 and other public methods in the file.
- Change:
  - Replace "Parameters" with "Args", ensure "Returns" and any sections follow Google style.
  - Keep content concise and aligned with actual behavior.
- Acceptance Criteria:
  - All public APIs in this file use Google-style sections (Args, Returns, Raises if applicable, Examples optional).
  - Ruff pydocstyle passes; no lint regressions.

## 2) core/resolver.py — Plaintext fallback security + Docstrings

### 2.1 Secure _apply_plaintext_change path handling
- Issue:
  - The plaintext fallback bypasses `InputValidator` and workspace anchoring.
- Change:
  - Before IO, validate and resolve the path analogous to handlers.
  - Proposed insertion (adapt around current imports):
    ```python
    # Validate and resolve path within workspace
    from pr_conflict_resolver.security.input_validator import InputValidator
    from pr_conflict_resolver.utils.path_utils import resolve_file_path
    if not InputValidator.validate_file_path(
        change.path, base_dir=str(self.workspace_root), allow_absolute=True
    ):
        return False
    file_path = resolve_file_path(
        change.path,
        self.workspace_root,
        allow_absolute=True,
        validate_workspace=True,
        enforce_containment=True,
    )
    ```
  - Optional: Replace the direct write with a best-effort atomic write mirroring handlers (temp file + os.replace). This can be added as a follow-up.
- Acceptance Criteria:
  - Path traversal and out-of-workspace writes are rejected.
  - Existing tests pass; add new unit test(s) if needed to cover validation.

### 2.2 Docstrings to Google Style (Resolver)
- Scope:
  - Around lines ~105–117, 122–144, 188–201, 400–405 (and other public methods still using "Parameters").
- Change:
  - Switch to "Args/Returns" and align content with actual behavior.
- Acceptance Criteria:
  - All public APIs in this file use Google-style sections.

## 3) handlers/json_handler.py — Conflict span + Docstrings + Durable fsync

### 3.1 Conflict span uses min/max lines
- Issue:
  - Uses first/last positions, assuming pre-sorted list.
- Change:
  - Compute `min_start = min(c.start_line for c in key_change_list)` and `max_end = max(c.end_line for c in key_change_list)`; set `line_range=(min_start, max_end)`.
- Acceptance Criteria:
  - Correct span regardless of input ordering; unit test continues to pass (or update to assert new behavior if ordering is shuffled).

### 3.2 Docstrings to Google Style
- Scope:
  - Around lines ~60–81 and ~193–225.
- Change:
  - Replace "Parameters" with "Args"; ensure "Returns", "Examples", and "Notes/Warning" sections align with Google style.
- Acceptance Criteria:
  - Lint/docstyle passes; content accurately reflects behavior.

### 3.3 Directory fsync after os.replace (durability)
- Issue:
  - Add best-effort directory fsync after atomic replacement.
- Change:
  - After `os.replace(temp_path, file_path)`, open the parent directory with `os.open(parent, os.O_DIRECTORY|os.O_RDONLY)`; `os.fsync(dir_fd)` in try/except; always close FD; ignore/log any errors.
- Acceptance Criteria:
  - No functional regressions; optional step failure does not raise; log at debug level (if logging available).

## 4) handlers/base.py — Logging hygiene

- Issue:
  - Local import of `logging` and `getLogger(__name__)` in helper.
- Change:
  - Move `import logging` to module top.
  - Add `logger = logging.getLogger(__name__)` at module level.
  - Replace inline `logging.getLogger(__name__).debug(...)` with `logger.debug(...)`.
- Acceptance Criteria:
  - Ruff import hygiene passes; no new warnings.

## 5) security/input_validator.py — Unicode normalization

- Issue:
  - Docstring claims Unicode normalization prevention but code does not normalize.
- Options (choose one):
  - Implement NFC normalization:
    - `import unicodedata` at top.
    - Normalize the original `path` (string) and each non-anchor segment via `unicodedata.normalize(NFC, value)` before checks (traversal, absolute, char sets, null byte, containment).
    - Update docstring to state inputs are normalized to NFC prior to validation.
  - OR remove the bullet from docstring if not implementing normalization.
- Acceptance Criteria:
  - Implementation and docstring are consistent; tests unaffected or extended to cover NFC edge cases.

## 6) tests/security/test_toml_handler_security.py — Clarify cleanup test intent

- Issue:
  - The `test_apply_change_temp_file_cleanup` currently fails early on invalid TOML, so no tmp file is created.
- Change (pick one):
  - Rename test to communicate early-return behavior (no temp file created).
  - OR create file inside handler workspace and mock `os.replace` to force error after temp creation so cleanup path is exercised here as well (parallel to later tests).
- Acceptance Criteria:
  - Test intent is clear; assertions match the code path being exercised.

## 7) tests/unit/test_cli_validation_enhanced.py — Strengthen pytest.raises match

- Issue:
  - Around lines ~160–169, `pytest.raises` lacks `match=` which reduces diagnostic specificity.
- Change:
  - Add `match=` patterns aligned with messages from `validate_github_repo` for:
    - Reserved names (`.` or `..`).
    - Names ending with `.git`.
- Acceptance Criteria:
  - Tests fail if messages change unintentionally, improving guardrails; entire suite remains green.

---

## Rollout & Validation

1) Update code and docs per above.
2) Run local quality gates:
   - `source .venv/bin/activate && make format && make lint && make test`
3) Run CodeRabbit review on uncommitted changes:
   - `coderabbit review --prompt-only -t uncommitted`
4) Address any additional nits from CodeRabbit (docstring tone, import placement, etc.).

## Risks & Mitigations
- Path validation changes may reject previously-allowed corner cases:
  - Mitigation: Add specific tests for plaintext fallback path validation.
- Directory fsync portability (Windows):
  - Mitigation: wrap in try/except and skip on platforms lacking `os.O_DIRECTORY`.
- Docstring mass edits could drift from behavior:
  - Mitigation: keep edits close to code and re-run lint/doc checks.

## Optional Follow-ups
- Implement atomic write in `_apply_plaintext_change` mirroring handlers (temp file + atomic replace + optional dir fsync + permission preservation).
- Add security-focused tests for Unicode normalization and path anchors on Windows/UNC paths.
