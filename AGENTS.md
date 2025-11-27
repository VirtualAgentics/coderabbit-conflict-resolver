# Repository Guidelines

## Project Structure & Module Organization

- `src/review_bot_automator/`: CLI (`cli/`), conflict engine (`analysis/`, `core/`), file handlers, LLM providers (`llm/`, prompt cache, provider factory), security utilities.
- `tests/`: unit/integration/llm/security + fuzz targets; fixtures in `tests/fixtures/`; mark `slow`/`integration`/`fuzz`.
- Supporting assets: `docs/`, `examples/`, `scripts/` (hooks, cleanup, model setup), `requirements*.txt` for hash-pinned deps, `Makefile` for common tasks.

## Build, Test, and Development Commands

- **Activate `.venv` first** (`source .venv/bin/activate`); never use `sudo` or `pip --break-system-packages`.
- `./setup-dev.sh` or `make install-dev` provisions `.venv`, installs `.[dev]`, and hooks.
- `make lint` (Black, Ruff, MyPy, Bandit, markdownlint); `make format` autofixes.
- `make test` (coverage) or `pytest tests/`; `make test-fuzz*` for Hypothesis; `make test-all` / `make check-all` before PRs.
- Extras: `make type-check`, `make security`, `make docs`, `python -m build`; smoke CLI via `pr-resolve analyze ...` then `pr-resolve apply --mode dry-run`.

## Coding Style & Naming Conventions

- Python 3.12, 4 spaces, 100-char lines; absolute imports preferred.
- Black drives formatting; Ruff enforces double quotes, import order, and security rules; markdownlint for docs.
- Google-style docstrings required for all public APIs; keep docstring coverage ≥80%; include Args/Returns/Raises.
- Type hints everywhere; MyPy strict; avoid `# type: ignore` without justification; naming: `snake_case` functions/vars, `PascalCase` classes, `SCREAMING_SNAKE` constants.

## Testing Guidelines

- Pytest strict with ≥80% coverage (`--cov=src/review_bot_automator`); HTML report in `htmlcov/`.
- Keep fast cases in unit; integration/llm/security/fuzz in their folders; fixtures in `tests/fixtures/`.
- Use markers `slow`, `integration`, `fuzz`; Hypothesis profiles via `HYPOTHESIS_PROFILE`.
- LLM integration defaults: OpenAI/Anthropic require env keys; Ollama uses `OLLAMA_MODEL_NAME` (default `llama2:7b`)—pull the model before running.

## Commit & Pull Request Guidelines

- Conventional Commits (`feat(scope):`, `chore:`, `deps:`); subject ≤72 chars with issue/PR refs like `(#232)` when relevant.
- Keep commits focused and green (`make check-all`); do not bypass hooks (`git ... --no-verify` is forbidden).
- PRs: concise summary, CLI/config examples, linked issue, tests run, risks/rollback plan, screenshots/logs if UI/CLI output changes; update docs for user-facing options.

## Security & Configuration Tips

- Never commit secrets; use `CR_*` env vars or `.env`; redact sensitive values in logs.
- Follow path containment via `InputValidator`; keep writes atomic and permission-preserving.
- Prefer `--mode dry-run` when testing against live repos; run `make security` or `bandit -r src/` for risky changes.
- Keep hash-pinned `requirements*.txt` aligned with Renovate updates; avoid altering CI scanning defaults (CodeQL, Trivy, TruffleHog, pip-audit).
