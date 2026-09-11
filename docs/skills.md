# Skills — what the field does, and what we take

The research behind phase 8. Read alongside [PHASES.md §Phase 8](../PHASES.md)
for the deliverables and [docs/rules.md](./rules.md) for the invariants it added.
Sources are at the end; every claim in the tables is from one of them.

## 1. The spec

[Agent Skills](https://agentskills.io/specification) is the format every client
below reads. A skill is a **directory**:

```
skill-name/
├── SKILL.md          # required: YAML frontmatter + Markdown instructions
├── scripts/          # optional: executable code
├── references/       # optional: documentation loaded on demand
└── assets/           # optional: templates, data
```

Frontmatter, the whole of it:

| Field | Required | Constraint |
|---|---|---|
| `name` | yes | 1–64 chars, `[a-z0-9]` and single hyphens, must match the directory |
| `description` | yes | 1–1024 chars, "what the skill does **and when to use it**" |
| `license` | no | free text |
| `compatibility` | no | ≤ 500 chars, environment requirements |
| `metadata` | no | string → string map |
| `allowed-tools` | no | space-separated, experimental |

Three tiers of **progressive disclosure**, which is the entire design idea:

| Tier | Loaded | When | Cost |
|---|---|---|---|
| catalog | `name` + `description` | every request | ~50–100 tokens per skill |
| instructions | the `SKILL.md` body | on activation | < 5k tokens recommended |
| resources | `references/`, `scripts/`, `assets/` | when the body names them | 0 until read |

The spec's [client guide](https://agentskills.io/client-implementation/adding-skills-support)
is prescriptive about the parts that matter to a harness:

- Scan `<project>/.agents/skills/` and `~/.agents/skills/` — the cross-client
  convention — as well as your own directory. Project beats user on a clash;
  warn on shadowing. Consider gating project-level skills on trust.
- **Lenient parsing.** `name` ≠ directory → warn, load. Missing description →
  skip. Unparseable YAML → skip. Quote-and-retry an unquoted
  `description: Use when: …`, the single most common cross-client breakage.
  Record diagnostics somewhere a person can see them.
- The catalog goes in the **system prompt or the activation tool's description**
  — both are blessed. Hide filtered skills entirely rather than listing and
  refusing. **No skills ⇒ no catalog and no tool**: "an empty
  `<available_skills/>` block or a skill tool with no valid options would confuse
  the model."
- A dedicated activation tool should **constrain `name` to the valid set** (an
  enum), return the body with the frontmatter stripped, wrap it in an
  identifying tag, and list bundled files without reading them.
- Users activate explicitly too (`/name`, `$name`): "the harness handles the
  lookup and injection, so the model receives skill content without needing to
  take an activation action itself."
- Protect loaded skill content from compaction; consider deduplicating a
  re-activation.

## 2. The clients

| | Claude Code | Codex / ChatGPT | OpenCode | Hermes Agent | OpenClaw |
|---|---|---|---|---|---|
| Shape | terminal coding agent | terminal + chat | terminal | **chat: CLI, Telegram, Discord** | **chat: messaging gateway, multi-agent** |
| Roots | `~/.claude/skills`, `.claude/skills`, nested, plugins, enterprise | `.agents/skills` repo → user → `/etc/codex` → bundled | `.opencode/`, `.claude/`, `.agents/` at project and home | `~/.hermes/skills`, `.hermes/`, `.agents/skills`, external dirs | workspace, `.agents/skills`, `~/.agents/skills`, managed state dir, bundled |
| Catalog placement | **in the `Skill` tool's description** — `<available_skills>` with name, description, location | system prompt, capped at 2 % of context or 8k chars | in the `skill` tool's description | a `skills_list()` tool (~3k tokens) | system-prompt XML; over budget it truncates descriptions but keeps names |
| Activation | `Skill(command=name)`; result "Launching skill", then an injected message with `<command-name>`, `Base Path:` and the body | the model reads the file | `skill({name})` | `skill_view(name[, path])` — `path` reads a bundled file | model told to read `SKILL.md` |
| User invocation | `/name args`; up to 6 stacked | `$name` (Codex), `@name` (ChatGPT) | — | `/name`; up to 5 stacked; bundles | `$name` in the composer; up to 8 |
| Visibility | `disable-model-invocation`, `user-invocable`, `skillOverrides` (on / name-only / user-invocable-only / off), `Skill(name)` permission rules | `policy.allow_implicit_invocation` | `permission.skill` glob → allow / deny / **ask** | `requires_toolsets` / `fallback_for_toolsets` | the same two flags; `agents.entries.*.skills` allowlist is the *final* set, no merge |
| Scoping | project / user | repo / user | per agent (`skill: false`) | project trust list | **per agent workspace** |
| Reload | watches `SKILL.md`; a new top-level directory needs a restart | — | — | — | snapshot per session; 250 ms debounced watcher |
| Re-invocation | identical rendered content → a one-line "already loaded" note | | | | |
| Compaction | re-attaches the last invocation of each skill, 5k tokens each, 25k total | | | | |
| Beyond the spec | `$ARGUMENTS`, `!`cmd`` preprocessing, `context: fork`, per-turn `allowed-tools` grants, `paths` globs, `hooks` | `agents/openai.yaml`: interface, MCP dependencies | | the agent writes its own skills (`skill_manage`), hubs, a scanner | `requires.bins/env/config` gates, installers, revisions, a proposal queue |

The Claude Developer Platform is a sixth data point: skills are uploaded and
versioned through `/v1/skills`, attached per request via `container.skills`,
and the model reads `SKILL.md` with bash inside the code-execution container.
Same three tiers; the catalog is in the system prompt.

## 3. What binds cell-harness

1. **The enum-constrained activation tool is the consensus.** cell-bot's
   generated `Literal[names]` (DESIGN.md) is what Claude Code, OpenCode and the
   spec all do.
2. **Nobody logs the catalog into the conversation.** Every client rebuilds it
   per request in the system prompt or the tool description. This harness
   already does exactly that with the tool list (`ToolPipeline.specs`) and the
   system prompt (`LoopAgent._request_messages`), neither of which is written to
   the log. PHASES.md's original "catalog message + digest + empty envelope +
   re-establish after compaction" was DeepSeek Harness's design and the outlier
   — it exists there because dsh injects the catalog as a user-role message and
   caches its prompt prefix. Rebuilding per request drops all four pieces and
   phase 12 has nothing to re-establish.
3. **No skills ⇒ no tool.** A provider that yields nothing is how that falls out
   of the registry.
4. **Two surfaces are the norm.** `disable-model-invocation` and
   `user-invocable` are Claude Code's names and OpenClaw's; user invocation is a
   harness expansion of `/name`, not a model action.
5. **Instruction-only skills are how chat products use them.** Scripts need a
   shell (phase 14). References, though, are read on demand — so the activation
   tool takes a `path`, Hermes-style, or a public skill with a `references/`
   directory is half unusable.
6. **`.agents/skills/` is the interop root**, and ranked roots with the project
   first are universal.
7. **Chat products scope per agent** (OpenClaw's allowlist, Hermes's trust
   list). Nobody scopes per conversation. That is phase 11's agent catalog;
   until then the catalog is global.
8. **Skills teach tool use.** Anthropic's own framing is that skills "complement
   MCP servers by teaching agents more complex workflows that involve external
   tools." The first committed skill here teaches the reel → place composition
   across two servers — the phase 7 demo, written down so the model does not
   rediscover it.

Not taken, with the reason: `!`cmd`` preprocessing (no shell; left literal, as
Claude Code does for synced skills), `context: fork` (no subagents until 15),
`allowed-tools` grants (7.5's rules already do this durably), installers and
hubs (a directory is the install), watchers (rescanning is cheaper and has no
"new directory needs a restart" hole), re-invocation dedupe (a second tool
result is the honest record of a second call).

## 4. Change detection — how each one notices an edited skill

Read from source for dsh (`packages/skill/skill-filesystem`), OpenClaw
(`src/skills/runtime/refresh*.ts`, `session-snapshot.ts`) and Hermes
(`tools/skills_tool.py`); from the docs for Claude Code.

| | dsh | OpenClaw | Hermes | Claude Code | cell-harness |
|---|---|---|---|---|---|
| Mechanism | chokidar watcher per root, invalidates a catalog cache | chokidar watcher, bumps a global snapshot version; per-session snapshot rebuilt when it moved | stat signature (max mtime of root + child *directories*) + 30 s TTL | watcher on skill dirs | `(mtime_ns, size)` per `SKILL.md`, rescanned per call |
| Size | ~1,040 lines, mostly watcher lifecycle | ~700 lines | ~30 lines | — | ~60 lines |
| In-place `SKILL.md` edit | seen after a 200 ms stability window | seen after a 250 ms debounce | **not until the TTL** — a directory's mtime does not move when a file inside is rewritten (their comment says so) | seen | seen next call |
| Root absent at startup | polls the nearest existing ancestor with `fs.watchFile` every 100 ms, one segment at a time | watches the nearest existing ancestor | picked up when it appears | **needs a restart** (documented) | picked up when it appears |
| Own writes | a synchronous `fs/observed` fast path, because the watcher would fire after the next step | same watcher | TTL | — | nothing special |
| Failure handling | watcher retry, 128-project LRU, symlink policy, teardown races | `EMFILE`/`ENOSPC` → warn once, stop watching | — | bare mode disables | unreadable root → last-good, warn once |

What it says: both TypeScript harnesses chose watchers and both paid in code
for the failure modes of *watching* — missing roots, handle exhaustion,
asynchrony against the model's own edits. Hermes chose stat-based detection but
at directory granularity, and needed a TTL to paper over in-place edits.
Statting the files closes that hole at the same cost class, needs no TTL, no
fast path for our own writes, and no ancestor polling — it is the primitive
git's index, `make` and `.pyc` caches rely on. Nobody hashes content.

## 5. Sources

- Agent Skills specification — https://agentskills.io/specification
- Agent Skills, adding skills support to a client — https://agentskills.io/client-implementation/adding-skills-support
- Agent Skills client showcase — https://agentskills.io/clients
- Anthropic, *Equipping agents for the real world with Agent Skills* — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Claude Code skills reference — https://code.claude.com/docs/en/skills
- Claude Developer Platform, Agent Skills overview — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Mikhail Shilkov, *Inside Claude Code Skills* (the Skill tool's schema and injected message, from the wire) — https://mikhail.io/2025/10/claude-code-skills/
- OpenAI, *How skills work in Codex* — https://learn.chatgpt.com/docs/build-skills
- OpenCode skills — https://opencode.ai/docs/skills/
- Hermes Agent skills — https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- OpenClaw skills — https://docs.openclaw.ai/tools/skills
- DeepSeek Harness `skill-filesystem` README and source — `github.com/deepseek-ai/deepseek-harness`, `packages/skill/skill-filesystem`
- OpenClaw source — `github.com/openclaw/openclaw`, `src/skills/runtime/refresh.ts`
- Hermes Agent source — `github.com/NousResearch/hermes-agent`, `tools/skills_tool.py`
