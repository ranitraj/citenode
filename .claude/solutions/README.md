# Solution Docs

Solution docs capture what was actually built — created automatically by Claude when a design doc reaches `status: done`. The user never has to ask.

## Trigger

The moment a design doc is marked `status: done`, immediately:

1. Read the completed `.claude/designs/<name>.md` for what was intended.
2. Read the files touched during implementation for what was actually built.
3. Copy `.claude/solutions/_template.md` → `.claude/solutions/<topic>.md`.
4. Fill every section — purpose, root cause (if a bug), solution, validation, prevention.
5. Present to the user for a quick review, then save.

The user's only job is to provide the requirement. Claude handles the rest.

## Status values

- `status: current` — actively relevant, follow the patterns in it.
- `status: archived` — superseded but kept for history.
- `status: deprecated` — pattern actively discouraged now.

These compound over time. Each doc makes the next feature faster to build.
