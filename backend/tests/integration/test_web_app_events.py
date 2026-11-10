"""The app's event stream, against a real server."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from tests.integration.test_web_stream import TIMEOUT, served
from tests.integration.web_helpers import assistant_chat
from tests.unit.fakes import SteppedClient, completed


async def next_frame(chunks: AsyncIterator[str], buffer: list[str]) -> tuple[str, dict]:
    """The next frame's event name and data, reading more chunks as needed."""
    while "\n\n" not in buffer[0]:
        buffer[0] += await asyncio.wait_for(anext(chunks), timeout=TIMEOUT)
    block, buffer[0] = buffer[0].split("\n\n", 1)
    lines = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
    return lines["event"], json.loads(lines["data"])


async def test_an_open_window_hears_that_a_turn_started_elsewhere(tmp_path) -> None:
    async with (
        served(tmp_path, SteppedClient(completed("hi"))) as (client, _, _),
        client.stream("GET", "/api/app-events") as response,
    ):
        chunks, buffer = response.aiter_text(), [""]
        connected = await next_frame(chunks, buffer)
        await assistant_chat(client, "from outside")
        started = await next_frame(chunks, buffer)

    assert connected == ("app/connected", {"type": "app/connected"})
    assert started == ("chat/turn-started", {"type": "chat/turn-started", "chat_id": "assistant"})
