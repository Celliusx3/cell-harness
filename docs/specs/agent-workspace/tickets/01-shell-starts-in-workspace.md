# 01 The shell starts in the chat's workspace

**Status.** open

**What to build.** The files repository gains the folder of a chat's workspace, `<files root>/workspaces/<chat id>/`, made on first use. The MCP tool's invoke sends that folder in the request `_meta` under one generic key, for example `harness/workspace`, from `CallOrigin.conversation_id`. It goes to every server, so the harness names no server. The MCP client and the connection command carry the `_meta` through. In `mcp-servers/computer`, `computer__shell` uses it as the start folder when the call gives no `cwd`, and `/home/pc` otherwise.

**Checks.**

- A harness integration test calls a stub MCP server's tool for a bot's chat.
- The server receives `_meta` naming `<files root>/workspaces/<bot id>/`, and the folder exists.
- A computer server test calls `shell` with that `_meta` and `pwd`.
- It prints the workspace.
- With `cwd` given, it prints `cwd`.
- With no `_meta`, it prints `/home/pc`.
- A worker's call carries its bot's workspace.
- `make test` and `make test-mcp-servers` pass at 80%.

**Blocked by.** none
