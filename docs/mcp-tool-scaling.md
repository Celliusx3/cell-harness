# Why MCP schemas load on demand

Every request re-sends every tool's name, description and argument schema. At
roughly **950 tokens per tool**, a handful of MCP servers costs more context than
the conversation does. This file records what the field does about that, what we
built, and what it costs.

**Our answer is select, then call** ([§7](#7-select-then-call)). The model
is offered three tools; it lists what exists, reads the schemas of the few it
needs, and from then on those are in its tool list and callable directly. A
program (`execute_typescript`) is for when one saves round trips — many calls,
or a large result filtered before it is seen. The request carries three schemas
plus whatever this conversation has read, however many servers are connected.

**How it got here.** Code mode — a program as the *only* route — was the answer
from §6 until phase 8. Read [§6 "Measured on this deployment"](#the-evidence-honestly)
for why that was already a loss at thirteen tools, and §7 for what changed it.

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
the model could have reached directly, by the same route, so a future approval
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

Worth knowing, and worth holding against our own choice: **every implementation
ships this opt-in.** DeepSeek puts it in one preset of four, the one named
`code`. Goose goes further — `pctx_code_mode` is a Cargo feature and
`crates/goose/Cargo.toml` has `default = []`, so it is not compiled into a stock
build at all. We made it the only mode. That was a bet before it was measured;
the measurement is below, and it is kept.

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

**Measured on this deployment.** Thirteen capabilities — a clock plus twelve
from two MCP servers — against `ToolPipeline(registry, dispatcher, ())`, whose
empty `default_tools` offers every registered spec. Two tasks, each run both
ways. The result did not improve, so per the instruction that used to sit here,
it is written down.

*Task A, deterministic — the current time in three cities:*

| | steps | prompt tokens | output tokens | tool-result chars |
|---|---|---|---|---|
| code mode | 4 | 11,946 | 171 | 13,111 |
| every tool offered | **2** | **12,123** | **95** | **75** |

*Task B, two remote Python jobs — result volume varies per run, so only steps and
tokens compare:*

| | steps | prompt tokens | output tokens |
|---|---|---|---|
| code mode | 4 | 19,991 | 155 |
| every tool offered | **2** | **15,586** | **136** |

**Code mode lost on every axis, both times.** Four findings, and only the last
was a bug:

1. **The input-token saving did not appear.** 11,946 against 12,123 — under 2%,
   and the wrong way on task B. `list_functions` does not avoid the cost of
   thirteen schemas, it *moves* it: the catalog is 12,830 characters, and it goes
   into the conversation rather than the request. That is 98% of code mode's
   entire tool-result volume on task A, spent to avoid schemas that cost about
   the same.
2. **Models batch tool calls.** The direct path made all three clock calls in a
   single assistant message — two steps, 75 characters of results. Code mode's
   round-trip argument assumes a model calls tools one at a time. Current ones
   do not.
3. **Output tokens went up** — 171 against 95, and 155 against 136. Exactly the
   metric noted above as the one nobody publishes.
4. **Wrong scripts cost turns.** Most MCP servers publish JSON as *text* rather
   than `structuredContent`, so a script reading `results.jobs` got `undefined`.
   Observed live: five failing scripts and a cancelled turn. Fixing it (parse
   text that is JSON, pass everything else through — the same rule Goose's
   `callback_result_to_value` applies) took task B from six steps to four and
   output from 552 tokens to 155. It improved code mode materially and changed
   no verdict.

None of this says code mode is wrong. It says **thirteen tools is not its use
case** — which is what Goose encodes by shipping it behind a Cargo feature that
`default = []` leaves off, and DeepSeek by making it one preset of four.

### The decision, and what would reverse it

**Code mode stays the only mode.** Taken with the numbers above in hand, so it is
a bet rather than an assumption: that server count only grows, and that one way
of reaching tools is worth more than a second one that is cheaper today. The
crossover is real but unmeasured — somewhere past thirteen tools the catalog
stops being the expensive half.

What would reverse it, concretely:

- The catalog exceeding what it saves by more than it does now — measure again at
  ~30 tools, when `list_functions` is 30K characters and the schemas it replaces
  are still roughly the same size.
- Scripts routinely needing a repair round. Before the JSON fix, task B took six
  steps rather than four and one live conversation burned five failing scripts
  before being cancelled; after it, both code-mode runs above wrote one script
  and stopped. If that regresses, the extra turns cost more than the catalog.

Cheaper than reversing: trim what `list_functions` emits, and re-measure. The
catalog prints every function with its one-line description; most of a turn's
13K characters is capability the model was never going to call.

### Re-measured at 17 tools (the Instagram/POI servers)

The first real growth in server count since the decision above — which is the
thing the bet was placed on. Two servers added under `mcp-servers/`, `instagram` (2 tools) and `places`
(2 tools), joining the clock, `jobs` (2) and `yt` (10).

| | tools | `list_functions` catalog |
|---|---|---|
| §6's measurement | 13 | 12,830 chars |
| now | **17** | **17,161 chars** |

So +4 tools cost +4,331 characters of catalog, or ~1,080 chars per tool — and
`get_function_details` over everything is 18,585, barely more than the catalog
itself. That ratio is what makes the two-stage disclosure look thin at this
scale: the summaries are nearly as expensive as the schemas they defer.

**The reversal trigger is not met and is now visibly closer.** At ~1,080 chars
per tool the 30K catalog named above arrives at roughly 28 tools, so one more
ten-tool server would reach it. The decision stands unchanged; the next server is
the one to re-measure at.

Worth noting separately, because it is not a cost: the newer `mcp` client sends
`server/discover` on connect, and servers that predate it log a wall of
`ClientRequest` validation errors before connecting normally. Cosmetic, and
upstream — but it makes a healthy startup look broken.

## 7. Select, then call

**What changed.** Three things landed together during phase 8.

1. **Anthropic's own guidance for programmatic tool calling is per tool, not
   per harness.** Each tool declares `allowed_callers: ["direct"]` or
   `["code_execution"]`, with the tip *"choose one rather than enabling both."*
   Their fit table: strong for fan-out and large results to filter; **weak for
   "strictly sequential workflows where each call depends on Claude reasoning
   over the previous result"** and for "a small number of tool calls with small
   responses." Measured: a 75-tool agent −38 % input tokens; **τ²-bench (one or
   two sequential calls per turn) unchanged accuracy, +8 % cost.** And Haiku 4.5
   is excluded from the feature entirely.
2. **The first real skill is a sequential workflow.** `find-place` is fetch →
   read the caption → decide → search → details; every step depends on the
   model looking at the previous result. Under code mode the default model wrote
   *three programs of one call each* — every cost of a script, none of its
   saving. That is Anthropic's weak-fit column, verbatim.
3. **A 4B model showed what small models do.** Given the skill, qwen3-4b copied
   the function names out of it and called them as plain tools. That ran (see
   "Registered is not offered" in CLAUDE.md for why it should not have), and got
   the right place. Forced through code mode, the same model guessed a return
   shape and got it wrong. Small models can call a tool; they cannot reliably
   write a program against a schema they have not read.

**The cache argument, re-examined.** §3 and §5 give "every discovery broke the
prompt cache" as the reason the earlier tool search was deleted. Measured on
this endpoint (two identical requests: `cached_tokens 0`, then `2624 of 2636`),
the cache is real — but the cost of a read is *one* miss, after which the
tools array is constant again. What was wrong with the old search was churning
the array step after step, not changing it at all. Code mode's "constant array"
saved nothing over that: its 17K-character catalog lands in the conversation
and is cached from its second appearance the same way. The `cached` column
below was read off the provider's `prompt_tokens_details.cached_tokens` by
hand; the adapter does not record it.

**The mechanism — Anthropic's shape.** Their tool search returns
`tool_reference` blocks, and *"the API expands `tool_reference` blocks
throughout the conversation history, so Claude can reuse discovered tools in
later turns without re-searching"*; a custom search tool participates by
returning the same blocks in an ordinary `tool_result`. Here,
`get_function_details` is that tool: its result is
`[Text(declarations), ToolReference(name)…]` (`llm/messages.py`), the loop logs
the blocks as they are, and `Session.tools_selected()` folds the references out
of the whole log — the same "read history, expand references" the docs
describe. The one thing their API does that ours cannot is the expansion: this
endpoint is OpenAI-shaped and has no `tool_reference`, so the harness expands —
the pipeline puts the referenced tools into the next request, and the adapter
renders the block as a sentence (`REFERENCES_NOTE`) so the model knows its list
changed. The pipeline's refusal of an unreferenced name says to read it first:
the gate is a sequence, not a wall, and it is the step the 4B model skipped.
Scripts never pass through the pipeline and are unaffected;
`execute_typescript` remains, for the workloads §6 was right about.

**Bounded.** Only the `MAX_TOOLS_SELECTED` (8, in `tools/pipeline.py`) most recently
selected tools are promoted; a re-read moves a tool back to the front, and one that fell off is
refused like one never read and re-read at the same one-miss cost. Without
that, reads accumulate for the life of a conversation and a long one that
wandered across every server would send most of the catalog this mechanism
exists to avoid — the request would scale with history rather than with the
task at hand.

**Measured, the same reel, the same prompt.**

| | steps | input tokens | cached | output | Deno spawns | result |
|---|---|---|---|---|---|---|
| ilmu-glm-5.1, code mode (before) | 6 | 28,264 | 20,544 | 463 | 3 | correct |
| ilmu-glm-5.1, select-then-call | 7 | 26,575 | 20,480 | 404 | **0** | correct |
| qwen3-4b, code mode (before) | 3 | — | — | — | 2 | **wrong** — guessed a shape |
| qwen3-4b, select-then-call | 9 | — | — | — | 0 | partial — three refusals before it read the schema; found the venue from the caption, never searched Places |

The two reads in the glm run show as the two dips in `cached` (1,856
each time the array grew) — the price of a read, visible for the first
time. Output tokens fell because a JSON call is shorter than a program that
makes one.

**What this does not change.** `list_functions` is still the catalog and still
scales as §6 measured; the reversal trigger there (a ~30K catalog at ~28 tools)
still stands and now argues for trimming what it prints, not for reopening the
mechanism. The doc's "one route" rule is relaxed: a selected tool is callable
both directly and from a program, and the model uses whichever the task shape
wants.

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
