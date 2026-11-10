"""The event stream of a chat between turns, against a real server."""

from __future__ import annotations

import asyncio

from harness.channels.web import sse as sse_module
from tests.integration.test_web_stream import TIMEOUT, served, until
from tests.integration.web_helpers import assistant_chat, events_from
from tests.unit.fakes import SteppedClient, completed


async def test_a_watcher_of_an_idle_chat_sees_a_turn_started_elsewhere(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(sse_module, "KEEP_ALIVE_SECONDS", 0.05, raising=False)
    async with served(tmp_path, SteppedClient(completed("first"), completed("second"))) as (
        client,
        _,
        runs,
    ):
        conversation_id = await assistant_chat(client, "from this window")
        await until(lambda: runs.active(conversation_id) is None, what="the first turn to end")
        head = (await client.get(f"/api/conversations/{conversation_id}")).json()["next_cursor"]

        async with client.stream(
            "GET", f"/api/conversations/{conversation_id}/events?after={head}"
        ) as response:
            chunks = response.aiter_text()
            first = await asyncio.wait_for(anext(chunks), timeout=TIMEOUT)
            assert first.startswith(":"), f"the idle stream closed instead of waiting: {first!r}"

            await client.post(
                f"/api/conversations/{conversation_id}/messages", json={"prompt": "from outside"}
            )
            body = ""
            async for chunk in chunks:
                body += chunk

    streamed = events_from(body)
    prompts = [e["message"]["content"] for e in streamed if e["type"] == "user/message"]
    assert prompts == ["from outside"]
    assert streamed[-1]["type"] == "turn/end"
    assert body.rstrip().endswith("event: end\ndata: {}")


async def test_hanging_up_on_an_idle_chat_leaves_nothing_waiting(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(sse_module, "KEEP_ALIVE_SECONDS", 0.05, raising=False)
    async with served(tmp_path, SteppedClient(completed("first"), completed("second"))) as (
        client,
        _,
        runs,
    ):
        conversation_id = await assistant_chat(client, "first")
        await until(lambda: runs.active(conversation_id) is None, what="the first turn to end")
        head = (await client.get(f"/api/conversations/{conversation_id}")).json()["next_cursor"]
        async with client.stream(
            "GET", f"/api/conversations/{conversation_id}/events?after={head}"
        ) as response:
            await asyncio.wait_for(anext(response.aiter_text()), timeout=TIMEOUT)

        await assistant_chat(client, "second")
        await until(lambda: runs.active(conversation_id) is None, what="the second turn to end")
