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
[PHASES.md](./PHASES.md) for the current status, the phase in progress and
what it must satisfy. Nothing in this file changes when a feature ships.

Four shapes that hold everywhere:

- **Code mode.** The model is offered three tools and reaches every capability
  by writing a TypeScript program that runs in a Deno sandbox, so the request
  carries three schemas however many servers are connected. **Deno is a startup
  requirement.** [docs/mcp-tool-scaling.md](./docs/mcp-tool-scaling.md).
- **A capability is an MCP server** under [mcp-servers/](./mcp-servers/) — a
  separate process with its own dependencies and its own 80% gate, declared in
  `mcp.servers` and connected at startup. The key is the tool namespace: `fs`
  gives the model `fs__read_file`. `backend/harness/` imports nothing from it.
  [mcp-servers/README.md](./mcp-servers/README.md).
- **A skill is a directory with a `SKILL.md`** — the
  [Agent Skills](https://agentskills.io) format — read from ranked roots on
  every request and loaded through one `skill` tool. Skills are how the model
  is told *how* to use tools. [docs/skills.md](./docs/skills.md).
- **Every channel is a client of one gateway** — browser, Telegram, Discord. A
  new platform is one class and one line in `build_channels`.
  [channels/__init__.py](./backend/harness/channels/__init__.py).

```sh
cp backend/config.local.example.json backend/config.local.json   # add your API key
# everything else — model, endpoint, sessions root, MCP servers — is in
# backend/config.json (committed); secrets go in config.local.json (gitignored)
make install && make test          # needs Deno on PATH — https://deno.com
make dev                           # backend :4896 + frontend :4897; `sysmon` needs Node (npx)
# open http://localhost:4897 — there is no CLI, the API is the only surface
```

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
- **Every file under 300 lines.** `make lint` refuses a longer one; split on the seam, never raise the cap.

## Invariants

Breaking one is not a style disagreement. The reasoning behind each is in
[docs/rules.md](./docs/rules.md).

- **Model-visible means logged.** New model-visible input = new session event.
- **Every `register()` returns a disposer.** No exceptions.
- **Tool schemas are an allowlist.** `name`, `description`, `input_schema`, nothing else.
- **Tolerant tool failures.** A typed `Failure` rendered as `"error: …"`, never a raise.
- **A decision hook fails open.** "Registered" never means "enforcing".
- **The guardrail is a fold, not a counter.** Every decision is computed from
  the turn's `tool/call` + `tool/result`, its own `BLOCKED` results skipped; what
  it tells the model is an `application/message`, never part of a `tool/result`.
  There is no step cap.
- **Prompt text is code.** Wording that fixes a model failure carries that failure.
- **A watcher owns nothing.** A reader hanging up cannot cancel a turn.
- **One cursor.** One sequence number for snapshot and live stream alike.
- **Every call the model or a script makes goes through the one dispatcher.**
  An MCP App's `tools/call` is not one of those: the harness proxies it to the
  app's own server, guarded at the MCP layer.
- **Registered is not offered; referenced is.** The dispatcher resolves any
  registered name; the pipeline refuses a call the model makes by a name it was
  not shown. A result's `tool_reference` blocks put the tool in the next
  request — the most recent eight.
- **The sandbox is granted nothing.** No `--allow-*`; the bridge is the only way
  out, and code mode never reaches itself.
- **`harness/sandbox/` imports nothing from `harness`.** It runs a script; it does
  not know what a tool is.
- **We reap what we spawn.** No SDK owns the Deno child; a `finally` kills it.
- **Prompt assembly cannot raise.** The schema printer degrades to `unknown`
  rather than costing the turn every tool.
- **No skills, no tool.** An enum with no members is never offered.
- **A skill's body is context, not data.** The `skill` tool is withheld from scripts.
- **The catalog is read, never published.** Skills are rebuilt from disk per
  request like the tool list; nothing to invalidate, nothing for phase 11 to
  re-establish.

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
| [docs/client-data.md](./docs/client-data.md) | Data the client holds: how `get_location` asks the browser, Telegram and Discord, the four shapes in the wild, and why the wait is in the tool |
| [docs/compaction.md](./docs/compaction.md) | Phase 11: the three events, how `derive_messages` honours the boundary, the trigger (window discovered + config cap), the reactive net, and the endpoint evidence |
