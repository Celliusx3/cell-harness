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
| 5 | **It answers on Telegram** ⭐ | Text the bot from your phone; it replies, and keeps working while you're away | 1100 |
| 6 | **One seam for every channel** | Browser and Telegram behind one adapter contract; a third is a file | 400 |
| 7 | **It uses your tools** | Add an MCP server in settings; its tools work next turn | 900 |
| 8 | **It follows instructions** | Attach a skill; it loads and applies it | 1000 |
| 9 | **You can steer it** | Correct it mid-turn without restarting | 450 |
| 10 | **It doesn't get stuck** | A runaway tool loop is stopped | 450 |
| 11 | **It picks the right specialist** | Multiple agents; the right one answers each turn | 700 |
| 12 | **It handles long conversations** | 200 turns without hitting the context window | 450 |
| 13 | **It reads and writes files** *(opt)* | File tools without going through MCP | 800 |
| 14 | **It runs commands** *(opt)* | `bash`, confined | 800 |
| 15 | **It delegates** *(opt)* | Subagents working in parallel | 800 |

**Phases 1–6 are the product.** 7–10 make it capable and safe. 11–12 make it
better than cell-bot. 13–15 are agentic capabilities to add only if the product
turns out to want them.

### Why this order

A chat product's constraints differ from a coding harness's:

| | Chat product (us) | Coding harness |
|---|---|---|
| The UI is | the product — pull it to phase 4 | optional |
| Capabilities arrive via | **MCP** (phase 7) | built-in fs/shell tools |
| A turn is | often long (a download, a deck) — runs must outlive connections | usually short |
| Multiple agents means | **routing** to a specialist (phase 11) | delegating to subagents |
| `bash`/fs tools are | optional, late | phase 2 material |

This is why phases 13–15 are marked optional. cell-bot ships a real product with
none of them — every capability arrives through an MCP server.

### Where the infrastructure lands

Nothing below is a phase. Each is written as part of the capability that needs it.

| Mechanism | Born in | Why then |
|---|---|---|
| Session event log | 1 | The loop derives history from it — retrofitting means rewriting the loop |
| Persistence + the model-visible invariant | 3 | Resume is what makes the invariant testable |
| Runs and cursors | 4 | A turn must outlive the tab that started it |
| `Scope` (reversible teardown) | ~~4~~ **7** | Phase 4 registers nothing; stopping a run is `task.cancel()`. An MCP connection is the first real connect/disconnect lifecycle |
| Tool result `meta` (UI cards) | ~~4~~ **7** | A UI exists now and still has nothing to put there — the only tool is a clock. The first MCP tool returning an image is the caller |
| Heartbeat, lease, reclaim | ~~4~~ **when a 2nd process exists** | Reclaiming a *process's* runs is a multi-process problem. One server, and phase 3's repair-on-resume already covers the single-process crash |
| `Session.after(cursor)` | ~~4~~ **never** | `session.events()[n:]` already is it. Proposed and cut twice |
| Prompt sections | ~~8~~ **11** | Skills turned out to contribute nothing to the prompt — the catalog rides on the tool. Personas are the first template with a variable |
| **Around-middleware on tool execution** | 10 | The timeout and guardrail are its first listeners |
| `ToolDefinition.timeout_s` | 10 | Nothing enforces a deadline until the timeout policy exists |
| Typed hooks | 10 | The guardrail is its first real consumer |
| Seams (`FileSystem`, `Subprocess`) | 13 | Two providers is when an interface earns its keep |
| `Layered` (scoped registries) | 15 | The first time a plugin registers into *one agent's* world |
| Durable inbox (`followup`/`steer`/`inject`) | 9 | Phase 5 queues at the channel, which is enough while a correction can wait for the next turn. `steer` mutates a turn already running, so it needs dsh's session-event inbox |
| `user/message` `source` field | when injected context exists (8 or 9) | Only `human` produces one until then |

**Phase 2 built four of these early and they were cut.** An event bus with no
listener, a `timeout_s` nothing enforced, a `meta` nothing rendered, and a cursor
nothing subscribed to. Each was justified by a docstring describing a *future*
caller — which is the tell. The check is `grep`: a definition whose only callers
are in `tests/` either belongs in `tests/` or does not exist yet.

On `Layered`: per-agent **tool selection** (phase 11) does not need layered
registries. cell-bot does it by filtering the provider at compose time
(`narrow(mode, patterns, provider)`), which is simpler and correct. `Layered` is
only needed when a plugin registers into one agent's world — which is subagents.

**Dependency graph:**

```
1 ── 2 ── 3 ── 4 ── 5 ── 6 ─┬─ 7 ─┬─ 8 ── 11
                            ├─ 9  │
                            ├─ 10 ┘
                            └─ 12

                            13 ── 14 ── 15   (optional track, needs 4)
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

**Not here, though an earlier draft said so.** The interception chain (phase 10,
when the timeout and guardrail need it), a per-agent tool filter (phase 7's MCP
wildcards or phase 11's selection), and `todo_write` (phase 4, when a UI renders a
checklist). Each would have been a mechanism with no user.

**Why live providers now.** Phase 7's MCP servers connect mid-conversation. A
registry that resolves its providers on every turn makes that free; one that
materializes a list at compose time freezes each agent's tools forever.

**Key contracts.**
- `schemas()` emits `name`, `description`, `input_schema` **by allowlist**.
- `from_model()` derives schema *and* parse from one Pydantic model. Construct
  directly only when the schema comes from elsewhere (MCP).
- `ToolOutcome` is typed: `Ok(content, meta) | Failure(code, message)`, rendered
  as `"error: …"` so the model recovers. Never raises.
- Serial dispatch. `concurrency_safe` arrives in phase 13 when reads can overlap.
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
real safety difference once phase 14 has `bash`.

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
for 15s; it lands with phase 7's slow MCP tools).

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

**Milestone.** Phases 1–4 are a working chat product in a browser. ~4,300 lines.

---

# Phase 5 — It answers on Telegram ⭐

**Demo.** Text your bot from your phone. It replies. Put your phone away
mid-answer and it still arrives. Send a follow-up while it works and it is
answered next, in order. Paste something long — Telegram's client splits it into
three messages and you still get **one** answer. The conversation appears in the
browser sidebar, live.

**Depends on.** 4.

**Why here.** Phase 4's run store made a turn survive the tab that started it, and
the honest answer to "what for?" was *not much yet* — a clock tool finishes in a
second. A messenger is where it stops being insurance: there is no connection to
outlive because there never was one, so a design that tied a turn to the request
that asked for it would have nowhere to put the answer.

**Ships.**
- `channels/transport.py` — `Channel`, one Protocol per platform, and `InboundMessage`
- `channels/gateway.py` — inbound → run, log → outbound, and supervision of every channel
- `channels/telegram/channel.py` — one platform: polling, batching, splitting, typing
- `channels/commands.py` — what `/new` and `/stop` *do*, shared by every platform
- `channels/telegram/commands.py` — recognising them, which is Telegram's convention alone
- `channels/repository.py`, `channels/repositories/jsonl.py` — per-chat state

**Polling is `python-telegram-bot`'s**, not ours. A hand-rolled `getUpdates` loop
was written first and replaced: it busy-looped on an empty response, died
permanently on the 409 that `--reload` causes on every save, and did so silently.
PTB is what `hermes-agent` uses, and its `Application` brings backoff, the rate
limiter and offset handling — so `client.py` and `poller.py` were deleted rather
than debugged.

**No frontend.** The token lives in `config.local.json` beside the LLM key, and a
Telegram conversation renders through the timeline phase 4 already built.

## Where the answers came from

Three references, and they disagree usefully.

**`hermes-agent`** (`gateway/platforms/telegram.py`, 5,861 lines) corrected this
plan twice. **Batching is required**, and not for burst typing: *"Buffer rapid
text messages so Telegram **client-side splits of long messages** are aggregated
into a single MessageEvent."* Paste 5,000 characters and the client splits it —
without a buffer that is two turns for one paste. Its tuned delays are adopted
(0.18s ≤320 codepoints, 0.24s ≤1024, 0.30s beyond, 1.0s when a split is
suspected). And **busy behaviour is a three-way policy** — `queue` | `steer` |
`interrupt` — with text defaulting to `queue`, `steer` falling back to queue "so
nothing is lost", and `interrupt` **demoted to queue while subagents are running**
so a conversational aside cannot destroy minutes of work.

**`duta-ilmu`** (`services/channel-gateway`), a production Telegram/WhatsApp
platform, settles transport: long polling in dev — *"no public URL needed"* —
feeding the same path a webhook would; the offset committed *after* publishing
with `(channel, provider_message_id)` dedupe absorbing replays; and
per-conversation FIFO, *"consumers MUST keep entries with the same partition_key
on one worker to preserve per-conversation ordering."*

**`dsh`**'s durable inbox — `agent/inbox/spliced` events projected into
`next-turn` and `next-step` lists — is the richest answer and belongs to phase 9,
because `steer` mutates a turn already running.

## Key contracts

- **Queue, and only queue.** A phone cannot grey out its composer, so a message
  during a turn is held and answered next — never refused (cell-bot's `409` is
  right for a browser and useless here), never merged into the running turn.
- **The queue drains as one turn.** Three lines typed in a burst were one thought.
- **The queue is channel state, not session events.** A *queued* message has not
  reached a model request yet, so "model-visible means logged" does not bind it;
  it becomes an ordinary `user/message` the moment its turn starts.
- **Outbound is a cursor over the session log** — the same numbering the browser
  uses for `?after=N`. It is what stops a restart re-texting a delivered reply.
- **Dedupe by consequence, not by default.** A redelivered message is answered
  again — annoying, not damaging. `hermes-agent` guards exactly one thing across
  5,861 lines of Telegram, `/restart`, because a repeated `/restart` perpetuates
  itself. Nothing here has that shape, so the `update_id` set planned for this
  phase was cut before it was written.
- **A conversation is created by the first message, not first contact.** Phase 3's
  `create()` writes nothing, so a chat that only ever sent `/stop` would otherwise
  hold an id `resume()` cannot find.
- **Split outbound at 4096 on a paragraph boundary**; never truncate. **Plain
  text, not MarkdownV2** — one unescaped character rejects the whole message.
- **Registering a platform twice is refused.** Two pollers on one bot token is a
  409 from Telegram, and it was reachable: a dict of transports silently replaced
  while a list of pollers silently appended.
- **A channel that stops listening says so.** `create_task` holds an exception
  until something awaits the task, and nothing does until shutdown — so a dead
  poller and a working one look identical from the outside.

## Acceptance

- A message becomes a turn and a reply.
- A message during a turn is queued and answered next, in order.
- Several queued messages drain as **one** turn.
- A client-split paste is **one** turn — both when the halves arrive together and
  when the second lands on the next poll.
- A restart re-sends nothing already delivered.
- `/new` starts fresh; `/stop` cancels and clears the queue.
- Registering one platform twice is refused.
- A second platform needs no change to `gateway.py`, `commands.py` or
  `repository.py` — proven by a `FakeDiscord` that implements `Channel` and
  nothing else.
- The conversation is listed and replayable over HTTP like any other.

---

# Phase 6 — One seam for every channel

**Demo.** The browser and Telegram run through one gateway. Type a second message
while the assistant is still answering: it is accepted, shown as queued, and
answered next — the behaviour Telegram always had. Reply from the browser to a
conversation that started on your phone.

**Depends on.** 5, deliberately: the seam was extracted from two working
implementations rather than guessed.

**Why the API becomes a channel.** Because the same ten lines existed twice and
answered every question oppositely — busy meant `409` in `web/routes/` and *queue*
in `gateway.py`; a missing conversation meant `404` in one and *recreate* in the
other. One of those pairs was a real difference and the other was an accident.

**Not the reason this phase was first planned.** The original justification was
that `hermes-agent` models its HTTP API as a platform adapter, "the answer that
scales". **That was false**, and it came from reading their file listing rather
than their implementation. `APIServerAdapter.send()` — the method their entire
outbound system calls — is a permanent stub:

    # gateway/platforms/api_server.py:4174
    return SendResult(success=False, error="API server uses ... not send()")

It never calls `build_source()`, never invokes the message handler the runner
wires into it, and four modules special-case it back out. Their `webhook.py` *is*
a real adapter, because it is genuinely push-based. The lesson kept is the
opposite of the one planned: one wide interface every platform must satisfy forces
the member that cannot to lie.

**So the split is by capability.** `Channel` is a name, an `on_missing` and
`run()`. `Pushing` — `send_message`, `send_typing` — is separate, and `WebChannel`
implements it not at all, because **a browser has no address to send to**. It
comes and reads, holding a `GET` open and following the log through `subscribe()`.
The gateway asks `isinstance(channel, Pushing)` before delivering, so a pull
channel is never asked and there is nothing to stub.

**What stays per-channel**, and it is two things, not four. `busy` and `mapping`
were planned and dropped: both channels queue now, so there was nothing left to
vary.

| | browser | Telegram |
|---|---|---|
| `Pushing` | no — the client reads the log | yes |
| `on_missing` | `raise` — a named id that is absent is a `404` | `recreate` — a chat cannot be left broken |

**The `409` is retired.** Being able to show a refusal is not a reason to refuse;
it makes someone retype what they wrote. `POST /{id}/messages` stays `202` and its
body gains `queued: bool`, because a queued message is *not in the log yet* and
the browser draws from the log — so the client renders it until its turn starts.

**What does not change: the HTTP endpoints.** They stay conversation-keyed.
Hermes keys on run id and therefore needs a fourth endpoint,
`GET /chats/{id}/turns/in_flight`, for a reconnecting client to find what to
attach to; `ilmuchat-enterprise` carries the same probe for the same reason.
Keying on the conversation removed that round trip in phase 4.

**Ships.**
- `channels/transport.py` — `Pushing` split off `Channel`; `on_missing`
- `channels/web/` — `WebChannel` and the HTTP surface moved from `web/`
- `channels/gateway.py` — one inbound path for every channel; `start_turn()`
- `web/server.py` — the composition root alone; `app.state` retired

**Acceptance.**
- A browser message mid-turn is queued and answered next, in order.
- Several queued browser messages drain as **one** turn.
- The browser can continue a conversation that started on Telegram.
- A bogus conversation id is a `404` and creates nothing.
- A `pull` channel is never asked to send, and its `run()` returning is not
  reported as "it will not answer".
- The browser still streams token by token.

---

# Phase 7 — It uses your tools

**Demo.** Add an MCP server in settings; its tools are callable on the next turn,
in the same conversation.

**Depends on.** 4.

**This is how a chat product gets capabilities.** cell-bot's five satellite
servers (yt-dlp, whisper, pptx, tradingagents, charts) are the model: a capability
is a separate process with its own README and tests, not backend growth.

**Ships.** Narrowed before building — stdio only, and four things cut. Each was
a mechanism with no caller in this phase, which is what phase 2 was burned by.

- `mcp/store.py` — `McpServerStore`, one owning task per connection
- `mcp/tool.py` — namespaced `{server}__{tool}`
- `mcp/repository.py` + `repositories/jsonl.py` — the catalog, `0600`
- `mcp/web/` — server catalog, connect/disconnect — and `frontend/` settings

**Cut, and why.** `control/` (a model-callable connect tool is not in the demo,
and it lets the model spawn processes); `credentials/` encryption (the provider
key is plaintext in `config.local.json`, so encrypting only this is not a threat
model); `Scope` (a server plugs in as *one* provider and unplugs as *one*
disposer, so there is nothing to group); tool-result `meta` (no tool returns an
image yet); remote HTTP transport (stdio is what all five cell-bot satellites
are).

**Servers are configuration, not a runtime catalog.** `mcp.servers` in
`config.json`, keyed by the id that is also the `{id}__{tool}` namespace. A
second, runtime store would give "which servers are configured?" two answers —
the fallback-chain problem the house rules forbid — and `config.local.json` is
already where secrets live, so the two files deep-merge *per server*: the shape
is committed, the `env` is not. This removed the settings UI, its five routes,
the repository and its JSONL backend.

**Key contracts.**
- The **command loop** is mandatory, not a style choice: MCP transports are anyio
  context managers bound to the entering task, and anyio *raises* on an exit from
  the wrong task. One owning task per connection, fed by a queue. A supervisor
  hosting a task group is the shape anyio forces and pure asyncio does not need.
- `COMMAND_TIMEOUT = 60s` bounds one call. Applied with `asyncio.timeout_at` on
  the owner, which — verified against the real SDK — leaves the session open, so
  a slow tool costs one call rather than the connection.
- MCP tools relay the **server's** schema verbatim. Never validate against our copy
  — that would silently drop arguments the server accepts.
- A tool name that no provider would accept is **dropped, not relayed**: one bad
  name fails the whole request, and with it every other tool in it.
- A server that fails to connect is logged and contributes nothing. One broken
  source must not cost the model every other server's tools.

**Acceptance.**
- A server declared in `config.json` is connected at startup and its tools are
  callable, namespaced, without the agent being rebuilt.
- Shutdown reaps every subprocess — proved by pid, not assumed.
- A server that accepts connections but stops answering fails within the timeout,
  and the connection survives it.
- A definition that could never spawn is rejected when the config loads.

---

# Phase 8 — It follows instructions

**Demo.** Drop a skill into a root — or type `/name` — and the model loads it
and follows it.

**Depends on.** 5 (a request to carry the tool), 7 (something for a skill to
teach).

**Format.** [Agent Skills](https://agentskills.io): a directory holding a
`SKILL.md` whose frontmatter names it and says when to use it. A skill written
for Claude Code, Codex or OpenClaw loads unchanged — every unknown frontmatter
field is ignored, not refused. Research and the six clients compared in
[docs/skills.md](./docs/skills.md).

**Ships, in four demoable insertions.**

| | Demo | Ships |
|---|---|---|
| 8.1 | `GET /api/skills` lists what is on disk, and why anything did not load | `skills/models.py`, `skills/catalog.py`, `skills.roots` / `skills.editable` in `Settings`, `web/routes/skills.py` |
| 8.2 | Share a reel; the model calls `skill(name="find-place")`, then one program across both servers | `skills/tool.py`, `withheld` in code mode, `SKILL` in `DEFAULT_TOOLS`, `.agents/skills/find-place/` |
| 8.3 | Type `/find-place <url>` in the browser or on Telegram; the model receives the body without deciding | `skills/invocation.py`, `UserMessageEvent.invoked`, gateway expansion, Telegram passthrough, a chip in the timeline |
| 8.4 | A `/skills` page: paste a public `SKILL.md`, save, it is used | `PUT`/`DELETE /api/skills/{name}`, `frontend/app/skills/` |

**Key contracts.**
- **The catalog is never logged.** It rides on the `skill` tool's description,
  rebuilt from disk on every request the way the tool list is. Nothing
  republishes it, nothing digests it, and phase 12 has nothing to re-establish.
  (An earlier draft of this phase took dsh's logged-catalog design; every other
  client rebuilds per request, and so does this one.)
- Ranked roots, first wins: `<project>/.agents/skills` (project = nearest
  `.git` ancestor of the config file), then `~/.agents/skills`. A shadowed copy
  is reported, not dropped. A root that fails to list keeps its last-good set.
- **Change detection is a `(mtime_ns, size)` stamp per file**, not a watcher:
  nothing here needs to be *told*, everything asks at request time.
- Generate the args model with `Literal[names]` so an invented name is a
  schema violation. Accept the prompt-cache cost. **No skills → no tool.**
- Index and enum are built from the same list in the same call.
- Catalog and body have **separate lifecycles**: the catalog is metadata cached
  by stamp; the body is read from disk at activation.
- **Two surfaces.** `disable-model-invocation: true` hides a skill from the
  model's enum and index but not from `/name`; `user-invocable: false` the
  reverse. A skill that failed to parse is invocable by nobody.
- **The `skill` tool is withheld from scripts** — its result is context for the
  model, not data for a program.
- Bundled files are listed with the body and readable by `path`, confined to
  the skill's directory and capped at 64 KiB. Scripts are listed but cannot run
  (no shell until phase 14); the tool says so.
- Skills are global until phase 11 gives agents allowlists.

**Acceptance.**
- A skill copied from anthropics/skills loads with no problems reported.
- Index and tool are built from the same subset and cannot disagree.
- Editing a body changes the next `skill()` result with the tool spec unchanged.
- Editing a description changes the next request's tool spec.
- Deleting the last skill removes the tool from the next request.
- A root that cannot be listed preserves its last-good set (incomplete ≠ empty).
- A script calling `skill(...)` is refused; `list_functions` never lists it.

**Security note.** A skill's `scripts/` cannot run here — there is no shell —
so a skill is instructions the model reads. Its instructions can still direct
the model to call any capability it has; install skills from sources you trust.

---

# Phase 9 — You can steer it

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

- `inject()` **not waking** the driver is the subtle, valuable bit:
  background-job completions ride along with the next real message.
- Cancellation: first cause wins; `keep_inbox` preserves pending work.

**Acceptance.**
- `inject()` on an idle agent does nothing until a `followup()` arrives; both then
  land in the same request.
- `steer()` during a turn is consumed at the next step boundary, not mid-stream.

---

# Phase 10 — It doesn't get stuck

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

# Phase 11 — It picks the right specialist

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

# Phase 12 — It handles long conversations

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
- `skill` tool results are exempt from pruning: a loaded skill is durable
  behavioural guidance, and losing it mid-conversation degrades the agent with
  no visible error (the spec's compaction rule; Claude Code re-attaches the
  last invocation of each skill, 5k tokens each).

**Acceptance.**
- A 200-turn conversation compacts and continues coherently.
- The raw log still replays in full; compaction is additive.
- A skill loaded before compaction is still in context after it.

**This is cell-bot's largest gap.** Worth doing even if 11–13 never ship.

---

# Optional track — agentic capabilities

Phases 13–15 are worth building only if the product wants them. cell-bot ships
without all three. **Decide before starting 13**, not during.

## Phase 13 — It reads and writes files *(optional)*

**Ships.** `seams/fs.py`, `seams/subprocess.py`, local providers,
`read`/`write`/`edit`, `glob`/`grep` via packaged ripgrep,
`fs/observation_policy.py`, `concurrency_safe`.

**Key contracts.** `glob`/`grep` spawn ripgrep **through `Subprocess`, never a
shell**. Read-before-write is a separate policy listener, not a check inside the
tools. Reads overlap; writes don't.

**Acceptance.** Pointing `FileSystem` + `Subprocess` at the test suite's in-memory
provider moves all five tools with **zero tool changes**. ~800 lines.

## Phase 14 — It runs commands *(optional)*

**Ships.** `seams/shell.py`, `seams/sandbox.py`, local providers,
`tools/native/bash.py`, `jobs/` + `job_*` tools, `interaction/approval.py`.

**Key contracts.** Sandbox **wraps argv before spawn**. Presets `read-only` /
`workspace-write` / `full` chosen explicitly, never defaulted. Background work
registers with the generic `Jobs` runtime; completion arrives via `inject()`.

**Risk.** Platform-specific and the most likely phase to overrun. POSIX only;
defer Windows. ~800 lines.

## Phase 15 — It delegates *(optional)*

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
| Phase 8 | Skills from DB, filesystem, or both | ~~Both~~ **Filesystem** — there is no DB, and a managed directory the page writes into is the same feature with one provider |
| Phase 13 | Build the optional track at all | **Defer** until the product asks |

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
