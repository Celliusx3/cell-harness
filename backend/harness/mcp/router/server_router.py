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


def build_router(mcp: McpService, saved: SavedServerService) -> APIRouter:
    """List every server; add, change, remove and restart one from this Mac."""
    router = APIRouter(prefix="/api/mcp/servers", tags=["mcp"])
    _reading_routes(router, mcp)
    _saving_routes(router, mcp, saved)
    _restart_route(router, mcp)
    return router


def _reading_routes(router: APIRouter, mcp: McpService) -> None:
    @router.get("", response_model=ServerEntries)
    async def list_servers(request: Request, response: Response) -> ServerEntries:
        response.headers.update(cors_headers(request))
        return ServerEntries(servers=tuple(_entry(mcp, s.id) for s in mcp.statuses()))

    @router.options("")
    @router.options("/{server_id}")
    @router.options("/{server_id}/restart")
    async def answer_preflight(request: Request) -> Response:
        """A page on this Mac may change servers here; any other page gets no permission."""
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=cors_headers(request))


def _saving_routes(router: APIRouter, mcp: McpService, saved: SavedServerService) -> None:
    @router.post("", status_code=status.HTTP_201_CREATED, response_model=ServerEntry)
    async def add_server(request: Request, response: Response) -> ServerEntry:
        headers = _permitted(request, response)
        body = parsed_body(NewServer, await request.body(), headers)
        added = body.saved(body.id, kept={})
        with _saved_or_answered(headers):
            saved.add(added)
        await mcp.add(added.id, added.server())
        logger.info("MCP server %s added", body.id)
        return _entry(mcp, body.id)

    @router.put("/{server_id}", response_model=ServerEntry)
    async def change_server(server_id: str, request: Request, response: Response) -> ServerEntry:
        headers = _permitted(request, response)
        body = parsed_body(ServerDraft, await request.body(), headers)
        with _saved_or_answered(headers):
            changed = saved.change(server_id, body)
        await mcp.change(server_id, changed.server())
        logger.info("MCP server %s changed", server_id)
        return _entry(mcp, server_id)

    @router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def remove_server(server_id: str, request: Request) -> Response:
        headers = permitted_write_headers(request)
        with _saved_or_answered(headers):
            saved.remove(server_id)
        await mcp.remove(server_id)
        logger.info("MCP server %s removed, its keys with it", server_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers=headers)


def _restart_route(router: APIRouter, mcp: McpService) -> None:
    @router.post("/{server_id}/restart", response_model=ServerEntry)
    async def restart_server(server_id: str, request: Request, response: Response) -> ServerEntry:
        headers = _permitted(request, response)
        with refusals_answered_with(headers, REFUSED):
            _known(mcp, server_id)
        await mcp.restart(server_id)
        return _entry(mcp, server_id)


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


def _known(mcp: McpService, server_id: str) -> None:
    if server_id not in {s.id for s in mcp.statuses()}:
        raise McpServerNotFound(f"no MCP server {server_id!r}")


def _entry(mcp: McpService, server_id: str) -> ServerEntry:
    """`server_id` as listed; a key it needs is only set or missing, whichever file set it."""
    server = mcp.server(server_id)
    state = next(s for s in mcp.statuses() if s.id == server_id)
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
