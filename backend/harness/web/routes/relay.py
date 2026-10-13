"""`/api/relay/{id}/…`: a loopback page and its websocket, reached from the browser through here."""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, WebSocket, status
from fastapi.responses import Response
from starlette.websockets import WebSocketDisconnect, WebSocketState
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake
from websockets.typing import Subprotocol

from harness.mcp.relay import RELAY_PREFIX, Relays

logger = logging.getLogger("harness.relay")

FETCH_TIMEOUT_SECONDS = 15.0
MAX_FRAME_BYTES = 16 * 1024 * 1024
ANY_ORIGIN = "*"


async def forward_to_upstream(browser: WebSocket, remote: ClientConnection) -> None:
    """The browser's frames, sent on until either side closes."""
    try:
        while True:
            message = await browser.receive()
            if message["type"] == "websocket.disconnect":
                return
            data, text = message.get("bytes"), message.get("text")
            if data is not None:
                await remote.send(data)
            elif text is not None:
                await remote.send(text)
    except ConnectionClosed:
        return


async def forward_to_browser(remote: ClientConnection, browser: WebSocket) -> None:
    """The upstream's frames, sent on until either side closes."""
    try:
        async for frame in remote:
            if isinstance(frame, bytes):
                await browser.send_bytes(frame)
            else:
                await browser.send_text(frame)
    except (ConnectionClosed, WebSocketDisconnect):
        return


async def pump(browser: WebSocket, remote: ClientConnection) -> None:
    """Frames both ways until either side closes; then the other one is closed too."""
    pumps = [
        asyncio.create_task(forward_to_upstream(browser, remote)),
        asyncio.create_task(forward_to_browser(remote, browser)),
    ]
    try:
        await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in pumps:
            task.cancel()
        await asyncio.gather(*pumps, return_exceptions=True)
        await remote.close()
        states = (browser.client_state, browser.application_state)
        if states == (WebSocketState.CONNECTED, WebSocketState.CONNECTED):
            await browser.close()


def build_router(relays: Relays) -> APIRouter:
    router = APIRouter(prefix=RELAY_PREFIX, tags=["relay"])

    @router.get("/{relay_id}/{path:path}")
    async def relay_page(relay_id: str, path: str, request: Request) -> Response:
        upstream = relays.upstream(relay_id)
        if upstream is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such relay")
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=FETCH_TIMEOUT_SECONDS) as http:
                response = await http.get(upstream.http_url(path, request.url.query))
        except httpx.HTTPError as err:
            logger.warning("relay %s: %s did not answer: %r", relay_id[:6], path, err)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, detail=f"the relayed page did not answer: {err!r}"
            ) from err
        headers = {"Access-Control-Allow-Origin": ANY_ORIGIN}
        content_type = response.headers.get("content-type")
        if content_type is not None:
            headers["Content-Type"] = content_type
        return Response(content=response.content, status_code=response.status_code, headers=headers)

    @router.websocket("/{relay_id}/{path:path}")
    async def relay_socket(browser: WebSocket, relay_id: str, path: str) -> None:
        upstream = relays.upstream(relay_id)
        if upstream is None:
            await browser.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        offered = [Subprotocol(name) for name in browser.scope.get("subprotocols", [])]
        try:
            async with connect(
                upstream.ws_url(path, browser.url.query),
                subprotocols=offered or None,
                max_size=MAX_FRAME_BYTES,
                ping_interval=None,
                proxy=None,
            ) as remote:
                await browser.accept(subprotocol=remote.subprotocol)
                await pump(browser, remote)
        except (OSError, InvalidHandshake, TimeoutError) as err:
            logger.warning("relay %s: the upstream socket refused: %r", relay_id[:6], err)
            if browser.application_state == WebSocketState.CONNECTING:
                await browser.close(code=status.WS_1011_INTERNAL_ERROR)

    return router
