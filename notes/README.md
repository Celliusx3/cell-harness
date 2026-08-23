# Design notes

Durable records of decisions, referenced **by path from the code comment that
embodies them**. Adopted from DeepSeek Harness' `.agents/notes/`, which is what
keeps a 256k-line codebase's rationale findable.

A note is not documentation. Docs say what the system does; a note says why this
and not the obvious alternative, written once, at the moment the choice was live.

## When to write one

- A decision whose rationale won't survive as a comment (too long, or spans files)
- A contract several packages depend on (parallel dispatch, cancellation ordering)
- A bug whose fix looks arbitrary without the failure it fixes
- A deliberate limitation someone will otherwise "fix"

Not for: anything a comment covers, anything the phase doc already states.

## Naming

```
notes/<category>/YYYY-MM-DD-<kebab-slug>.md
```

Categories: `architecture`, `feature`, `bug-fix`, `simplification`, `process`.

## Referencing

From code, by path — that is the whole point:

```python
# Opted-in executions must not mutate parent-owned state; shared state must
# tolerate concurrent dispatch. Full contract:
# notes/architecture/2026-08-22-parallel-tool-dispatch.md
concurrency_safe: bool = False
```

## Template

```markdown
# <Title>

**Date:** YYYY-MM-DD · **Phase:** <n> · **Status:** implemented | superseded by <path>

## Problem
What forced a decision. If a bug, the observed failure.

## Decision
What we did, in one paragraph.

## Alternatives rejected
Each with the reason it lost. This is the section future readers actually need.

## Consequences
What this makes easy, what it makes hard, and what it forecloses.
```
