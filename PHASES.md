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

**Done: phases 1–9 and 11, and nineteen insertions:** 1 code mode, 2 places from
Instagram reels, 3 skills (8.1–8.2), 4 select-then-call (`tool_reference`),
5 Discord, 6 MCP Apps, 7 markets, 8 `get_location`, 9 memory, 10 web search
(`exa`), 11 approvals, 12 skill upload, 13 tap an answer (`ask_user`, build
order 1), 14 asks before it writes (a server's tool asks first unless its
name has a read verb, build order 2), 15 helpers inside a turn (`run_subagent`,
build order 4), 16 long results cut for the model (12,000 characters, build
order 6), 17 API keys it never sees (`ask_for_secret` saves a key into one
keyring, sealed as Rakazo seals it, and lets the asking bot use it; the Keys
page lists every key and each bot's page the keys it may use;
`fetch_with_secret` sends a key only to its site, build order 7), 18 a computer
the bots share (Rakazo's image in Docker on this machine; the bots read and click
pages as text; the Computer page streams its screen over VNC through the app's
relay, so any device can watch it, and takes control on open; `hand_over` pauses
a bot for a step only you should do; a terminal and files beside the screen;
build order 12 and 13, phases 17 and 18), 19 a skill's scripts run in that
computer (`computer__shell`, with the chat's files and the skills shipped with the
app at their own paths, PhotoCraft on the Mac reachable from its commands, `view_image` to see
what they save; the comic translator is the first such skill. Known risk: the
app has no login, and the computer reaches every port on this Mac through
`host.docker.internal`, so a bot allowed to run commands can call the app's API
as the person; a network guard such as Tailscale does not cover it;
phase 13, built in the computer, spec in `docs/specs/comic-skill/`). Their plans
were deleted once built; read them with `git show f9865e4:PHASES.md`.

**Open:** 10, begun (bots, each with its own instructions and one chat, made
from a form or from chat, groups of them that take turns, and bots that message each other); 15, begun (skills from chat, the route ↔ tool
table); 17, begun (old pages trimmed on every step, and the `browse-web`
skill); and the build order below.

## Build order

What to build next, taken from [Rakazo](./docs/rakazo.md) (commit `df708491`):
cheap and unlocking first, large or blocked last. A feature gets a phase section
when it starts; the ones that already have one name it. Rakazo paths are under
`packages/adapters/src/` unless they say otherwise.

| # | Feature | Phase | Needs first | Rakazo |
|---|---|---|---|---|
| 5 | **Connect hosted apps by URL**, with sign-in | | 2 | `remote-mcp.ts`, `mcp-oauth.ts` |
| 8 | **Charts in chat**: an MCP App draws the chart from the data | | | `builtin-tools.ts:407` |
| 9 | **Files it hands you**, versioned by name, with a tab to reopen them | | | `thread-artifacts.ts` |
| 10 | **Reminds you when it is waiting** on you, then gives up | | 3 | `stuck-work.ts` |
| 11 | **A second opinion**: a cheap model checks a risky call and can only make it ask | | 2 | `auto-review.ts` |
| 14 | **Saved website logins**, typed only on their own site | | 7, 13 | `docs/bot-secrets.md` |
| 15 | **Teach it by showing**: you do a task once, it does it next time | | 13 | `teaching-session.ts` |
| 17 | **Webhooks start it**: the payload is fenced as untrusted data, and its side effects always ask | | 3, a signed-in public URL | `apps/api/src/webhook-inbound.ts:52-56` |
| 18 | **It sees its screen** | 19 | 12, a vision model | `pi-runtime.ts` |
| 19 | **Trusts a server you vouch for**: a server marked trusted in config has its read-only marks honoured, so memory's `build_context` and `recent_activity` stop asking; every other server stays on the name rule | | | none; VS Code's per-server trust and Codex's per-server approval mode |
| 3 | **Scheduled jobs**: on Telegram, silent when nothing changed | 20 | | `schedule-tools.ts`, `silent-reply.ts` |

Row 3 moved last on 2026-10-04, after helpers (4) and long results (6). When it starts, what
the research and a review found: the run goes in the conversation that made it,
as Rakazo's `wakeRoutine` does (`executor.ts:1013-1151`); a due time is written
past before the run starts, so a restart never runs it twice, and missed times
collapse into one run; cron is read on local wall time (`croniter`, MIT), so a
daylight-saving change does not move it an hour; a conversation is busy while a
chat's last reply is still being sent, not only while a turn runs, or that reply
goes out twice; compaction must count the routine's opening event as input; and
`/new` clears the chat in place, so a routine keeps its chat and loses only the
history before the clear.

Also open, outside this order: 12 (files), 13 (commands), 15 (begun) and 16
(steering), in the optional track below.

## Why this order

A chat product's constraints differ from a coding harness's:

| | Chat product (us) | Coding harness |
|---|---|---|
| The UI is | the product — pull it to phase 4 | optional |
| Capabilities arrive via | **MCP** (phase 7) | built-in fs/shell tools |
| A turn is | often long (a download, a deck) — runs must outlive connections | usually short |
| Multiple agents means | **bots** you pick, each with its own chat (phase 10) | delegating to subagents |
| `bash`/fs tools are | optional, late | phase 2 material |

This is why phases 12–14 are marked optional. cell-bot ships a real product with
none of them — every capability arrives through an MCP server.

## Where the infrastructure lands

Nothing below is a phase. Each is written as part of the capability that needs it.

| Mechanism | Born in | Why then |
|---|---|---|
| Heartbeat, lease, reclaim | ~~4~~ **when a 2nd process exists** | Reclaiming a *process's* runs is a multi-process problem. One server, and phase 3's repair-on-resume already covers the single-process crash |
| Prompt sections | ~~8~~ **10** | Skills contribute nothing to the system prompt. The catalog rides as a system-reminder on the first user message, from a step hook (issue #40). Personas are the first template with a variable |
| Seams (`FileSystem`, `Subprocess`) | 12 | Two providers is when an interface earns its keep |
| `Layered` (scoped registries) | 14 | The first time a plugin registers into *one agent's* world |
| Durable inbox (`followup`/`steer`/`inject`) | 16 | Phase 5 queues at the channel, which is enough while a correction can wait for the next turn. `steer` mutates a turn already running, so it needs dsh's session-event inbox |

On `Layered`: per-agent **tool selection** (phase 10) does not need layered
registries. cell-bot does it by filtering the provider at compose time
(`narrow(mode, patterns, provider)`), which is simpler and correct. `Layered` is
only needed when a plugin registers into one agent's world — which is subagents.

**Dependency graph** of the open phases:

```
10                  (begun: its Next list)
12 ── 13 ── 14      (optional track)
16                  (optional)
17 ── 19            (computer track: 17 begun; 19 needs a vision model)
20                  (needs nothing open)
```

---

# Phase 10 — Bots, each with its own instructions and one chat

**Demo.** You press New bot, pick a kind, finish the sentence and answer Bot
builder's questions, or ask Assistant for a bot in chat. It appears under Bots in the sidebar with its own chat and answers
there by its instructions.

**Reshaped on 2026-10-04, after Rakazo.** The router this phase planned (one
structured call per turn choosing among agents, cell-bot's `RouterAgent`) is
dropped: you pick the bot by opening its chat, as in Rakazo and LibreChat. One
chat per bot, as in Rakazo ("one bot has one continuous visible thread",
`VISION.md:59`).

**Shipped so far.**
- `bots/` — `Bot` (id, name, instructions, the keys it may use) in the file at `bots.path`, read on
  every call. A bot's chat id is the bot's id; only `BotService.members_of_chat`
  and `chat_of` rely on that. Assistant (`"assistant"`) is
  today's prompt, there from the first start, and cannot be archived or deleted.
  Bot builder (`"builder"`) is built in the same way and left out of the sidebar.
  Every chat is a bot's or a group's: an id that is neither is a 404 on every
  chat route.
- `bot/instructions` — the event that brings a bot's instructions into its
  chat, logged when a turn starts with instructions that differ from the last
  ones logged for that bot. It and `turn/start` carry the bot's id. The request
  and compaction both build the system prompt from it
  (`runtime/system_prompt.py`): the speaker's instructions, in a group the
  group note, then the fixed guidance.
- `/api/bots`, the sidebar's Bots and Archived, the Edit bot form.
- New bot — four kinds of bot to start from, as Rakazo's focus card offers four
  (`apps/api/src/onboarding.ts:32-61`); a pick puts a sentence in the message
  box to finish. Sending clears Bot builder's chat and sends it there. Its
  instructions ask up to two questions with `ask_user`, then call `bot_create`.
  Rakazo's card is scripted; Bot builder's questions come from the model.
- `bot_create` (`tools/native/bots/`) — `POST /api/bots`'s save as a tool. It asks
  first and is withheld from scripts and helpers; Rakazo's `spawn_bot` does not
  ask (`packages/core/src/action-approval.ts:19`).
- Clear — the Clear button and `/new` wipe a chat in place, as Rakazo's
  `clearThread` does (`packages/db/src/events.ts:257-342`): the turn stops, and
  `SessionService.clear` rewrites the chat's file to one `chat/cleared` line
  under the same id. Its numbering carries on (`SessionHeader.numbered_from`)
  and every streamed event carries its number (`id:`), so an open tab or a
  Telegram chat keeps its place.
- One chat per bot, as in Rakazo. Telegram and Discord write into Assistant's
  chat (`Channel.conversation_for`), and a chat app hears only the turns it
  started or the calls it was asked (`ChatState.asked`; Rakazo
  `packages/adapters/src/messaging-delivery.ts:87-90`). There is no
  conversation list, no way to start another chat, and no title.
- Archive, as in Rakazo (`Bot.archivedAt`): an archived bot and its chat are
  hidden and refused; the sidebar's Archived section restores one, or deletes
  it with its chat for good.
- Groups — two to six bots sharing one chat, kept in the bots file, made from
  the New group page. Your message lines up who speaks: the members you
  @mention, else every member in order, as Grok Bot's group "wakes each member
  in turn". They answer one after another inside one run, so Stop ends the
  discussion. A reply that @mentions a member puts it at the back of the line,
  at most 6 per message of yours (Rakazo's hop limit,
  `packages/core/src/bot-messages.ts:14`); a reply of exactly `NO_RESPONSE`
  is shown to nobody (Rakazo's `silent-reply.ts`). Who is next is worked out
  from the log each time (`bots/_turn_order.py`). Each bot reads your messages,
  its own turns in full, and the others' replies as your-side text tagged
  `<speaker name="…" />`, as LobeChat's `GroupRoleTransform` does; the
  `group/members` event carries the roster its group note is built from.
  Approvals and the tools a bot has read count per bot. Archiving or deleting a
  bot stops a discussion it is speaking in, as Rakazo's archive cancels the
  bot's runs (`packages/adapters/src/child-bots.ts:274-288`). In the chat each
  turn sits under the bot's name and colored initial, and its tool calls fold
  behind one "Done · N tools" line, as Rakazo's `ToolActivityDisclosure` does.
- Bot messages — `message_bot` writes a message into another bot's own chat,
  where a `bot/message` event opens a turn, and returns at once, as Rakazo's
  `message_bot` does (`packages/adapters/src/bot-messages.ts`). When that turn
  ends, its final reply goes back once into the sender's own chat as a
  `bot/message` of intent `result` and wakes it; nothing replies to a result.
  A chat busy with a turn takes the message when the turn ends. Each message
  carries its hop: a turn you started is 0, and a send past 6 is refused
  (Rakazo's `BOT_MESSAGE_MAX_HOPS`); the answer going back never is. The tool
  offers the active bots by name, rebuilt each request; it never asks first,
  is withheld from scripts and helpers, and refuses the sender itself and a
  group chat, where Rakazo hides it. A bot archived or deleted while a message
  waits for it drops the message with a warning (`runs/bot_messages.py`). The
  chat shows each one as "Message from X".

**Key contracts.**
- Model-visible means logged: a request's instructions come from the chat's last
  `bot/instructions` event, never from the bots file.
- An old conversation's request is byte-for-byte what it was before bots, and
  a bot's own chat sends the same request once turns carry bot ids
  (`tests/unit/test_bot_prompt.py`).
- Who speaks next in a group is a fold over the log, never stored
  (`tests/unit/test_turn_order.py`).
- A bot's message is logged in the chat it enters, and a turn's hop is read
  from the `bot/message` that opened it, never stored
  (`tests/unit/test_bot_messages.py`, `tests/integration/test_web_bot_messages.py`).

**Next.**
- An open chat shows a turn a bot's message started without a reload; today a
  tab follows only the turns it sent. Then a bot's message drawn as its own
  bubble, not the person's.
- Telegram and Discord hear Assistant when a bot's answer wakes it; a chat app
  hears only the turns it started.
- A message waiting for a busy chat survives a restart, as Rakazo's job
  reconciler retries it; today it lives in memory.
- A bot's message arriving while its chat waits on you skips that card, as
  your typing does; the hop count starts over after an approval; a dropped
  message tells the sender nothing.
- `message_bot` from a group chat, and Rakazo's `fyi` and `status` intents.
- `bot_create` with a first task, which needs the same turn no person started.
- A lead per group: only the lead answers your message and @mentions whoever
  it needs, as OpenMaus's lead mode does; taking turns stays the default.
- Rename a group, change its members, archive or delete it; an @ picker in the
  composer.
- Compaction in a group summarizes from the view of the bot that hit the
  limit; a neutral summary is its own piece.
- Per-bot model, skills and tools: every bot sees every skill today, so a skill
  that matches a message can pull a small model off its bot's instructions.

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

**Built differently, 2026-10-17 (insertion 19).** Commands run in the bots'
Docker computer through one `shell` tool, as Rakazo runs its bots' commands, not
on this Mac: there is no host shell and none of the presets below. What follows
is the original plan for a host shell, kept for when the product asks for one.

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

**Rakazo's lighter shape, built as insertion 15 (build order 4).** One `run_subagent` call
carries one to four tasks, `{ tasks: [{ name, task }] }`, run at once inside the
tool, as Hermes's `delegate_task(tasks=[...])` does; Rakazo instead runs several
calls of one step at once (`pi-runtime.ts:89`, `:1069-1119`), and our loop runs a
step's calls in order. A helper starts with no history, gets the tools minus
`run_subagent`, `ask_user`, `get_location` and the skill writes, and a call that
needs approval stops it with a reason the parent can act on. Each helper's steps
are logged in its own session, `subagents/<call id>.<n>.jsonl` beside the sessions
folder, which no chat route reads.

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

**Depends on.** 8 (the editor service and the `/skills` page it shares).

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
- `bot_create`, shipped with phase 10; editing or deleting a bot from chat is not yet.
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
- `runtime/inbox.py` — one inbox, `InboxTarget`, wakeup flag
- `runtime/handle.py` — `send`, `followup`, `steer`, `inject`, `when_idle`
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
capability is reached here: an MCP server, a skill, and a page in the app.
`backend/harness/` gained a relay (a tool result's loopback page and its live
connection, served under `/api/relay` to any device) and one client tool
(`hand_over`); it gains code again only in 17 (trimming old pages), 19 (an image
block) and 20 (a scheduler). Docker is a requirement of the
`computer` server, not of the harness: without it the server fails to connect and
the rest of the product runs. 20 needs no computer; it is here because Rakazo is
where it comes from. Rakazo paths below are under `packages/adapters/src/`.

## Phase 17 — It browses on its own computer *(begun)*

Built: `mcp-servers/computer/` and the Computer page (see Status, insertion 18).
What is left of the phase:

- `runtime/compaction/` — old pages trimmed on every step, not only at 80% of the
  window: the newest 3 page results over 1,000 characters stay, a failure never
  counts, and the rest are cleared by the `compaction/prune` event compaction
  already writes (`pi-runtime.ts:1413-1466`). The page tools are named in config;
  the harness knows no server's tools.
- `skills/browse-web/` — when to browse and when `exa` is enough; read the page
  before acting; a captcha or a login means `hand_over`, never a password in chat.

**Acceptance.** Ten page reads in one turn leave three in the request; a failed one
is not counted.

## Phase 19 — It sees its screen

**Demo.** A page its text cannot describe — a canvas, a map, a picture captcha.
The bot takes a screenshot, says what it sees, and clicks by coordinates.

**Depends on.** 17, and the decision gate: a model that accepts images.

**Ships.**
- `llm/models/blocks.py` — an `Image` block beside `Text` and `ToolReference`, and the
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
- A phone per bot — declined in the decision gates below.

---

# Decision gates

| Before | Decide | Default if silent |
|---|---|---|
| Phase 12 | Build the optional track at all | **Defer** until the product asks |
| Phase 15 | Which mutations the model may make without an approval gate | ~~Skills only~~ **None** — skill writes ask first too, the person's call once insertion 11's gate existed |
| Phase 17 | Reuse Rakazo's computer image or build our own | **Reuse** `ghcr.io/elie222/rakazo/computer` (Apache-2.0, published); fork it only when we need a change it will not take |
| Phase 17 | Where the computer runs | **This machine, in Docker** (chosen 2026-10-12 over a Boat cloud computer); on a server, the whole harness moves with it |
| Phase 19 | Which vision model | **None** — the phase does not start until `llm` points at a model that accepts images |
| — | A phone per bot | **No** — 0.8–3.2 GB per phone measured against 0.6 GB for the desktop ([docs/rakazo.md §5](./docs/rakazo.md)); mobile websites go through phase 17's browser |
