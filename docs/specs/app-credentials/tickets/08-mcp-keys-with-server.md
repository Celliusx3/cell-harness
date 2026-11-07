# 08 MCP keys are saved with their server

**Status.** done

**What to build.** The MCP servers screen asks for each key a server `needs` in a hidden field, and saves it in that server's `env` in the servers file, written 0600. `CapabilityDetails`, `capability_keys` and the capability parts of Credentials go. The list on MCP servers shows each key as set or missing, never its value. Files: `web/routes/mcp_servers.py`, `mcp/keys.py`, `mcp/service.py`, `secrets/` (capability removal), `web/credential_effects.py`, `frontend/components/mcp/ServerFields.tsx`.

**Checks.** Integration: a server added with a key connects with the key in its env. The servers file is 0600 and holds the key. `GET /api/credentials` lists no capability entry. The MCP list shows the key as set, without its value.

**Blocked by.** none
