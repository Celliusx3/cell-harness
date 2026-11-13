"""The person's servers, kept through a repository, each under an id no other server has."""

from __future__ import annotations

from harness.mcp.domain.errors import McpServerNotFound, McpServerTaken
from harness.mcp.domain.saved import SavedServer, ServerDraft
from harness.mcp.repository.saved_server_repository import SavedServerRepository


class SavedServerService:
    """Every saved server, read on every call; added, changed and removed by id."""

    def __init__(self, repository: SavedServerRepository) -> None:
        self._repository = repository

    def servers(self) -> tuple[SavedServer, ...]:
        """Every saved server, in the order each was added."""
        return self._repository.saved_servers()

    def add(self, server: SavedServer) -> None:
        """Save `server`; `McpServerTaken` when a saved server has its id."""
        stored = self._repository.saved_servers()
        if any(saved.id == server.id for saved in stored):
            raise McpServerTaken(f"a server is already named {server.id!r}; pick another name")
        self._repository.replace_all((*stored, server))

    def change(self, server_id: str, draft: ServerDraft) -> SavedServer:
        """Save `draft` over `server_id`, keeping its id, its place and each key not typed."""
        stored = self._saved_or_refused(server_id)
        existing = next(saved for saved in stored if saved.id == server_id)
        changed = draft.saved(server_id, existing.env)
        self._repository.replace_all(
            tuple(changed if saved.id == server_id else saved for saved in stored)
        )
        return changed

    def remove(self, server_id: str) -> None:
        """Forget the server `server_id`."""
        stored = self._saved_or_refused(server_id)
        self._repository.replace_all(tuple(saved for saved in stored if saved.id != server_id))

    def _saved_or_refused(self, server_id: str) -> tuple[SavedServer, ...]:
        """The saved servers, if `server_id` is one; refused for an unknown id."""
        stored = self._repository.saved_servers()
        if not any(saved.id == server_id for saved in stored):
            raise McpServerNotFound(f"no MCP server {server_id!r}")
        return stored
