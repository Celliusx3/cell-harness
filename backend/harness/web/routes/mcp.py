"""What the browser needs of an MCP server directly: an app's HTML and its calls back."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from mcp.server.apps import APP_MIME_TYPE
from mcp.types import TextResourceContents
from pydantic import BaseModel, ConfigDict

from harness.mcp.errors import McpConnectionError, McpNotConnectedError, McpTimeoutError
from harness.mcp.store import McpServerStore
from harness.mcp.tool import app_visible, ui_resource_uri

logger = logging.getLogger("harness.mcp")

UI_SCHEME = "ui://"

_CSP_DEFAULT_SOURCES = {
    "script-src": ["'unsafe-inline'"],
    "style-src": ["'unsafe-inline'"],
    "img-src": ["data:", "blob:"],
    "font-src": ["data:"],
    "media-src": ["data:", "blob:"],
    "connect-src": [],
    "frame-src": [],
}
_CSP_DOMAIN_KEYS = {
    "resourceDomains": ("script-src", "style-src", "img-src", "font-src", "media-src"),
    "connectDomains": ("connect-src",),
    "frameDomains": ("frame-src",),
}


class AppResource(BaseModel):
    """An app's HTML and the policy to render it under."""

    model_config = ConfigDict(frozen=True)

    html: str
    csp: str


class AppToolCall(BaseModel):
    """What the app asks: a tool of its own server, and which app is asking."""

    model_config = ConfigDict(frozen=True)

    arguments: dict[str, object]
    resource_uri: str


def build_csp(meta: dict | None) -> str:
    """The Content-Security-Policy for one app's iframe, from the resource's `_meta`."""
    sources = {directive: list(values) for directive, values in _CSP_DEFAULT_SOURCES.items()}
    ui = meta.get("ui") if isinstance(meta, dict) else None
    csp = ui.get("csp") if isinstance(ui, dict) else None
    if isinstance(csp, dict):
        for key, directives in _CSP_DOMAIN_KEYS.items():
            for origin in _origins(csp.get(key)):
                for directive in directives:
                    sources[directive].append(origin)
    directives = ["default-src 'none'", "object-src 'none'", "base-uri 'none'"]
    for directive, values in sources.items():
        directives.append(f"{directive} {' '.join(values)}" if values else f"{directive} 'none'")
    return "; ".join(directives)


def _origins(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    origins: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        parts = urlsplit(value)
        if parts.scheme in ("https", "wss") and parts.hostname and parts.hostname != "*":
            origins.append(f"{parts.scheme}://{parts.netloc}")
    return origins


def build_router(mcp: McpServerStore) -> APIRouter:
    router = APIRouter(prefix="/api/mcp", tags=["mcp"])

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
        try:
            result = await mcp.read_resource(server, uri)
        except McpNotConnectedError as err:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(err)) from err
        except (McpTimeoutError, McpConnectionError) as err:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(err)) from err
        content = result.contents[0] if result.contents else None
        if not isinstance(content, TextResourceContents) or content.mime_type != APP_MIME_TYPE:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=f"{uri!r} is not {APP_MIME_TYPE!r} text"
            )
        return AppResource(html=content.text, csp=build_csp(content.meta))

    @router.post("/{server}/tools/{name}")
    async def call_app_tool(server: str, name: str, body: AppToolCall) -> JSONResponse:
        known(server)
        try:
            published = mcp.published(server)
        except McpNotConnectedError as err:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(err)) from err
        tool = next((t for t in published if t.name == name), None)
        if tool is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{server} has no tool {name!r}")
        if not app_visible(tool):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=f"{name!r} is not callable by apps"
            )
        bound = ui_resource_uri(tool)
        if bound is not None and bound != body.resource_uri:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=f"{name!r} belongs to another app, {bound}"
            )
        logger.info("app %s on %s calls %s", body.resource_uri, server, name)
        try:
            result = await mcp.call(server, name, body.arguments)
        except McpNotConnectedError as err:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(err)) from err
        except (McpTimeoutError, McpConnectionError) as err:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(err)) from err
        return JSONResponse(result.model_dump(mode="json", by_alias=True, exclude_none=True))

    return router
