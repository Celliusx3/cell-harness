# cell-harness

Design work for an agent harness of our own, derived from two studied sources.

| Document | What's in it |
|---|---|
| [DESIGN.md](./DESIGN.md) | **The proposal.** What we take from each source, module layout, core contracts, and the open decisions. |
| [PHASES.md](./PHASES.md) | **The execution plan.** 13 phases, each a demoable capability — deliverables, contracts, and acceptance criteria. |
| [docs/deepseek-harness.md](./docs/deepseek-harness.md) | Teardown of `deepseek-ai/deepseek-harness` (256k lines, 227 packages) and three replication tiers. |
| [docs/cell-bot.md](./docs/cell-bot.md) | Teardown of cell-bot (6.9k lines Python), its feature inventory, and its honest gaps. |
| [docs/without-cordis.md](./docs/without-cordis.md) | How to get dsh's plugin properties — reversible registration, per-agent scoping, waterfall events — in ~250 lines of Python, and what we give up. |

The thesis in one line: **dsh's spine at cell-bot's size** — the event-sourced
log, turn/step semantics, and capability seams from DeepSeek Harness, built with
cell-bot's shallow contracts and typed decisions, targeting ~10k lines of Python.

Shape: a **chat product** (browser UI, conversations, agent catalog,
capabilities via MCP), not a terminal coding harness. That decision drives the
phase ordering.

## Getting started

```sh
cp backend/config.local.example.json backend/config.local.json   # add your API key
# everything else — model, endpoint, sessions root — is in backend/config.json (committed)
make install                           # uv sync the backend package + dev deps
make test                              # pytest, 80% coverage gate
make lint                              # ruff check + format check

cd backend && uv run harness run "what time is it in Tokyo?"
cd backend && uv run harness list
```

## Layout

```
backend/harness/
  llm/          the model seam — messages, stream vocabulary, adapters/
  session/      the event log, its header, persistence, repair, the store
  agent/        the turn loop and its events
  tools/        definition, registry, pipeline, progress, native/
  config/       one Settings: config.json + config.local.json + env
  cli.py        `harness run "<prompt>"`
backend/tests/  unit/ and integration/
docs/           source teardowns + long-form rules
notes/          design notes, referenced by path from code comments
CLAUDE.md       project rules, loaded into every session
```

Subpackages arrive with the phase that needs them; the full intended layout is in
[DESIGN.md §3](./DESIGN.md).

Status: **phase 3 — "it remembers" — implemented, awaiting review.** Every phase
in [PHASES.md](./PHASES.md) is a capability you can demo. Next is phase 4, "you
can chat with it".
