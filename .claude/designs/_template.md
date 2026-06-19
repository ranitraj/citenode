---
type: feature | model | service | tool | refactor
name: descriptive-kebab-case-name
status: draft | ready | in-progress | shipped | superseded
depends_on: []          # names of other design docs this one depends on
superseded_by:          # only when status=superseded; forward link to replacement
---

# [Name]

## Purpose
One sentence. What does this module/feature do and why does it exist?

## Problem
What gap does this fill? What breaks or is missing without it?

## Public API
List every public function, class, and method with full type signatures.
No implementation — signatures and intent only.
All paths are repo-relative.

```python
# Example
def process(input_id: str, limit: int = 100) -> Result: ...
```

## Data Models
Pydantic models or dataclasses that this module owns or introduces.

```python
# Example
class Result(BaseModel):
    id: str
    status: str
    created_at: datetime
```

## Data Flow
How data moves through this module. Input → processing → output.

## Dependencies
- **Internal**: other modules in this repo (repo-relative paths)
- **External**: third-party libraries

## Test Scenarios
Real-world scenarios only. Format: [ID] Given / When / Then

- **T1** — Given ..., when ..., then ...
- **T2** — Given ..., when ..., then ...

## Error Cases
| Error | Trigger | Handling |
|---|---|---|

## Out of Scope
What this module does NOT do.

## Open Questions
- [ ] Unresolved decisions go here.

## Decision Log
ADRs scoped to this design (append as they are written; see `.claude/decisions/`).

- _NNNN — short title_
