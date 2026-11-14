"""What the browser needs of an MCP server directly: an app's HTML and its calls back."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from mcp.server.apps import APP_MIME_TYPE
from mcp.types import TextResourceContents

from harness.mcp import McpService, is_app_visible, ui_resource_uri
from harness.mcp.domain.csp import build_csp
from harness.mcp.router.schemas import AppResource, AppToolCall, ServerList
from harness.relay import RelayService, with_relay_url

logger = logging.getLogger("harness.mcp")

UI_SCHEME = "ui://"


class McpRouter:
    """The configured servers, an app's HTML, and the calls an app makes back to its server."""

    def __init__(self, mcp: McpService, relays: RelayService) -> None:
        self._mcp = mcp
        self._relays = relays
        self.router: APIRouter = APIRouter(prefix="/api/mcp", tags=["mcp"])
        self.router.add_api_route("", self.list_servers, methods=["GET"], response_model=ServerList)
        self.router.add_api_route(
            "/{server}/resources", self.read_app, methods=["GET"], response_model=AppResource
        )
        self.router.add_api_route("/{server}/tools/{name}", self.call_app_tool, methods=["POST"])

    async def list_servers(self) -> ServerList:
        """Every configured server, connected or not."""
        return ServerList(servers=tuple(s.id for s in self._mcp.statuses()))

    async def read_app(self, server: str, uri: str) -> AppResource:
        self._refuse_unknown_server(server)
        if not uri.startswith(UI_SCHEME):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=f"{uri!r} is not a ui:// resource"
            )
        result = await self._mcp.read_resource(server, uri)
        content = result.contents[0] if result.contents else None
        if not isinstance(content, TextResourceContents) or content.mime_type != APP_MIME_TYPE:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=f"{uri!r} is not {APP_MIME_TYPE!r} text"
            )
        return AppResource(html=content.text, csp=build_csp(content.meta))

    async def call_app_tool(self, server: str, name: str, body: AppToolCall) -> JSONResponse:
        self._refuse_unknown_server(server)
        published = self._mcp.published_tools(server)
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
        result = await self._mcp.call_tool(server, name, body.arguments)
        rewritten = with_relay_url(result, self._relays)
        return JSONResponse(rewritten.model_dump(mode="json", by_alias=True, exclude_none=True))

    def _refuse_unknown_server(self, server: str) -> None:
        if server not in {s.id for s in self._mcp.statuses()}:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no MCP server {server!r}")
