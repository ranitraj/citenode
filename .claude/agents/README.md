# Review Agents

Read-only specialist subagents invoked by [`/review`](../commands/review.md). Each runs with its own context window (separate from the main session, so it doesn't carry session drift), a restricted tool set (`Read, Grep, Glob, Bash` — no `Edit` or `Write`), and a structured Markdown output format.

| Agent | Catches |
|---|---|
| [dry-reviewer](dry-reviewer.md) | Duplicate logic, parameter signature drift, missed reuse |
| [simplicity-reviewer](simplicity-reviewer.md) | YAGNI violations, the six over-production traps |
| [docs-sync](docs-sync.md) | Design / solution / ADR / CLAUDE drift vs current code |

## Cost

Default model is `haiku`. One `/review` ≈ three Haiku invocations (typically ~$0.02 total). Upgrade individual agents by editing the `model:` field in their frontmatter — `sonnet` for better nuance, `opus` for the highest bar.

## Why opt-in (not always-on)?

Hooks and pre-commit linters are mechanical — they fire on every edit / commit, so their cost has to be near-zero. Agents are semantic — they read files, reason about intent, and produce structured reports. That costs tokens, and adopters on personal projects are often token-budgeted.

The tradeoff: agents run only when *you* invoke `/review`. You decide when the depth is worth the cost — typically at the end of a meaningful chunk, before a commit, or before opening a PR. Hooks remain the always-on safety net; agents are the deeper checkpoint.

## Adding an agent

1. Create `.claude/agents/<name>.md` with frontmatter (`name`, `description`, `model`, `tools`).
2. Keep the agent **read-only** — no `Edit` / `Write` in `tools`.
3. Define a structured output format in the prompt so `/review` can synthesize cleanly.
4. Update [.claude/commands/review.md](../commands/review.md) to launch the new agent in parallel.
5. Add a row to the table above.

## Related

- [.claude/commands/review.md](../commands/review.md) — orchestration entry point
- [.claude/hooks/pre-edit-reuse.sh](../hooks/pre-edit-reuse.sh) — the always-on, mechanical layer that the dry-reviewer complements
- [Whetstone plugin](https://github.com/iliaal/whetstone) — install with `claude plugins add iliaal/whetstone` if you want the broader compound-engineering suite (`/ia-compound`, `/ia-resolve-pr-feedback`, framework-specific reviewers). This template intentionally ships a smaller, Python-focused subset.
