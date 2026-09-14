"""Building and reading the HTTP surface in-process, for `test_web*.py`.

`ASGITransport` rather than a real port: those tests are about status codes,
bodies, and the cursor handoff, and a socket would add scheduling noise without
adding coverage. See `test_web.py` for what that transport cannot test.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from harness.runs.store import RunStore
from harness.session.service import SessionService
from tests.unit.helpers import durable_service, run_store
from tests.webapp import web_app


def build(tmp_path, client, *tools) -> tuple[SessionService, RunStore]:
    service = durable_service(tmp_path / "sessions")
    return service, run_store(service, client, *tools)


def api(tmp_path, service: SessionService, runs: RunStore) -> httpx.AsyncClient:
    app = web_app(tmp_path, service, runs)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://harness.test")


async def settle(runs: RunStore, conversation_id: str) -> None:
    run = runs.active(conversation_id)
    if run is not None:
        await asyncio.wait_for(run._outer, timeout=5)


def events_from(body: str) -> list[dict]:
    """The `session` frames of an SSE body, decoded."""
    frames = [block for block in body.split("\n\n") if block.strip()]
    return [
        json.loads(block.split("data: ", 1)[1])
        for block in frames
        if block.startswith("event: session")
    ]


def frame_names(body: str) -> list[str]:
    return [
        block.split("event: ", 1)[1].split("\n", 1)[0]
        for block in body.split("\n\n")
        if block.strip()
    ]
