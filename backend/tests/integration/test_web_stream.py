"""The event stream, against a real server.

These four tests are the reason this file is separate and slower. `ASGITransport`
buffers a response to completion before handing it back (see `test_web.py`), so
the one thing it can never do is hang up on a stream that is still running — and
that is the contract this whole phase exists to uphold:

    a closed tab must not kill the turn

Checking it needs a real socket, a real `StreamingResponse`, and a real
disconnect, because what is being tested is partly Starlette's behaviour: when a
client goes away it cancels the task running the response generator. The design
answer is that our generator owns nothing, so the cancellation stops at the
subscription. That claim is only worth as much as this file.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import pytest
import uvicorn

from harness.agent.loop import LoopAgent
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry
from tests.unit.fakes import SteppedClient, calls_tool, hanging_tool
from tests.webapp import web_app

# Generous, because a failure here should read as "the contract broke" rather
# than "CI was busy". Nothing in these tests waits on wall-clock time on purpose.
TIMEOUT = 10.0


@asynccontextmanager
async def serving(app) -> AsyncIterator[str]:
    """Run `app` on an ephemeral port for the duration of the block.

    `port=0` so parallel test runs cannot collide, then the actual port is read
    back off the bound socket.
    """
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        for _ in range(int(TIMEOUT / 0.01)):
            if server.started:
                break
            await asyncio.sleep(0.01)
        else:  # pragma: no cover - the fixture is broken if this fires
            raise AssertionError("uvicorn never started")
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=TIMEOUT)


@pytest.fixture
async def live(tmp_path):
    """A server whose turn parks inside a tool until something stops it.

    A turn that never finishes on its own is what makes "hang up while it is
    still running" a reachable state at all.
    """
    ids = iter(f"c{n}" for n in range(100))
    service = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )
    agent = LoopAgent(
        name="t",
        model="m",
        client=SteppedClient(calls_tool("hang", '{"value": "x"}')),
        tools=ToolPipeline(ToolRegistry([hanging_tool()])),
        checkpoint=service.flush,
    )
    runs = RunStore(service, agent)
    async with (
        serving(web_app(tmp_path, service, runs)) as base_url,
        httpx.AsyncClient(base_url=base_url, timeout=TIMEOUT) as client,
    ):
        yield client, service, runs


async def start(client: httpx.AsyncClient) -> str:
    created = await client.post("/api/conversations", json={"prompt": "go"})
    assert created.status_code == 201
    return created.json()["id"]


async def until(predicate, *, what: str) -> None:
    for _ in range(int(TIMEOUT / 0.005)):
        if predicate():
            return
        await asyncio.sleep(0.005)
    raise AssertionError(f"timed out waiting for {what}")


async def read_events(response: httpx.Response, *, count: int) -> list[dict]:
    """Take `count` `session` frames off a live response, then stop reading."""
    collected: list[dict] = []
    buffer = ""
    async for chunk in response.aiter_text():
        buffer += chunk
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            if block.startswith("event: session"):
                collected.append(json.loads(block.split("data: ", 1)[1]))
                if len(collected) >= count:
                    return collected
    return collected


# ── the central contract ──────────────────────────────────────────────────────


async def test_hanging_up_mid_stream_does_not_cancel_the_run(live) -> None:
    """**The phase in one test.**

    Starlette cancels the task running a `StreamingResponse` generator when the
    client disconnects. Our generator owns nothing — the subscription only reads —
    so the cancellation must stop there and leave the turn running.
    """
    client, _, runs = live
    conversation_id = await start(client)

    async with client.stream(
        "GET", f"/api/conversations/{conversation_id}/events?after=0"
    ) as response:
        assert response.status_code == 200
        await read_events(response, count=1)  # attach, take one frame, leave

    await asyncio.sleep(0.05)  # let the disconnect propagate through Starlette

    run = runs.active(conversation_id)
    assert run is not None, "the run was cancelled by a closed connection"
    assert not run.settled

    await client.delete(f"/api/conversations/{conversation_id}/run")


async def test_reconnecting_with_a_cursor_misses_nothing(live) -> None:
    """Refresh mid-turn: the demo's second action, at the protocol level."""
    client, _, runs = live
    conversation_id = await start(client)

    async with client.stream(
        "GET", f"/api/conversations/{conversation_id}/events?after=0"
    ) as first:
        early = await read_events(first, count=2)

    await until(
        lambda: any(e.type == "tool/call" for e in runs.active(conversation_id).session.events()),
        what="the turn to progress past where the first reader stopped",
    )

    async with client.stream(
        "GET", f"/api/conversations/{conversation_id}/events?after={len(early)}"
    ) as second:
        later = await read_events(second, count=2)

    live_log = [
        json.loads(e.model_dump_json()) for e in runs.active(conversation_id).session.events()
    ]
    assert early == live_log[: len(early)]
    assert later == live_log[len(early) : len(early) + len(later)]

    await client.delete(f"/api/conversations/{conversation_id}/run")


async def test_several_watchers_see_the_same_stream(live) -> None:
    """A run is not owned by whoever started it, so two tabs are equally valid."""
    client, _, runs = live
    conversation_id = await start(client)

    async def watch() -> list[dict]:
        async with client.stream(
            "GET", f"/api/conversations/{conversation_id}/events?after=0"
        ) as response:
            return await read_events(response, count=2)

    first, second = await asyncio.gather(watch(), watch())

    assert first == second
    await client.delete(f"/api/conversations/{conversation_id}/run")


async def test_a_watcher_is_released_when_the_turn_is_stopped(live) -> None:
    """The stop button, from the watching tab's side: it must be told, not hang."""
    client, _, runs = live
    conversation_id = await start(client)

    async def watch_to_end() -> str:
        response = await client.get(f"/api/conversations/{conversation_id}/events?after=0")
        return response.text

    watching = asyncio.create_task(watch_to_end())
    await until(
        lambda: any(e.type == "tool/call" for e in runs.active(conversation_id).session.events()),
        what="the tool to be dispatched",
    )

    stopped = await client.delete(f"/api/conversations/{conversation_id}/run")
    assert stopped.status_code == 204

    body = await asyncio.wait_for(watching, timeout=TIMEOUT)
    assert body.rstrip().endswith("data: {}")
    assert '"reason":"cancelled"' in body.replace(" ", "")
