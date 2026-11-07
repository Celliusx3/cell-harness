# 01 The person's MCP servers are saved, and start and stop live

**Status.** done

**What to build.** A saved list of the person's servers in its own file
(`mcp.path`, default `~/.harness/mcp.json`; the Mac app's is in its data
folder), read and written like `bots.json`. Each entry has an id, command,
args, plain env settings and the key names it `needs`. `McpService` opens
the built-in servers from config plus the saved ones, and gains add, change
and remove, each starting or stopping only that server. Routes under
`/api/mcp/servers` list, add, change and remove them, and restart one; only
a page on this Mac may change them, as for credentials. An id taken by a
built-in server is refused.

**Checks.** Backend tests: adding a server starts it and its tools are
offered on the next request; changing it restarts it; removing it stops it
and its tools go; the list survives a harness restart; a server that needs
a key waits until a Capability key is saved; a change from another device
is refused. `make lint` and `make test` are green.

**Blocked by.** none
