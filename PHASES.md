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

## Status

**Done: phases 1–9 and 11, and twelve insertions:** 1 code mode, 2 places from
Instagram reels, 3 skills (8.1–8.2), 4 select-then-call (`tool_reference`),
5 Discord, 6 MCP Apps, 7 markets, 8 `get_location`, 9 memory, 10 web search
(`exa`), 11 approvals, 12 skill upload. Their plans were deleted once built; read
them with `git show f9865e4:PHASES.md`.

**Open:** 10, deferred until a second agent is wanted; 15, begun (skills from
chat, the route ↔ tool table); and the build order below.

## Build order

What to build next, taken from [Rakazo](./docs/rakazo.md) (commit `df708491`):
cheap and unlocking first, large or blocked last. A feature gets a phase section
when it starts; the ones that already have one name it. Rakazo paths are under
`packages/adapters/src/` unless they say otherwise.

| # | Feature | Phase | Needs first | Rakazo |
|---|---|---|---|---|
| 1 | **Tap an answer**: one question, 2–4 buttons, and the turn waits | | | `builtin-tools.ts:342` |
| 2 | **Asks before it writes**: a tool named send, delete, pay… asks first; read verbs pass; an unknown verb asks | | | `packages/core/src/action-approval.ts` |
| 3 | **Scheduled jobs**: on Telegram, silent when nothing changed | 20 | | `schedule-tools.ts`, `silent-reply.ts` |
| 4 | **Helpers inside a turn**: up to 4 at once, each reports back | 14, see its note | | `pi-runtime.ts:1069-1119` |
| 5 | **Connect hosted apps by URL**, with sign-in | | 2 | `remote-mcp.ts`, `mcp-oauth.ts` |
| 6 | **Huge results don't break a chat**: a tool result is cut at 12,000 characters | | | `pi-runtime-limits.ts:29-63` |
| 7 | **API keys it never sees**: a masked card stores the key; the server adds it to the request | | | `docs/bot-secrets.md` |
| 8 | **Charts in chat**: an MCP App draws the chart from the data | | | `builtin-tools.ts:407` |
| 9 | **Files it hands you**, versioned by name, with a tab to reopen them | | | `thread-artifacts.ts` |
| 10 | **Reminds you when it is waiting** on you, then gives up | | 3 | `stuck-work.ts` |
| 11 | **A second opinion**: a cheap model checks a risky call and can only make it ask | | 2 | `auto-review.ts` |
| 12 | **It browses on its own computer**, live view in the app | 17 | Docker | `computer-*.ts`, `browser-tools.ts` |
| 13 | **You take over its browser** for a captcha, then press Done | 18 | 12 | `takeover-resume.ts` |
| 14 | **Saved website logins**, typed only on their own site | | 7, 13 | `docs/bot-secrets.md` |
| 15 | **Teach it by showing**: you do a task once, it does it next time | | 13 | `teaching-session.ts` |
| 16 | **Several bots that talk** and hand work over | | phase 10, see its note | `builtin-tools.ts:889-1008` |
| 17 | **Webhooks start it**: the payload is fenced as untrusted data, and its side effects always ask | | 3, a signed-in public URL | `apps/api/src/webhook-inbound.ts:52-56` |
| 18 | **It sees its screen** | 19 | 12, a vision model | `pi-runtime.ts` |

Also open, outside this order: 12 (files), 13 (commands), 15 (begun) and 16
(steering), in the optional track below.

## Why this order

A chat product's constraints differ from a coding harness's:

| | Chat product (us) | Coding harness |
|---|---|---|
| The UI is | the product — pull it to phase 4 | optional |
| Capabilities arrive via | **MCP** (phase 7) | built-in fs/shell tools |
| A turn is | often long (a download, a deck) — runs must outlive connections | usually short |
| Multiple agents means | **routing** to a specialist (phase 10) | delegating to subagents |
| `bash`/fs tools are | optional, late | phase 2 material |

This is why phases 12–14 are marked optional. cell-bot ships a real product with
none of them — every capability arrives through an MCP server.

## Where the infrastructure lands

Nothing below is a phase. Each is written as part of the capability that needs it.

| Mechanism | Born in | Why then |
|---|---|---|
| Heartbeat, lease, reclaim | ~~4~~ **when a 2nd process exists** | Reclaiming a *process's* runs is a multi-process problem. One server, and phase 3's repair-on-resume already covers the single-process crash |
| Prompt sections | ~~8~~ **10** | Skills turned out to contribute nothing to the prompt — the catalog rides on the tool. Personas are the first template with a variable |
| Seams (`FileSystem`, `Subprocess`) | 12 | Two providers is when an interface earns its keep |
| `Layered` (scoped registries) | 14 | The first time a plugin registers into *one agent's* world |
| Durable inbox (`followup`/`steer`/`inject`) | 16 | Phase 5 queues at the channel, which is enough while a correction can wait for the next turn. `steer` mutates a turn already running, so it needs dsh's session-event inbox |

On `Layered`: per-agent **tool selection** (phase 10) does not need layered
registries. cell-bot does it by filtering the provider at compose time
(`narrow(mode, patterns, provider)`), which is simpler and correct. `Layered` is
only needed when a plugin registers into one agent's world — which is subagents.

**Dependency graph** of the open phases:

```
10 ── 15            (agent_* tools)
12 ── 13 ── 14      (optional track)
16                  (optional)
17 ─┬─ 18           (computer track, needs Docker)
    └─ 19           (needs a vision model)
20                  (needs nothing open)
```

---

# Phase 10 — It picks the right specialist

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
not frozen at compose time. Scoped registries are a phase-12 concern.

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
  recorded in `docs/prompt-failures.md` beside the constant that fixed it.
- Deleting the default agent is refused; a conversation whose agent was deleted
  resolves to the default.

**Acceptance.**
- Every failure path leaves the conversation on its current agent.
- A model answering with an agent *name* fails validation rather than resolving.
- An agent sees only its own skills; the `<available_skills>` index proves it.
- Routing does not delay the first token beyond one call.

**Rakazo's several bots (build order 16).** Rakazo's lasting bots, each with its
own chat and memory, hand work over with `message_bot` and, in a group chat,
`handoff_to_bot` (`builtin-tools.ts:971-1008`). This phase refuses handoff tools
for routing; which shape 16 takes is decided when it starts.

---

# Optional track — agentic capabilities

Phases 12–16 are worth building only if the product wants them. cell-bot ships
without any of them. **Decide before starting 12**, not during. 15 and 16 depend
on none of 12–14 — they are here because they are capabilities the product may
not want, not because they need a shell.

## Phase 12 — It reads and writes files *(optional)*

**Ships.** `seams/fs.py`, `seams/subprocess.py`, local providers,
`read`/`write`/`edit`, `glob`/`grep` via packaged ripgrep,
`fs/observation_policy.py`, `concurrency_safe`.

**Key contracts.** `glob`/`grep` spawn ripgrep **through `Subprocess`, never a
shell**. Read-before-write is a separate policy listener, not a check inside the
tools. Reads overlap; writes don't.

**Acceptance.** Pointing `FileSystem` + `Subprocess` at the test suite's in-memory
provider moves all five tools with **zero tool changes**. ~800 lines.

## Phase 13 — It runs commands *(optional)*

**Ships.** `seams/shell.py`, `seams/sandbox.py`, local providers,
`tools/native/bash.py`, `jobs/` + `job_*` tools, `interaction/approval.py`.

**Key contracts.** Sandbox **wraps argv before spawn**. Presets `read-only` /
`workspace-write` / `full` chosen explicitly, never defaulted. Background work
registers with the generic `Jobs` runtime; completion arrives via `inject()`.

**Risk.** Platform-specific and the most likely phase to overrun. POSIX only;
defer Windows. ~800 lines.

## Phase 14 — It delegates *(optional)*

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

**Rakazo's lighter shape (build order 4).** One `run_subagent(name, task)` tool:
the helper gets the same tools minus delegation, runs one level deep, at most 4
at once, and returns its answer as the tool result (`pi-runtime.ts:89`,
`:1069-1119`). Build order 4 chooses between it and the layered design above,
and decides how a helper's steps are logged, before it starts.

## Phase 15 — It operates itself *(optional)*

**Demo.** The model has just walked a reel to a place across two servers. "Save
that as a skill." It calls `skill_save`; `/skills` lists it; a new
conversation's `skill` enum offers it and `/name` invokes it. Hermes's
`skill_manage` and OpenClaw's proposal queue are the precedents — a chat
product's agent writes its own instructions.

**The principle.** A feature we build for the system ships with a tool for the
model, or a recorded reason it does not. The API is the only surface for
people; after this phase the tool list is the same surface for the model.

**Shipped so far.** `skill_save` and `skill_delete` in `tools/native/skills/`,
the path the phase planned, over `SkillService`'s
own `save` and `delete`. They are withheld from scripts, offered every request,
and listed in `approval.tools`: insertion 11's gate is the one this section waited
for, so a skill write asks first on every channel. `tests/unit/test_every_feature_has_a_tool.py`
is the stay-in-step test, and it covers every `config.json` section as well as every
changing route. Written by hand, never generated from the routes: nine of the
eighteen must never be tools, answering an approval card and stopping the reply
among them. `skill_write_file` writes one bundled file under the upload's own path
rules plus what the reader would refuse, so a skill arrives with its references and
scripts; a TypeScript script runs by passing its text to `execute_typescript`, in the
same sandbox, granted nothing. Next is MCP connect and disconnect,
no longer cut, because the gate exists; `conversation_*` is superseded by insertion 9.

**Depends on.** 8 (the editor service and the `/skills` page it shares); 10 for
`agent_*`.

**Ships.**
- `tools/native/skills/` — `skill_save(name, text)`, `skill_delete(name)`, thin
  over `skills/editor.py` — the same service `PUT`/`DELETE /api/skills/{name}`
  call, so the page and the model have one validator and one write path.
- `tools/native/conversations/` — `conversation_search(query)`,
  `conversation_read(id)`: read-only, the model's cross-conversation memory
  until phase 11 gives it a better one.
- `tools/native/mcp/` — `mcp_servers()`: which servers are connected, which
  failed and why, so the model can tell a person "places is not connected"
  instead of failing a program.
- After 10: `agent_save`, `agent_delete` over `agents/service.py`.
- A stay-in-step test: every mutating `/api` route maps to a tool or to a line
  in a `NOT_EXPOSED` table with the reason.

**Key contracts.**
- **Self-modification is a visible call.** Every `*_save`/`*_delete` is
  withheld from code mode, like `skill`, so a write to the model's own
  instructions is its own `tool/call` in the timeline, never a line inside a
  program.
- **The tool can do exactly what the page can.** Same validation, same
  editable-root rule, same refusals — rendered as a `Failure`, never a raise. A
  skill the page would refuse, the model cannot save.
- **Nothing that spawns or destroys without an approval gate.** MCP
  connect/disconnect stays cut for phase 7's reason (a model-callable connect
  tool spawns processes); conversation delete and config edits likewise. They
  wait for phase 13's `interaction/approval.py`, which must not fail open.
- Reads are offered to scripts; writes are not.

**Acceptance.**
- The demo, end to end, with the saved skill visible on `/skills` and the write
  visible as a tool card in the conversation that made it.
- `skill_save` with a body the page would reject returns the page's message as
  a `Failure`.
- `skill_delete` on a project-root skill is refused naming the root.
- `list_functions` never lists a `*_save`/`*_delete`; a script calling one is
  refused.
- The route ↔ tool table test fails when a mutating route is added without a
  tool or a reason.

**Cut, and why.** `mcp_connect` (phase 7's cut stands), `conversation_delete`
(destructive, no gate), `settings_*` (secrets), a proposal queue for
model-written skills (OpenClaw) — the timeline is the review surface; if someone
wants approval before a write, that is phase 13's gate, not a second queue.
~500 lines.

---

# Cross-cutting, from phase 1

Not phases. They start immediately and run throughout.

| Practice | From |
|---|---|
| `CLAUDE.md` — project rules, loaded into every session | cell-bot |
| cell-bot's house rules verbatim | cell-bot |
| Comment discipline: no comments; a reason lives in a name, a type, a test or a docs file | cell-bot |
| Generated `tool-catalog.md` by **booting** each tool, with a completeness guard | dsh |
| A "where new behavior goes" table, updated whenever the loop changes | dsh |
| Tests that assert two things stay in step (templates ↔ enum, tools ↔ manifest) | cell-bot |

---

## Phase 16 — You can steer it *(optional)*

**Demo.** It's going the wrong way; type a correction and it adjusts at the next
step instead of restarting.

**Moved here from the core arc, last of all.** Of the three verbs, `followup`
already exists — it is the channel `pending` queue from phase 6 — and `inject`
has no caller: nothing runs in the background and reports back later. Only
`steer` is new, and a correction that waits for the turn to end is tolerable.

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

# Computer track — a bot with its own computer

What [Rakazo](./docs/rakazo.md) does — a bot with its own Linux desktop and
Chrome, a live view of it, and a person who can take over — reached the way every
capability is reached here: an MCP server, a skill, and an MCP App.
`backend/harness/` gains code only in 17 (trimming old pages), 18 (one client
tool), 19 (an image block) and 20 (a scheduler). Docker is a requirement of the
`computer` server, not of the harness: without it the server fails to connect and
the rest of the product runs. 20 needs no computer; it is here because Rakazo is
where it comes from. Rakazo paths below are under `packages/adapters/src/`.

## Phase 17 — It browses on its own computer

**Demo.** "Find the cheapest Pokémon 30th Celebration ETB on Lazada." The bot
opens a real Chrome on its own desktop, reads the results as text, clicks into
listings by their refs and answers with prices and links. The tool card's "Open
app" link shows that desktop live.

**Depends on.** 7, insertion 6 (MCP Apps).

**Ships.**
- `mcp-servers/computer/` — one uv project, its own 80% gate:
  - the container: Rakazo's published image, started on the first call and reused
    after; stopped after `idle_minutes` without a call; Chrome profile and home on
    a named volume, so a login survives a stop
  - `browser_navigate(url)`, `browser_snapshot()`, `browser_act(actions)` — up to
    24 `click`, `fill` or `type` steps, each on a ref (`builtin-tools.ts:221`) —
    `docker exec` of the image's own `rakazo-page-browser`, text in and text out
  - `screen()` and `click(x, y)` / `type(text)` / `key(name)` — the image's control
    endpoint, for the view only
  - `ui://computer/screen` — an MCP App that redraws `screen()` through
    `tools/call`, sysmon's pattern; view only in this phase
- `agent/compaction/` — old pages trimmed on every step, not only at 80% of the
  window: the newest 3 page results over 1,000 characters stay, a failure never
  counts, and the rest are cleared by the `compaction/prune` event compaction
  already writes (`pi-runtime.ts:1413-1466`). The page tools are named in config;
  the harness knows no server's tools.
- `skills/browse-web/` — when to browse and when `exa` is enough; snapshot before
  acting; a captcha or a login means stop and say so
- `config.json` declares `computer`; its control token goes in `config.local.json`

**Key contracts.**
- **Text first; the model sees no screenshot.** `browser_snapshot` returns page
  text and up to 80 numbered elements, which a text-only model such as
  `ilmu-glm-5.1` can act on. Screenshots for the model are phase 19.
- **One computer, shared by every conversation.** An MCP call carries no
  conversation, and this is a one-person product. A computer per conversation or
  per agent is a later phase, not a parameter now.
- **The control path never depends on the viewer.** The server reaches its
  container through ports it published on `127.0.0.1` when it created it.
  Rakazo's supervisor joins a computer's network only when a viewer opens, and
  its bots' clicks failed until then ([docs/rakazo.md §4](./docs/rakazo.md)).
- **We reap what we spawn**, for containers too: stopped on shutdown, and one left
  by a previous run is found by its label and reused, never duplicated.
- **A failed step is never repeated blindly.** The result says which steps
  completed and whether the outcome is uncertain; the model looks at the page
  before going on (`browser-tools.ts:93-100`).
- **The view asks for the next screen only after the last one arrives**, never on
  a timer: its calls and the model's share one connection that serves one call at
  a time ([mcp-servers/README.md](./mcp-servers/README.md)), so a timer would queue
  screens in front of the bot's next click.
- The view's tools say "App-only" in their description, as sysmon's do; keeping
  them out of `list_functions` is mcp-apps.md §7's deferred item, and this is its
  second caller.

**Acceptance.**
- With a fake Docker client: the first call starts one container, the second
  reuses it, the idle stop fires, shutdown stops it, a labelled leftover is reused.
- A fixture page's snapshot lists its elements with refs; acting on a stale ref is
  a typed failure, never a guess; 25 steps in one `browser_act` are refused.
- Ten snapshots in one turn leave three in the request; a failed one is not counted.
- `screen()` returns one PNG `ImageContent`, and the view is served under the
  default CSP: it declares no `connectDomains`.

~700 lines.

## Phase 18 — You can take over its browser

**Demo.** The page shows a captcha. The bot stops and says why; the chat shows a
card with "Open computer" and Done — a button on Telegram. You solve the captcha
in the app, press Done, and the bot carries on.

**Depends on.** 17, insertion 8 (client tools), insertion 11 (the card).

**Ships.**
- `tools/client/hand_over.py` — `hand_over(reason)`, a client tool whose outcome
  is `Pending`, as `get_location`'s is
- `mcp-servers/computer/` — `hold(on)` for the view; while held, the model's
  browser tools answer "the person has the computer" and send no input, and the
  app turns interactive: a click becomes `click`, a keypress `type` or `key`
- the card in `frontend/`, and the button on Telegram and Discord

**Key contracts.**
- **Done resumes with "snapshot before acting", nothing else.** What the person
  did on the page is read again, never assumed.
- **It ends one of two ways**, as Rakazo's does (`takeover-resume.ts:18-34`). Done:
  "The user finished. Continue from where you left off. Do not request takeover
  again." Typing instead, or the hold expiring: the user skipped, so continue
  without treating the login as complete.
- **Held belongs to the server**, cleared by Done or after `hold_minutes` without
  input, so a closed tab cannot strand the bot.
- A password is never asked for in chat; `browse-web` says hand over instead.

**Acceptance.**
- `hand_over` ends the turn `pending`; Done resumes it; typing a message instead
  writes `SKIPPED`, as for every client tool, and the model is told the login is
  not complete.
- While held, `browser_act` returns the held message and the fake container
  received no input.

~400 lines.

## Phase 19 — It sees its screen

**Demo.** A page its text cannot describe — a canvas, a map, a picture captcha.
The bot takes a screenshot, says what it sees, and clicks by coordinates.

**Depends on.** 17, and the decision gate: a model that accepts images.

**Ships.**
- `llm/messages.py` — an `Image` block beside `Text` and `ToolReference`, and the
  OpenAI adapter's mapping for it. Check the endpoint first: many
  OpenAI-compatible endpoints refuse an image inside a `tool` message, and then it
  rides a user message after the result.
- `mcp/tool.py` — `ImageContent` becomes an `Image` block, not `[image …]` text
- `session/` — the bytes in `blobs/<sha256>.png` beside the session, the event
  holding the hash: still logged, and the JSONL stays small. This answers the
  open question in mcp-apps.md §7.
- `session/derive.py` — only the latest two screenshots reach the model; older
  ones become a one-line note
- `computer` — `screenshot()` and `act(steps)` offered to the model; a screen that
  has not changed returns "unchanged" and no image

**Key contracts.**
- `llm.vision: false` withholds the screenshot tools: an image nobody can see is
  not offered.
- Pruning is a function of the log, so the same log builds the same request and
  the cached prefix holds.

**Acceptance.** An image survives log, repair and derive; pruning keeps exactly
two; a reload reads the same bytes by hash; the tools are withheld without
vision. ~600 lines.

## Phase 20 — It works while you're away

**Demo.** "Every Monday at 9, tell me on Telegram if AAPL drops under $200." On
Monday it runs with nobody watching, using `markets`, and messages you only if
it dropped.

**Depends on.** 5.

**Ships.**
- `routines/` — the store (`~/.harness/routines.json`), and a scheduler task
  started in the composition root
- `schedule_create`, `schedule_list`, `schedule_cancel` — create goes through the
  approval gate
- a run that no person started: a `routine/run` event says so, and the gateway
  delivers the reply to the routine's chat

**Key contracts.**
- **A missed run runs once.** A Mac asleep through three Mondays runs the routine
  once on waking, not three times.
- A routine that reaches `hand_over` waits and notifies; it never blocks the next
  routine.
- **Silent when nothing changed.** A run whose reply is exactly `NO_RESPONSE`
  posts nothing (`silent-reply.ts`).
- **A routine cannot make routines.** A routine run is not offered
  `schedule_create` (`schedule-tools.ts:16-21`), and it replies in the chat that
  created it.
- Creating a routine asks first. Rakazo does not ask
  (`packages/core/src/action-approval.ts:20`); the phase 15 gate says every
  model write asks.

**Acceptance.** With a fake clock: a run fires once per due time, a restart never
duplicates one, delivery reaches the chat, and creating a routine asks first. A
`NO_RESPONSE` run posts nothing; a routine run's tool list has no
`schedule_create`. ~600 lines.

**Later, not phases yet.**
- A computer per conversation or per agent — the harness must first pass the
  conversation on an MCP call.
- Teammates that hand work to each other — build order 4 and 16.
- A phone per bot — declined in the decision gates below.

---

# Decision gates

| Before | Decide | Default if silent |
|---|---|---|
| Phase 12 | Build the optional track at all | **Defer** until the product asks |
| Phase 15 | Which mutations the model may make without an approval gate | ~~Skills only~~ **None** — skill writes ask first too, the person's call once insertion 11's gate existed |
| Phase 17 | Reuse Rakazo's computer image or build our own | **Reuse** `ghcr.io/elie222/rakazo/computer` (Apache-2.0, published); fork it only when we need a change it will not take |
| Phase 19 | Which vision model | **None** — the phase does not start until `llm` points at a model that accepts images |
| — | A phone per bot | **No** — 0.8–3.2 GB per phone measured against 0.6 GB for the desktop ([docs/rakazo.md §5](./docs/rakazo.md)); mobile websites go through phase 17's browser |
