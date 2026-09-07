# Why MCP schemas load on demand

Every request re-sends every tool's name, description and argument schema. At
roughly **950 tokens per tool**, a handful of MCP servers costs more context than
the conversation does. This file records what the field does about that, what we
built, and what it costs.

**Our answer is code mode.** The model is offered three tools and reaches every
capability by writing a program that runs in a Deno sandbox, so the request
carries a fixed three schemas however many servers are connected
([§6](#6-code-mode)). There is no setting: this is how the harness reaches its
tools, and Deno is a startup requirement.

---

## 1. Neither source project helps

Both send everything. This was checked, not assumed.

**DeepSeek Harness.** `wireSchemas()` (`packages/core/tools/src/index.ts:983`) is
the whole assembly:

```ts
if (mode === 'native') {
  const schemas = [...view.visible.values()].map(d => this.schemaOf(d, false))
  return { schemas, knownNames: [...view.knownNames] }
}
```

No budget, no truncation, no caching. MCP registers into the *unscoped* global
layer (`packages/mcp/mcp-client/src/tools.ts:143`), and its config schema has no
allow/deny field at all. Two reduction mechanisms exist and neither is a token
win: `tools.restrict({allow, deny})` (`:680`) is a static filter used by **no
shipped preset**, only subagents; Code Mode (`:994`) collapses the array to one
`run_code` schema and re-emits the rest as an SDK block in the system prompt —
their own README says it *"trades end-tool schemas for generated SDK text plus
one transport schema rather than promising a universal reduction."*

Most telling is the negative evidence: their provider adapter deliberately
withholds the upstream switches that would enable deferral
(`packages/llm/llm-pi-ai/src/catalog.ts`):

```ts
deferredToolsMode: 'withhold',
supportsToolSearch: 'withhold',
supportsToolReferences: 'withhold',
```

**opencode.** Builds every MCP tool with its full schema, then deletes keys
(`packages/opencode/src/session/llm.ts:253`). It adds wildcard config —
`{"tools": {"mymcp_*": false}}`, overridable per agent — which is more than
DeepSeek ships, but it is still a hand-maintained list. No schema stripping:
`convertMcpTool` (`src/mcp/index.ts:120`) spreads the server's schema verbatim
and *adds* `additionalProperties: false`. And `listTools()` runs on **every
turn, uncached** (`src/mcp/index.ts:618`), so even a fully-denied server costs a
round-trip per turn.

## 2. What the vendors ship, and why we cannot use it

| Who | Mechanism | Available to us? |
|---|---|---|
| Anthropic | `tool_search_tool_{regex,bm25}_20251119` + `defer_loading` — **GA, no beta header** | ❌ |
| OpenAI | `{"type": "tool_search"}` + `defer_loading`, gpt-5.4+ | ❌ |
| Claude Code | `ENABLE_TOOL_SEARCH`, on by default, `auto:N` at N% of context | ❌ |
| VS Code Copilot | virtual tools — collapse servers behind `activate_*` stubs; hard 128-tool cap | pattern only |
| Goose | Tool Router — embedding or LLM shortlist per query | pattern only |
| FastMCP v3.1 | server-side `tool_search` transform: `search_tools` + `call_tool` | pattern only |

`config.json` points at an OpenAI-compatible endpoint. Every ❌ above is a
first-party serving-stack feature — Anthropic's own SDK disables tool search when
`ANTHROPIC_BASE_URL` is not first-party, *"since most proxies don't forward
`tool_reference` blocks."* So only the client-side patterns were ever on the
table.

## 3. The constraint that shaped our version

The load-bearing sentence, from Anthropic's tool-search docs:

> You still send every tool's full definition in the `tools` array on every
> request, including the deferred ones. The API needs them server-side to run the
> search and expand `tool_reference` blocks.

`defer_loading` saves **context tokens, not upload bytes**. It works by excluding
deferred tools from the *system-prompt prefix* and appending discovered ones
inline in the conversation body — so the prefix never moves and prompt caching
survives.

**We cannot do that** — our only lever is the top-level `tools` array, and
appending to it mutates the prefix, so every discovery would invalidate the
prompt cache from that point on. This is the strongest argument for code mode
over a client-side tool search, and it is why an earlier tool-search
implementation here was removed: with code mode the tools array is **constant**,
so the prefix never moves at all.

One design lesson worth keeping, from OpenAI's docs: defer at the
**namespace/server** level where you can. Deferring an individual function still
shows its name and description and hides only the parameter schema.

## 4. Numbers

Trustworthy, and checkable:

- **~950 tokens/tool** — Anthropic's five-server worked example: GitHub 35 +
  Slack 11 + Sentry 5 + Grafana 5 + Splunk 2 = 58 tools ≈ 55K tokens. This is the
  cost anchor used everywhere in this file.
- [arXiv 2606.17519](https://arxiv.org/abs/2606.17519) (Jun 2026, deployed
  system, 110 agents / 584 tools) — routing F1 drops 16–23pp as the catalog
  grows; embedding shortlisting recovers +10–11pp.
- [LiveMCPBench](https://arxiv.org/abs/2508.01780) (70 servers, 527 tools) —
  **retrieval errors are about half of all failures.** Discoverability is the
  risk deferral introduces, not availability. It is why the three tool
  descriptions and `CODE_PROMPT` in `tools/native/code/tools.py` are treated as code.

Assertions and myths — do not repeat these as measurements:

- *"Accuracy degrades past 30–50 tools"* — stated in Anthropic's docs with no
  citation. MCP SEP-1300 says ~10. Cursor enforces 40. Nobody has published a
  clean accuracy-vs-count curve.
- *"98.7% reduction"* — an illustrative worked example in Anthropic's
  code-execution-with-MCP blog, not a benchmark. Every secondary citation traces
  back to that one sentence.
- *"7–85% drops at 49–741 tools"* — no traceable primary source.

One landmine worth knowing:
[claude-code#40314](https://github.com/anthropics/claude-code/issues/40314) —
tool search does not defer HTTP/Streamable-HTTP MCP tools. 250 tools behind a
LiteLLM gateway measured **120.2K tokens (60% of the window) over HTTP vs 290
over stdio**. Closed as *not planned*. Phase 7 cut remote HTTP transport; this is
a reason to keep it cut.

## 5. What we tried first, and why it went

Tool search shipped here before code mode: one `search_tools` tool, MCP schemas
withheld until the model asked, discoveries recorded on the `tool/result` that
produced them so the set survived resume and replay. It worked, and it is worth
knowing why it was deleted rather than kept as an alternative.

- **It fixed one of three costs.** Schemas, not results, not round-trips.
- **Its record was transcript-derived**, which is the right shape and the one
  Anthropic, OpenAI and VS Code all use — but that only matters if you are
  mutating the tools array, and code mode never does.
- **Every discovery broke the prompt cache** ([§3](#3-the-constraint-that-shaped-our-version)).
  Code mode has no discovery step in the request at all.
- **Two ways to reach a tool is one too many.** `list_functions` *is* the search.
  Keeping both would have answered one question twice, and left a feature with no
  caller.

The removal took `tools/search.py`, the `loaded` plumbing through the loop, and
`ToolResultEvent.revealed` with it — about 500 lines. What survives is
`Ok.data`, which turned out to matter more for code mode than it ever did for
search: a script wants an object, not prose.

## 6. Code mode

`harness/sandbox/` runs the script and knows nothing else — `runner.py` is the
`Runner` seam, `deno.py` the only implementation today. `harness/tools/native/code/`
holds the three tools and the codegen they need.

Tool search fixes **schema** tokens. It does nothing about the other two costs,
and code mode fixes all three: MCP tools become a typed TypeScript API, the model
writes one program, and only what the program returns enters the conversation.

- **Result tokens.** A transcript fetched inside a script is filtered there and
  thrown away. Today it enters the log whole and is re-sent every turn after.
- **Round-trips.** Three subtitle fetches are three model calls; one script.

**There is no switch.** A flag would offer a second way to do the only thing
there is, so `load()` simply refuses to start when Deno is not on PATH, naming
the install and the setting to change. `code.deno_path` and `code.timeout_seconds`
are the only knobs.

### The three tools

| Tool | Returns |
|---|---|
| `list_functions()` | every capability as a signature, argument types omitted |
| `get_function_details(names)` | full types for the few the model intends to use |
| `execute_typescript(code, description)` | the script's return value and its `console.log` output |

Two-stage disclosure, then execution. Goose's shape, and the reason it beats
DeepSeek's whole-SDK-in-the-prompt is that the schemas never enter the prompt at
all — only the signatures do, and only until something asks for more.

### MCP → TypeScript, in five stages

Three of the five we already owned:

1. `tools/list` JSON arrives from the server.
2. Namespaced `{server}__{tool}` — `namespaced()` in `mcp/tool.py`.
3. Split apart again; the schema is carried **verbatim**.
4. **New:** JSON Schema → a `declare function`. Four rules (`string`→`string`,
   `integer`/`number`→`number`, `enum`→union, absent-from-`required`→`?`), plus
   `$ref`/`$defs` resolution because `model_json_schema()` emits them.
5. Calling reverses nothing: the script uses the **exact** MCP name, and the
   bridge dispatches it through `ToolDispatcher.dispatch` — the same path a
   model-issued call takes.

**Names are exact.** `yt__get_subtitles`, not `Yt.getSubtitles`. Namespacing and
camelCase read better and Goose does it, but every conversion needs an inverse,
and a name that appears one way in the declarations, another in an error and a
third in the log is a name the model cannot reason about. Declarations are
*grouped* by server instead, which buys the readability without the mapping.

**The printer never raises.** It runs during prompt assembly, where an exception
kills the turn, and its input is third-party JSON Schema of any draft. Every
construct it does not understand degrades to `unknown`. DeepSeek's
`jsonSchemaToTs` has the same property for the same reason.

### The sandbox

One Deno process per execution, started with **no `--allow-* flags at all`**. The
shim ships as a `data:` URL on the command line, so it is never a file on disk and
the child needs no read permission. The model's script is imported as a nested
`data:text/typescript` module, which is what strips its type annotations.

Four properties, verified against Deno 2.8.3 in
`tests/integration/test_code_mode.py` rather than assumed:

| | |
|---|---|
| generated declarations are valid TypeScript | Deno parses them |
| a script cannot reach the network | `fetch` throws |
| a script cannot read the filesystem | `readTextFileSync` throws |
| a runaway or cancelled script leaves no process | proved by pid |

That last one matters because there is no SDK here to reap the child — `mcp/store.py`
never kills anything because the MCP transport does it. Here a `finally` must.

**Every call goes through `ToolDispatcher.dispatch`.** A script reaches exactly what
the model could have reached directly, by the same route, so phase 12's approval
gate will cover scripts without knowing code mode exists. DeepSeek confirms the
seam: its bindings re-enter the full pipeline and denials surface to the script as
a catchable error. A `Failure` becomes a thrown `Error` at the language boundary,
because TypeScript callers expect `throw`.

**The recursion guard is doubled.** The three code-mode tools are excluded from
the catalog, so Deno never installs them as globals; and the bridge refuses them
by name, for a script that constructs one anyway. Without it,
`execute_typescript` inside a script spawns Deno from inside Deno, unbounded.

### Who else does this

| | Sandbox | Notes |
|---|---|---|
| Cloudflare `@cloudflare/codemode` | V8 isolates | most complete OSS; discovery moved *inside* the sandbox |
| Anthropic Programmatic Tool Calling | hosted container | Python, not TypeScript; tool results are strings |
| Goose via **pctx** | Deno | the shape we copied; pctx is Rust and shells out, as we do from Python |
| Vercel AI SDK | QuickJS/WASM | experimental |
| DeepSeek Harness | own runtime | whole SDK in the prompt, no discovery step |

Cursor, Windsurf and Continue ship nothing. LangChain archived `langgraph-codeact`.
Goose *deleted* its earlier LLM tool router (1,270 lines, Dec 2025) and replaced
it with this. Sandboxes converged on **JS engines, not containers** — startup cost
dominates when every turn spawns one.

Worth knowing, and worth holding against our own choice: DeepSeek ships code mode
in **one preset of four**, the one named `code`, and it is an opt-in
specialisation everywhere else it exists too. We made it the only mode. That is a
deliberate bet that one way of reaching tools beats two, and the measurement below
is what would falsify it.

### The evidence, honestly

Only one published figure has a quality metric beside it: **Anthropic's PTC,
+11% average performance with −24% input tokens** on BrowseComp and DeepSearchQA.
Self-reported, on public eval sets.

Everything else is token arithmetic. Cloudflare's "99.9%" compares tool-definition
size (1.17M tokens of OpenAPI vs ~1,000 tokens of two tools) and measures nothing
running. Anthropic's "98.7%" is one illustrative example in a design doc. pctx's
"2–3× input token cut" has no methodology.

**What nobody reports:** output tokens go *up* — the model writes a program
instead of a JSON blob — and debugging failed code costs extra turns. Every
published number is the one metric code mode trivially wins.

**Measured on this deployment:** _not yet recorded._ Run a multi-tool task and
record `prompt_tokens`, `output_tokens` and step count, against a build with
`ToolPipeline(registry)` — the no-code branch, kept precisely so the comparison
stays available. Expect fewer input tokens and steps, and **more output tokens**.
If total cost does not improve, write that here; it is the result.

### Follow-ups, with their triggers

- **Inner-call visibility.** A script is one `execute_typescript` card that says
  `running…` until it finishes; its inner calls are neither logged nor shown.
  Fixing it needs `parent` on `ToolCallEvent`/`ToolResultEvent`, a
  `derive_messages` filter (an inner result reaching a request would be a tool
  message no assistant message asked for, which a provider **rejects**), and
  nested cards. Trigger: a script slow enough that the silence hurts.
- **A result cap.** The cheap alternative to code mode for large results, which
  `mcp/tool.py` already says belongs in the pipeline. Claude Code caps at
  25K tokens and spills to disk; DeepSeek caps per tool and reports `truncated`.
  Trigger: one result blowing the window, without the round-trip problem.
- **Per-tool timeout in the pipeline.** `code.timeout_seconds` bounds a whole
  script and MCP bounds its own calls, but a native tool that hangs still hangs
  the turn. Trigger: a tool source arriving without its own bound.
