# Rules — the reasoning

[CLAUDE.md](../CLAUDE.md) states each rule in one line. This file says why, and
is where a rule goes when its justification outgrows that line.

Behavioral guidelines — think first, KISS/YAGNI, surgical changes — are in
[coding-principles.md](./coding-principles.md). This file is about the code.

## Coding rules

**KISS + YAGNI.** Write the minimum code that solves the *asked* problem — no
speculative features, no abstractions for single-use code, no
"flexibility"/config nobody requested, no "might need it later" hooks. Three
similar paths is fine; extract at ~5 when the shape genuinely converges.

This applies to infrastructure as much as features. Subpackages arrive with the
phase that needs them: `Scope` in phase 7, `Layered` in phase 15, tool-execution
middleware in phase 10. A registry is a flat dict until a plugin needs to
register into one agent's world. Phase 2 cut four such things, phase 3 five, and
phase 4 deferred six more before writing a line.

**Surgical changes.** Touch only what the task requires; every changed line
should trace to the request. Don't refactor or reformat adjacent code that isn't
broken.

**Don't truncate user-facing strings.** No `[:N]` on error messages, API
responses, etc. The rendering layer handles overflow. Log lines are the only
exception.

**Typed boundaries, and fail closed.** Model *structured* data at every boundary
— never a bare/untyped `dict` or `Any`. Pydantic models for request bodies *and*
responses; validate invariants at the edge (a config that can't work is a `422`,
not a silent no-op). A genuine open key/value map (HTTP headers) is correctly
`dict[str, str]`, not a model. When input is invalid or unexpected, raise —
never guess a default that silently does the wrong thing.

**Explicit over implicit defaults.** Prefer required parameters over defaulted
ones. A *behavioral* choice (a mode, a flag, which credential, on/off) should be
passed explicitly. Reserve defaults for genuinely-absent optionals
(`x: T | None = None`) and obvious zero-values (`default_factory=list`).

**One setting, one place to look.** No `a.x or b.y` fallback chains between
settings — it makes "which value is actually in use?" unanswerable without
tracing two objects. Give each setting its own default, even if two defaults
repeat a value.

## Harness invariants

These are what the project exists to uphold. Breaking one is not a style
disagreement.

**Model-visible means logged.** Anything that reaches a model request must be
reconstructable from the session log. A new model-visible input requires a new
session event — extend the event union and render from the log. Never a second
store alongside it.

**Every `register()` returns a disposer.** No exceptions. Registering through a
`Scope` ties the entry's lifetime to it.

**Tool schemas are an allowlist.** `schemas()` emits `name`, `description`,
`input_schema` and nothing else. Adding a field to a tool definition must not be
able to leak it to the model.

**Tolerant tool failures.** An unknown tool, invalid arguments, or a refusal
return a typed `Failure` rendered as `"error: …"` — the model can recover. They
do not raise.

**A decision hook fails open.** A hook that raises refuses nothing and replaces
nothing. "Registered" must never be read as "enforcing" — say so where it
matters.

**Prompt text is code.** When wording changes because a model got it wrong,
record the observed failure in a comment next to the wording that fixes it.

**A watcher owns nothing.** A turn belongs to the run store, never to a
connection. Anything reading a run — an SSE response, a future WebSocket — only
reads, so a client hanging up has no ownership to propagate through. The moment
a reader can cancel, "close the tab and come back" stops being true.

**One cursor.** A session sequence number means the same thing to a stored
snapshot and a live stream. Don't add a second numbering for a subscriber, and
don't let the UI derive one — that is what makes a replayed conversation and a
live one the same code path.

## Comment discipline

Comment the *why*, and keep it short. A comment that restates the code is noise;
a comment that says why this and not the obvious alternative is the point. Lines
that exist because of a bug carry the bug.

**Budget: one or two lines.** Not a paragraph, not a numbered argument, not a
record of what you tried. If the reason genuinely needs more than that, the
design belongs in [DESIGN.md](../DESIGN.md) or here, with a one-line pointer
from the code. Prefer no comment to a padded one — most lines need none.

Module docstrings state what the module is for in a sentence or two, not the
history of how it got that way.

## When the plan and the principles disagree

PHASES.md was reviewed and approved. When KISS/YAGNI argues against something it
calls for, raise it before building, not after — narrowing an approved plan is a
decision to surface, not one to take quietly and report afterwards.
