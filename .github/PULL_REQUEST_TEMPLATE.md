## Summary

<!-- One or two lines on what changes and why. Link the issue if any. -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature / convention (non-breaking)
- [ ] Breaking change (adopters need to update)
- [ ] Documentation only
- [ ] Internal / chore

## Affects

- [ ] `init.py` setup wizard
- [ ] `CLAUDE.md` or `.claude/*.md` conventions
- [ ] Pre-commit hooks / linters (`.pre-commit-config.yaml`, `pyproject.toml`)
- [ ] Claude Code hooks (`.claude/hooks/`, `.claude/settings.json`)
- [ ] Review agents / `/review` command (`.claude/agents/`, `.claude/commands/`)
- [ ] CI (`.github/workflows/`)
- [ ] Documentation (`README.md`, `CHANGELOG.md`)
- [ ] Other

## Checklist

- [ ] Pre-commit passes locally (`make lint`).
- [ ] If this changes conventions, `CLAUDE.md` or `.claude/*.md` is updated in the same PR.
- [ ] If this changes the wizard, opt-out flows still work (test both `Y` and `n` paths).
- [ ] `CHANGELOG.md` updated under `[Unreleased]` (or relevant version section).
- [ ] If this changes the template-shipping surface, downstream adopters can re-sync the diff cleanly.

## Test plan

<!-- How did you verify this works? Bullet list of checks. -->
