# 03 Only the PC is built in

**Status.** open

**What to build.** `backend/config.json` and `desktop/config.json` list only
the `computer` server. A server named only in a config file stops the
harness at start, saying to add it on the MCP servers screen. The app's
bundle drops uv, Node and the instagram, places and markets servers; it
keeps Python, Deno and the computer server. Tests that pinned the app's
capability list change with it.

**Checks.** `make test` green. `make dev` with a `config.local.json` that
still lists a server refuses with the message naming it. The packaged app's
`Resources` has no `node` folder, no `uv`, and only `servers/computer`.

**Blocked by.** 02
