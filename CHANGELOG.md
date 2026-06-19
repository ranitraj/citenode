# Changelog

All notable changes to this template will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-05-17

### Changed

- **Rebrand to `moor`** (from `agentic-python-template`). Old GitHub URLs auto-redirect, so existing clones keep working. README now leads with the etymology blockquote (*"moor (v.): to tie a boat so it can't drift in the current"*), then a "Why moor exists" section that surfaces the drift-prevention story before the standard Python tooling table.
- Lowered default pylint score from `10` to `9.5` in the setup wizard. Pylint 10 is the score of a blank file; real code tends to land at 8.x to 9.x and felt punitive on first run. `10` is still available for adopters who want strict mode.
- Reordered the "What's included" table so AI guardrails, AI conventions, and DDD workflow surface first; standard Python tooling (uv, ruff, mypy, pylint, pre-commit, CI) follows.
- README declares its target audience explicitly: multi-service AI agent projects. Points single-service users at cookiecutter-pypackage / hatch.

### Added

- `scripts/new-service.sh`: scaffolds an additional service from `_service-template/` post-init. Handles directory creation, package-directory rename, and string substitution across `pyproject.toml`, tests, and `.envrc`. Leaves the CI matrix update as a single-line manual edit.
- README "Why moor exists" section: three-bullet summary of the drift-prevention layers (mechanical hooks, deterministic pylint similarities, semantic `/review` agents).

## [1.0.0] - 2026-05-17

Initial stable release.

### Highlights

- One-shot setup wizard (`init.py`) with workflow toggles for TDD, DDD, branch protection, GitHub Actions, and docstring style (numpy / google / skip).
- UV-based per-service virtualenvs with direnv auto-activation.
- Strict pre-commit: ruff (with `D` pydocstyle rules + NumPy convention by default), mypy strict, pylint (with duplicate-code detection via `[tool.pylint.similarities]`).
- Document Driven Design (DDD) with a 5-state design-doc lifecycle, solution docs, and append-only ADRs.
- Three layers of AI guardrails for Claude Code:
  - Hooks (mechanical, always-on): pre-edit reuse reminder, stop-time `/simplify` nudge, periodic review prompt.
  - Pylint similarities (deterministic, commit-time): flags 6+ identical lines across files.
  - `/review` slash command (semantic, opt-in): orchestrates three read-only review agents (dry-reviewer, simplicity-reviewer, docs-sync) in parallel.
- GitHub Actions CI with a per-service test matrix.
- Apache 2.0 license.

### Added

- `.claude/agents/` with `dry-reviewer`, `simplicity-reviewer`, `docs-sync`, and a directory README.
- `.claude/commands/review.md` for the `/review` orchestrator.
- `.claude/DDD.md` and `.claude/TDD.md` referenced from `CLAUDE.md`.
- `.claude/solutions/README.md` and `.claude/decisions/README.md`.
- `LICENSE` (Apache 2.0).
- `init.py` cleanup on init: always removes template-meta GitHub PR/issue templates; if adopters decline TDD or DDD, also strips the matching `CLAUDE.md` sections, deletes orphan `.claude/{DDD,TDD}.md` files, and removes `docs-sync` references across the template.

[1.0.0]: https://github.com/ranitraj/moor/releases/tag/v1.0.0
[1.1.0]: https://github.com/ranitraj/moor/releases/tag/v1.1.0
