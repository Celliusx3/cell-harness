# 09 The app ships no built-in MCP servers

**Status.** done

**What to build.** `config.json` has no `mcp.servers`. The split between built-in and saved servers goes, so every server comes from the servers file. CLAUDE.md, the README, `config.local.example.json` and the drive-cell-harness skill say to add servers, `computer` too, on MCP servers. Files: `backend/config.json`, `config/settings.py`, `mcp/saved.py`, `web/server.py`, docs.

**Checks.** Integration: the app starts from the committed config and connects no MCP server. Adding `computer` on MCP servers connects it, and `computer__shell` is in the next turn's tools.

**Blocked by.** 08
