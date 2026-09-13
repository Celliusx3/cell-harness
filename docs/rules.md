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

**A decision hook fails open.** A hook that raises refuses nothing and appends
nothing. "Registered" must never be read as "enforcing" — say so where it
matters. Each hook also runs under a timeout, because cell-bot's do not and a
slow one there stalls every conversation's stream.

**The guardrail is a fold, not a counter.** Phase 10's guardrail keeps no
state: every decision is computed from the current turn's `tool/call` and
`tool/result` events, the way `tools_selected()` is computed from
`tool_reference` blocks. That is why it lives at the loop rather than at the
dispatcher — the log is what it reads — and why a refusal is logged as an
ordinary `BLOCKED` result and skipped when counting: the guardrail's own output
must not feed the count that produced it. What it tells the model is its own
`application/message`, logged once per step after the step's tool calls settle
— never inside a `tool/result`. Two reasons: a provider wants the tool messages
directly behind the assistant that asked, so nothing may sit between them; and
a note inside a result with a changing count would make every result differ and
reset the very detector that wrote it. It reaches the model in the user role —
`derive_messages` sends it as a `UserMessage`, which is also where Claude Code
puts its reminders — but it is its own event type in the log, not a flag on
`user/message`: storage, the stream and the UI all discriminate on `type`, and
a second field is one a reader forgets to check. That is what keeps the note
out of the conversation's title and out of the person's bubbles.

**No step cap.** The loop had one until phase 10, as a backstop against a bug
in the loop itself. It was dropped by decision, with the consequence stated:
a decision hook fails open and the guardrail bounds only repeated *failures*,
so an endless succeeding loop — or a loop bug that never clears `owed` — is now
bounded by the user's stop button and nothing else. dsh has no cap either.

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

**Registered is not offered.** Every MCP tool is registered at startup and the
dispatcher runs whatever name it is handed, because a script's calls arrive
there with names that were never in the request. That left a
gap nobody had walked through until a 4B model did: it copied
`instagram__fetch_reels` out of a skill body, emitted it as a plain tool call,
and it ran — correct answer, wrong door. The request is supposed to be the
record of what the model may call directly; a name hallucinated from context is
not on it. So `ToolPipeline.execute` checks the model's own calls against the
same `_offered` that built the request, and refuses with the route that does
exist (`list_functions`) and *without* listing what else is registered — that
list is what the direct route would feed on. Scripts never pass through the
pipeline, so they are untouched. It is not a hook, because a hook fails open
and a door that must stay shut cannot. The cost was measured: the same model,
forced through code mode, then guessed a return shape and got the place wrong —
which is the honest result, and a skill-text fix, not a reason to reopen it.

**Selected is offered.** The door above was first shut outright, and a 4B
model, forced through code mode, guessed a return shape and got the place
wrong. The right answer was not to reopen the door but to make the refusal a
sequence: a name the model has read with `get_function_details` is promoted
into the request from the next step, and the refusal of an unread one says to
read it. The record is the log, in Anthropic's shape: a tool result is a list
of typed blocks, the reading tool's result carries `tool_reference` blocks, and
`Session.tools_selected()` folds them out of history the way `next_turn()`
folds `turn/start`, knowing nothing about which tool references. The wire this
harness speaks has no such block, so the adapter renders it as a sentence — the
expansion Anthropic's API does server-side, done here. It survives resume, and the tools
array changes once per selection rather than once per step, which is what keeps
the prompt cache an earlier tool search lost. Only the most recent eight are
carried, so the request scales with the task rather than the conversation.
`docs/mcp-tool-scaling.md` §7 has the measurements.

**No skills, no tool.** The spec's client guide says it outright: an empty
`<available_skills/>` block or a skill tool with no valid names "would confuse
the model." So the factory returns `None`, the provider yields nothing, and the
pipeline's "skip an absent default name" does the rest. The alternative — a
tool that is always there and sometimes says "nothing to load" — spends a schema
on every request to describe an absence.

**A skill's body is context, not data.** A script that called `skill(...)`
would get the instructions as a string and could only `return` them into the
conversation — the same result by a slower route, with `list_functions` having
advertised a "capability" that is not one. So the composition root names it
`withheld` and code mode keeps it out of the catalog, out of the sandbox
globals, and refused at the bridge. Code mode does not know what a skill is; it
knows a name it was told not to bind.

**The catalog is read, never published.** Every shipping client rebuilds the
skill list per request in the system prompt or the tool description; only
DeepSeek Harness writes it into the conversation as a message, and pays with a
digest, an "empty envelope" event, an inbox to slip replacements in, and a
re-injection after compaction. The tool list here was already rebuilt per step
and never logged; the skill catalog is the same kind of thing. A `SKILL.md`
edit is seen at the next step because the next step looks.

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
