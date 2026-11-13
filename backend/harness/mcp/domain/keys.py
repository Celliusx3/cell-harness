"""The keys a server waits for, which are still missing from its env."""

from __future__ import annotations

from harness.mcp.domain.server import McpServer


def missing_keys(server: McpServer) -> tuple[str, ...]:
    """Each key `server` needs that its env lacks or leaves blank, in the order it lists them."""
    return tuple(name for name in server.needs if not server.env.get(name, "").strip())
