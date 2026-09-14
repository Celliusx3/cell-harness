# CLAUDE.md — Project Rules

Loaded into every session in this directory. Kept thin on purpose: each rule is
one line, and the reasoning lives in [docs/rules.md](./docs/rules.md).

## Project

cell-harness — an agent harness in Python, built as a **chat product**
(cell-bot shaped: browser UI, conversations, agent catalog, capabilities via
MCP — not a terminal coding harness). Synthesized from
[DeepSeek Harness](./docs/deepseek-harness.md) for the architecture and
[cell-bot](./docs/cell-bot.md) for the taste. Target ~10k lines.

Read before writing code: [DESIGN.md](./DESIGN.md) for the contracts,
[PHASES.md](./PHASES.md) for the current phase and what it must satisfy.

**Status: phase 10 — "it doesn't get stuck" — done, ahead of 8.3–8.4 and 9.**
Phase 8 is in progress (8.1–8.2 done). Since phase 7, six insertions not in
PHASES.md, then phase 10 as written there with three cuts recorded in it.

**1. Code mode.** The model is offered three tools and
reaches every capability by writing a TypeScript program that runs in a Deno
sandbox, so the request carries three schemas however many servers are connected.
**Deno is a startup requirement.** Reasoning, evidence, and the tool-search
attempt it replaced, in
[docs/mcp-tool-scaling.md](./docs/mcp-tool-scaling.md).

**2. It finds places from Instagram reels** — the first real capability, and the
first test of phase 7's claim. Two MCP servers under
[mcp-servers/](./mcp-servers/): `instagram` reads a shared reel into text
observations, `places` resolves them to a POI with a Maps link. The model
composes them in one program, and `backend/harness/` gained nothing. Instagram
needs no credentials; Google Places needs a key in `config.local.json`.

**3. It follows instructions** (8.1–8.2). A skill is a directory with a
`SKILL.md` — the [Agent Skills](https://agentskills.io) format, so one written
for Claude Code, Codex or OpenClaw loads here unchanged. `skills/catalog.py`
reads ranked roots (`.agents/skills` in the project, then `~/.agents/skills`)
on **every request**, a `(mtime, size)` stamp per file standing in for a
watcher; `skills/tool.py` is the one tool the model loads one through, rebuilt
per request so its `name` enum and its `<available_skills>` index are the same
list. **The catalog is never logged** — it rides on the tool description the
way the tool list rides on the request, so nothing republishes it and phase 12
has nothing to re-establish. The body is the tool *result*, read from disk at
that moment. No skill on disk, no tool in the request. The first committed
skill, `find-place`, teaches the reel → place composition from insertion 2:
skills are how the model is told *how* to use tools. Research and the choices
it forced in [docs/skills.md](./docs/skills.md). Still to come: `/name`
invocation from a chat (8.3) and the settings page (8.4).

**4. It selects, then calls.** The first skill was a sequential workflow, and
under code mode the model wrote a program per step — every cost of a script,
none of its saving — while a 4B model could call tools and could not write
programs. Anthropic's own guidance for programmatic tool calling says the same:
strong for fan-out, weak for sequential single calls, per tool not per harness.
So `get_function_details` now has a consequence, in Anthropic's shape: a tool
result is a list of typed blocks, and its result carries `tool_reference`
blocks for what it read. The log keeps them; `Session.tools_selected()` folds
them out of history; the pipeline puts the **eight most recent** into the next
request; and because this wire has no such block, the adapter renders it as a
sentence so the model knows its list changed. The pipeline's refusal of an
unreferenced name says to read it first. Programs remain for many calls or a
large result. Reasoning and the measurements in
[docs/mcp-tool-scaling.md §7](./docs/mcp-tool-scaling.md).

**5. It answers on Discord** — the seam's first real test after `FakeDiscord`,
and it held: `channels/discord/` is one class and one line in `build_channels`,
with `gateway.py`, `commands.py` and `repository.py` untouched. Every DM is
answered; a guild channel or thread only when the bot is `@mentioned` — the
Hermes and OpenClaw default, and what lets it run **without the privileged
Message Content intent**. One conversation per DM, channel or thread. `/new`
and `/stop` are native slash commands. `split_message` moved to
`channels/text.py` on the way, since the 2000-character cut is the 4096 one
with a different number. Token in `config.local.json`; no frontend.

**6. It shows a UI.** [MCP Apps](https://github.com/modelcontextprotocol/ext-apps)
(SEP-1865, Final) — a tool's `_meta.ui.resourceUri` names a `ui://` HTML
resource, and the chat renders it in a sandboxed iframe that receives the tool
result and may call the same server back. The harness is the MCP client, so
`mcp/store.py` reads the resource over its command loop, `open_client`
negotiates the extension, and `ToolResultEvent.ui` carries the binding plus the
`structuredContent` the view draws — the "tool result `meta`" row PHASES.md
deferred twice, with its caller. The browser holds no MCP client: two routes
under `/api/mcp/{server}/` serve the HTML (with a CSP the harness composed) and
**proxy** a view's `tools/call` to its own server — by the server's name, from
the server's published list, answered verbatim; not the dispatcher, which is
the model's path. No session event results.
`frontend/components/McpApp.tsx` is the official `AppBridge` over a single
`srcdoc` iframe with an opaque origin, on **its own page**:
`/apps/{conversation}/{call}` renders one call's app, and every chat gets a link
to it rather than the app — the browser card an "Open app" link,
`Pushing.send_link` for the rest (Telegram: a Mini App `web_app` button over
https; Discord: a link button), all pointed at `web.public_url` — empty by default, so no link is sent until you set one. No auth exists yet, so `public_url` must stay local until it
does — see the doc. Proven against a public app with no server code of ours: `sysmon` in `config.json` is
`npx @modelcontextprotocol/server-system-monitor --stdio`, whose dashboard
polls an app-only tool through the harness every second. Kebab-case tool names
are now mapped (`get-system-info` → `sysmon__get_system_info`) rather than
dropped. Deferred, and why, in [docs/mcp-apps.md](./docs/mcp-apps.md).

```sh
cp backend/config.local.example.json backend/config.local.json   # add your API key
# everything else — model, endpoint, sessions root, MCP servers — is in
# backend/config.json (committed); secrets go in config.local.json (gitignored)
make install && make test          # needs Deno on PATH — https://deno.com
make dev                                # backend :4896 + frontend :4897; `sysmon` needs Node (npx) on PATH
# open http://localhost:4897 — there is no CLI, the API is the only surface
```

Capabilities are MCP servers, declared under `mcp.servers` and connected at
startup. The key is the tool namespace — `fs` gives the model `fs__read_file`.
The model never sees them as tools: it calls `list_functions`, then writes one
TypeScript program that calls `fs__read_file(...)` inside a Deno sandbox.

```json
{ "mcp": { "servers": {
    "fs": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"] }
} } }
```

The two config files **deep-merge per server**, so a server's shape is committed
and only its `env` secrets go in `config.local.json`.

## Layout

```
backend/harness/
  llm/          the model seam — messages, stream vocabulary, adapters/
  session/      the event log, its models, repository/, service, repair
  agent/        the turn loop, its events, and hooks/ — the chain + native/<hook>/
  tools/        definition, registry, dispatcher, pipeline, progress, native/<tool>/
  sandbox/      the Runner seam + deno.py — runs a script, imports nothing else
  runs/         a turn that outlives its connection — store, subscribe
  channels/     every way in and out — telegram/, discord/, web/, and per-chat state
  web/          server — the composition root (the HTTP surface is channels/web/)
  config/       one Settings: config.json + config.local.json + env
backend/tests/  unit/ and integration/
mcp-servers/    the capabilities we build — one uv project each, own tests
frontend/       Next.js chat — app/, components/, lib/
docs/           source teardowns + long-form rules
```

`mcp-servers/` is where a capability goes, not `backend/harness/`. Each is a
separate process with its own dependencies and its own 80% gate, reached only by
being declared in `mcp.servers` — `backend/harness/` imports nothing from it. See
[mcp-servers/README.md](./mcp-servers/README.md) for the layout every one
follows and the four things the harness makes non-negotiable.

Subpackages and infrastructure arrive with the phase that needs them, never
earlier. Full intended layout in [DESIGN.md §3](./DESIGN.md); paths in PHASES.md
are relative to `backend/harness/`.

## Rules

- **KISS + YAGNI.** Minimum code that solves the *asked* problem.
- **Surgical changes.** Every changed line traces to the request.
- **Don't truncate user-facing strings.** Rendering handles overflow.
- **Typed boundaries, and fail closed.** No bare `dict`/`Any`; raise, don't guess.
- **Explicit over implicit defaults.** Pass behavioral choices explicitly.
- **One setting, one place to look.** No `a.x or b.y` fallback chains.
- **Comments: the *why*, in one or two lines.** Longer reasoning goes in docs.

## Invariants

Breaking one is not a style disagreement.

- **Model-visible means logged.** New model-visible input = new session event.
- **Every `register()` returns a disposer.** No exceptions.
- **Tool schemas are an allowlist.** `name`, `description`, `input_schema`, nothing else.
- **Tolerant tool failures.** A typed `Failure` rendered as `"error: …"`, never a raise.
- **A decision hook fails open.** "Registered" never means "enforcing".
- **The guardrail is a fold, not a counter.** Every decision is computed from
  the turn's `tool/call` + `tool/result`; nothing to restore on resume, and its
  own `BLOCKED` results are skipped so refusing never inflates the count that
  caused it. What it tells the model is an `application/message` — user role
  on the wire, its own event in the log — after the step's results; a `tool/result` is the
  tool's words alone. There is no step cap: repeated failures are the
  guardrail's, and everything else is the stop button's.
- **Prompt text is code.** Wording that fixes a model failure carries that failure.
- **A watcher owns nothing.** A reader hanging up cannot cancel a turn.
- **One cursor.** One sequence number for snapshot and live stream alike.
- **Every call the model or a script makes goes through the dispatcher**, and
  there is exactly one, which is what makes one timeout and one gate cover both.
  An MCP App's call is not one of those: it is the harness proxying to the
  app's own server, by the server's own name, answered verbatim — with its
  guards (same server, `visibility`, resource binding) at the MCP layer, where
  every other host puts them.
- **Registered is not offered; referenced is.** The dispatcher resolves any
  registered name — scripts need it to — but a call the *model* makes by a name
  it was not shown is refused by the pipeline, told to read it first. A result's
  `tool_reference` blocks (Anthropic's shape) put the tool in the request from
  the next step on — the most recent eight, so a long conversation never carries
  the catalog. The harness expands references, since this wire cannot.
- **The sandbox is granted nothing.** No `--allow-*`; the bridge is the only way
  out, and code mode never reaches itself.
- **`harness/sandbox/` imports nothing from `harness`.** It runs a script; it does
  not know what a tool is.
- **We reap what we spawn.** No SDK owns the Deno child; a `finally` kills it.
- **Prompt assembly cannot raise.** The schema printer degrades to `unknown`
  rather than costing the turn every tool.
- **No skills, no tool.** An enum with no members is never offered; the
  provider yields nothing and the request carries nothing.
- **A skill's body is context, not data.** The `skill` tool is withheld from
  scripts: `list_functions` never advertises it and the bridge refuses it.
- **The catalog is read, never published.** Skills are rebuilt from disk per
  request like the tool list; a `SKILL.md` edit is visible at the next step
  with nothing to invalidate.

## Before marking work complete

- `make lint` and `make test` are green (coverage gate is 80%). If you touched
  `mcp-servers/`, so are `make lint-mcp-servers` and `make test-mcp-servers` —
  deliberately separate, so one server's flake cannot fail the harness's suite.
- The phase's acceptance criteria in [PHASES.md](./PHASES.md) are met, as tests.
- **Every new definition has a caller outside `tests/`.** `grep -rn '\bname\b'
  harness/` — if the only hits are the definition and test files, it belongs in
  `tests/` or does not exist yet.
- When KISS/YAGNI argues against what PHASES.md calls for, raise it **before**
  building — narrowing an approved plan is a decision to surface, not to take.

## Docs index

| File | What's in it |
|------|--------------|
| [DESIGN.md](./DESIGN.md) | The proposal: what we take from each source, module layout, core contracts, open decisions |
| [PHASES.md](./PHASES.md) | 13 phases, each a demoable capability — deliverables, contracts, acceptance criteria |
| [docs/rules.md](./docs/rules.md) | The reasoning behind every rule and invariant above |
| [docs/coding-principles.md](./docs/coding-principles.md) | Behavioral guidelines (Karpathy): think first, KISS/YAGNI, surgical changes, goal-driven |
| [docs/deepseek-harness.md](./docs/deepseek-harness.md) | Teardown of DeepSeek Harness and three replication tiers |
| [docs/cell-bot.md](./docs/cell-bot.md) | Teardown of cell-bot, its feature inventory, and its gaps |
| [docs/without-cordis.md](./docs/without-cordis.md) | Scope / Layered / Events in ~250 lines, and what we give up — built when first needed, not now |
| [docs/mcp-tool-scaling.md](./docs/mcp-tool-scaling.md) | Why MCP schemas load on demand, how code mode works and who else ships it, and what the evidence actually says |
| [docs/skills.md](./docs/skills.md) | The Agent Skills spec, how six clients implement it, and which of their choices bind phase 8 |
| [docs/mcp-apps.md](./docs/mcp-apps.md) | MCP Apps: the contract, what the SDKs ship, how VS Code / Vercel / MCPJam host it, and the choices made here |
