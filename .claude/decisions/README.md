# Architecture Decision Records (ADRs)

Append-only log of non-trivial design decisions made during implementation.
Each ADR captures one decision — its context, what we chose, and the consequences.

## When to write one

Write an ADR when:
- The user **pushes back** on a default ("don't do X", "is X the right place?").
- The user asks **"why not X?"** and the answer affects the design.
- A **non-obvious choice** is made that the next reader (human or agent) wouldn't infer from the code (e.g. deferring a dep, choosing one abstraction over another).

If a routine, low-stakes choice gets made, don't write an ADR — code review covers it. ADRs are for the choices a future agent will wonder about.

## Conventions

- One ADR per file. Filename: `NNNN-kebab-case-title.md`, four-digit zero-padded sequence.
- **Append-only.** Never edit an accepted ADR's substance. If a decision changes, write a *new* ADR with `status: accepted`, set the prior one's `status: superseded` and `superseded_by:` link, and link forward.
- Each ADR declares its `scope:` — the design doc it belongs to (so you can find all decisions for a feature).
- Sequence numbers are global to this project, not per-scope.

## Template

See [_adr_template.md](_adr_template.md).
