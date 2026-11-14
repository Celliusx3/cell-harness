"""The app's event stream, against a real server."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI

from harness.app_events import AppEventService
from harness.bots import ASSISTANT_ID, BUILDER_ID, BotRepository, BotService
from harness.runs.service.run_service import RunService
from tests.integration.test_web_stream import TIMEOUT, served, serving
from tests.integration.web_helpers import assistant_chat
from tests.unit.fakes import ScriptedClient, SteppedClient, completed
from tests.unit.group_helpers import groups_in
from tests.unit.helpers import durable_service, no_skills, runtime_over
from tests.webapp import MODEL_CREDENTIAL, a_model_saved_in, web_app

RESEARCHER = {"name": "Researcher", "instructions": "Cite.", "model": MODEL_CREDENTIAL}


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


def _app_keeping_bots_and_groups(tmp_path) -> FastAPI:
    """An app whose bots, groups and runs tell one event stream, all kept under `tmp_path`."""
    service = durable_service(tmp_path / "sessions")
    app_events = AppEventService()
    bots = BotService(
        BotRepository(tmp_path / "bots.json"),
        service,
        assistant_instructions="Help.",
        app_events=app_events,
    )
    runs = RunService(
        service,
        runtime_over(ScriptedClient(completed("hi"))),
        bots,
        groups_in(tmp_path, bots, service, app_events),
        app_events=app_events,
    )
    return web_app(
        tmp_path, service, runs, skills=no_skills(), bots=bots, secrets=a_model_saved_in(tmp_path)
    )


async def test_an_open_window_hears_that_the_bots_changed(tmp_path) -> None:
    async with (
        serving(_app_keeping_bots_and_groups(tmp_path)) as base_url,
        httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT) as client,
        client.stream("GET", "/api/app-events") as response,
    ):
        chunks, buffer = response.aiter_text(), [""]
        await next_frame(chunks, buffer)
        created = await client.post("/api/bots", json=RESEARCHER)
        changed = await next_frame(chunks, buffer)

    assert created.status_code == 201
    assert changed == ("bots/changed", {"type": "bots/changed"})


async def test_an_open_window_hears_that_a_group_was_made(tmp_path) -> None:
    async with (
        serving(_app_keeping_bots_and_groups(tmp_path)) as base_url,
        httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT) as client,
        client.stream("GET", "/api/app-events") as response,
    ):
        chunks, buffer = response.aiter_text(), [""]
        await next_frame(chunks, buffer)
        created = await client.post(
            "/api/groups", json={"name": "Pair", "member_ids": [ASSISTANT_ID, BUILDER_ID]}
        )
        changed = await next_frame(chunks, buffer)

    assert created.status_code == 201
    assert changed == ("bots/changed", {"type": "bots/changed"})
