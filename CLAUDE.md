# Project Memory

Living document of best practices, decisions, and conventions for this project.
Updated as we discover and agree on new standards. Auto-read by Claude Code every session.

---

## Python Packaging

### `__init__.py` conventions
- **`tests/__init__.py`** — always empty. Marker file only; pytest uses it for test discovery.
- **`src/<package>/__init__.py`** — always empty for application services.
  - Do NOT add re-exports until there is a clear public API need.
  - If this becomes a library, curate the public API here with explicit re-exports + `__all__`.
  - `__version__` is acceptable here if needed.
  - Consumers import from submodules directly: `from wiki_agent.agent import WikiAgent`

---

## Docstring & Comment Conventions

### Module docstrings
Every `.py` file we create (e.g. `agent.py`, `wiki.py`) gets a single-line docstring at the top.
`__init__.py` files are exempt — they stay empty.

```python
"""Short description of what this module does."""
```

### Function / method docstrings — NumPy style
Every public function and method must have a NumPy-style docstring with all applicable sections:

```python
def fetch_entry(title: str) -> WikiEntry:
    """Fetch a wiki entry by title.

    Parameters
    ----------
    title : str
        Exact title to retrieve.

    Returns
    -------
    WikiEntry
        The retrieved entry.

    Raises
    ------
    EntryNotFoundError
        If `title` does not exist.
    """
```

Rules:
- One-line summary, imperative mood ("Fetch", "Update", "Run").
- Include `Parameters` / `Returns` / `Raises` only when they apply (omit `Returns` for `None`-returners, etc.).
- Private helpers (`_prefixed`) follow the same rules as public functions.

---

## Code Organisation

### Function ordering within a file
Public functions and methods first, private helpers (`_prefixed`) at the bottom.
Readers see the interface before implementation details.

### Private functions
- Defined at the bottom of the file / class.
- Never imported from another module. Private means private to the module.

### Design principles
- **SOLID** — single responsibility, open/closed, Liskov substitution, interface segregation, dependency inversion.
- **DRY** — before writing new code, search for an existing utility that does the job and reuse it. If similar logic exists elsewhere, refactor the existing one instead of duplicating. Match parameter names/order of nearby functions for consistency.
- **Python best practices** — type hints everywhere, prefer dataclasses/Pydantic models over raw dicts, use `pathlib` over `os.path`.
- **Closed vocabularies as `StrEnum`** — model a fixed set of string values as a `StrEnum` (with a one-line docstring), not a bare `Literal` or string constants repeated across modules. Centralise it once so callers share one source of truth.

---

## Prompts

LLM prompts live as **Jinja2 `.j2` templates**, kept separate from code under the package's `prompts/` directory (`src/<package>/prompts/`), with the system prompt and per-call prompt as distinct templates. Render them through a `prompting.py::render_prompt(name, /, **context)` loader — never inline prompt strings in code. The loader uses `StrictUndefined`, so a missing template variable raises rather than rendering empty. Write real prompts (role framing, chain-of-thought, verbatim grounding, abstain-when-thin), not bare data stubs.

---

## Code Review

Before finalising a feature, run [`/review`](.claude/commands/review.md) — it spawns three parallel read-only agents (DRY, simplicity, docs-sync) that produce a ranked report. Agents are user-invoked, not hook-fired, so they don't burn tokens on every edit. See [.claude/agents/README.md](.claude/agents/README.md) for cost / when to upgrade the model / how to add an agent.

---

## Development Workflow — TDD

This template ships with TDD (RED → GREEN → REFACTOR) as the default workflow. Full rules — test quality, code review pace, real-world scenarios — live in [.claude/TDD.md](.claude/TDD.md). Adopters who don't follow TDD can replace this section.

---

## Document Driven Design (DDD)

For non-trivial features, follow the workflow in [.claude/DDD.md](.claude/DDD.md) — two-phase questioning, then a design doc in `.claude/designs/` before any code. Claude reads `.claude/DDD.md` whenever a DDD step is involved.

---

## Solution Docs

When a design doc reaches `status: shipped`, Claude auto-generates a matching solution doc in `.claude/solutions/`. See [.claude/solutions/README.md](.claude/solutions/README.md) for the trigger + format.

## Architecture Decision Records

Non-trivial design decisions made during implementation (user pushback, "why not X?" calls, non-obvious steers) are captured as ADRs in `.claude/decisions/`. Append-only. See [.claude/decisions/README.md](.claude/decisions/README.md).

---

## Keeping Docs Current

Docs are the source of truth. When implementation diverges from a design doc, update the doc first. When conventions or workflows change, update `CLAUDE.md` or the relevant `.claude/*.md` file in the same change — Claude does this proactively; the user shouldn't have to ask.
