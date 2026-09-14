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

from tests.integration.web_helpers import events_from, frame_names, settle
from tests.unit.helpers import until

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
