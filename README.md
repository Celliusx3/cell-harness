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
```

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
sent while it is working is answered next rather than refused — a phone cannot
grey out its composer.

With no token the channel simply does not start.

## Layout

```
backend/harness/
  llm/          the model seam — messages, stream vocabulary, adapters/
  session/      the event log, its models, repository/, service, repair
  agent/        the turn loop and its events
  tools/        definition, registry, pipeline, progress, native/
  runs/         a turn that outlives its connection — store, subscribe
  channels/     telegram/, and the per-chat state a messenger needs
  web/          schemas, sse, routes/, server — the HTTP surface + composition root
  config/       one Settings: config.json + config.local.json + env
backend/tests/  unit/ and integration/
frontend/       Next.js chat — app/, components/, lib/
docs/           source teardowns + long-form rules
CLAUDE.md       project rules, loaded into every session
```

Subpackages arrive with the phase that needs them; the full intended layout is in
[DESIGN.md §3](./DESIGN.md).

Status: **phase 5 — "it answers on Telegram" — implemented, awaiting review.**
Every phase in [PHASES.md](./PHASES.md) is a capability you can demo. Next is
phase 6, "one seam for every channel".
