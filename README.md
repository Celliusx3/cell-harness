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
cp backend/.env.example backend/.env   # fill in HARNESS_LLM_API_KEY + _MODEL
make install                           # uv sync the backend package + dev deps
make test                              # pytest, 80% coverage gate
make lint                              # ruff check + format check

cd backend && uv run harness run "explain async generators"
```

## Layout

```
backend/harness/
  llm/          the model seam — messages, stream vocabulary, adapters/
  session/      the append-only event log + derive_messages
  agent/        the turn loop and its events
  config/       settings, read at the composition root
  cli.py        `harness run "<prompt>"`
backend/tests/  unit/ and integration/
docs/           source teardowns + long-form rules
notes/          design notes, referenced by path from code comments
AGENTS.md       project rules (CLAUDE.md is a symlink to it)
```

Subpackages arrive with the phase that needs them; the full intended layout is in
[DESIGN.md §3](./DESIGN.md).

Status: **phase 1 — "it answers" — implemented, awaiting review.** Every phase in
[PHASES.md](./PHASES.md) is a capability you can demo. Next is phase 2, "it uses
tools".
