# Claude Project Rules and Context

## Purpose
Claude should assist with code edits and reviews in this repository while strictly following our Python 3.12, venv-first, and quality-gated workflow.

## Execution & Environment
- Always run Python-related commands inside the virtualenv:
  - `source .venv/bin/activate && <tool>`
  - Prefer `make` targets: `make check-all`, `make test`, `make lint`, `make format`, `make type-check`.
- Strictly forbidden:
  - `sudo`, `pip --break-system-packages`, and `git * --no-verify`.
- Use CodeRabbit to review uncommitted changes:
  - `coderabbit review --prompt-only -t uncommitted`.

## Code Standards
- Python 3.12; formatting with Black (line-length=100).
- Ruff linting with comprehensive rules; fix lint issues.
- MyPy in strict mode; no untyped public APIs.
- Bandit and Safety must pass.
- Google-style docstrings for all public functions/classes.
- Absolute imports (e.g., `from pr_conflict_resolver.core.models import Change`).

## Architecture Overview
- `src/pr_conflict_resolver/`
  - `analysis/`: conflict detection/analysis
  - `handlers/`: file-type handlers (JSON/YAML/TOML) inheriting `BaseHandler`
  - `strategies/`: resolution strategies (priority-based, semantic)
  - `core/`: models and resolver
  - `integrations/`: GitHub extraction
  - `config/`: configuration/presets
  - `security/`: security validation and helpers
- Handler pattern: validate paths, apply safe/atomic edits, preserve permissions.
- Strategy pattern: if/elif chains to avoid overwriting priorities.

## Data Models
- `Change`: mutable dataclass with `slots=True` (tests depend on mutability).
- `Conflict`, `Resolution`, `ResolutionResult`: dataclasses with `slots=True` (favor immutability where feasible).
- Use `ChangeMetadata` (TypedDict) and `Mapping[str, object]` for flexible metadata.
- `type LineRange = tuple[int, int]`.

## Security Rules
- Path validation via `InputValidator`:
  - Enforce workspace containment by default; fall back to safe per-segment validation only when specified by tests.
  - Segment validation must skip anchors (drive/root) and disallow separators in parts.
- Never execute code from config inputs; sanitize/validate JSON/YAML/TOML; detect duplicate keys and dangerous tags.
- Redact secrets in logs; log lengths/hashes instead of raw sensitive values.

## Testing & CI
- Pytest with clear, atomic tests; >80% coverage target.
- Cross-platform:
  - Windows read-only file replacement can behave differently; adjust tests to skip or relax where needed.
- Pre-commit hooks are required; do not bypass.

## Performance & File Ops
- Overlap calculation: line-sweep event method; avoid large in-memory sets.
- Perform atomic writes; preserve original permissions on replacement.
- Avoid deep nesting and blanket `except`; catch specific exceptions; add meaningful logging.

## How to Run
- Daily checks: `source .venv/bin/activate && make check-all`.
- Tests: `source .venv/bin/activate && make test` or `pytest`.
- Lint/format/type:
  - `ruff check src/ tests/ --fix`
  - `black src/ tests/`
  - `mypy src/ --strict`
- Review uncommitted changes: `coderabbit review --prompt-only -t uncommitted`.

## Edit Guidance for Claude
- Prefer small, focused edits that preserve existing style and indentation.
- Do not add explanatory comments inside code beyond what future maintainers need.
- Keep functions well-typed; avoid `Any` unless explicitly warranted and documented.
- If a change impacts tests, update or add tests accordingly.
