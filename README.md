# cell-harness

Design work for an agent harness of our own, derived from two studied sources.

| Document | What's in it |
|---|---|
| [DESIGN.md](./DESIGN.md) | **The proposal.** What we take from each source, module layout, core contracts, and the open decisions. |
| [PHASES.md](./PHASES.md) | **The execution plan.** 13 phases, each a demoable capability — deliverables, contracts, and acceptance criteria. |
| [docs/deepseek-harness.md](./docs/deepseek-harness.md) | Teardown of `deepseek-ai/deepseek-harness` (256k lines, 227 packages) and three replication tiers. |
| [docs/cell-bot.md](./docs/cell-bot.md) | Teardown of cell-bot (6.9k lines Python), its feature inventory, and its honest gaps. |
| [docs/without-cordis.md](./docs/without-cordis.md) | How to get dsh's plugin properties — reversible registration, per-agent scoping, waterfall events — in ~250 lines of Python, and what we give up. |
| [docs/rules.md](./docs/rules.md) | The reasoning behind every rule and invariant in [CLAUDE.md](./CLAUDE.md). |
| [docs/coding-principles.md](./docs/coding-principles.md) | Behavioral guidelines (Karpathy): think first, KISS/YAGNI, surgical changes, goal-driven. |
| [docs/mcp-tool-scaling.md](./docs/mcp-tool-scaling.md) | Why MCP schemas load on demand, how code mode works and who else ships it, and what the evidence actually says. |
| [docs/skills.md](./docs/skills.md) | The Agent Skills spec, how six clients implement it, and which of their choices bind phase 8. |
| [docs/mcp-apps.md](./docs/mcp-apps.md) | MCP Apps: the contract, what the SDKs ship, how VS Code / Vercel / MCPJam host it, and the choices made here. |

The thesis in one line: **dsh's spine at cell-bot's size** — the event-sourced
log, turn/step semantics, and capability seams from DeepSeek Harness, built with
cell-bot's shallow contracts and typed decisions, targeting ~10k lines of Python.

Shape: a **chat product** (browser UI, conversations, agent catalog,
capabilities via MCP), not a terminal coding harness. That decision drives the
phase ordering.

## Getting started

```sh
cp backend/config.local.example.json backend/config.local.json   # add your API key
# everything else — model, endpoint, sessions root, MCP servers — is in
# backend/config.json (committed); a server's `env` secrets go in config.local.json
make install                           # uv sync the backend package + dev deps
make test                              # pytest, 80% coverage gate — needs Deno on PATH, https://deno.com
make lint                              # ruff check + format check
```

Deno is a startup requirement: the model reaches every capability by writing a
TypeScript program that runs in a Deno sandbox. The `sysmon` MCP App also needs
Node (`npx`).

Then:

```sh
make dev            # backend :4896 + frontend :4897 together (Ctrl-C stops both)
make dev-backend    # or just one of them
make dev-web
```

Open <http://localhost:4897>.

There is no command-line interface. `harness run` / `list` / `resume` existed to
demo the harness before there was a UI; the API does all three, so keeping them
would be a second surface to hold in step with the first. To smoke-test a
provider without the browser:

```sh
curl -sN -X POST localhost:4896/api/conversations \
  -H 'content-type: application/json' \
  -d '{"prompt":"what time is it in Tokyo?"}'
curl -s localhost:4896/api/conversations
```

## Telegram

Optional. Message [@BotFather](https://t.me/BotFather), send `/newbot`, and put
the token in `backend/config.local.json`:

```json
{ "telegram": { "bot_token": "123456:AA…" } }
```

`make dev` then polls for messages alongside the web server — no public URL and no
tunnel, because it long-polls rather than taking a webhook. Text the bot and the
conversation shows up in the browser sidebar like any other.

`/new` starts a fresh conversation, `/stop` cancels the current reply. A message
sent while it is working is answered next rather than refused — and since phase 6
the browser behaves the same way, because being able to *show* a refusal is not a
reason to make someone retype what they wrote.

`/skills` lists the skills you can type. `/find-place <url>` — any `/name` —
loads that skill for the model before it reads your message, on every channel alike. A `/word` that is neither a command
nor a skill is answered with the list of what is, never handed to the model.

With no token the channel simply does not start.

## Discord

Optional, same shape. Create a bot in the
[Developer Portal](https://discord.com/developers/applications), invite it with
the `bot` and `applications.commands` scopes, and put the token in
`backend/config.local.json`:

```json
{ "discord": { "bot_token": "…" } }
```

DMs are always answered. In a server, only messages that `@mention` the bot are
read — that is what keeps the privileged *Message Content* intent unnecessary,
so the bot never sees a channel's traffic it was not addressed in. `/new`, `/stop` and
`/skills` are slash commands. With no token the channel does not start.

## Layout

```
backend/harness/
  llm/          the model seam — messages, stream vocabulary, adapters/
  session/      the event log, its models, repository/, service, repair
  agent/        the turn loop, its events, and hooks/ — the chain + native/<hook>/
  tools/        definition, registry, dispatcher, pipeline, progress, native/<tool>/
  sandbox/      the Runner seam + deno.py — runs a script, imports nothing else
  mcp/          the MCP client — one owning task per server, namespaced tools
  skills/       the catalog read from ranked roots, and the one `skill` tool
  runs/         a turn that outlives its connection — store, subscribe
  channels/     every way in and out — telegram/, discord/, web/, and per-chat state
  web/          server — the composition root (the HTTP surface is channels/web/)
  config/       one Settings: config.json + config.local.json + env
backend/tests/  unit/ and integration/
mcp-servers/    the capabilities we build — one uv project each, own tests
frontend/       Next.js chat — app/, components/, lib/
docs/           source teardowns + long-form rules
CLAUDE.md       project rules, loaded into every session
```

Subpackages arrive with the phase that needs them; the full intended layout is in
[DESIGN.md §3](./DESIGN.md).

Status: **phases 1–8 and 10 done.** Type `/find-place <url>` in the browser or
on a phone and the skill is loaded for the model; paste a public `SKILL.md` on
the `/skills` page and it is used next turn. Seven capabilities not in the
original arc have shipped since phase 7 — code mode, Instagram → Places, skills,
tool references, Discord, MCP Apps, markets — each recorded in
[PHASES.md §Status](./PHASES.md#status). Every phase in PHASES.md is a capability
you can demo. Next is phase 9, steering.
