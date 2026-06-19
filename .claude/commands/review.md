---
description: Run three parallel read-only review agents (DRY, simplicity, docs-sync) and synthesize one ranked review.
---

You are running the project's compound review. Three specialist agents read the diff in parallel and return structured reports; you then synthesize a single review for the user.

## Scope resolution

If `$ARGUMENTS` is supplied, that's the scope (file paths, a feature name, or a directory). Otherwise the default scope is the current working tree's uncommitted + staged changes — discover via:

```bash
git status --short
git diff --cached --name-only
git diff --name-only
```

Mention the resolved scope at the top of your synthesis so the user can verify you reviewed what they expected.

## Preflight — decide which agents to launch

Before fanning out, check which agents are applicable to *this* project:

```bash
# docs-sync only applies when DDD is enabled (designs/solutions/decisions dirs exist)
test -d .claude/designs && test -d .claude/solutions && test -d .claude/decisions
```

- **All three DDD dirs present:** launch all three agents.
- **Any DDD dir missing:** skip `docs-sync`, launch only `dry-reviewer` + `simplicity-reviewer`, and note in the synthesis: *"docs-sync skipped: DDD not enabled in this project."*

Also: if `.claude/agents/docs-sync.md` doesn't exist (init.py removed it on opt-out), do not attempt to invoke it.

## Execution

Launch the applicable subagents **in parallel** — a single message with parallel `Task` tool calls. Do not invoke them sequentially; the parallel fan-out is the point.

| `subagent_type` | Prompt | When |
|---|---|---|
| `dry-reviewer` | Review the scope for duplicate logic, parameter drift, and missed reuse. Scope: `<resolved scope>` | Always |
| `simplicity-reviewer` | Review the scope for YAGNI violations and over-production traps. Scope: `<resolved scope>` | Always |
| `docs-sync` | Check the scope for design / solution / ADR / CLAUDE drift. Scope: `<resolved scope>` | Only when preflight passes |

All are read-only (`Read, Grep, Glob, Bash`). They cannot modify files. They return structured Markdown reports.

## Synthesis

After all launched reports arrive, present **one** consolidated review to the user. Group findings by **severity**, not by reviewer:

```markdown
# Code Review — <scope>

## Critical (must fix before commit)
- [reviewer] [finding] — `file:line`

## Warnings (consider before commit)
- [reviewer] [finding] — `file:line`

## Suggestions (optional)
- [reviewer] [finding] — `file:line`

## Verdict
- DRY: <pass | warnings | critical>
- Simplicity: <pass | warnings | critical>
- Docs-sync: <pass | warnings | critical>
```

Each finding shows which reviewer flagged it in `[brackets]`.

## Rules of synthesis

- **Don't pad.** If every launched reviewer returned a clean report, say *"Every launched reviewer returned clean. No findings."* and stop.
- **Don't dedupe across reviewers** — if dry-reviewer and simplicity-reviewer both flag the same code from different angles, show both. They're different perspectives, both worth seeing.
- **Don't auto-fix.** After synthesis, ask the user which findings (if any) to act on. The agents are advisory by design.
- **Cite line numbers.** Every finding must include `file:line` so the user can jump straight there.

## When to invoke this command

Good moments to run `/review`:
- End of a feature chunk, before commit.
- Before opening a PR.
- After a long session where the main agent's context may have drifted.

Bad moments:
- Mid-chunk, when code is intentionally incomplete.
- For a one-line bug fix — the overhead outweighs the value.
