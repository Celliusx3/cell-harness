# DeepSeek Harness — teardown and replication guide

Source: `/Users/coyan.oh/Desktop/cellstudio/deepseek-harness`, tracking
`github.com/deepseek-ai/deepseek-harness`. Pulled to `b150a551b8`
(`release/dsh-0.1.1-rc.2`) on 2026-08-22 — 854 commits ahead of the checkout that
was on disk.

## 0. Scale check — read this before deciding to "replicate"

| Measure | Value |
|---|---|
| Workspace packages | 227 `package.json` under `packages/` |
| Apps | 2 (`apps/cli`, `apps/web`) |
| Source TS (excl. tests) | ~256,000 lines across 1,518 files |
| Test files | 696 `.spec.ts` |
| Language surfaces | TypeScript monorepo (pnpm) + a Python SDK (`python/sdk`) + `native/` |

This is not a project you clone the *code* of. It is a project you clone the
*architecture* of. Sections 1–5 extract the design; section 6 is the actual
replication plan at a tractable size.

## 1. The one idea: everything is a plugin

dsh is built on [Cordis](https://github.com/cordiverse/cordis) — a
dependency-injection + reversible-effects framework. Plugins contribute
**services**, **typed events**, and **reversible effects** to a shared `Context`
(`ctx`).

From `docs/architecture.md`:

> Every part of the product is a plugin, including the model adapter, the tool
> registry, the session log, and the agent loop itself, so every part is
> replaceable from configuration. There is no privileged core to patch.

Concretely, the runtime is a tree of rows like:

```yaml
- insert:
    - id: llm
      name: '@deepseek-ai/dsh-llm'
    - id: session
      name: '@deepseek-ai/dsh-session'
    - id: session-title-llm
      name: '@deepseek-ai/dsh-session-title-first-prompt-llm'
      config:
        targetWords: 5
```
(`packages/bundle/base/cordis.patch.yml`)

Registrations are **effects that unwind when their plugin unloads**. That single
property is what makes per-agent scoping, hot reload, and teardown correct rather
than best-effort.

### Profiles and bundles

- A **bundle** is a distribution format for config rows + the code they mount
  (`dsh.bundle` field in `package.json`).
- A **profile** is a named composition stacking bundles, stored in the Harness
  home (`dsh.profile` field).

Layering order, applied to an empty entry list:

1. each bundle in the profile's listed order (`dsh-base` is always first)
2. the profile's `cordis.patch.yml`
3. the home-level `cordis.patch.yml`
4. any `--patch` overlay

A patch targets a row **by id and replaces its whole config** — deliberately no
deep merge. `dsh --profile web --dump-config` prints the exact tree your machine
boots, and every row it prints is overridable.

Shipped bundles: `dsh-base` (adapters, tools, persistence, sandbox, approval,
settings, credentials, telemetry), `dsh-web-app` (browser app), `dsh-headless`
(one-shot runner, no server).

## 2. The spine — six core packages

| Package | Owns | `ctx` key |
|---|---|---|
| `core/session` | Append-only `SessionEvent` log + in-memory store | `ctx.sessions` |
| `core/system-prompt` | Prompt-section and tool-schema assembly | `ctx.systemPrompt` |
| `core/tools` | Scoped tool registry + guarded execution pipeline | `ctx.tools` |
| `core/agent` | `Agent` interface, live registry, `agent/*` events | `ctx.agents` |
| `core/agent-loop` | The default driver implementing that interface | `ctx.agentLoop` |
| `core/scope` | Per-agent scoped-registration primitive | library, no key |
| `llm/llm` | Message/stream vocabulary + adapter seam | `ctx.llm` |

`scope/` is dependency-free and sits *below* `session/` and `system-prompt/` in
the module graph precisely so they can consume it without a cycle. Extension
plugins depend on `agent`, **never** on `agent-loop` — that is what keeps the
loop swappable.

## 3. Turn flow

```text
turn/start
  claim next-step input plus one queued message
  assemble prompt sections + tool schemas
  -> agent/pre-step                   reject | enter(messages)
     step/start
     append entered messages as user/message
     derive model history from the log
     agent/request -> llm/stream -> assistant/chunk* -> assistant/message
     tool/call* -> tools/pre-execute -> tools/execute -> tools/post-execute -> tool/result*
     step/end
     tools owe another request, or next-step input arrived -> claim -> next step
  -> agent/turn-stopping
turn/end
```

Definitions that matter:

- A **step** is one model request plus the tools it calls.
- A **turn** is zero or more steps; it opens before its first input is claimed
  and closes once nothing is owed.

`turn/*`, `step/*`, `user/message`, `assistant/*`, `tool/*` are **durable session
events**. `agent/pre-step`, `agent/request`, `llm/stream`, and the three
`tools/*` events are **waterfalls** (listeners call `next()` to delegate).
`agent/turn-stopping` is serial with no `next()`.

Input reaches the driver through **one inbox** with three fixed presets on the
`Agent` handle:

| Method | Target | Wakes driver? |
|---|---|---|
| `followup(msg)` | next turn, sole ordinary message of its own turn | yes |
| `steer(msg)` | nearest step boundary | yes (starts a turn if idle) |
| `inject(msg)` | next pre-step, model-facing context | **no** — waits for another message |

All three are aliases over one `send(message, target, wakeup)`.

## 4. The session log is the source of truth

`docs/subsystems/session.md`:

> A `Session` is an **append-only log** of typed `SessionEvent`s — the single
> source of truth. The LLM message history is *derived* from the log, never
> stored separately; replay is re-derivation from the same events.

The invariant that gives this teeth:

> **Model-visible means logged.** Anything that reaches a model request must be
> reconstructable from the log, and a runtime invariant asserts it.

So adding a new model-visible input *requires* a new session event — you extend
`SessionEventMap` (declaration merging) and render from the log. Compaction and
the hook protocol both do exactly this (`compaction/start|summary|end`,
`hook/invoked|result`).

Every event is lossless JSON with contiguous sequence numbers, **including raw
`assistant/chunk` events**, so persistence stores the canonical log verbatim and
UI replay is token-faithful.

## 5. Capability seams

A **seam** = three roles: a **Service Definition** (the interface), a **Service
Provider** (an implementation), and a **Consumer** (usually a model-facing tool).
One role alone is not a seam; adding a capability means designing all three.

This is why one provider swap changes the whole product: filesystem and
subprocess providers share one execution world, so pointing them at a remote
sandbox moves Bash, PTY, and LSP with them — no provider forks.

The full package inventory as shipped, grouped by seam:

| Group | Packages |
|---|---|
| shell | `shell`, `bash-local`, `bash-sandbox`, `pwsh-local`, `pwsh-sandbox`, `tool-bash`, `tool-bash-persistent`, `tool-pwsh`, `tool-pwsh-persistent` |
| fs | `fs`, `fs-local`, `fs-sandbox`, `fs-observation-policy`, `tool-fs`, `tool-fs-search`, `tool-str-replace-editor` |
| llm | `llm`, `llm-deepseek`, `llm-pi-ai`, `llm-retry`, `token-meter` |
| session | `session-persistence` (+`-jsonl`, `-sqlite`), `session-projection` (+`-cache`), `session-checkpoint-policy`, `session-stats`, `session-telemetry` (+`-otel`), `session-title` (+3 strategies) |
| subagent | `subagent`, `-acp`, `-claude-code`, `-codex`, `-dsh-sdk`, `-fork-in-process`, `-spawn-in-process`, `-in-process-driver`, `tool-subagent`, `tool-subagent-control`, `tool-subagent-report` |
| sandbox | `sandbox`, `sandbox-local`, `sandbox-policy`, `sandbox-windows-acl` |
| storage | `storage`, `storage-domain`, `storage-json`, `storage-sqlite` |
| context | `agent-instructions`, `file-reference`(+`-local`), `session-reference`, `time-context`, `tmux-context` |
| compaction | `compaction`, `compaction-basic`, `compaction-tool-result-pruner`, `command-compact` |
| workflow | `workflow`, `workflow-worker-thread`, `tool-workflow`, `tool-ralph` |
| jobs | `jobs`, `jobs-local`, `tool-jobs` |
| goal | `goal`, `goal-round-driver`, `tool-goal`, `command-goal` |
| interaction | `commands`, `permission-presets`, `tool-ask-user`, `user-approval`, `user-questions` |
| hooks | `hook-protocol`, `hooks-claude-code`, `hooks-codex` |
| code-runtime | `code-runtime`, `code-runtime-python`, `code-runtime-worker-thread` |
| spill | `spill`, `spill-local`, `spill-policy` |
| guard | `repeat-tool-reminder`, `timeout-policy` |
| other | `skill`(+`-badge`,`-filesystem`,`tool-skill`), `mcp-client`, `lsp`, `terminal`, `plan-mode`, `todo`, `schedule`, `credentials`, `settings`, `acp`, `api/gateway`, `sdk`, `experimental/agent-team` |

### Model-facing tool surface

The generated `docs/tool-catalog.md` is the authoritative list. Headline tools:

`bash` · `read` / `write` / `edit` / `read_image` · `str_replace_editor` ·
`glob` / `grep` (packaged ripgrep via `ctx.subprocess`, never a shell) ·
`web_search` / `web_fetch` · `todo_write` · `skill` · `subagent` /
`subagent_fork` / `send_message` / `interrupt_agent` / `list_agents` /
`report` · `job_list` / `job_output` / `job_kill` · `terminal_*` (6) ·
`ask_user_question` · `exit_plan_mode` · `create_goal` / `get_goal` /
`update_goal` · `schedule_*` · `session_*` (5 read-only) · `lsp` ·
`workflow` / `ralph` · `run_code` (code mode)

Three details worth stealing outright:

1. **`schemas()` uses an explicit allowlist.** `output`, `execute`,
   `finalizeContent`, `timeoutMs`, `isConcurrencySafe`, `presentCall`,
   `presentResult` must never leak into a model request. The registry enforces
   this structurally rather than by convention.
2. **`isConcurrencySafe(args)` is opt-in and defaults closed.** Omission,
   exceptions, and non-`true` returns are all exclusive.
3. **The tool catalog is generated by *booting* each plugin** and reading
   `ctx.tools.schemas()` — because a schema is not statically knowable
   (runtime-spread enums, config-driven names, raw MCP schemas). A completeness
   guard globs `packages/*/tool-*` and fails if any package is missing from the
   generator's manifest, so a new tool cannot be silently undocumented.

### Code mode

`run_code` is a reserved transport: under `mode: code` the registry's *only* wire
contribution is `run_code`, and the other capabilities are declared as a
generated SDK in the runtime's language. A program calls them through bindings
that **re-enter the complete guarded tool pipeline**, with submission-ordered
starts and overlap up to `maxParallelSubCalls`. Each nested execution links back
to the outer result.

## 6. How to replicate — three tiers

### Tier 1 — "the architecture, at 5% of the size" (recommended)

Target: ~8–12k lines, one language, no plugin framework. You keep every load-bearing
idea and drop the generality.

| dsh mechanism | Tier-1 substitute |
|---|---|
| Cordis plugins + reversible effects | A `Registry` object with `register()` returning a disposer; a `Composition` that holds an ordered list |
| Profiles/bundles/YAML patches | One typed config file + a `dict` overlay, applied by row id |
| `SessionEventMap` declaration merging | A tagged-union event type + a `register_event()` for extensions |
| Waterfall events | An ordered middleware chain (`async def mw(ctx, next)`) |
| Per-agent `agent.ctx` scoping | A scope key on every registration; registry filters by scope |
| Seams as packages | Seams as `Protocol`s in one `seams/` module |

Build order (each step ships something runnable):

1. **Event log first.** `SessionEvent` union, append-only `Session`,
   `derive_messages(log) -> list[Message]`. Write the "model-visible means
   logged" assertion *now* — retrofitting it is the expensive path.
2. **LLM seam.** One `LLMClient` Protocol streaming a chunk union with exactly
   one terminal event. One adapter.
3. **Tool registry.** `ToolDefinition` with a schema allowlist, guarded
   `execute`, and the three-stage pipeline (`pre_execute` / `execute` /
   `post_execute`) as middleware.
4. **The loop.** turn/step semantics exactly as section 3. Emit every durable
   event. This is where you earn the right to everything else.
5. **System-prompt assembly.** Ordered named sections (`-100` harness identity,
   `0` deployment persona, `100–199` tool guidance), a `complete` override, and
   `{{variable}}` interpolation at render time.
6. **Inbox.** `send(msg, target, wakeup)` + the three presets. `inject()` not
   waking the driver is the subtle, valuable bit.
7. **Persistence.** JSONL append of the canonical log. Resume = replay.
8. **First seam pair.** `fs` + `subprocess` behind Protocols, with a local
   provider. Now `bash`/`read`/`write`/`grep` all move together when you add a
   sandbox provider.
9. **Subagents.** One `SubagentProvider` Protocol; `fork-in-process` first.
10. **Compaction** as a seam that appends its own events.

### Tier 2 — "adopt Cordis, write our own packages"

`pnpm add cordis`, then rebuild the six spine packages against it. You get
reversible effects, service DI, and hot reload for free and skip the hardest
plumbing. Cost: TypeScript-only, and you inherit Cordis' learning curve —
budget real time on `docs/cordis-primer.md` and `docs/cordis-tutorial/01..04`.

### Tier 3 — "fork dsh"

MIT licensed, so legally fine. Practical objections: it is in *developer
preview* with explicitly promised compatibility-breaking changes, it moved 854
commits in ~6 days on our own checkout, and the Windows/POSIX shell gating,
i18n triple-file convention (`x.md` / `x.zh.md` / `x.i18n.yaml`), and generated
doc verification (`pnpm run doc-sync`) are all maintenance you would inherit.
Only worth it if you intend to track upstream, not diverge.

**Recommendation: Tier 1.** See `../DESIGN.md`.

## 7. Practices worth copying regardless of tier

- **Generated documentation with a verification gate.** `docs/tool-catalog.md`,
  `docs/config-catalog.md`, `docs/persistence-catalog.md`, and
  `apps/cli/composition.md` are all generated and CI-verified fresh. A drifted
  doc fails the build.
- **`docs/event-producer-consumer.md`** — a map of every event's producers and
  consumers. In an event-driven harness this is the file that keeps the system
  comprehensible.
- **A "where new behavior goes" table** (`architecture.md` §"Where new behavior
  goes"): goal → mechanism, 20 rows. Changing the loop means updating this map.
  It is the cheapest possible defense against ad-hoc extension points.
- **`.agents/notes/`** — durable design notes referenced by path from code
  comments and docs (e.g. the parallel-tool-call contract, the
  cancel-convergence wake latch). Decisions stay findable from the code.
- **`AGENTS.md` with `CLAUDE.md` as a symlink to it.** One file, both toolchains.
- **Per-package README sections**: every package README carries a *Model
  Experience*, a *KV Cache effect*, and a *Known Limitations and Deferred Work*
  section. Prompt-cache impact as a mandatory review field is a genuinely good
  idea for any harness.
