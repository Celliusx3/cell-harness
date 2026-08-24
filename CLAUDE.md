# CLAUDE.md — Project Rules

Loaded automatically into every session in this directory. Keep it thin —
long-form rules and rationale live in [docs/](./docs/).

## Project

cell-harness — an agent harness in Python, built as a **chat product**
(cell-bot shaped: browser UI, conversations, agent catalog, capabilities via
MCP — not a terminal coding harness). Synthesized from two studied sources:
[DeepSeek Harness](./docs/deepseek-harness.md) for the architecture and
[cell-bot](./docs/cell-bot.md) for the taste. Target ~10k lines.

Read before writing code: [DESIGN.md](./DESIGN.md) for the contracts,
[PHASES.md](./PHASES.md) for what phase we are in and what it must satisfy.

**Status: phase 3 — "it remembers" — implemented, awaiting review.** Next is
phase 4, "you can chat with it".

```sh
cp backend/config.local.example.json backend/config.local.json   # add your API key
# everything else — model, endpoint, sessions root — is in backend/config.json (committed)
make install && make test
cd backend && uv run harness run "what time is it in Tokyo?"
cd backend && uv run harness list
```

## Layout

```
backend/harness/
  llm/          the model seam — messages, stream vocabulary, adapters/
  session/      the event log, its header, persistence, repair, the store
  agent/        the turn loop and its events
  tools/        definition, registry, pipeline, progress, native/
  config/       one Settings: config.json + config.local.json + env
  cli.py        `harness run "<prompt>"` — a driver, not an interface
backend/tests/  unit/ and integration/
docs/           source teardowns + long-form rules
notes/          design notes, referenced by path from code comments
```

Subpackages arrive with the phase that needs them — and so does infrastructure.
`Scope` in phase 4, `Layered` in phase 13, tool-execution middleware in phase 8.
A registry is a flat dict until a plugin needs to register into one agent's
world. Building any of them earlier is the speculative structure the KISS/YAGNI
rule below forbids — phase 2 did it four times and had to cut them back out.

**No HTTP before phase 4.** A quick endpoint in phases 1–3 would stream on the
request connection, which is exactly the design phase 4 exists to undo.

The full intended layout is in [DESIGN.md §3](./DESIGN.md); paths in PHASES.md
are relative to `backend/harness/`.

## One-rule reminders worth repeating

- **KISS + YAGNI.** Write the minimum code that solves the *asked* problem — no
  speculative features, no abstractions for single-use code, no
  "flexibility"/config nobody requested, no "might need it later" hooks. Three
  similar paths is fine; extract at ~5 when the shape genuinely converges. See
  [docs/coding-principles.md](./docs/coding-principles.md).
- **Surgical changes.** Touch only what the task requires; every changed line
  should trace to the request. Don't refactor or reformat adjacent code that
  isn't broken.
- **Don't truncate user-facing strings.** No `[:N]` on error messages, API
  responses, etc. The rendering layer handles overflow. Log lines are the only
  exception.
- **Typed boundaries, and fail closed.** Model *structured* data at every
  boundary — never a bare/untyped `dict` or `Any`. Pydantic models for request
  bodies *and* responses; validate invariants at the edge (a config that can't
  work is a `422`, not a silent no-op). A genuine open key/value map (HTTP
  headers) is correctly `dict[str, str]`, not a model. When input is invalid or
  unexpected, raise — never guess a default that silently does the wrong thing.
- **Explicit over implicit defaults.** Prefer required parameters over defaulted
  ones. A *behavioral* choice (a mode, a flag, which credential, on/off) should
  be passed explicitly. Reserve defaults for genuinely-absent optionals
  (`x: T | None = None`) and obvious zero-values (`default_factory=list`).
- **One setting, one place to look.** No `a.x or b.y` fallback chains between
  settings — it makes "which value is actually in use?" unanswerable without
  tracing two objects. Give each setting its own default, even if two defaults
  repeat a value.

## Harness-specific rules

These are the invariants this project exists to uphold. Breaking one is not a
style disagreement.

- **Model-visible means logged.** Anything that reaches a model request must be
  reconstructable from the session log. A new model-visible input requires a new
  session event — extend the event union and render from the log. Never a second
  store alongside it.
- **Every `register()` returns a disposer.** No exceptions. Registering through a
  `Scope` ties the entry's lifetime to it.
- **Tool schemas are an allowlist.** `schemas()` emits `name`, `description`,
  `input_schema` and nothing else. Adding a field to a tool definition must not
  be able to leak it to the model.
- **Tolerant tool failures.** An unknown tool, invalid arguments, or a refusal
  return a typed `Failure` rendered as `"error: …"` — the model can recover. They
  do not raise.
- **A decision hook fails open.** A hook that raises refuses nothing and replaces
  nothing. "Registered" must never be read as "enforcing" — say so where it matters.
- **Prompt text is code.** When wording changes because a model got it wrong,
  record the observed failure in a comment next to the wording that fixes it.

## When the plan and the principles disagree

PHASES.md was reviewed and approved. When KISS/YAGNI argues against something it
calls for, **raise it before building, not after** — narrowing an approved plan
is a decision to surface, not one to take quietly and report afterwards.

## Comment discipline

This is half the method, not decoration. cell-bot is legible at 7k lines because
non-obvious lines carry their *reason*, and lines that exist because of a bug
carry the bug. Match that density. A comment that restates the code is noise; a
comment that says why this and not the obvious alternative is the point.

## Before marking work complete

- `make lint` and `make test` are green (coverage gate is 80%).
- The phase's acceptance criteria in [PHASES.md](./PHASES.md) are met, as tests.
- Anything non-obvious you decided is either a comment or a note in `notes/`.
- **Every new definition has a caller outside `tests/`.** `grep -rn '\bname\b'
  harness/` — if the only hits are the definition and test files, it belongs in
  `tests/` or does not exist yet. A docstring describing a *future* caller is the
  tell, not the justification.

## Docs index

| File | What's in it |
|------|--------------|
| [DESIGN.md](./DESIGN.md) | The proposal: what we take from each source, module layout, core contracts, open decisions |
| [PHASES.md](./PHASES.md) | 13 phases, each a demoable capability — deliverables, contracts, acceptance criteria |
| [docs/coding-principles.md](./docs/coding-principles.md) | Behavioral guidelines (Karpathy): think first, KISS/YAGNI, surgical changes, goal-driven |
| [docs/deepseek-harness.md](./docs/deepseek-harness.md) | Teardown of DeepSeek Harness and three replication tiers |
| [docs/cell-bot.md](./docs/cell-bot.md) | Teardown of cell-bot, its feature inventory, and its gaps |
| [docs/without-cordis.md](./docs/without-cordis.md) | Scope / Layered / Events in ~250 lines, and what we give up — built when first needed, not now |
| [notes/](./notes/) | Design notes, referenced by path from code comments |
