"""The HTTP surface, driven in-process."""

from __future__ import annotations

from tests.integration.web_helpers import events_from, frame_names, settle
from tests.unit.helpers import until


async def test_a_created_conversation_is_listed(simple) -> None:
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


async def test_the_snapshot_carries_the_cursor_to_stream_from(simple) -> None:
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()

    assert detail["next_cursor"] == len(detail["events"])
    assert detail["running"] is False


async def test_the_snapshot_reads_the_live_log_while_a_turn_runs(slow) -> None:
    client, _, runs = slow
    conversation_id = (await client.post("/api/conversations", json={"prompt": "go"})).json()["id"]
    session = runs.active(conversation_id).session
    await until(lambda: len(session.events()) > 3, what="the turn to get going")

    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()

    assert detail["running"] is True
    assert detail["next_cursor"] == len(session.events())


async def test_the_snapshot_renders_the_same_events_the_stream_does(simple) -> None:
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    streamed = await client.get(f"/api/conversations/{conversation_id}/events?after=0")

    assert events_from(streamed.text) == detail["events"]


async def test_the_stream_ends_with_an_end_frame(simple) -> None:
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)

    body = (await client.get(f"/api/conversations/{conversation_id}/events?after=0")).text

    assert frame_names(body)[-1] == "end"
    assert frame_names(body).count("end") == 1


async def test_an_idle_conversation_streams_its_stored_tail(simple) -> None:
    client, _, runs = simple
    conversation_id = (await client.post("/api/conversations", json={"prompt": "hi"})).json()["id"]
    await settle(runs, conversation_id)
    assert runs.active(conversation_id) is None

    body = (await client.get(f"/api/conversations/{conversation_id}/events?after=2")).text

    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    assert events_from(body) == detail["events"][2:]


async def test_snapshot_then_stream_reconstructs_the_log_exactly(simple) -> None:
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
