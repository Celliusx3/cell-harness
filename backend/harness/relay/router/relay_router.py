"""`/api/relay/{id}/…`: a loopback page and its websocket, reached from the browser through here."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, WebSocket, status
from fastapi.responses import Response
from starlette.websockets import WebSocketState
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidHandshake
from websockets.typing import Subprotocol

from harness.relay.domain.models import RELAY_PREFIX
from harness.relay.router.websocket_bridge import bridge_websockets
from harness.relay.service.relay_service import RelayService

logger = logging.getLogger("harness.relay")

MAX_FRAME_BYTES = 16 * 1024 * 1024
ANY_ORIGIN = "*"


class RelayRouter:
    """A loopback page and its websocket, relayed to the browser by their relay id."""

    def __init__(self, relays: RelayService) -> None:
        self._relays = relays
        self.router: APIRouter = APIRouter(prefix=RELAY_PREFIX, tags=["relay"])
        self.router.add_api_route("/{relay_id}/{path:path}", self.relay_page, methods=["GET"])
        self.router.add_api_websocket_route("/{relay_id}/{path:path}", self.relay_socket)

    async def relay_page(self, relay_id: str, path: str, request: Request) -> Response:
        page = await self._relays.fetch_page(relay_id, path, request.url.query)
        headers = {"Access-Control-Allow-Origin": ANY_ORIGIN}
        if page.content_type is not None:
            headers["Content-Type"] = page.content_type
        return Response(content=page.content, status_code=page.status_code, headers=headers)

    async def relay_socket(self, browser: WebSocket, relay_id: str, path: str) -> None:
        upstream = self._relays.upstream(relay_id)
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
                await bridge_websockets(browser, remote)
        except (OSError, InvalidHandshake, TimeoutError) as err:
            logger.warning("relay %s: the upstream socket refused: %r", relay_id[:6], err)
            if browser.application_state == WebSocketState.CONNECTING:
                await browser.close(code=status.WS_1011_INTERNAL_ERROR)
