"""A bot's first screenshot starts the phone and waits for Android; the next finds it running."""

from __future__ import annotations

import base64

from mcp import Client
from mcp.types import ImageContent

from tests.fakes import BOOT_POLLS, PNG, FakeEngine, phone_server


async def test_the_first_screenshot_starts_the_phone_once_and_a_second_does_not() -> None:
    engine = FakeEngine(state="missing")

    async with Client(phone_server(engine)) as client:
        first = await client.call_tool("screenshot", {})
        second = await client.call_tool("screenshot", {})

    assert engine.created == 1
    assert engine.boot_polls == BOOT_POLLS
    for result in (first, second):
        assert not result.is_error
        (image,) = result.content
        assert isinstance(image, ImageContent)
        assert image.mime_type == "image/png"
        assert base64.b64decode(image.data) == PNG


async def test_a_stopped_phone_is_started_not_made_again() -> None:
    engine = FakeEngine(state="stopped")

    async with Client(phone_server(engine)) as client:
        result = await client.call_tool("screenshot", {})

    assert not result.is_error
    assert (engine.created, engine.started) == (0, 1)
