# 01 Bots are told about the PC

**Status.** open

**What to build.** Keep each MCP server's `instructions` from its connect reply
in `mcp/_connection.py`, and expose them per server in `mcp/service.py`. Add a
session event `server/instructions` beside `bot/instructions` in
`session/models.py`, written when the text first reaches a turn or changes.
`runtime/system_prompt.py` puts the logged text in the prompt. The `computer`
server sends instructions that say what the PC holds and when to use it.

**Checks.** A unit test connects a fake server with instructions. The prompt
holds that text, and the session log holds one `server/instructions` event.
With the app running, a new bot asked "what can you do?" mentions the PC.

**Blocked by.** none
