# Memory — each bot's and each group's workspace

A bot keeps what it learns in its own workspace, and a group keeps what its
members learn in the group's. "The client only accepts PDFs", said once in one
chat, is in front of the bot in every later chat. The workspace itself is
[specs/agent-workspace/spec.md](./specs/agent-workspace/spec.md).

## How it works

A workspace is a chat's folder under the files root, `workspaces/<chat id>/`.
A bot's own chat gives the bot's workspace, and a group's chat gives the
group's. It holds any files, like a Claude Code project, and
`memory/MEMORY.md` in it is that bot's or that group's memory. You can open
the folder in Obsidian.

On every step the bot is shown the first 200 lines of its own
`memory/MEMORY.md`, read from disk like the skill list. In a group's chat it
is also shown the group's. Every other file is read, searched or edited with
the `workspace_*` tools when the bot needs it. Claude Code's
auto-memory, Letta's memory blocks and LobeHub's agent documents keep a short
part always in view in the same way.

The bot keeps its memory itself, without being asked: the rule is the last
part of `ORCHESTRATOR_INTRO`. It never saves health, money, religion or
politics unless the person asks.

## Why not Basic Memory any more

Until this change, memory was [Basic Memory](https://github.com/basicmachines-co/basic-memory),
one MCP server with one notes folder that every bot shared, searched on
demand. The person wanted memory per bot and per group, in the same folder as
the bot's other work. The old page, with the research behind Basic Memory, is
`git show 47b764ca:docs/memory.md`.

`~/basic-memory` is left untouched. Remove the `memory` server on
Settings → MCP servers if it is still added.
