"""The MCP servers screen: every server listed; the person's own added, changed and removed live."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Request, Response, status

from harness.mcp import (
    McpServerNotFound,
    McpServerTaken,
    McpService,
    NewServer,
    SavedServerService,
    ServerDraft,
)
from harness.mcp.domain.keys import missing_keys
from harness.mcp.router.server_schemas import KeyState, ServerEntries, ServerEntry
from harness.web.http.this_mac import (
    cors_headers,
    parsed_body,
    permitted_write_headers,
    refusals_answered_with,
)

logger = logging.getLogger("harness.mcp")

REFUSED = (McpServerNotFound, McpServerTaken)


class ServerRouter:
    """List every server; add, change, remove and restart one from this Mac."""

    def __init__(self, mcp: McpService, saved: SavedServerService) -> None:
        self._mcp = mcp
        self._saved = saved
        self.router: APIRouter = APIRouter(prefix="/api/mcp/servers", tags=["mcp"])
        self._add_reading_routes()
        self._add_saving_routes()
        self.router.add_api_route(
            "/{server_id}/restart",
            self.restart_server,
            methods=["POST"],
            response_model=ServerEntry,
        )

    def _add_reading_routes(self) -> None:
        """Listing the servers, and answering a write's preflight."""
        self.router.add_api_route(
            "", self.list_servers, methods=["GET"], response_model=ServerEntries
        )
        for path in ("/{server_id}/restart", "/{server_id}", ""):
            self.router.add_api_route(path, self.answer_preflight, methods=["OPTIONS"])

    def _add_saving_routes(self) -> None:
        """Adding, changing and removing a server."""
        self.router.add_api_route(
            "",
            self.add_server,
            methods=["POST"],
            status_code=status.HTTP_201_CREATED,
            response_model=ServerEntry,
        )
        self.router.add_api_route(
            "/{server_id}", self.change_server, methods=["PUT"], response_model=ServerEntry
        )
        self.router.add_api_route(
            "/{server_id}",
            self.remove_server,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
        )

    async def list_servers(self, request: Request, response: Response) -> ServerEntries:
        response.headers.update(cors_headers(request))
        return ServerEntries(servers=tuple(self._entry(s.id) for s in self._mcp.statuses()))

    async def answer_preflight(self, request: Request) -> Response:
        """A page on this Mac may change servers here; any other page gets no permission."""
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=cors_headers(request))

    async def add_server(self, request: Request, response: Response) -> ServerEntry:
        headers = _permitted(request, response)
        body = parsed_body(NewServer, await request.body(), headers)
        added = body.saved(body.id, kept={})
        with _saved_or_answered(headers):
            self._saved.add(added)
        await self._mcp.add(added.id, added.server())
        logger.info("MCP server %s added", body.id)
        return self._entry(body.id)

    async def change_server(
        self, server_id: str, request: Request, response: Response
    ) -> ServerEntry:
        headers = _permitted(request, response)
        body = parsed_body(ServerDraft, await request.body(), headers)
        with _saved_or_answered(headers):
            changed = self._saved.change(server_id, body)
        await self._mcp.change(server_id, changed.server())
        logger.info("MCP server %s changed", server_id)
        return self._entry(server_id)

    async def remove_server(self, server_id: str, request: Request) -> Response:
        headers = permitted_write_headers(request)
        with _saved_or_answered(headers):
            self._saved.remove(server_id)
        await self._mcp.remove(server_id)
        logger.info("MCP server %s removed, its keys with it", server_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=headers)

    async def restart_server(
        self, server_id: str, request: Request, response: Response
    ) -> ServerEntry:
        headers = _permitted(request, response)
        with refusals_answered_with(headers, REFUSED):
            self._known(server_id)
        await self._mcp.restart(server_id)
        return self._entry(server_id)

    def _known(self, server_id: str) -> None:
        if server_id not in {s.id for s in self._mcp.statuses()}:
            raise McpServerNotFound(f"no MCP server {server_id!r}")

    def _entry(self, server_id: str) -> ServerEntry:
        """`server_id` as listed; a key it needs is only set or missing, whichever file set it."""
        server = self._mcp.server(server_id)
        state = next(s for s in self._mcp.statuses() if s.id == server_id)
        missing = missing_keys(server)
        return ServerEntry(
            id=server_id,
            command=server.command,
            args=server.args,
            env={name: value for name, value in server.env.items() if name not in server.needs},
            keys=tuple(KeyState(name=name, is_set=name not in missing) for name in server.needs),
            status=state.status,
            error=state.error,
        )


def _permitted(request: Request, response: Response) -> dict[str, str]:
    """The write's CORS headers, set on `response` too; a 403 for a page not on this Mac."""
    headers = permitted_write_headers(request)
    response.headers.update(headers)
    return headers


@contextmanager
def _saved_or_answered(headers: dict[str, str]) -> Iterator[None]:
    """A refused save answered with its status; a file that cannot be written, with a 500."""
    with refusals_answered_with(headers, REFUSED):
        try:
            yield
        except OSError as err:
            logger.exception("the MCP servers file could not be written")
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"The MCP servers file could not be saved, so nothing changed: {err}",
                headers=headers,
            ) from err
