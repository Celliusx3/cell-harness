# Memory — insertion 9, "it remembers"

The model keeps notes across conversations and finds them again: "remember
this cafe", "remember my dentist's number", and in a later chat "which cafe
did I like in Petaling Jaya?". The notes are Markdown files a person can open
in Obsidian. There is no limit on how many.

Memory is a capability, so it is an MCP server declared in `config.json`
(`mcp.servers.memory`), like `places` and `markets`; `backend/harness/` gained
one sentence of system prompt and nothing else. The server is
[Basic Memory](https://github.com/basicmachines-co/basic-memory). A skill,
`.agents/skills/remember/SKILL.md`, tells the model when to save and when to
search.

## The three shapes, and why this one

Seven read-only researchers over two rounds (this project, GitHub three times,
library docs, the web twice), 2026-09-19.

| Shape | Who builds it | The line that defines it |
|---|---|---|
| **A store of notes plus search on demand** | Basic Memory, mcp-obsidian, mem0, langmem, Letta archival, OpenClaw daily notes | "archival memory fragments cannot be pinned to the context window, and must be queried on-demand via tools" ([Letta](https://docs.letta.com/guides/agents/archival-memory)) |
| A file tree with an index always in view, bodies read on demand | Anthropic API memory tool, Claude Code auto-memory | "it is an index, not a memory container" ([Claude Code](https://github.com/Windy3f3f3f3f/how-claude-code-works/blob/main/en/docs/08-memory-system.md)) |
| Blocks always in context with a character limit | Letta core memory, Hermes, ChatGPT saved memories | "They are always visible - no retrieval needed" ([Letta](https://docs.letta.com/guides/agents/memory-blocks)) |

The first shape is the pick because the person expects many things in memory
over time (places, contacts, whatever comes) and wants to ask it to search; the
other two are bounded by what fits in a prompt. The cost, from every source
that has run one for long: the model has to decide to search, and "the setup
breaks around a few hundred notes: retrieval gets noisy, the vault goes stale,
and nothing prunes or reconciles it"
([a year-long user](https://theaioperator.io/p/claude-code-as-a-second-brain-what)).
The system-prompt sentence and the skill are the answer to the first; the
second is a known follow-up, not solved here.

## Why Basic Memory, and not our own server

| Candidate | What it is | Why or why not |
|---|---|---|
| **Basic Memory** (4.0k stars, AGPL-3.0, pushed 2026-09-16) | Markdown notes with frontmatter in a folder, SQLite index, "Hybrid full-text + vector ranking with FastEmbed embeddings"; `write_note`, `search_notes`, `read_note`, `edit_note`, `delete_note`; "Notes created by your AI ... automatically appear in Obsidian since they share the same markdown files" | Picked: proven, Obsidian-native, search built in, every tool declares an `outputSchema` (checked 2026-09-19, the README's test for a third-party server), zero harness code |
| `mcp-servers/memory/`, ours | A folder of notes plus SQLite FTS5, five tools, ~300 lines | The fallback if Basic Memory fails; not needed |
| mcp-obsidian (4.4k stars) | Search and patch over a live vault through the Local REST API plugin | The assistant would search every private note; needs Obsidian running |

AGPL is fine because it runs as a separate process over MCP. It phones home
with anonymous telemetry by default; `BASIC_MEMORY_NO_PROMOS=1` in the
committed `env` turns that off.

## Setup

`uvx` is on PATH wherever `uv` is. The first start downloads the package and
an embedding model; later starts are quick. Notes live in `~/basic-memory`
(`~/.basic-memory/config.json` holds the project path; `basic-memory project
add` points it elsewhere, a subfolder of an Obsidian vault included). Open
that folder in Obsidian to see and edit what the model remembers.

## What the model is told

`SYSTEM_PROMPT` (`web/agent.py`): search before answering about anything the
person said in an earlier conversation, and save what they ask to remember.
The `remember` skill names the four functions, the `directory` for each kind
of note (`places`, `people`, `notes`), what never to save unasked (health,
finances, religion, politics), and what to say on an empty search. Both
wordings have their observed failures in
[prompt-failures.md](./prompt-failures.md).

## Verified 2026-09-19

Through the API, model gemma-4-e4b (a 4B-class model on LM Studio; `config.local.json` overrides the committed `llm`): a cafe saved (`places/Nadi Kopi.md`), a contact
saved (`people/Dr Lim.md`), the cafe recalled in a new conversation with its
cash-only detail, "what is my mum's birthday?" answered "I have nothing saved
about that" after three searches, and a diabetes remark left unsaved. The model
tried a direct call before reading the schema on two of four runs and recovered
from the refusal each time; one wasted call per turn, the shape phase 7's
"registered is not offered" intends.
