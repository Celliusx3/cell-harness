# mcp-servers/

The MCP servers we build. Capabilities that are **separate processes**, not
backend growth — the model `docs/cell-bot.md` describes and PHASES.md phase 7
prescribes: *"a capability is a separate process with its own README and tests"*.
cell-bot ships five (yt-dlp, whisper, pptx, tradingagents, charts) and its
backend never learned what a video is.

cell-bot calls these **satellites**, and DESIGN.md and PHASES.md use that word
for cell-bot's. The directory does not, because a folder called `mcp-servers`
needs no glossary — and because `backend/harness/mcp/` is the MCP *client*, so a
top-level `mcp/` would name both sides of one protocol.

Third-party servers we merely *declare* — `sysmon`, `memory` — are not here. They are
an `npx` or `uvx` line in config, so being in this directory is what "ours"
means. `memory` is Basic Memory, the model's long-term memory over a folder of
Markdown notes; why it and not our own server, and how to set it up, is in
[docs/memory.md](../docs/memory.md).

Each directory is its own `uv` project with its own dependencies, its own tests
and its own coverage gate. `backend/harness/` imports nothing from here and
knows nothing about them — a server here reaches the model only by being
declared in `mcp.servers`.

| Server | Capability |
|---|---|
| [instagram](./instagram) | Read a shared Instagram reel into text observations a POI can be reasoned from |
| [places](./places) | Resolve a described place to a real POI via Google Places API (New) |
| [markets](./markets) | Investment research data — quotes, history, fundamentals, filings, news — for US stocks/ETFs, crypto and Bursa Malaysia, from free sources |

`places` began as the third-party `@cablate/mcp-google-map` and
was replaced, which is worth recording because the reason generalises: **it
declared no `outputSchema`**, so it could not populate `structuredContent`, and a
code-mode script reading its result would get `undefined` — the exact failure
`docs/mcp-tool-scaling.md` §6 finding 4 measured at *"five failing scripts and a
cancelled turn."* Its hardcoded Enterprise-tier field masks also cut the free
allowance by 80% and pulled reviews into the permanent session log. Before
declaring any third-party server, list its tools and check for an `outputSchema`;
without one it is the wrong shape for this harness however well maintained it is.

## Declaring one

Committed shape in `backend/config.json`, secrets in `backend/config.local.json`.
The two **deep-merge per server**, so a server's `command` and `args` are
committed and only its `env` secrets are not.

```jsonc
// backend/config.json
{"mcp": {"servers": {"instagram": {
  "command": "uv",
  "args": ["run", "--quiet", "--project", "../mcp-servers/instagram", "instagram"],
  "env": {"INSTAGRAM_MEDIA_BACKEND": "instaloader"}
}}}}
// backend/config.local.json
{"mcp": {"servers": {"instagram": {"env": {"INSTAGRAM_PROVIDER_API_KEY": "sk-..."}}}}}
```

### Three things that will bite you

**The server id may not contain a hyphen.** `config/sections.py` and
`mcp/tool.py` both permit one, but `tools/native/code/typescript.py` emits
`declare function {name}(...)` **unquoted** — so a server keyed `instagram`
prints `declare function my-server__fetch_reels(...)`, which is not
parseable TypeScript, and the model writes a call the sandbox cannot resolve.
Use a hyphen-free id. (The id validator and the TypeScript printer disagreeing is a real
backend bug, not a rule.)

**Relative paths resolve from `backend/`, not from the repo root.** The harness
never sets a `cwd` for a server it spawns, so one of these inherits the harness
process's — which the `Makefile` fixes as `backend/` via `cd backend && uv run
uvicorn ...`. Hence `../mcp-servers/...`. Start the backend any other way and
the server will not spawn. An absolute path would be machine-specific and so
could not live in the committed file.

**Warm the venv once.** The first spawn may sync dependencies, which can outrun
the MCP initialize handshake and look like a broken server. `make
test-mcp-servers` does it, or `uv sync --project mcp-servers/<name>`. The same
symptom with a different cause: a `.venv` records its own absolute path, so
*moving* one of these directories leaves `uv run` falling through to a system
interpreter and failing on an import. `rm -rf .venv && uv sync` fixes it.

## How one is laid out

Both follow the same shape, and it is the shape `backend/harness/` uses: grouped
by **seam**, not by technical role. A folder earns its place by being a thing
that changes for its own reasons.

```
<server>/
  config.py      one Settings, validated before the transport binds
  models.py      the shared return vocabulary
  server.py      the composition root, and nothing else
  <domain>/      one package per seam — e.g. media/ acquires, read/ interprets
  tools/         the MCP surface: descriptions, and what the protocol imposes
```

Two rules that fell out of doing it:

- **`server.py` stays thin.** The harness's own `web/server.py` is documented as
  "the composition root alone", and the same discipline applies here — the
  Instagram server's dropped from 372 lines to 75 when the tool bodies moved into
  `tools/` and the pipeline into `read/`.
- **`models.py` is top-level, not under `tools/`.** It looks like an API concern,
  but putting it there made `media/` and `read/` import *upward* from the surface
  they feed. Shared vocabulary belongs where everything can reach it — the same
  place `llm/messages.py` sits in the harness.

## Writing one

Four properties the harness makes non-negotiable. Each is enforced by a test in
`instagram/tests/`, which is the place to copy from.

1. **Return a pydantic model, so `structuredContent` is populated.** The harness
   passes it through as `Ok.data` and code mode hands it to the model's program as
   an object. `docs/mcp-tool-scaling.md` §6 records the cost of getting this
   wrong: *"a script reading `results.jobs` got `undefined`. Observed live: five
   failing scripts and a cancelled turn."*
2. **Per-item `status`, never a per-item failure.** A tool `Failure` reaches the
   sandbox as a thrown `Error` and destroys every sibling result in the same call.
   Only facts about the *whole call* may fail.
3. **Write the return shape and every argument into the tool description.** The
   printer collapses a description to one line, emits argument types with no doc
   comments, and declares the return type as `Promise<unknown>` — so anything not
   in the prose is invisible to the model.
4. **Never write to stdout.** stdout is the protocol. Log to stderr, which the
   harness attaches to its own.

One call is capped at **60 seconds** (`mcp/connection.py`, a module constant), and one
connection serves **one call at a time** — so `Promise.all` over several calls to
the same server serializes them. A server that can be slow should batch
internally and return partial results rather than hoping.

A tool description says what one call does. **How to compose several — across
servers, in what order, with what judgement — is a skill**: a `SKILL.md` under
`.agents/skills/` that the model loads when a request matches it.
`find-place` is the one that teaches the `instagram` → `places` workflow.

## Targets

```sh
make test-mcp-servers   # each server's own suite and its own coverage gate
make lint-mcp-servers   # ruff check + format --check in each
```

Deliberately **not** part of `make test` / `make lint`: one server's flake must
not fail the harness's suite, and folding a second `--cov` source into one pytest
run makes the 80% gate mean nothing about either. There is no `install`
target — `uv run` syncs on demand.
