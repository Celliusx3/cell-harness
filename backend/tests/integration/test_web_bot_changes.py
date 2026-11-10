"""The bot list's change stream, against a real server."""

from __future__ import annotations

import asyncio

import httpx

from harness.app_events import AppEvents
from harness.bots import BotService
from harness.runs.service import RunService
from tests.integration.test_web_stream import TIMEOUT, serving
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import durable_service, no_skills, runtime_over
from tests.webapp import MODEL_CREDENTIAL, a_model_saved_in, web_app

RESEARCHER = {"name": "Researcher", "instructions": "Cite.", "model": MODEL_CREDENTIAL}


async def test_an_open_page_hears_of_a_bot_made_elsewhere(tmp_path) -> None:
    service = durable_service(tmp_path / "sessions")
    app_events = AppEvents()
    bots = BotService(
        tmp_path / "bots.json", service, assistant_instructions="Help.", events=app_events
    )
    runs = RunService(
        service, runtime_over(ScriptedClient(completed("hi"))), bots, events=app_events
    )
    app = web_app(
        tmp_path, service, runs, skills=no_skills(), bots=bots, secrets=a_model_saved_in(tmp_path)
    )
    async with (
        serving(app) as base_url,
        httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT) as client,
        client.stream("GET", "/api/bots/changes") as response,
    ):
        frames = response.aiter_text()
        first = await asyncio.wait_for(anext(frames), timeout=TIMEOUT)
        assert first.startswith("event: changed"), first

        created = await client.post("/api/bots", json=RESEARCHER)
        assert created.status_code == 201
        after = await asyncio.wait_for(anext(frames), timeout=TIMEOUT)

    assert after.startswith("event: changed"), after
