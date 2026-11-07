# 06 The docs describe the MCP servers screen

**Status.** open

**What to build.** README (Desktop app and MCP sections), CLAUDE.md's "a
capability is an MCP server" line, mcp-servers/README.md (how to add one of
ours on the screen), PHASES.md, `docs/specs/full-app/spec.md` (this spec
replaces its capability decisions), and a drive-cell-harness feature page
for the screen.

**Checks.** `make lint` and `make test` green. No doc says the app carries
uv or Node, or that capabilities are listed in config.json.

**Blocked by.** 03, 04, 05
