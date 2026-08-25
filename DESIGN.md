# cell-harness — design

A harness of our own, synthesized from two studied sources:

- **dsh** (`docs/deepseek-harness.md`) — 256k lines, 227 packages. Gives us the
  *architecture*: event-sourced session log, capability seams, turn/step
  semantics, composition from config.
- **cell-bot** (`docs/cell-bot.md`) — 6.9k lines Python. Gives us the *taste*:
  shallow contracts, typed decisions, tolerant tool failures, runs that outlive
  their connection, and a comment discipline that keeps a small codebase legible.

The thesis: **dsh's spine at cell-bot's size.** Target ~10k lines of Python,
one repo, no plugin framework, every load-bearing idea intact.

## 1. What we take from each

| Concern | Source | Decision |
|---|---|---|
| Session as append-only event log | dsh | **Take.** cell-bot's biggest gap. |
| "Model-visible means logged" invariant | dsh | **Take**, asserted at runtime from day one. |
| turn / step vocabulary | dsh | **Take** verbatim. |
| Inbox with `followup` / `steer` / `inject` | dsh | **Take.** `inject` not waking the driver is the subtle win. |
| Capability seams (definition / provider / consumer) | dsh | **Take** as `Protocol`s in one module, not as packages. |
| System-prompt sections with explicit ordering | dsh | **Take.** |
| Tool-schema allowlist (execute/timeout never on the wire) | dsh | **Take.** |
| `isConcurrencySafe` defaulting closed | dsh | **Take** — but ship serial dispatch first. |
| Cordis / plugins / bundles / YAML patches | dsh | **Leave.** Replace with a typed composition root + a small registry. |
| Code mode (`run_code` as sole transport) | dsh | **Defer.** Great idea, not a v1. |
| Agent Teams | dsh | **Leave.** |
| Shallow `BaseAgent` (name, model, `run()`) | cell-bot | **Take.** |
| Engine / state-holder split | cell-bot | **Take.** |
| Router as advisory per-turn structured call | cell-bot | **Take.** Best idea in either repo for multi-agent. |
| Typed hook decisions (`str \| None` = refuse/replace) | cell-bot | **Take**, merged with dsh's waterfall shape. |
| Guardrail as a hook, not a loop feature | cell-bot | **Take.** |
| Runs outliving connections, cursor-indexed buffer | cell-bot | **Take.** |
| Tolerant `"error: "` tool results | cell-bot | **Take**, with a typed `ToolFailure` carried in the event. |
| `Tool.from_model` schema/parse from one model | cell-bot | **Take.** |
| Three-mode tool selection (all/selected/except) | cell-bot | **Take.** |
| Skills as progressive disclosure + generated `Literal` enum | cell-bot | **Take.** |
| MCP command-loop manager | cell-bot | **Take** near-verbatim; the anyio problem is real. |
| Prompts as Jinja + `StrictUndefined` + enum-addressed | cell-bot | **Take.** |
| One implementation, two surfaces (native tool + MCP) | cell-bot | **Take.** |
| Satellite MCP servers | cell-bot | **Take** as the capability-packaging default. |
| Adaptive inbound batching (a client-split paste is one turn) | hermes-agent | **Take**, with its tuned delays. |
| Busy-input policy: queue \| steer \| interrupt | hermes-agent | **Take `queue` only.** The other two need a durable inbox. |
| `/new` and `/stop`, bypassing the queue | hermes-agent | **Take.** A chat window has no buttons. |
| Long polling in dev, feeding the webhook's path | duta-ilmu | **Take.** No tunnel, and a webhook is additive later. |
| Offset committed after processing + id dedupe | duta-ilmu | **Take.** At-least-once, made effectively once. |
| Per-conversation FIFO ordering | duta-ilmu | **Take.** |
| The HTTP API as one platform adapter among many | hermes-agent | **Take at phase 6**, once there are two implementations to generalise from. |

## 2. Language and shape

**Python 3.13+**, single repo, `uv`. Rationale: cell-bot is the codebase we
actually maintain, its MCP satellites are Python, and Protocol + generics +
Pydantic cover everything we need from dsh's type layer. Adopting Cordis would
mean a TypeScript rewrite to buy reversible effects we can approximate in ~200
lines.

The one thing we must reimplement rather than skip is **reversible
registration** — it is what makes per-agent scoping and teardown correct:

```python
class Registry[T]:
    """Scoped registrations that unwind. Every register() returns a disposer."""
    def register(self, item: T, *, scope: ScopeKey | None = None) -> Disposer: ...
    def resolve(self, scope: ScopeKey | None) -> list[T]: ...   # global + scoped

class Scope:
    """One agent's world. close() unwinds every registration made under it,
    in reverse order, and rejects registration afterward."""
```

Everything scoped — tools, prompt sections, hooks — goes through this. It is
the single primitive that buys us dsh's "an extension can be agent-local".

## 3. Module layout

```
cell_harness/
  session/      events.py     SessionEvent union + SessionEventMap registry
                log.py        append-only Session, sequence numbers, invariants
                derive.py     derive_messages(log) -> list[Message]
                persist.py    JSONL append; SQLite behind the same Protocol
  llm/          client.py     LLMClient Protocol, exactly one terminal event
                messages.py   Message / ContentBlock / ToolCall vocabulary
                stream.py     StreamChunk union
                structured.py StructuredOutputClient (segregated interface)
                adapters/     openai.py, anthropic.py, deepseek.py
  tools/        definition.py ToolDefinition, schema allowlist, from_model()
                registry.py   scoped registry, live providers, three-mode filter
                pipeline.py   pre_execute / execute / post_execute middleware
                progress.py   ToolProgressReporter + the queue fan-in pattern
                native/       read, write, edit, glob, grep, bash, todo_write
  prompt/       assembly.py   ordered named sections, `complete` override
                render.py     {{variable}} interpolation
                templates/    *.jinja, enum-addressed, StrictUndefined
  agent/        base.py       BaseAgent: name, model, run()
                handle.py     Agent: send/followup/steer/inject, cancel, whenIdle
                inbox.py      one inbox, three targets, wakeup flag
                loop.py       LoopAgent — the turn/step driver
                router.py     RouterAgent — advisory per-turn structured choice
                hooks.py      typed decisions + HookChain
                guardrail.py  three detectors, warn/block, as a hook
  seams/        fs.py subprocess.py shell.py sandbox.py subagent.py
                web.py storage.py   — Protocols only
  providers/    fs_local.py subprocess_local.py shell_local.py
                sandbox_local.py subagent_fork.py ...
  skills/       catalog.py tool.py     progressive disclosure
  mcp/          manager.py tool.py auth.py    command-loop connection manager
  runs/         store.py subscribe.py heartbeat.py    outlive-the-connection
  compose/      composition.py config.py     the typed composition root
  web/          server.py sse.py routes/
```

## 4. Core contracts

### 4.1 The event log

```python
type SessionEvent = (
    TurnStart | TurnEnd | StepStart | StepEnd
    | UserMessageEvent | AssistantChunk | AssistantMessageEvent
    | ToolCallEvent | ToolResultEvent
    | ExtensionEvent          # registered by name; compaction, hooks, goals
)
```

Rules, enforced not documented:

1. Append-only, contiguous sequence numbers, lossless JSON. `append()` validates
   serializability at the source — a non-serializable payload is rejected where
   it is produced, not where it is read back.
2. `derive_messages(log)` is the **only** way model history is produced. There is
   no second store.
3. **Every model-visible input is an event.** A runtime assertion compares the
   assembled request against a re-derivation from the log and raises on
   divergence. Enabled in dev and test, sampled in production.
4. Raw `AssistantChunk` events are kept — token-faithful replay is what makes
   run-reattach and post-hoc analysis possible.

Everything else follows: fork is a log prefix, resume is replay, compaction is an
event pair, telemetry is a projection.

### 4.2 The turn

```text
turn/start
  claim: one queued message + any pending next-step input
  assemble: prompt sections + tool schemas (scoped to this agent)
  pre_step waterfall -> reject | enter(messages)
     step/start
     append entered messages as user/message
     history = derive_messages(log)
     request waterfall -> llm stream -> assistant/chunk* -> assistant/message
     for each tool call: pre_execute -> execute -> post_execute -> tool/result
     step/end
     more owed? -> claim -> next step
  turn_stopping (serial)
turn/end
```

Same shape as dsh, same guarantee: a rejected or empty first claim still closes a
durable turn that spent no step, so the log records the attempt.

### 4.3 Hooks — dsh's waterfall, cell-bot's typed returns

cell-bot's insight is that a decision hook's *return type* should make malformed
directives unrepresentable. dsh's insight is that a waterfall needs explicit
delegation. Merge them:

```python
class Hooks:
    async def on_turn_start(self, *, agent, turn) -> None: ...
    async def on_turn_end(self, *, agent, turn, reason) -> None: ...
    async def pre_step(self, *, messages: list[Message]) -> StepDecision: ...
    async def pre_tool_call(self, *, call: ToolCall) -> str | None: ...      # refuse
    async def transform_tool_result(self, *, call, result: str) -> str | None: ...
    async def post_tool_call(self, *, call, result: str) -> None: ...
```

`HookChain` semantics, taken from cell-bot unchanged: observers all run; first
non-None decision wins; ordering *is* precedence; an exception is logged and
contributes nothing, so **a decision hook fails open**.

Two corrections to cell-bot's version, both from its own honest gap list:

- **Hooks get a timeout.** `HOOK_TIMEOUT_SECONDS` per call; a timeout is logged
  and treated as "contributed nothing". A slow hook must not stall every other
  conversation.
- **Blocking-call detection in dev.** A hook that does sync I/O trips a warning.

### 4.4 Tools

```python
@dataclass(frozen=True)
class ToolDefinition[ArgsT]:
    name: str
    description: str
    input_schema: dict                 # what the model is told
    parse: Callable[[dict], ArgsT]     # raw -> typed
    execute: Callable[[ArgsT, ToolRun], Awaitable[ToolOutcome]]
    timeout_s: float | None = None     # never on the wire
    concurrency_safe: bool = False     # opt-in, defaults closed
    present: Callable[[ArgsT, ToolOutcome], Card] | None = None   # UI, never model
```

`schemas()` emits `{name, description, input_schema}` **by allowlist**. Adding a
field to `ToolDefinition` cannot leak it to the model.

`ToolOutcome` is typed (`Ok(content, meta) | Failure(code, message)`), and the
wire projection renders `Failure` as cell-bot's tolerant `"error: …"` string so
the model can recover. The guardrail keys on the typed code, not on string
prefix matching — that removes the one fragility in cell-bot's design ("a tool
executor that reports failure some other way is invisible to the failure
detectors").

`Toolbox` keeps cell-bot's live resolution: static tools plus `providers`
re-queried each turn, with `narrow(mode, patterns, provider)` wrapping rather
than materializing.

### 4.5 Seams

Six Protocols, each with one local provider at v1:

| Seam | Consumers | Why it matters |
|---|---|---|
| `FileSystem` | `read`, `write`, `edit`, `str_replace` | swap → all file tools move |
| `Subprocess` | `glob`, `grep`, shell providers | ripgrep spawns here, never through a shell |
| `Shell` | `bash` | local now, sandboxed/remote later |
| `Sandbox` | wraps argv before spawn | the approval story attaches here |
| `Subagent` | `subagent`, `subagent_fork` | fork-in-process first |
| `Storage` | persistence, spill | JSONL now, SQLite behind the same Protocol |

Point `FileSystem` + `Subprocess` at a remote and every file/search/shell tool
follows, with no tool changes. That is the whole payoff of the seam discipline
and the reason to pay for it in v1.

## 5. Build order

Owned by [PHASES.md](./PHASES.md). The organizing rule: **every phase is a
capability you can demo.** Infrastructure is never its own phase — it arrives
inside the first phase that needs it, sized for that one consumer.

**cell-harness is a chat product**, cell-bot shaped — a browser UI,
conversations, an agent catalog, capabilities arriving through MCP. Not a
terminal coding harness. That decision drives the ordering.

| # | Phase | Demo at the end |
|---|---|---|
| 1 | It answers | `harness run "explain X"` streams a reply |
| 2 | It uses tools | Calls a tool, uses the result, answers |
| 3 | It remembers | Conversations persist; resume one after a restart |
| 4 | **You can chat with it** | Browser UI. Send, stream, stop. Refresh mid-turn and keep watching |
| 5 | It uses your tools | Add an MCP server in settings; its tools work next turn |
| 6 | It follows instructions | Attach a skill; it loads and applies it |
| 7 | You can steer it | Correct it mid-turn without restarting |
| 8 | It doesn't get stuck | A runaway tool loop is stopped |
| 9 | It picks the right specialist | Multiple agents; the right one answers each turn |
| 10 | It handles long conversations | 200 turns without hitting the context window |
| 11–13 | *(optional track)* | Files, shell, subagents — only if the product asks |

Phases 1–4 are the product. 5–8 make it capable and safe. 9–10 make it better
than cell-bot. The optional track is what a coding harness would need and a chat
product may never want — cell-bot ships a real product without any of it.

The mechanisms in §2 and §4 land where they are first needed: `Events` in phase 2
(the tool pipeline is the first thing needing interception), `Scope` in phase 4
(the first runtime agent teardown), `Layered` in phase 13 (the first time a plugin
registers into *one agent's* world). Per-agent tool *selection* in phase 9 needs
no layers — filtering the provider at compose time is simpler and correct.

## 6. Practices adopted from day one

From dsh:

- **Generated docs with a CI verification gate.** A `tool-catalog.md` produced by
  *booting* each tool and reading `schemas()`, plus a completeness guard that
  fails when a tool module is missing from the generator manifest. Drift fails
  the build.
- **An event producer/consumer map.** In an event-driven system this is the file
  that keeps it comprehensible.
- **A "where new behavior goes" table.** Goal → mechanism. Changing the loop
  means updating the map. Cheapest possible defense against ad-hoc extension
  points.
- **A prompt-cache impact note on every change that touches prompt assembly.**

Not adopted: dsh's `notes/` directory of design notes referenced by path from code
comments. At their size a decision needs somewhere to live that is not a 200-line
comment; at ours the reasoning fits beside the code that embodies it, and a second
place to look is a second place to fall out of date. The one note this project
wrote was folded back into the comment it was explaining.

Not adopted: dsh's `AGENTS.md` name, with `CLAUDE.md` symlinked to it. One rules
file is right; two names for it is a cross-tool convenience we do not need yet.
`CLAUDE.md` is the real file.

From cell-bot:

- **The house rules verbatim** (`CLAUDE.md`): KISS/YAGNI, surgical changes, no
  truncating user-facing strings, typed boundaries and fail closed, explicit over
  implicit defaults, one setting one place to look.
- **The comment discipline.** Non-obvious lines carry the *reason*; lines that
  exist because of a bug carry the bug. This is what makes the codebase
  extensible by someone who did not write it — including an agent.
- **Prompt text treated as code**, with the observed failure recorded next to the
  wording that fixes it.
- **Tests that assert two things stay in step** (template dir ↔ prompt enum,
  tool modules ↔ catalog manifest), not just that code works.

## 7. Decisions

### Settled

1. **Product shape: a chat product**, cell-bot shaped — browser UI,
   conversations, agent catalog, capabilities via MCP. This is the decision the
   others hang off. It moves the web UI to phase 4, MCP to phase 5, and the
   router into the plan; it moves file/shell tools and subagents into an optional
   track that may never ship.
2. **Python**, not TypeScript + Cordis. We need reversible registration and
   waterfall dispatch, both small in Python
   ([docs/without-cordis.md](./docs/without-cordis.md)). Adopting Cordis would
   mean rewriting cell-bot's Python to inherit DI and hot reload we do not need,
   from a framework in developer preview.
3. **The router ships** (phase 9). A multi-agent catalog is exactly what a chat
   product wants, and routing answers a different question from delegation —
   "who should answer this?" rather than "run these parts in parallel."
4. **JSONL, not SQLite** — reverted after reading how dsh actually does it. My
   SQLite argument was that a chat product must list conversations and a
   directory of files answers that poorly. It doesn't: dsh puts the
   `SessionHeader` on **line 1 of the log**, so listing reads one line per file
   and never parses a log. SQLite stays the answer for searching message
   *content*, which is not phase 3. Both remain behind `Persistence`.

5. **REST, not dsh's RPC gateway** (phase 4). Their actions surface is
   `POST /api/<namespace>/<method>` with an `{args}` payload, generated by Typert
   — compile-time TypeScript analysis that turns `@Remote`-decorated host methods
   into typed client methods with schemas and codecs. Without the generator the
   shape buys nothing: it is a namespace dispatcher in front of six endpoints.
   What we *do* take is their insistence that actions and event streams stay
   separate protocols (`docs/api-gateway.md` §Boundaries).
6. **SSE, not dsh's WebSocket mux** (phase 4). They run two downlinks,
   `/api/events.mux` and `/api/events.host`, because they multiplex many
   concurrent stream types — session events across several agents, plus "host
   frames" for settings, MCP and skills changes. We have one stream type,
   server→client only, which is exactly SSE's shape, and SSE is readable
   in-process by `httpx.ASGITransport` where a WebSocket needs its own harness.
   **Revisit at three or more concurrent stream types** — phase 5's MCP status and
   phase 6's skills changes are their host frames, and that is the trigger.
7. **A messenger queues; it never refuses** (phase 5). cell-bot's `409` is
   right for a browser, which can grey out its composer, and wrong for a phone,
   which cannot stop someone typing. hermes-agent makes this a three-way policy
   (`queue` | `steer` | `interrupt`) and defaults text to `queue`; duta-ilmu
   enforces per-conversation FIFO by construction. We ship `queue` alone —
   `steer` mutates a turn already running and needs dsh's durable inbox, which
   is phase 9.
8. **The channel seam is extracted, not designed** (phase 6). hermes-agent runs
   twenty platforms behind one `BasePlatformAdapter` and models its own HTTP API
   as one of them; duta-ilmu keeps its widget on a separate path entirely. We
   follow Hermes, but only after Telegram exists — the browser streams
   token-by-token from the raw event log while Telegram gets one finished
   message, and a contract spanning both is not guessable before writing both.
9. **The session log is the run's event buffer** (phase 4). It is already
   append-only with its index as a stable cursor, and the loop appends before it
   yields. So one cursor means the same thing to a disk snapshot and a live
   stream, the UI has one renderer, and there is no second copy to keep in step —
   the same argument that put `derive_messages` in phase 1 rather than a message
   list.

### Still open

10. **Serial vs parallel tool dispatch.** Ship serial. `concurrency_safe` has no
   reason to exist until the fs seam (phase 11) makes overlap meaningful and
   testable — and phase 11 is optional.
11. **How much of the run layer survives a multi-process future.** Phase 4 ships
   one process and no lease: reclaiming a *process's* runs cannot be exercised,
   and phase 3's repair-on-resume already covers a single-process crash. When a
   second process exists, the heartbeat + reclaim design is cell-bot's.
12. **Whether the optional track (13–15) is ever built.** Decide before phase 11,
    not during. cell-bot ships a real product without any of it; every capability
    arrives through an MCP server.

---

**Next step:** phase 1. See [PHASES.md](./PHASES.md).

The one discipline to hold: the loop reads its history from
`derive_messages(log)`, never a list it accumulated. That is what keeps phases 3,
10, and 13 cheap instead of rewrites.
