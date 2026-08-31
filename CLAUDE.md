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

**Status: phase 6 — "one seam for every channel" — implemented, awaiting review.**
Next is phase 7, MCP.

```sh
cp backend/config.local.example.json backend/config.local.json   # add your API key
# everything else — model, endpoint, sessions root, MCP servers — is in
# backend/config.json (committed); secrets go in config.local.json (gitignored)
make install && make test
make dev                                # backend :4896 + frontend :4897
# open http://localhost:4897 — there is no CLI, the API is the only surface
```

Capabilities are MCP servers, declared under `mcp.servers` and connected at
startup. The key is the tool namespace — `fs` gives the model `fs__read_file`:

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
  agent/        the turn loop and its events
  tools/        definition, registry, pipeline, progress, native/
  runs/         a turn that outlives its connection — store, subscribe
  channels/     every way in and out — telegram/, web/, and per-chat state
  web/          server — the composition root (the HTTP surface is channels/web/)
  config/       one Settings: config.json + config.local.json + env
backend/tests/  unit/ and integration/
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

## Invariants

Breaking one is not a style disagreement.

- **Model-visible means logged.** New model-visible input = new session event.
- **Every `register()` returns a disposer.** No exceptions.
- **Tool schemas are an allowlist.** `name`, `description`, `input_schema`, nothing else.
- **Tolerant tool failures.** A typed `Failure` rendered as `"error: …"`, never a raise.
- **A decision hook fails open.** "Registered" never means "enforcing".
- **Prompt text is code.** Wording that fixes a model failure carries that failure.
- **A watcher owns nothing.** A reader hanging up cannot cancel a turn.
- **One cursor.** One sequence number for snapshot and live stream alike.

## Before marking work complete

- `make lint` and `make test` are green (coverage gate is 80%).
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
