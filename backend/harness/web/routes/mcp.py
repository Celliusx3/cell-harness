"""What the browser needs of an MCP server directly — an app's HTML, and the
calls the app makes back.

MCP Apps put an interface in the chat: a tool declares `_meta.ui.resourceUri`,
the browser reads that `ui://` resource and renders it in a sandboxed iframe,
and the iframe may call the *same server's* tools. The harness is the MCP client,
so both cross here.

**An app's call is a proxy, not a tool call of ours.** It goes to the server by
the server's own name and the answer comes back verbatim — the shape every
host that ships this does (VS Code, ChatGPT, Openwork), and what the app was
written against. It does not go through the dispatcher: that is the model's
and a script's path, with a menu to offer and refusals to give, and an app has
neither. What guards it lives at this layer instead: the path's server is the
only one reachable, the tool must be visible to apps, and a tool bound to some
other app's resource is refused. It is not a session event — nothing the model
sees results from it, and a poll every second would otherwise fill the log.
"""

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

# What a view may reach when its resource declares nothing. The spec's default:
# inline script and style, data images, and no network at all.
_CSP_DEFAULT_SOURCES = {
    "script-src": ["'unsafe-inline'"],
    "style-src": ["'unsafe-inline'"],
    "img-src": ["data:", "blob:"],
    "font-src": ["data:"],
    "media-src": ["data:", "blob:"],
    "connect-src": [],
    "frame-src": [],
}
# Which `_meta.ui.csp` list feeds which directives.
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
    """The Content-Security-Policy for one app's iframe, from the resource's `_meta`.

    The spec's defaults, widened only by the https origins `_meta.ui.csp`
    declares. Values come from the server, so each is parsed as an absolute URL
    and only its origin kept — a string that is not an origin cannot add a
    directive of its own.
    """
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
        # By the server's own name, from the server's own list: an app can
        # reach nothing the path's server did not publish — not another
        # server, not `execute_typescript`.
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
        # The wire shape, `_meta` and all: `isError` is part of the result, not
        # a status — a tool that failed is a result the app can show.
        return JSONResponse(result.model_dump(mode="json", by_alias=True, exclude_none=True))

    return router
