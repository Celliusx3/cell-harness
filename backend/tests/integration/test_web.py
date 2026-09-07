"""The HTTP surface, driven in-process.

`ASGITransport` rather than a real port: these tests are about status codes,
bodies, and the cursor handoff, and a socket would add scheduling noise without
adding coverage.

**It cannot test a live stream.** `ASGITransport.handle_async_request` runs
`await self.app(...)` to completion, collecting the body, and only then returns a
`Response` — so `client.stream()` sees a finished response and there is no way to
hang up midway. Every stream read here is therefore of a stream that *ends*.

Mid-stream behaviour — hanging up on a running turn, reconnecting with a cursor —
lives in `test_web_stream.py`, against a real uvicorn server, because what it
checks is precisely what the transport elides.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from harness.agent.loop import LoopAgent
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    hanging_tool,
)
from tests.unit.helpers import pipeline_for
from tests.webapp import web_app


def build(tmp_path, client, *tools) -> tuple[SessionService, RunStore]:
    ids = iter(f"c{n}" for n in range(100))
    service = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )
    agent = LoopAgent(
        name="t",
        model="m",
        client=client,
        tools=pipeline_for(*tools) if tools else None,
        checkpoint=service.flush,
    )
    return service, RunStore(service, agent)


def api(tmp_path, service: SessionService, runs: RunStore) -> httpx.AsyncClient:
    app = web_app(tmp_path, service, runs)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://harness.test")


@pytest.fixture
async def simple(tmp_path):
    """An app whose model answers in one step."""
    service, runs = build(tmp_path, ScriptedClient(completed("hello")))
    async with api(tmp_path, service, runs) as client:
        yield client, service, runs


@pytest.fixture
async def slow(tmp_path):
    """An app whose turn parks inside a tool until something stops it."""
    service, runs = build(
        tmp_path, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool()
    )
    async with api(tmp_path, service, runs) as client:
        yield client, service, runs


async def settle(runs: RunStore, conversation_id: str) -> None:
    run = runs.active(conversation_id)
    if run is not None:
        await asyncio.wait_for(run._outer, timeout=5)


async def until(predicate, *, what: str) -> None:
    for _ in range(500):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError(f"timed out waiting for {what}")


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


# ── creating and listing ──────────────────────────────────────────────────────


async def test_a_created_conversation_is_listed(simple) -> None:
    """The phantom-create bug this endpoint shape exists to avoid.

    A bodyless create would return an id for a session that lazy materialization
    never wrote, so it would be absent here and gone on refresh.
    """
    client, _, runs = simple
    created = await client.post("/api/conversations", json={"prompt": "hi"})
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    await settle(runs, conversation_id)

    listed = await client.get("/api/conversations")

    assert [row["id"] for row in listed.json()] == [conversation_id]


async def test_the_list_is_empty_before_anything_is_sent(simple) -> None:
    client, _, _ = simple

    assert (await client.get("/api/conversations")).json() == []


async def test_a_blank_prompt_is_refused_on_both_post_paths(simple) -> None:
    """Validated at the edge, so no turn ever asks the model nothing."""
    client, _, runs = simple
    created = await client.post("/api/conversations", json={"prompt": "hi"})
    conversation_id = created.json()["id"]
    await settle(runs, conversation_id)

    assert (await client.post("/api/conversations", json={"prompt": ""})).status_code == 422
    sent = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "   "}
    )
    assert sent.status_code == 422


async def test_an_unknown_conversation_is_a_404(simple) -> None:
    client, _, _ = simple

    assert (await client.get("/api/conversations/nope")).status_code == 404
    assert (
        await client.post("/api/conversations/nope/messages", json={"prompt": "hi"})
    ).status_code == 404


# ── the snapshot ──────────────────────────────────────────────────────────────


async def test_the_snapshot_carries_the_cursor_to_stream_from(simple) -> None:
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()

    assert detail["next_cursor"] == len(detail["events"])
    assert detail["running"] is False


async def test_the_snapshot_reads_the_live_log_while_a_turn_runs(slow) -> None:
    """Reading disk instead would show a conversation mysteriously behind, since
    flushes happen at checkpoints rather than per event."""
    client, _, runs = slow
    conversation_id = (await client.post("/api/conversations", json={"prompt": "go"})).json()["id"]
    session = runs.active(conversation_id).session
    await until(lambda: len(session.events()) > 3, what="the turn to get going")

    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()

    assert detail["running"] is True
    assert detail["next_cursor"] == len(session.events())


async def test_the_snapshot_renders_the_same_events_the_stream_does(simple) -> None:
    """One event type, one renderer — the acceptance criterion, as a test."""
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    streamed = await client.get(f"/api/conversations/{conversation_id}/events?after=0")

    assert events_from(streamed.text) == detail["events"]


# ── the stream ────────────────────────────────────────────────────────────────


async def test_the_stream_ends_with_an_end_frame(simple) -> None:
    """A clean ending and a dropped connection must be distinguishable, or a
    client cannot tell "stop" from "reconnect at your cursor"."""
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    body = (await client.get(f"/api/conversations/{conversation_id}/events?after=0")).text

    assert frame_names(body)[-1] == "end"
    assert frame_names(body).count("end") == 1


async def test_an_idle_conversation_streams_its_stored_tail(simple) -> None:
    """The gap this branch closes.

    A turn settling between a client's snapshot and its subscribe would otherwise
    leave those events unreachable: the cursor says n, the log holds n + k, and a
    bare `end` would confirm the client was up to date.
    """
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)
    assert runs.active(conversation_id) is None  # the timing being simulated

    body = (await client.get(f"/api/conversations/{conversation_id}/events?after=2")).text

    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    assert events_from(body) == detail["events"][2:]


async def test_snapshot_then_stream_reconstructs_the_log_exactly(simple) -> None:
    """No gap, no overlap — the whole point of one cursor for both."""
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    tail = await client.get(
        f"/api/conversations/{conversation_id}/events?after={detail['next_cursor']}"
    )

    assert events_from(tail.text) == []
    whole = (await client.get(f"/api/conversations/{conversation_id}/events?after=0")).text
    assert detail["events"] + events_from(tail.text) == events_from(whole)


async def test_a_negative_cursor_is_refused(simple) -> None:
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    streamed = await client.get(f"/api/conversations/{conversation_id}/events?after=-1")

    assert streamed.status_code == 422


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
    app = web_app(tmp_path, service, runs)
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
