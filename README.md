# moor

[![Release](https://img.shields.io/github/v/release/ranitraj/moor)](https://github.com/ranitraj/moor/releases)
[![License](https://img.shields.io/github/license/ranitraj/moor)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue)](https://www.python.org/)

> *moor (v.): to tie a boat so it can't drift in the current.*

A Python project template that does that for AI agents: keeps Claude Code anchored to engineering discipline over long sessions. Three layers of guardrails so the agent doesn't drift.

**For multi-service AI agent projects** (an agent service + tool services + frontend, all in one repo). If you're building a single-service library or CLI, try [cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) or [hatch new](https://hatch.pypa.io/) instead.

**Opinionated, not prescriptive.** Workflow defaults (TDD, DDD, branch protection, CI) are opt-in at init time; decline any that don't fit your team.

---

## Why moor exists

LLMs drift over long sessions: duplicate logic, mismatched parameter names, missed reuse, design docs that go stale. Most templates have good Python tooling. This one adds **three layers of drift prevention** specifically for AI-agent workflows:

- **Mechanical** (always-on): Claude Code hooks fire on every Edit to remind the agent to reuse existing utilities.
- **Deterministic** (commit-time): pylint similarities flags semantic duplicate logic before it lands.
- **Semantic** (opt-in): the `/review` slash command runs three read-only review agents in parallel.

Plus all the standard Python tooling adopters expect (uv, ruff, mypy, pylint, pre-commit, CI).

---

## What's included

| Layer | Tool / Convention |
|---|---|
| AI guardrails | 3 layers: hooks (mechanical), pylint similarities (deterministic), opt-in `/review` agents (semantic) |
| AI conventions | `CLAUDE.md` + `.claude/{DDD,TDD}.md` — NumPy docstrings, RED/GREEN TDD, DDD workflow, SOLID |
| Design workflow *(optional)* | Document Driven Design (DDD) with design, solution, and ADR templates |
| Setup wizard | `init.py` — interactive, replaces all placeholders, self-deletes |
| Code quality | pylint (default score 9.5, McCabe complexity, duplicate-code detection) |
| Pre-commit hooks | All of the above + optional TDD enforcement + optional branch protection |
| Linting & formatting | ruff (E, F, I, B, UP, RUF, D rules — NumPy docstring convention by default) |
| Type checking | mypy strict mode |
| Dependency management | [uv](https://docs.astral.sh/uv/) — fast, per-service virtualenvs |
| Venv auto-activation | [direnv](https://direnv.net/) — `cd` into a service, venv activates automatically |
| CI *(optional)* | GitHub Actions — quality gate + per-service test matrix |

---

## Quickstart

### 1. Install prerequisites (one-time)

```bash
brew install uv direnv python@3.12
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc   # or ~/.bashrc for bash
```

### 2. Create your project from the template

Click **Use this template** on GitHub, then clone and enter your new repo:

```bash
git clone https://github.com/<you>/<your-project>.git
cd <your-project>
```

### 3. Run the setup wizard

```bash
python3 init.py
```

Five question categories: project identity, first service, code quality thresholds, **workflow toggles** (TDD, DDD, branch protection, GitHub Actions), and final confirm. Decline any toggle your team doesn't use.

### 4. Bootstrap dependencies and hooks

```bash
make init
direnv allow .
```

Installs dev deps + git hooks and approves the root direnv.

### 5. Set up your first service

```bash
cd services/<your-service>
direnv allow .
```

The service venv auto-activates from now on. No manual `source .venv/bin/activate`.

---

## AI guardrails

LLMs drift over long sessions — duplicate logic, mismatched parameter names, missed reuse, doc / code drift. The template ships **three complementary layers**, each tuned to a different cost / depth tradeoff. All three are removable later (see *To disable* below).

### Layer 1 — Mechanical (always-on, near-zero cost)

Claude Code hooks in [`.claude/hooks/`](.claude/hooks/), wired via [`.claude/settings.json`](.claude/settings.json):

- **Reuse reminder before edits** — `PreToolUse` on `Edit`/`Write`/`MultiEdit` injects: *grep for an existing utility first, match parameter names of nearby functions, refactor rather than duplicate.*
- **Auto-`/simplify` on stop** — when Claude tries to stop with uncommitted changes, blocks once-per-session and nudges to run `/simplify` first. A per-session marker prevents looping after `/simplify`'s own edits.

### Layer 2 — Deterministic (commit-time, free)

`pylint similarities` (configured in `pyproject.toml`) flags 6+ identical lines across files, ignoring imports/signatures/comments/docstrings — so logic duplication can't slip past `pre-commit`. The rest of [`.pre-commit-config.yaml`](.pre-commit-config.yaml) handles formatting, types, and TDD enforcement.

### Layer 3 — Semantic (opt-in, ~$0.02 per invocation)

Read-only specialist agents in [`.claude/agents/`](.claude/agents/), orchestrated by the [`/review`](.claude/commands/review.md) slash command. Three agents run in parallel and return a ranked report:

- **dry-reviewer** — duplicate logic, parameter signature drift, missed reuse. Catches what `pylint similarities` can't: semantic duplication in different shapes.
- **simplicity-reviewer** — YAGNI violations and the six over-production traps (`while-I'm-here`, `for-future-flexibility`, `defensive-coding`, `modernization`, `consistency`, `cleanup`).
- **docs-sync** — design / solution / ADR / CLAUDE drift vs current code (the one rule we explicitly couldn't enforce mechanically).

Invoke `/review` at the end of a feature, before a commit, or before a PR. They never fire automatically — see [.claude/agents/README.md](.claude/agents/README.md) for cost, model selection, and how to add an agent.

### To disable

- **Hooks:** edit `.claude/settings.json` (or delete the file).
- **Pylint similarities:** remove the `[tool.pylint.similarities]` section from `pyproject.toml`.
- **Agents:** simply don't invoke `/review` — they're never auto-fired.

---

## Development workflow

These are template defaults — selected (or declined) during `python3 init.py`. Skip the ones your team doesn't use; the rest still work independently.

- **Before code** *(if DDD enabled)* — copy `.claude/designs/_template.md`, fill it, get sign-off, then implement. Full rules: [.claude/DDD.md](.claude/DDD.md).
- **While coding** *(if TDD enabled)* — RED → GREEN → REFACTOR. Pre-commit blocks a `src/` commit without a matching `tests/test_<module>.py`. Full rules: [.claude/TDD.md](.claude/TDD.md).
- **After shipping** *(if DDD enabled)* — solution docs auto-generate when a design doc hits `status: shipped`. See [.claude/solutions/README.md](.claude/solutions/README.md).
- **Non-obvious decisions** *(if DDD enabled)* — capture as ADRs in [.claude/decisions/](.claude/decisions/).

---

## Useful commands

```bash
make init              # full bootstrap (install + git hooks)
make lint              # run all pre-commit hooks on every file
make hooks-update      # update pre-commit hooks to latest versions
make clean             # remove __pycache__, .mypy_cache, .ruff_cache, .pytest_cache
/review                # spawn DRY + simplicity + docs-sync agents on uncommitted changes
```

---

<details>
<summary><strong>Adding a new service</strong></summary>

```bash
scripts/new-service.sh <new-service>
# Then add '<new-service>' to the matrix in .github/workflows/ci.yml
cd services/<new-service> && direnv allow .
```

The script copies `_service-template/`, renames the package directory, and substitutes service names in `pyproject.toml`, tests, and `.envrc`. Lint and type checks auto-discover the new service: `scripts/lint_service.py` (invoked by the `mypy-services` and `pylint-services` pre-commit hooks) groups staged files by service root and runs mypy/pylint inside each service's own venv via `uv run --directory`. No `.pre-commit-config.yaml` edits needed.

</details>

<details>
<summary><strong>Troubleshooting Claude Code</strong></summary>

### Claude is ignoring CLAUDE.md conventions

`CLAUDE.md` loads once at session start. If Claude isn't following it:

1. Verify it's at the repo root, not a subdirectory.
2. Start a new session — `CLAUDE.md` reloads.
3. Re-anchor mid-session: *"Re-read CLAUDE.md and confirm the conventions before continuing."*

### Claude is not reading the design doc automatically

`CLAUDE.md` instructs Claude to scan `.claude/designs/` before each implementation task. If skipped, run `/clear` to reload, or re-anchor: *"Check CLAUDE.md's DDD rules and follow them before continuing."*

### Claude jumps to code without exploring

DDD is two-phase: open exploration, then 3 targeted rounds (gaps, edge cases, constraints). If Claude skips: *"Stop. We haven't done the two-phase questioning yet. Start with exploration."*

### Hooks aren't firing

The settings watcher only sees `.claude/settings.json` if it existed when the session started. Run `/hooks` once (opens the menu, reloads config) or restart the session.

</details>

---

> **Maintainer note:** After pushing your template, go to **Settings → General → check "Template repository"** so the green "Use this template" button appears for visitors.
