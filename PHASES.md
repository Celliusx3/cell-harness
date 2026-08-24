# cell-harness — phased build plan

The execution companion to [DESIGN.md](./DESIGN.md).

**cell-harness is a chat product** — cell-bot shaped: a browser UI, conversations,
an agent catalog, capabilities arriving through MCP. Not a terminal coding
harness. That decision drives the ordering below; see §"Why this order".

**Every phase is a capability you can demo.** Infrastructure is never its own
phase — it arrives inside the first phase that needs it, sized for that one
consumer. If a phase ends with nothing you can run, the phase is wrong.

Sizes are rough line estimates (implementation + tests) for ordering and risk,
not scheduling. Paths are relative to `backend/harness/` unless noted.

---

## The arc

| # | Phase | Demo at the end | ~Lines |
|---|---|---|---|
| 1 | **It answers** | `harness run "explain X"` streams a reply | 900 |
| 2 | **It uses tools** | Calls a tool, uses the result, answers | 800 |
| 3 | **It remembers** | Conversations persist; resume one after a restart | 600 |
| 4 | **You can chat with it** ⭐ | Browser UI. Send, stream, stop. Refresh mid-turn and keep watching | 2000 |
| 5 | **It uses your tools** | Add an MCP server in settings; its tools work next turn | 900 |
| 6 | **It follows instructions** | Attach a skill; it loads and applies it | 1000 |
| 7 | **You can steer it** | Correct it mid-turn without restarting | 450 |
| 8 | **It doesn't get stuck** | A runaway tool loop is stopped | 450 |
| 9 | **It picks the right specialist** | Multiple agents; the right one answers each turn | 700 |
| 10 | **It handles long conversations** | 200 turns without hitting the context window | 450 |
| 11 | **It reads and writes files** *(opt)* | File tools without going through MCP | 800 |
| 12 | **It runs commands** *(opt)* | `bash`, confined | 800 |
| 13 | **It delegates** *(opt)* | Subagents working in parallel | 800 |

**Phases 1–4 are the product.** 5–8 make it capable and safe. 9–10 make it
better than cell-bot. 11–13 are agentic capabilities to add only if the product
turns out to want them.

### Why this order

A chat product's constraints differ from a coding harness's:

| | Chat product (us) | Coding harness |
|---|---|---|
| The UI is | the product — pull it to phase 4 | optional |
| Capabilities arrive via | **MCP** (phase 5) | built-in fs/shell tools |
| A turn is | often long (a download, a deck) — runs must outlive connections | usually short |
| Multiple agents means | **routing** to a specialist (phase 9) | delegating to subagents |
| `bash`/fs tools are | optional, late | phase 2 material |

This is why phases 11–13 are marked optional. cell-bot ships a real product with
none of them — every capability arrives through an MCP server.

### Where the infrastructure lands

Nothing below is a phase. Each is written as part of the capability that needs it.

| Mechanism | Born in | Why then |
|---|---|---|
| Session event log | 1 | The loop derives history from it — retrofitting means rewriting the loop |
| Persistence + the model-visible invariant | 3 | Resume is what makes the invariant testable |
| Runs and cursors | 4 | A turn must outlive the tab that started it |
| `Scope` (reversible teardown) | ~~4~~ **5** | Phase 4 registers nothing; stopping a run is `task.cancel()`. An MCP connection is the first real connect/disconnect lifecycle |
| Tool result `meta` (UI cards) | ~~4~~ **5** | A UI exists now and still has nothing to put there — the only tool is a clock. The first MCP tool returning an image is the caller |
| Heartbeat, lease, reclaim | ~~4~~ **when a 2nd process exists** | Reclaiming a *process's* runs is a multi-process problem. One server, and phase 3's repair-on-resume already covers the single-process crash |
| `Session.after(cursor)` | ~~4~~ **never** | `session.events()[n:]` already is it. Proposed and cut twice |
| Prompt sections | 6 | Skills are the first thing that contributes to the prompt |
| **Around-middleware on tool execution** | 8 | The timeout and guardrail are its first listeners |
| `ToolDefinition.timeout_s` | 8 | Nothing enforces a deadline until the timeout policy exists |
| Typed hooks | 8 | The guardrail is its first real consumer |
| Seams (`FileSystem`, `Subprocess`) | 11 | Two providers is when an interface earns its keep |
| `Layered` (scoped registries) | 13 | The first time a plugin registers into *one agent's* world |
| `user/message` `source` field | when injected context exists (6 or 7) | Only `human` produces one until then |

**Phase 2 built four of these early and they were cut.** An event bus with no
listener, a `timeout_s` nothing enforced, a `meta` nothing rendered, and a cursor
nothing subscribed to. Each was justified by a docstring describing a *future*
caller — which is the tell. The check is `grep`: a definition whose only callers
are in `tests/` either belongs in `tests/` or does not exist yet.

On `Layered`: per-agent **tool selection** (phase 9) does not need layered
registries. cell-bot does it by filtering the provider at compose time
(`narrow(mode, patterns, provider)`), which is simpler and correct. `Layered` is
only needed when a plugin registers into one agent's world — which is subagents.

**Dependency graph:**

```
1 ── 2 ── 3 ── 4 ─┬─ 5 ─┬─ 6 ── 9
                  ├─ 7  │
                  ├─ 8 ─┘
                  └─ 10
                  
                  11 ── 12 ── 13     (optional track, needs 4)
```

---

# Phase 1 — It answers

**Demo.** `harness run "explain async generators"` streams a reply to stdout.

**Ships.**
- `llm/messages.py` — `Message`, `ContentBlock`, `ToolCall`, `ToolSpec`
- `llm/stream.py` — `StreamChunk` union with terminal events
- `llm/client.py` — `LLMClient` Protocol
- `llm/adapters/openai.py` — first adapter
- `session/events.py` — five event types: `turn/start`, `turn/end`, `user/message`,
  `assistant/chunk`, `assistant/message`
- `session/log.py` — append-only, contiguous sequence numbers, JSON validation
- `session/derive.py` — `derive_messages(log) -> list[Message]`
- `agent/loop.py` — the turn driver, no tools yet
- `cli.py` — `harness run "<prompt>"`

**The CLI is a driver, not an interface.** No config, no session management, no
argument parsing beyond a prompt — those are phases 3 and 4. If `cli.py` passes
~60 lines it is absorbing something that belongs elsewhere. **Non-goal: no HTTP
in this phase.** The browser arrives at phase 4 with the run store, because a
naive "stream on the request connection" API is exactly what phase 4 exists to
undo.

**Why the log is here and not later.** The loop's history comes from
`derive_messages(log)`. Write the loop against a `list[Message]` and you rewrite
the loop when the log arrives — plus the session store, persistence, and every
test that built a history by hand. Five event types at this point, not the full
vocabulary.

**Key contracts.**
- An adapter MUST yield exactly one terminal event (`Completed` | `Failed`).
- Append-only, contiguous sequence numbers, lossless JSON. `append()` validates
  serializability **at the source**.
- `derive_messages()` is the *only* way model history is produced. No second store.
- The system prompt is **never** in the log — prepended per request, so it can
  reflect the agent running *this* turn.

**Acceptance.**
- `harness run "hi"` prints a streamed reply.
- A stream that dies mid-flight yields `Failed`, never hangs.
- Chunks replayed from the log reassemble to the same `assistant/message`.
- A cancelled turn finalizes its text prefix with `interrupted: true`.

---

# Phase 2 — It uses tools

**Demo.** `harness run "what time is it in Tokyo?"` calls a clock tool and uses
the result.

**Depends on.** 1.

**Ships.**
- `tools/definition.py` — `ToolDefinition`, `from_model()`, `ToolOutcome`
- `tools/registry.py` — flat dict + live providers
- `tools/pipeline.py` — resolve the named tool and run it
- `tools/progress.py` — the queue fan-in pattern
- `tools/native/clock.py`
- `session/events.py` — add `step/start`, `step/end`, `tool/call`, `tool/result`

**Not here, though an earlier draft said so.** The interception chain (phase 8,
when the timeout and guardrail need it), a per-agent tool filter (phase 5's MCP
wildcards or phase 9's selection), and `todo_write` (phase 4, when a UI renders a
checklist). Each would have been a mechanism with no user.

**Why live providers now.** Phase 5's MCP servers connect mid-conversation. A
registry that resolves its providers on every turn makes that free; one that
materializes a list at compose time freezes each agent's tools forever.

**Key contracts.**
- `schemas()` emits `name`, `description`, `input_schema` **by allowlist**.
- `from_model()` derives schema *and* parse from one Pydantic model. Construct
  directly only when the schema comes from elsewhere (MCP).
- `ToolOutcome` is typed: `Ok(content, meta) | Failure(code, message)`, rendered
  as `"error: …"` so the model recovers. Never raises.
- Serial dispatch. `concurrency_safe` arrives in phase 11 when reads can overlap.
- A provider that raises is logged and contributes nothing — one broken source
  must not cost the model every other tool.

**Acceptance.**
- A `timeout_s` or `execute` field never appears in `schemas()` output.
- Unknown tool and invalid args both return a `Failure`, not an exception.
- Progress reported mid-call interleaves correctly; the sentinel always fires.
- A tool added by a provider between turns is callable on the next turn.
- End to end: prompt → model → tool call → result → model → answer.

---

# Phase 3 — It remembers

**Demo.** `harness list` shows past conversations; `harness resume <id>` continues
one after a restart — including one killed mid-tool.

**Depends on.** 2.

Modelled on dsh's [session-persistence seam](../deepseek-harness/docs/subsystems/persistence.md),
scaled down. Their design decisions we adopt are marked **[dsh]**.

**Ships.**
- `session/persist.py` — `Persistence` Protocol + JSONL backend
- `session/header.py` — `SessionHeader`, the metadata that is not an event
- `session/repair.py` — crash recovery: close what a dead process left open
- `session/store.py` — `create` / `load` / `list` / `resume`
- `session/invariant.py` — `assert_derivable(request, log)`
- `cli.py` — `list`, `resume`

## Storage layout

```
<root>/<session-id>.jsonl
   line 1   {"type":"session","version":1,"id":...,"created_at":...,"title":...}
   line 2+  one SessionEvent per line, seq == line number - 1
```

**JSONL, not SQLite** — reversing DESIGN.md's earlier default. dsh ships JSONL and
keeps SQLite opt-in, and the reason my SQLite argument was wrong is that listing
never needs the log: the header is line 1, so `list()` reads one line per file.
Search across message *content* is the real SQLite case, and that is not phase 3.

Flat files rather than dsh's `<project>/<id>/` directories: their nesting exists
for per-project navigation and session-owned artifacts, and we have neither yet.

No zstd and no chunk packing. Both are dsh optimizations (~60% smaller logs);
neither changes the contract, and `load` in either system is layout-blind.

## `SessionHeader` — metadata is not an event **[dsh]**

> Per-session metadata travels **separately** from the event log: format version,
> cwd, lineage, and the seed boundary are storage concerns, not conversation
> events, so they stay out of `SessionEventMap` and never reach `deriveMessages()`.

So: `version`, `id`, `created_at`, `title`. Never a `conversation/renamed` event —
that would put storage concerns into the model's history.

**Title** is stamped at first append, when the first user message is known. This
falls out of lazy materialization below and costs nothing. Renaming is phase 4's
problem, and the answer is probably a sidecar, not a log rewrite.

## Key contracts

- **Lazy materialization [dsh].** `create()` writes nothing. The first `append`
  writes header + first batch. A created-but-never-appended session leaves no file
  and is absent from `list`.
- **Append-only, fsync per batch [dsh].** Flushed events are never rewritten. A
  failed write rolls the file back to its prior byte length.
- **Contiguous seq [dsh].** `append` rejects a batch whose first `seq` does not
  continue the stored log. Cheap, and it catches a whole class of loop bug.
- **Format version, no migration [dsh].** An unknown `version` refuses loudly and
  names the file. Migration is a real feature; pretending by best-effort parsing
  is how a log becomes unreadable quietly.
- **Torn tail vs corruption [dsh].** A structurally incomplete *last* line is
  dropped. A defect at or before the last committed `turn/end` is corruption and
  **rejects** — silently skipping it would hand the model a history with a hole.
- **Checkpoint before each model request.** Durability where it matters: never
  send a prompt that is not yet durable. `assert_derivable` runs at the same
  boundary, which is what finally gives "model-visible means logged" teeth.

## Crash repair — close, do not truncate **[dsh]**

Our loop's `finally` handles graceful abandonment. `kill -9` never runs it, so a
log can end with an open `turn/start` and dispatched calls with no results.

> It does **not** truncate — a single turn can be huge in a long-horizon task…
> Instead it closes the orphaned turn with a synthetic `turn/end { reason:
> interrupted }`… `interrupted` is the one `TurnEndReason` no loop emits.

Adopt that exactly, including the marker no loop can produce, so "this was
repaired" stays unambiguous forever. Add `interrupted` to `TurnEndReason` and
never emit it from `agent/loop.py`.

**Two repair outcomes, not one [dsh]** — and this is better than our blunt
`error: interrupted`:

| On disk | Synthetic result | Why it differs |
|---|---|---|
| assistant asked, no `tool/call` logged | `TOOL_NOT_STARTED` | the tool provably never ran; safe to retry |
| `tool/call` logged, no `tool/result` | `TOOL_OUTCOME_UNKNOWN` | it may have completed a side effect |

dsh's wording for the second tells the model to *"retry only read-only or
idempotent work and to verify possible side effects or ask the user."* That is a
real safety difference once phase 12 has `bash`.

## Acceptance

- Append 1,000 events, reload, get identical events back.
- `kill -9` mid-tool, resume, and the loaded log is balanced: every dispatched
  call has a result, every turn is closed.
- A repaired turn ends with `interrupted`, which no loop emits.
- A call that was logged but unfinished repairs to `TOOL_OUTCOME_UNKNOWN`; one
  never logged repairs to `TOOL_NOT_STARTED`.
- A half-written last line is dropped; a corrupted line before the last
  `turn/end` rejects.
- An unknown format version refuses and names the file.
- `append` rejects a batch that does not continue the stored seq.
- `list()` reads only line 1 per file — proven by a test that corrupts line 2 and
  still lists.
- The invariant fires when a test injects an unlogged message.

## Deliberately skipped from dsh

Their seam has 11 methods; we need 4. Skipped: `inspect` (non-committing view),
`prepare` (reservation + LRU), `readFrom` (suffix reads), `listSnapshots`
(revision identity), `locate`, `readRaw`, packed chunk rows, zstd frames, the
prepared-session cache, and write batching. Each solves a problem at their scale —
concurrent resume, HMR adopting a live session, hundreds of MB of logs — that we
do not have. Revisit when we do.

---

# Phase 4 — You can chat with it ⭐

**Demo.** Browser at `localhost:4897` (the API is on `4896`). Send a message,
watch it stream, press stop. Start a long turn, **refresh the page**, keep
watching. Close the tab, come back, it's still running.

**Depends on.** 3.

**This is the product moment and the biggest phase.** Budget for it.

**Ships.**
- `session/service.py` — `read()`, the display path beside `resume()`'s write path
- `runs/store.py`, `runs/subscribe.py`
- `web/schemas.py`, `web/sse.py`, `web/routes/conversations.py`, `web/server.py`
- `Makefile` — `make dev`, running uvicorn against the factory as cell-bot does
- **`cli.py` is deleted.** `run`/`list`/`resume` were drivers to demo the harness
  before a UI existed; the API does all three, and a second surface is one more
  thing to hold in step. Composition moved into `web/server.py`, where cell-bot
  keeps its own. Phases 1–3 below still describe the CLI because that is what
  they shipped — the record is not rewritten.
- `frontend/` — Next.js chat: timeline, composer, stop button, reconnect

**Cut before building, each deferred to the phase with a first caller:**
`core/scope.py`, `agent/handle.py` + `agent/registry.py`, `runs/heartbeat.py`,
`guard/repeat_reminder.py`, tool-result `meta`, `Session.after()`. See "Where the
infrastructure lands". Also cut *during* building, for the same reason: run ids
(nothing addressed a run — a client subscribes and stops by *conversation*), a
`RunStatus` vocabulary (how a turn ended is the `reason` on its `turn/end`, which
is already on the wire), `FINISHED_RUN_TTL` (the flush before settling means disk
serves the same events), and the SSE keepalive (nothing in this phase goes silent
for 15s; it lands with phase 5's slow MCP tools).

**Why runs are here and not later.** A chat product's turns are long — a
download, a generated deck. Tying a turn to the connection that asked for it
means a closed tab kills four minutes of work. This is a product requirement, not
an optimization, and it is why phase 1 shipped no HTTP.

**No event buffer — the session log is the buffer.** It is already append-only
with its index as a stable cursor, and the loop appends *before* it yields, so a
subscriber reads `session.events()[after:]` directly. One cursor then means the
same thing to the disk snapshot and the live stream, which is what makes "renders
identically" true by construction rather than by keeping two paths in step.

**Where we leave dsh, deliberately.** Their web transport is unary RPC at
`POST /api/<namespace>/<method>` plus two WebSocket downlinks
(`packages/client/connection/src/api-path.ts`), and `docs/api-gateway.md` insists
actions and event streams stay separate protocols. We keep that split and reject
both shapes: their RPC gateway exists to serve compile-time TypeScript codegen we
do not have, and their mux socket exists because they have many concurrent stream
types where we have one. Revisit SSE at 3+ stream types — phases 5 and 6 add MCP
status and skills changes, which are their "host frames".

**Key contracts.**
- `start()` spawns a task the store holds, and is **synchronous** so its busy
  check and registration cannot be split by an await. A client **subscribes**; it
  does not drive. Disconnect drops a subscription; `stop` is the only thing that
  ends a run.
- One `asyncio.Condition` guards the log's growth and `settled` **together** —
  read separately, a subscriber can park forever on a run that finished between
  the two reads.
- A second run on one conversation is **refused, not queued** — telling the user
  "still working" is honest where silently ordering their turns is not. The check
  runs *before* the session load too, because loading for writing calls `resume`,
  which would commit crash repair over a tool that is still executing.
- A subscriber **owns nothing**, so a browser hang-up has no ownership to
  propagate through. This is stronger than remembering not to wrap `sse_frames`
  in `aclosing`.
- An idle conversation streams its **stored tail** before `end`, so a turn
  settling between a client's snapshot and its subscribe cannot strand events.
- The UI renders from session events, not a bespoke API shape. A new event type is
  a new renderer, not a new endpoint — enforced by `test_frontend_types.py`.

**Acceptance.**
- Start a run, disconnect, reconnect with a cursor, receive every missed event.
- Closing the SSE response does not cancel the run. *(Needs a real server:
  `httpx.ASGITransport` buffers the whole body, so it can never hang up midway.)*
- The stop button ends the run and leaves a `tool/result` for every dispatched call.
- A reloaded conversation renders identically to the live stream.
- Two simultaneous messages start exactly one turn.
- ~~Kill the process mid-run; another instance reclaims the lease within 30s.~~
  Deferred with the heartbeat — needs a second process.
- ~~Disposing an agent unwinds every registration it made.~~ Deferred with `Scope`.

**Milestone.** Phases 1–4 are a working chat product. ~4,300 lines.

---

# Phase 5 — It uses your tools

**Demo.** Add an MCP server in settings; its tools are callable on the next turn,
in the same conversation.

**Depends on.** 4.

**This is how a chat product gets capabilities.** cell-bot's five satellite
servers (yt-dlp, whisper, pptx, tradingagents, charts) are the model: a capability
is a separate process with its own README and tests, not backend growth.

**Ships.**
- `mcp/manager.py` — command-loop connection manager
- `mcp/tool.py` — namespaced `{server}__{tool}`
- `mcp/auth.py`, `credentials/` — encrypted credential store
- `control/` — one implementation, two surfaces (native tool + MCP endpoint)
- `web/routes/mcp.py`, `frontend/` settings — server catalog, connect/disconnect

**Key contracts.**
- The **command loop** is mandatory, not a style choice: MCP transports are anyio
  context managers bound to the entering task, so a connection cannot be opened in
  one request task and closed in another. One long-lived `_serve` task hosts the
  group; `connect`/`disconnect` submit commands and await replies.
- `COMMAND_TIMEOUT = 60s` bounds the whole round trip so a wedged loop surfaces as
  a failed request, not a hang.
- MCP tools relay the **server's** schema verbatim. Never validate against our copy
  — that would silently drop arguments the server accepts.
- Credentials are encrypted at rest and referenced by name; a server definition
  carries no secret.
- Auth validation lives in the schema's `model_validator`, so it guards the HTTP
  surface and the control tool at once.

**Acceptance.**
- Connect mid-conversation; tools callable next turn without rebuilding the agent.
- Disconnect; tools vanish, no orphaned subprocess.
- A server that accepts connections but stops answering fails within the timeout.
- An auth combination that could never connect is rejected on both surfaces.

---

# Phase 6 — It follows instructions

**Demo.** Attach a skill to an agent; ask something matching it — it loads and
follows it.

**Depends on.** 5.

**Ships.**
- `prompt/assembly.py` — ordered named sections, `complete` override
- `prompt/render.py`, `prompt/templates/`, `prompt/catalog.py`
- `skills/catalog.py` — `SkillProvider` Protocol
- `providers/skills_db.py` — the catalog agents attach skills from
- `providers/skills_fs.py` — ranked roots, `SKILL.md` + flat markdown, watching
- `skills/tool.py`, `skills/invocation.py`
- `web/routes/skills.py`, `frontend/` settings — skills editor

**Why prompt sections are here.** Skills are the first thing that contributes to
the system prompt. Before this, one string was enough.

**Two providers, deliberately.** A DB catalog (what a chat product's settings UI
edits) *and* a filesystem provider (ranked roots, `.agents/skills` for cross-tool
interop). That is what makes `SkillProvider` a real seam rather than an interface
with one implementation.

**Key contracts.**
- Section ordering: `-100` harness identity, `0` persona, `100–199` tool guidance.
  Duplicate names raise. `StrictUndefined` — a missing variable raises, because a
  silently half-built prompt is the worst failure mode (the model answers anyway).
- Ranked roots: `<project>/.agents/skills` and `~/.agents/skills` for cross-tool
  interop; project root is the nearest `.git` ancestor.
- Two independent surfaces. `disable-model-invocation: true` hides from the model
  but not from human commands. Invocation policy **fails closed**.
- The registry is **policy-neutral**; each consumer enforces its own predicate.
- Catalog and body have **separate lifecycles**. Body edits need no invalidation.
  Only frontmatter/membership changes republish, gated by a **digest over
  `(name, description)`** compared against the last catalog message in the log.
- Skills are scoped per agent, so the index stays small however large the catalog.
- Generate the args model with `Literal[names]` so an invented name is a schema
  violation. Accept the prompt-cache cost.

**Acceptance.**
- Template directory ↔ prompt enum match **in both directions** (a test).
- Index and tool are built from the same subset and cannot disagree.
- Editing a body changes the next `skill()` result with no catalog republish.
- Editing a description appends exactly one replacement catalog.
- Deleting every skill appends an empty envelope, not silence.
- An I/O error preserves the last-good catalog (incomplete ≠ empty).

**Security note.** A skill shipping executable scripts is code running with
whatever authority the harness has. Until phase 12 there is no sandbox — either
keep skills instruction-only, or accept the risk explicitly.

---

# Phase 7 — You can steer it

**Demo.** It's going the wrong way; type a correction and it adjusts at the next
step instead of restarting.

**Depends on.** 4.

**Ships.**
- `agent/inbox.py` — one inbox, `InboxTarget`, wakeup flag
- `agent/handle.py` — `send`, `followup`, `steer`, `inject`, `when_idle`
- `frontend/` — send-while-running affordance

**Key contracts.**

| Method | Target | Wakes driver? |
|---|---|---|
| `followup(msg)` | next turn, sole ordinary message of its own turn | yes |
| `steer(msg)` | nearest step boundary | yes (starts a turn if idle) |
| `inject(msg)` | next pre-step, model-facing context | **no** |

- `inject()` **not waking** the driver is the subtle, valuable bit: skill catalog
  replacements and background-job completions ride along with the next real message.
- Cancellation: first cause wins; `keep_inbox` preserves pending work.

**Acceptance.**
- `inject()` on an idle agent does nothing until a `followup()` arrives; both then
  land in the same request.
- `steer()` during a turn is consumed at the next step boundary, not mid-stream.

---

# Phase 8 — It doesn't get stuck

**Demo.** An MCP tool keeps failing; it stops instead of burning 60 turns.

**Depends on.** 5 (for realistic failures).

**Ships.**
- `agent/hooks.py` — typed decisions + `HookChain` + timeouts
- `agent/guardrail.py` — three detectors, as a hook
- `guard/timeout_policy.py` — a `tools/execute` waterfall wrapper

**Key contracts.**
- Three observers return `None`. Two decisions carry meaning in the return type:
  `pre_tool_call -> str | None` (refuse), `transform_tool_result -> str | None`
  (replace). A hook cannot hand back a malformed directive.
- First non-None wins; **ordering is precedence**.
- An exception is logged and contributes nothing, so a **decision hook fails
  open**. "Registered" must not be read as "enforcing" — say so in the docstring.
- **Improvement on cell-bot:** `HOOK_TIMEOUT_S` per call, plus a dev-mode warning
  when a hook does blocking I/O. cell-bot's hooks run inline with no timeout, so a
  slow one stalls every other conversation's stream.
- Detectors: `exact_failure` (2 warn / 5 block), `same_tool_failure` (3 / 8),
  `idempotent_no_progress` (2 / 5). A repeated **success** is never detected.
  `warn` appends guidance and still runs; `block` is pre-execution. `before_call`
  only reads; only `after_call` mutates.
- The guardrail keys on the typed `Failure` code, never a string prefix.
- **`LoopAgent.max_steps` can drop here.** It exists only as a backstop against a
  bug in the loop itself; once a detector enforces a real bound, counting steps
  and hoping is no longer the protection. dsh has no step cap at all.

**Acceptance.**
- A raising decision hook refuses nothing and suppresses nothing.
- A hook exceeding the timeout is skipped and logged.
- The 5th identical failing call is blocked; a succeeding one never is.
- Removing the guardrail from the composition root changes no loop code.

---

# Phase 9 — It picks the right specialist

**Demo.** Several agents in the catalog; each turn is answered by the right one,
with its own prompt, skills, and tool subset.

**Depends on.** 6.

**Ships.**
- `agents/catalog.py` — agent rows: name, description, prompt, tool mode/names,
  skill links, default flag
- `agents/service.py` — compose a runtime agent per turn from the catalog
- `agent/router.py` — `RouterAgent`, built per turn
- `llm/structured.py` — `StructuredOutputClient` (segregated interface)
- `web/routes/agents.py`, `frontend/` settings — agent editor

**Composed per turn, never cached.** An agent reads the catalog when it is built,
so it always reflects what the database holds — no cached copy to invalidate and
no refresh step a future mutator can forget.

**Per-agent tools without layered registries.** `narrow(mode, patterns, provider)`
wraps the provider rather than materializing a list, so an agent's MCP tools are
not frozen at compose time. Scoped registries are a phase-13 concern.

**Key contracts.**
- One cheap structured call per turn. **Not** `transfer_to_*` handoff tools —
  those grow the tool list with every agent added, and a specialist that never
  volunteers to hand back strands the conversation.
- **Advisory, never authoritative.** Unparseable reply, low confidence, unknown
  agent, timeout, any provider error → stay on the current agent. `run()` has no
  failure terminal; it always yields exactly one `AgentSelected`.
- Choice model built **per call** with `Literal[uuids]`, so the roster's ids are a
  schema enum. Address by uuid, never name — names are not unique.
- Field descriptions are written **for the model**, with the observed failure
  recorded in a comment beside the wording that fixed it.
- Deleting the default agent is refused; a conversation whose agent was deleted
  resolves to the default.

**Acceptance.**
- Every failure path leaves the conversation on its current agent.
- A model answering with an agent *name* fails validation rather than resolving.
- An agent sees only its own skills; the `<available_skills>` index proves it.
- Routing does not delay the first token beyond one call.

---

# Phase 10 — It handles long conversations

**Demo.** A 200-turn session stays coherent instead of hitting the context window.

**Depends on.** 3.

**Ships.**
- `seams/compaction.py` — the seam + `compaction/start|summary|end` events
- `providers/compaction_basic.py`, `providers/compaction_tool_pruner.py`
- `web/routes/` — a manual compact action

**Key contracts.**
- Compaction **appends its own events**; it never rewrites the log.
  `derive_messages()` honors the boundary. Only possible because of phase 1.
- Prune tool results before summarizing prose — they're the bulk and the least
  re-readable. A yt-dlp or transcription result is enormous and stale immediately.
- A hidden skill catalog must be re-established by the next complete observation.

**Acceptance.**
- A 200-turn conversation compacts and continues coherently.
- The raw log still replays in full; compaction is additive.
- The skill catalog reappears after compaction hides it.

**This is cell-bot's largest gap.** Worth doing even if 11–13 never ship.

---

# Optional track — agentic capabilities

Phases 11–13 are worth building only if the product wants them. cell-bot ships
without all three. **Decide before starting 11**, not during.

## Phase 11 — It reads and writes files *(optional)*

**Ships.** `seams/fs.py`, `seams/subprocess.py`, local providers,
`read`/`write`/`edit`, `glob`/`grep` via packaged ripgrep,
`fs/observation_policy.py`, `concurrency_safe`.

**Key contracts.** `glob`/`grep` spawn ripgrep **through `Subprocess`, never a
shell**. Read-before-write is a separate policy listener, not a check inside the
tools. Reads overlap; writes don't.

**Acceptance.** Pointing `FileSystem` + `Subprocess` at the test suite's in-memory
provider moves all five tools with **zero tool changes**. ~800 lines.

## Phase 12 — It runs commands *(optional)*

**Ships.** `seams/shell.py`, `seams/sandbox.py`, local providers,
`tools/native/bash.py`, `jobs/` + `job_*` tools, `interaction/approval.py`.

**Key contracts.** Sandbox **wraps argv before spawn**. Presets `read-only` /
`workspace-write` / `full` chosen explicitly, never defaulted. Background work
registers with the generic `Jobs` runtime; completion arrives via `inject()`.

**Risk.** Platform-specific and the most likely phase to overrun. POSIX only;
defer Windows. ~800 lines.

## Phase 13 — It delegates *(optional)*

**Ships.** `core/layered.py` (converting the registries), `seams/subagent.py`,
`providers/subagent_fork.py`, `providers/subagent_spawn.py`, the `subagent` /
control / `report` tools.

**Key contracts.** **Unlike every other seam, multiple named providers coexist** —
that's what lets `subagent` and `subagent_fork` be different backends behind one
tool shape, and what would let us delegate to Claude Code or Codex later.
Providers advertise start-time capabilities and a request needing one the provider
lacks is **rejected loudly**. Layer resolution is global → farthest ancestor →
nearest; `own()` is chain-blind because capabilities inherit and restrictions
don't. ~800 lines.

---

# Cross-cutting, from phase 1

Not phases. They start immediately and run throughout.

| Practice | From |
|---|---|
| `CLAUDE.md` — project rules, loaded into every session | cell-bot |
| cell-bot's house rules verbatim | cell-bot |
| Comment discipline: non-obvious lines carry the *reason*; bug-driven lines carry the bug | cell-bot |
| Generated `tool-catalog.md` by **booting** each tool, with a completeness guard | dsh |
| A "where new behavior goes" table, updated whenever the loop changes | dsh |
| Tests that assert two things stay in step (templates ↔ enum, tools ↔ manifest) | cell-bot |

---

# Decision gates

| Before | Decide | Default if silent |
|---|---|---|
| Phase 1 | Python vs TypeScript | **Python** — settled |
| Phase 1 | Product shape | **Chat product** — settled, drives this ordering |
| Phase 3 | JSONL vs SQLite | **JSONL**, header on line 1 (dsh's design) |
| Phase 4 | Frontend stack | **Next.js**, matching cell-bot's `frontend/` |
| Phase 6 | Skills from DB, filesystem, or both | **Both** — that's what makes it a seam |
| Phase 11 | Build the optional track at all | **Defer** until the product asks |

---

# Start here

**Phase 1.** ~900 lines, and at the end you can talk to it from a terminal.

The only thing to be strict about: the loop reads its history from
`derive_messages(log)`, never from a list it accumulated. That one discipline is
what makes phases 3, 10, and 13 cheap instead of rewrites.

And the one temptation to resist: **no HTTP before phase 4.** A quick endpoint in
phase 1 streams on the request connection, which is precisely the design phase 4
exists to undo — and it would shape phases 2 and 3 around a model where the
connection owns the turn.
