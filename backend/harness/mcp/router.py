"""What the browser needs of an MCP server directly: an app's HTML and its calls back."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from mcp.server.apps import APP_MIME_TYPE
from mcp.types import TextResourceContents

from harness.mcp import McpService, is_app_visible, ui_resource_uri
from harness.mcp.domain.csp import build_csp
from harness.mcp.schemas import AppResource, AppToolCall, ServerList
from harness.relay import RelayService, with_relay_url

logger = logging.getLogger("harness.mcp")

UI_SCHEME = "ui://"


def _server_list_route(router: APIRouter, mcp: McpService) -> None:
    @router.get("", response_model=ServerList)
    async def list_servers() -> ServerList:
        """Every configured server, connected or not."""
        return ServerList(servers=tuple(s.id for s in mcp.statuses()))


def build_router(mcp: McpService, relays: RelayService) -> APIRouter:
    router = APIRouter(prefix="/api/mcp", tags=["mcp"])
    _server_list_route(router, mcp)

    def known(server: str) -> None:
        if server not in {s.id for s in mcp.statuses()}:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no MCP server {server!r}")

    @router.get("/{server}/resources", response_model=AppResource)
    async def read_app(server: str, uri: str) -> AppResource:
        known(server)
        if not uri.startswith(UI_SCHEME):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=f"{uri!r} is not a ui:// resource"
            )
        result = await mcp.read_resource(server, uri)
        content = result.contents[0] if result.contents else None
        if not isinstance(content, TextResourceContents) or content.mime_type != APP_MIME_TYPE:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=f"{uri!r} is not {APP_MIME_TYPE!r} text"
            )
        return AppResource(html=content.text, csp=build_csp(content.meta))

    @router.post("/{server}/tools/{name}")
    async def call_app_tool(server: str, name: str, body: AppToolCall) -> JSONResponse:
        known(server)
        published = mcp.published(server)
        tool = next((t for t in published if t.name == name), None)
        if tool is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{server} has no tool {name!r}")
        if not is_app_visible(tool):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=f"{name!r} is not callable by apps"
            )
        bound = ui_resource_uri(tool)
        if bound is not None and bound != body.resource_uri:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=f"{name!r} belongs to another app, {bound}"
            )
        logger.info("app %s on %s calls %s", body.resource_uri, server, name)
        result = await mcp.call(server, name, body.arguments)
        rewritten = with_relay_url(result, relays)
        return JSONResponse(rewritten.model_dump(mode="json", by_alias=True, exclude_none=True))

    return router
