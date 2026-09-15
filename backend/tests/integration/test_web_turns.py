"""One turn at a time, stopping it, and a whole one end to end — over HTTP.

The same in-process transport as `test_web.py`, with the same limit: every
stream read here is of a stream that ends.
"""

from __future__ import annotations

import asyncio

import httpx

from tests.integration.web_helpers import api, build, events_from, frame_names, settle
from tests.unit.fakes import (
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    gated_tool,
    hanging_tool,
)
from tests.unit.helpers import no_skills, until
from tests.webapp import web_app

# ── one turn at a time ────────────────────────────────────────────────────────


async def test_a_second_message_while_running_is_queued(slow) -> None:
    """It used to be a `409`. Refusing makes someone retype what they wrote, and
    Telegram never could refuse — a phone has no composer to grey out — so the two
    channels answered this differently until the browser became a channel too."""
    client, _, runs = slow
    conversation_id = (await client.post("/api/conversations", json={"prompt": "go"})).json()["id"]

    second = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "again"}
    )

    assert second.status_code == 202
    assert second.json()["queued"] is True
    await client.delete(f"/api/conversations/{conversation_id}/run")


async def test_a_queued_message_does_not_repair_the_running_turn(slow) -> None:
    """Why the busy check happens *before* the load, not only after.

    Loading for writing calls `resume`, which commits crash repair — and a running
    turn legitimately has a dispatched call with no result yet. Resuming
    underneath it would append a synthetic "outcome unknown" for a tool still
    executing, and the real result would land beside it: two answers to one call,
    in an append-only log.
    """
    client, service, runs = slow
    conversation_id = (await client.post("/api/conversations", json={"prompt": "go"})).json()["id"]
    session = runs.active(conversation_id).session
    await until(
        lambda: any(e.type == "tool/call" for e in session.events()),
        what="the tool to be dispatched",
    )

    await client.post(f"/api/conversations/{conversation_id}/messages", json={"prompt": "again"})

    stored = await service.read(conversation_id)
    assert [e for e in stored.events() if e.type == "tool/result"] == []
    await client.delete(f"/api/conversations/{conversation_id}/run")


async def test_two_simultaneous_messages_start_exactly_one_turn(simple, monkeypatch) -> None:
    """Both requests get past the pre-check, so the post-check has to catch one.

    The interleaving is **forced**, not hoped for. Left to chance, both requests
    serialize and the second is refused by the *pre*-check — which passes this
    assertion while never exercising the branch it is about. So both are parked
    inside the session load until each has cleared the pre-check, and only then
    released to race for `start()`.
    """
    client, service, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    released = asyncio.Event()
    arrived = 0
    real_resume = service.resume

    async def gated_resume(session_id: str):
        nonlocal arrived
        arrived += 1
        await released.wait()
        return await real_resume(session_id)

    monkeypatch.setattr(service, "resume", gated_resume)

    first = asyncio.create_task(
        client.post(f"/api/conversations/{conversation_id}/messages", json={"prompt": "a"})
    )
    second = asyncio.create_task(
        client.post(f"/api/conversations/{conversation_id}/messages", json={"prompt": "b"})
    )
    await until(lambda: arrived == 2, what="both requests to clear the busy pre-check")
    released.set()

    responses = await asyncio.gather(first, second)

    # Both are accepted now; exactly one starts a turn and the other is queued.
    assert [r.status_code for r in responses] == [202, 202]
    assert sorted(r.json()["queued"] for r in responses) == [False, True]
    await settle(runs, conversation_id)
    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    # The opening message, the one that won the race, and the queued one drained
    # after it — nothing is lost, which is the point of queueing over refusing.
    prompts = [e["message"]["content"] for e in detail["events"] if e["type"] == "user/message"]
    assert prompts == ["hi", "a", "b"] or prompts == ["hi", "b", "a"]


async def test_a_stream_follows_the_turn_queued_behind_the_one_it_watched(tmp_path) -> None:
    """The bug: send while streaming, and the answer only appears on refresh.

    A queued message is drained into a *new* run when the watched one settles.
    A stream bound to the first run said `end` right then, the browser parked on
    it, and nothing ever woke it. The stream must follow the conversation across
    the drain: both turns, one cursor, one `end` — when nothing is left.
    """
    release = asyncio.Event()
    service, runs = build(
        tmp_path,
        SteppedClient(calls_tool("gate", '{"value": "x"}'), completed("done")),
        gated_tool(release),
    )
    async with api(tmp_path, service, runs) as client:
        conversation_id = (await client.post("/api/conversations", json={"prompt": "go"})).json()[
            "id"
        ]
        session = runs.active(conversation_id).session
        await until(
            lambda: any(e.type == "tool/call" for e in session.events()),
            what="the tool to be dispatched",
        )
        watching = asyncio.create_task(
            client.get(f"/api/conversations/{conversation_id}/events?after=0")
        )

        second = await client.post(
            f"/api/conversations/{conversation_id}/messages", json={"prompt": "again"}
        )
        assert second.json()["queued"] is True
        release.set()

        body = (await asyncio.wait_for(watching, timeout=5)).text
        seen = events_from(body)
        prompts = [e["message"]["content"] for e in seen if e["type"] == "user/message"]
        assert prompts == ["go", "again"]
        assert [e["reason"] for e in seen if e["type"] == "turn/end"] == ["completed", "completed"]
        assert frame_names(body)[-1] == "end"
        # One cursor across two runs: nothing repeated, nothing skipped.
        await settle(runs, conversation_id)
        assert len(seen) == len((await service.read(conversation_id)).events())


async def test_a_corrupt_log_reports_the_file_it_could_not_read(simple, tmp_path) -> None:
    """Not the client's fault, so a 500 — but one that names the file.

    The message carries the path and line an operator needs, so it is passed
    through whole rather than collapsed into a bare "internal server error".
    """
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)
    log = tmp_path / "sessions" / f"{conversation_id}.jsonl"
    lines = log.read_text().splitlines()
    lines[1] = "{not json"  # a committed line, not the tail
    log.write_text("\n".join(lines) + "\n")

    response = await client.get(f"/api/conversations/{conversation_id}")

    assert response.status_code == 500
    assert conversation_id in response.json()["detail"]


async def test_a_conversation_accepts_another_message_once_it_settles(simple) -> None:
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    second = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "again"}
    )

    assert second.status_code == 202
    await settle(runs, conversation_id)
    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    assert [e["reason"] for e in detail["events"] if e["type"] == "turn/end"] == [
        "completed",
        "completed",
    ]


# ── stopping ──────────────────────────────────────────────────────────────────


async def test_stopping_ends_the_turn_and_answers_every_call(slow) -> None:
    client, service, runs = slow
    conversation_id = (await client.post("/api/conversations", json={"prompt": "go"})).json()["id"]
    session = runs.active(conversation_id).session
    await until(
        lambda: any(e.type == "tool/call" for e in session.events()),
        what="the tool to be dispatched",
    )

    stopped = await client.delete(f"/api/conversations/{conversation_id}/run")

    assert stopped.status_code == 204
    stored = await service.read(conversation_id)
    assert [e.reason for e in stored.events() if e.type == "turn/end"] == ["cancelled"]
    calls = [e.call.id for e in stored.events() if e.type == "tool/call"]
    answered = [e.message.tool_call_id for e in stored.events() if e.type == "tool/result"]
    assert sorted(calls) == sorted(answered)


async def test_stopping_an_idle_conversation_is_a_404(simple) -> None:
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    assert (await client.delete(f"/api/conversations/{conversation_id}/run")).status_code == 404


async def test_a_stream_open_when_a_turn_is_stopped_is_released(slow) -> None:
    """A watching client must be told the turn ended, not left hanging."""
    client, _, runs = slow
    conversation_id = (await client.post("/api/conversations", json={"prompt": "go"})).json()["id"]
    session = runs.active(conversation_id).session

    async def read_to_end() -> str:
        response = await client.get(f"/api/conversations/{conversation_id}/events?after=0")
        return response.text

    watching = asyncio.create_task(read_to_end())
    await until(
        lambda: any(e.type == "tool/call" for e in session.events()),
        what="the tool to be dispatched",
    )
    await client.delete(f"/api/conversations/{conversation_id}/run")

    body = await asyncio.wait_for(watching, timeout=5)
    assert frame_names(body)[-1] == "end"
    assert [e["reason"] for e in events_from(body) if e["type"] == "turn/end"] == ["cancelled"]


# ── a full turn, end to end ───────────────────────────────────────────────────


async def test_a_tool_using_turn_reaches_the_client(tmp_path) -> None:
    service, runs = build(
        tmp_path,
        SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("it is 42")),
        echo_tool(),
    )
    async with api(tmp_path, service, runs) as client:
        conversation_id = (await client.post("/api/conversations", json={"prompt": "go"})).json()[
            "id"
        ]

        body = (await client.get(f"/api/conversations/{conversation_id}/events?after=0")).text

        seen = events_from(body)
        assert [e["type"] for e in seen if e["type"] == "tool/call"] == ["tool/call"]
        assert [e["reason"] for e in seen if e["type"] == "turn/end"] == ["completed"]


async def test_shutdown_stops_a_running_turn_durably(tmp_path) -> None:
    """A turn in flight when the server stops stays resumable."""
    service, runs = build(
        tmp_path, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool()
    )
    app = web_app(tmp_path, service, runs, skills=no_skills())
    transport = httpx.ASGITransport(app=app)
    conversation_id = ""

    async with httpx.AsyncClient(transport=transport, base_url="http://harness.test") as client:
        conversation_id = (await client.post("/api/conversations", json={"prompt": "go"})).json()[
            "id"
        ]
        session = runs.active(conversation_id).session
        await until(
            lambda: any(e.type == "tool/call" for e in session.events()),
            what="the tool to be dispatched",
        )

    await runs.aclose()  # what the lifespan's shutdown does

    stored = await service.read(conversation_id)
    assert [e.reason for e in stored.events() if e.type == "turn/end"] == ["cancelled"]
