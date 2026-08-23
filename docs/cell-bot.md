# cell-bot — teardown and feature inventory

Source: `/Users/coyan.oh/Desktop/cellstudio/cell-bot`. Local-only git repo (no
remote configured — nothing to pull). HEAD `746d60e`, working tree clean except
three untracked strategy docs (`CLIPPING.md`, `PLAN.md`, `STRATEGY.md`).

## 0. Scale check

| Measure | Value |
|---|---|
| Backend | ~6,900 lines Python across 60 modules (`backend/app`) |
| Frontend | Next.js app (`frontend/`) — chat + settings |
| Tests | 27 unit + 16 integration suites |
| Satellite MCP servers | 5 (`ytdlp`, `whisper`, `pptx`, `tradingagents`, `charts`) |
| Largest file | `conversations/runs.py`, 385 lines |

cell-bot is what dsh is *not*: small, single-purpose, readable end to end in an
afternoon. It is a working proof that the interesting parts of a harness fit in
7k lines. Its own lineage is a TypeScript project called cell-studio — the
docstrings say "ported in shape from cell-studio's `runAgenticLoop`" repeatedly,
which is itself a useful signal about what survived the port.

## 1. Module map

```
backend/app/
  agents/       base.py events.py guardrail.py hooks.py models.py
                repository.py routes.py schemas.py service.py session.py
    kinds/      loop.py router.py
  llm/          client.py events.py lifecycle.py messages.py structured.py text.py
    openai/     adapter.py client.py observers.py
  tools/        base.py progress.py
    native/     clock.py
  mcp/          auth.py config.py errors.py manager.py models.py
                repository.py routes.py schemas.py service.py tool.py
  conversations/ chat_routes.py models.py repository.py routes.py
                 run_repository.py runs.py schemas.py service.py sessions.py
  skills/       models.py repository.py routes.py schemas.py service.py tool.py
  prompts/      service.py + templates/
  control/      server.py tools.py
  credentials/  models.py repository.py routes.py schemas.py
  web/          server.py sse.py
  db/           base.py engine.py registry.py
  config/       settings.py
  crypto.py
```

## 2. The features worth taking

### 2.1 A two-layer agent contract that stays shallow

`agents/base.py` declares exactly three things: `name`, `model`, `run()`.

> Deliberately shallow. It declares only what both genuinely have […] so neither
> inherits fields it can't use.

Two kinds implement it:

- **`LoopAgent`** (`kinds/loop.py`) — gather-context → act → repeat.
- **`RouterAgent`** (`kinds/router.py`) — one structured call, picks who answers.

Both stream events and end with a terminal one, so a caller consumes either
without knowing which it holds. `AgentEvent` is a **`Protocol`, not a union** —
an agent declares its own event types and satisfies it structurally, so adding an
agent kind never means editing the events module.

### 2.2 Engine / state-holder split

`LoopAgent` is the engine and owns no state; `AgentSession` (`agents/session.py`)
owns `history`, `status`, `turn_index`, and the hook bus, and passes them in.

> Resume is just replaying that history into another `run()`.

The system prompt is deliberately **not** part of `history` — it is prepended per
model call in `_request_messages()`, never appended, never persisted. That is
what lets it reflect the agent running *this* turn, including a different agent
after routing.

### 2.3 Routing as a per-turn structured call, not handoff tools

`kinds/router.py` is the sharpest design in the repo:

> One cheap structured LLM call per turn, deliberately *not* a `transfer_to_*`
> handoff tool. Handoff tools grow the tool list with every agent added, and a
> specialist that never volunteers to hand back strands the conversation;
> deciding afresh each turn has neither problem.

And it is **advisory, never authoritative**:

> An unparseable reply, low confidence, an unknown agent, a timeout, or any
> provider error all leave the conversation on the agent it was already using.
> […] So `run()` has no failure terminal: it always yields exactly one
> `AgentSelected`.

Two implementation details that generalize:

- The choice model is built **per call** with `Literal[uuids]`, so the roster's
  ids become a schema enum — an invented agent is rejected by validation, not by
  a runtime lookup.
- Field descriptions are written *for the model*: `_AGENT_FIELD` says "the UUID
  … Not the agent's name — a name is not a UUID", with a code comment recording
  the observed failure that prompted the wording. Prompt text treated as code,
  with a regression trail.

### 2.4 Typed hooks with typed decisions

`agents/hooks.py`. Five lifecycle points; three are pure observers, two are
*decisions* and their return type says so:

| Hook | Return | Meaning |
|---|---|---|
| `on_run_start` / `on_run_end` / `post_tool_call` | `None` | observer |
| `pre_tool_call` | `str \| None` | a reason to **refuse**, or None to run |
| `transform_tool_result` | `str \| None` | a **replacement** result, or None to keep |

> Because those are typed returns rather than free-form payloads, there is
> nothing to validate — a hook physically cannot hand back a malformed directive,
> and an observer physically cannot veto a call.

`HookChain` composes many into one; first non-None wins (ordering *is*
precedence); an exception is logged and contributes nothing, so a **decision hook
fails open**. The docstring is explicit that "registered" must not be read as
"enforcing", and that hooks run inline, serially, awaited, with no timeout.

### 2.5 The loop guardrail as a hook, not a loop feature

`agents/guardrail.py` — three detectors:

| Detector | Keys on | warn | block |
|---|---|---|---|
| `exact_failure` | same tool + same args, and the call *failed* | 2 | 5 |
| `same_tool_failure` | same tool failing, any args | 3 | 8 |
| `idempotent_no_progress` | same tool + args + result, read-only tool | 2 | 5 |

What is *not* detected: a repeated call that **succeeds**. `warn` never blocks —
guidance is appended to the result the model sees. `block` is pre-execution. A
success wipes that signature's failure counters. `before_call` only reads state;
only `after_call` mutates, so a blocked call never moves a counter.

Crucially it is registered on the hook bus by the composition root, so the loop
does not know it exists and it can be swapped or removed without touching the
engine.

### 2.6 Runs that outlive the connection

`conversations/runs.py` — the single most product-relevant piece.

> A turn can be a four-minute download, so it must not be tied to whoever happens
> to be watching it. `start` spawns a task this store holds, the task drives the
> agent to completion regardless of who is listening, and a client *subscribes*
> to the event buffer rather than driving it. A disconnect drops a subscription;
> `cancel` is the only thing that ends a run.

Mechanics:

- Event buffer is an **append-only list; the index is the subscriber's cursor**,
  so a cursor stays valid for the life of the run.
- A single `asyncio.Condition` guards `events` and `status` **together** — read
  separately, a subscriber could park forever on a run that finished between the
  two reads.
- `FINISHED_RUN_TTL_SECONDS = 300` keeps a finished run subscribable so a client
  reconnecting just after completion drains the tail instead of falling back to
  history.
- `HEARTBEAT_INTERVAL_SECONDS = 20` on a **timer, not at checkpoints** — "a turn
  spends its time *inside* tools: a four-minute download checkpoints twice, so
  tying liveness to progress lets the lease lapse mid-download."
- `RECLAIM_INTERVAL_SECONDS = 30` reclaims abandoned runs periodically, not only
  at startup, because a run whose process died moments before a restart still
  holds a valid lease then.
- `_unanswered_calls()` is the invariant guard: an assistant message with
  `tool_calls` and no matching `ToolMessage` is a history the provider will
  reject on the next turn. Both the checkpoint gate and the closeout ask it, and
  `INTERRUPTED_RESULT = "error: interrupted"` fills the gap.
- `RunConflictError`: a second run over one history is **refused, not queued** —
  "telling them 'still working' is honest where silently ordering their turns is
  not."

And the matching SSE rule (`web/sse.py`) — the deliberate exception to the
repo's own `aclosing` discipline:

> Closing `events` would propagate a client disconnect down into whatever is
> producing them — which for a run would mean a closed browser tab cancelling a
> four-minute download, the exact failure runs exist to prevent. A run ends on
> `DELETE`, never on a hang-up.

### 2.7 Tools: one shape, live resolution

`tools/base.py`.

- `ToolLike` is a `Protocol` (`name`, `spec()`, `invoke(args, progress=)`) — the
  loop depends on a shape, not a class.
- `Tool.from_model` derives **schema and parse from one Pydantic model**, so what
  the model is told and what the executor accepts cannot drift. You build a
  `Tool` directly only when the schema comes from somewhere you don't control (an
  MCP server publishes its own — "validating against our copy of it would let us
  silently drop arguments that server actually accepts").
- `Toolbox` holds static tools *plus* `providers` (callables re-queried every
  turn), so a server connected mid-conversation is usable on the next turn
  without rebuilding the agent.
- Failures are **tolerant strings**, not exceptions: unknown tool, invalid args,
  and refusals all return `"error: …"` so the model can recover. `ERROR_PREFIX`
  is a shared constant the guardrail's failure detectors key on.

Per-agent tool selection is three modes, not "empty means all":

```
TOOL_MODE_ALL       every tool, including ones that connect later
TOOL_MODE_SELECTED  only those named — a snapshot
TOOL_MODE_EXCEPT    everything but those named
```

> These are two separate questions: *which tools now* (the patterns) and *what
> about tools that appear later* (the mode). Collapsing them loses the ability to
> say "this agent gets no tools" — indistinguishable from "not configured".

An unknown mode allows **nothing** (fail closed). `{server}__*` wildcards mirror
the MCP namespacing. `narrow()` wraps the provider rather than materializing a
list, so filtering doesn't freeze an agent's MCP tools at composition time.

### 2.8 Progress fan-in inside a single tool call

`LoopAgent._tool_events` is a small masterclass. A generator can only yield from
its own frame, so a progress callback firing inside `_tool_result` has no way to
put an event on the stream. Solution: the call runs as a **task**, the frame
drains an `asyncio.Queue`, and a `None` sentinel the task *always* posts in its
`finally` ends the drain.

- `asyncio.Queue` rather than anyio: "anyio cancel scopes are bound to the task
  that entered them, and an async generator's frame can be finalized by a
  *different* task than the one running it."
- Unbounded on purpose — a bounded queue would make `report` block, stalling the
  tool on a consumer that isn't reading.
- Ordering is by construction: FIFO + every report awaited *inside*
  `_tool_result` + sentinel enqueued only after it returns.
- `aclosing()`, not a bare `async for`: GeneratorExit unwinds this frame but
  would leave the inner one to the GC's asyncgen hook, with the tool task still
  running.

### 2.9 Skills as progressive disclosure

`skills/tool.py`, following the [agentskills.io](https://agentskills.io/specification)
format. Two levels:

- **discovery** — `render_available_skills()` builds an `<available_skills>`
  index appended to the system prompt (name + one-line description only).
- **activation** — one `skill` tool whose *result is the body*.

> only the name + description sit in context, and the body — which can be long —
> costs nothing until the model asks for it.

The args model is **generated**, not declared: `Literal[names]` from the current
catalog gives the schema its enum and rejects an invented name in one move.
Skills are scoped per-agent (`agent_skills` link table), so the index stays small
however large the catalog grows — and index and tool are built from the same
subset so they cannot disagree.

### 2.10 MCP manager with a command loop

`mcp/manager.py`. The MCP SDK's transports and `ClientSession` are anyio context
managers bound to the task that entered them, and a task group can only spawn
from its host task — so a connection cannot be opened in one request task and
closed in another. The fix:

> a single long-lived `_serve` task hosts the connection task group; each
> connection runs in its own child task that opens the session, reports ready,
> then waits for a shutdown signal and closes it — all in one task.
> `connect`/`disconnect` submit a command over a memory stream and await a reply.

`COMMAND_TIMEOUT_SECONDS = 60` bounds the whole round trip (dial, initialize,
list_tools) so a wedged loop surfaces as a failed request, not a hang.

### 2.11 Prompts as data files

`prompts/service.py` — Jinja templates inside the package, addressed by a
`Prompt` `StrEnum` so a typo fails at import rather than at the call site. Two
settings carried over deliberately:

- `undefined=StrictUndefined` — a missing variable raises instead of rendering
  empty. "A silently half-built prompt is the worst failure mode here, because
  the model will cheerfully answer anyway."
- `autoescape=False` — these are prompts, not HTML; escaping mangles the angle
  brackets the templates deliberately emit.

A test asserts template directory and enum match **in both directions**.

### 2.12 Control plane: one implementation, two surfaces

`control/tools.py` defines six operations as arg model + executor. The executors
are the single source of truth: `control/server.py` re-exposes them over MCP for
external clients, and `control_tools()` wraps them as native `Tool`s for
cell-bot's own agent. Neither adapter contains logic. Validation lives in the
Pydantic `model_validator` in `mcp/schemas.py`, so a fail-closed auth check
guards **both surfaces at once**.

### 2.13 Satellite MCP servers as capability packaging

Rather than growing the backend, capabilities ship as separate `uv` projects,
each with its own README, tests, and Makefile targets:

| Server | Capability |
|---|---|
| `ytdlp-mcp` | YouTube video/audio download (ffmpeg) |
| `whisper-mcp` | Local transcription (whisper.cpp + ggml), media-root boundary |
| `pptx-mcp` | Editable .pptx generation, drives a `ppt-master` skill |
| `tradingagents-mcp` | Multi-agent stock analysis (a second model does the reasoning) |
| `charts-mcp` | Charting |

## 3. The house rules (`CLAUDE.md` + `docs/coding-principles.md`)

These are as much a deliverable as the code, and they show up in every module:

- **KISS + YAGNI.** "Three similar paths is fine; extract at ~5 when the shape
  genuinely converges."
- **Surgical changes.** Every changed line traces to the request.
- **Don't truncate user-facing strings.** No `.slice(0, N)` on errors or API
  responses; the rendering layer handles overflow. Logs are the only exception.
- **Typed boundaries, fail closed.** No bare `dict`/`any` at a boundary. Pydantic
  models for request *and* response bodies. "A config that can't work is a `422`,
  not a silent no-op."
- **Explicit over implicit defaults.** A *behavioral* choice (a mode, a flag,
  which credential) is passed explicitly, never defaulted. Defaults are reserved
  for genuinely-absent optionals and obvious zero-values.
- **One setting, one place to look.** No `a.x or b.y` fallback chains —
  `settings.router.model or settings.llm.default_model` makes "which model is
  actually in use?" unanswerable without tracing two objects.

The comment density is the other half of the method: nearly every non-obvious
line carries the *reason*, and several carry the observed bug that produced it.
That is what makes a 7k-line codebase legible enough to extend confidently.

## 4. What cell-bot does not have

Honest gaps, relevant to the synthesis:

- **No event log.** History is a `list[LlmMessage]`; run events are an in-memory
  buffer explicitly not durable. Replay fidelity, forking, and post-hoc analysis
  are all out of reach.
- **No compaction.** Long conversations will hit the context window.
- **No sandbox / approval / permission model.** Tools run with process authority.
- **No filesystem or shell tools** in-tree — capabilities arrive only via MCP.
- **No subagents.** One agent per turn, routed.
- **No plugin/config composition.** Wiring is Python in a composition root.
- **`AgentSession` is in-memory**; durable resume is noted as a later phase.
- **Hooks have no timeout** — a slow hook stalls the event loop for every
  conversation.
