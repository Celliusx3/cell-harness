"""A browser's websocket joined to its relay's upstream one: frames copied both ways."""

from __future__ import annotations

import asyncio

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed


async def forward_to_upstream(browser: WebSocket, upstream: ClientConnection) -> None:
    """The browser's frames, sent on until either side closes."""
    try:
        while True:
            message = await browser.receive()
            if message["type"] == "websocket.disconnect":
                return
            data, text = message.get("bytes"), message.get("text")
            if data is not None:
                await upstream.send(data)
            elif text is not None:
                await upstream.send(text)
    except ConnectionClosed:
        return


async def forward_to_browser(upstream: ClientConnection, browser: WebSocket) -> None:
    """The upstream's frames, sent on until either side closes."""
    try:
        async for frame in upstream:
            if isinstance(frame, bytes):
                await browser.send_bytes(frame)
            else:
                await browser.send_text(frame)
    except (ConnectionClosed, WebSocketDisconnect):
        return


async def bridge_websockets(browser: WebSocket, upstream: ClientConnection) -> None:
    """Frames both ways until either side closes; then the other one is closed too."""
    forwards = [
        asyncio.create_task(forward_to_upstream(browser, upstream)),
        asyncio.create_task(forward_to_browser(upstream, browser)),
    ]
    try:
        await asyncio.wait(forwards, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in forwards:
            task.cancel()
        await asyncio.gather(*forwards, return_exceptions=True)
        await upstream.close()
        states = (browser.client_state, browser.application_state)
        if states == (WebSocketState.CONNECTED, WebSocketState.CONNECTED):
            await browser.close()
