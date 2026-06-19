# Document Driven Design (DDD)

Before implementing any non-trivial feature or module, a design doc must be created and approved.
Template lives at `.claude/designs/_template.md` — copy it, fill it, get sign-off, then code.
Non-trivial decisions made during implementation are captured as **Architecture Decision Records (ADRs)** in `.claude/decisions/` (see [decisions/README.md](decisions/README.md)).

## Workflow

1. **Two-phase questioning** before writing anything:
   - **Phase 1 — Exploration**: Ask open questions to help the user discover what they want. Continue as long as the user is still pivoting or undecided. Do not ask implementation-detail questions yet.
   - **Phase 2 — Finalisation** (once direction is clear): Ask exactly 3 targeted rounds:
     - Round 1: gaps and ambiguities surfaced by exploration
     - Round 2: edge cases and failure modes
     - Round 3: constraints (scale, security, ops, cost)
   - After Round 3: ask *"Want to dig deeper, or shall we proceed to the design doc?"*
   - If dig deeper → continue targeted rounds, repeat the question after each.
   - If proceed → move to step 2.
2. Copy `_template.md` → `.claude/designs/<name>.md` and fill every section. New docs start at `status: draft`.
3. Get explicit sign-off — transition to `status: ready`.
4. Implement against the doc; transition to `status: in-progress`. Update the doc as the design evolves — doc stays the source of truth.
5. When the feature is live and stable, transition to `status: shipped`.

The same two-phase flow applies to `STRATEGY.md`.

## Frontmatter rules

- `type`: `feature` | `model` | `service` | `tool` | `refactor`
- `status`: `draft` → `ready` → `in-progress` → `shipped`, or `superseded` (with `superseded_by:` link)
- `depends_on`: list of other design doc **names** (not step numbers) — e.g. `[wiki-entry-model]`
- `superseded_by`: forward link to the replacement design doc's name; required only when `status: superseded`

## Status lifecycle

| Status | Meaning | Allowed transitions |
|---|---|---|
| `draft` | Under exploration. Sections may be incomplete; direction may still pivot. **No implementation yet.** | → `ready`, → `superseded` |
| `ready` | Signed off by the user. Sections complete, open questions resolved or scoped out. **Implementation can begin.** | → `in-progress`, → `superseded` |
| `in-progress` | Being built. Doc is updated alongside each chunk: new models, on-disk formats, dependency changes, error cases, resolved open questions. | → `shipped`, → `superseded` |
| `shipped` | Feature is live and stable; no active work. A matching solution doc has been generated in `.claude/solutions/`. | → `superseded` |
| `superseded` | Replaced by another design. The `superseded_by:` field links forward. **Never delete a superseded doc** — readers need to trace history. | (terminal) |

## Architecture Decision Records (ADRs)

ADRs live in `.claude/decisions/NNNN-kebab-case-title.md` and capture non-trivial design decisions made during implementation. They are **append-only**: an accepted ADR is never edited in substance; if the decision changes, write a new ADR and mark the old one `superseded`.

**When to write one:** the user pushes back on a default, asks *"why not X?"*, or steers a non-obvious choice. Routine, low-stakes choices don't need an ADR — they're visible in the diff. ADRs are for the choices a future reader (or agent) will wonder about.

**Linking:** every ADR declares a `scope:` field naming the design doc it belongs to. Design docs may include an optional "Decision Log" section listing the ADRs scoped to them.

See [decisions/README.md](decisions/README.md) for the full conventions and [decisions/_adr_template.md](decisions/_adr_template.md) for the template.

## Stable IDs

Test scenarios in design docs use T-IDs (T1, T2…) that never renumber — gaps from deletion are fine.
T-IDs live only in the design doc as scenario references. Test function names use plain descriptive snake_case:
`test_fetch_entry_returns_entry`, not `test_T1_fetch_entry_returns_entry`.

## Hard rules

- Before starting any implementation task, automatically scan `.claude/designs/` for a doc whose
  name matches the feature. If one exists, read it in full before writing a single line of code.
  The user should never have to say "read the design doc" — Claude does it proactively.
- All file paths in design docs are **repo-relative only** — never absolute paths.
- No implementation code in design docs — signatures and intent only.
- `depends_on` is enforced: do not start work on a design whose dependencies are not at `status: shipped` (or `ready` if working in parallel is explicitly approved).
- Design docs must be updated **in the same change** as code that diverges from them. Don't let the doc drift behind the implementation.
