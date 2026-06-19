# Development Workflow — TDD (RED / GREEN)

All implementation follows strict RED → GREEN TDD:

1. **RED** — write a failing test that describes the real-world behaviour first. No implementation yet.
2. **GREEN** — write the minimal code that makes the test pass. No extra logic.
3. **REFACTOR** — clean up while keeping tests green.

## Test quality rules

- Tests must cover **real-world scenarios** — actual inputs, edge cases, and failure modes that will occur in production.
- No contrived tests (e.g. `assert 1 + 1 == 2`, trivial round-trips that test nothing meaningful).
- Each test should have a single, clear reason to fail.
- Use descriptive test names: `test_fetch_entry_raises_when_title_missing` not `test_error`.

## Code review pace

- Claude writes code in **small, reviewable chunks** — one logical unit at a time.
- No skeletons / signature-only stubs. Each chunk is real, tested, working code.
- Wait for explicit approval before moving to the next chunk.
