"""A client tool over HTTP: the model asks, the turn ends pending, and the
browser's output opens the turn that carries it.

Same in-process transport as `test_web.py`. The route is the only surface;
what it guards — only the pending call, only a body its declaration accepts,
only while nothing is running — is tested from the outside, by status code.
`get_location` is the declaration used because it is the one that exists.
"""

from __future__ import annotations

import httpx

from harness.agent.loop import SKIPPED
from harness.runs.store import RunStore
from harness.tools.native.location import LOCATION
from tests.integration.web_helpers import build, events_from, settle
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import client_tools, durable_service, no_skills, run_store
from tests.webapp import web_app

SHARED = {"kind": "shared", "data": {"latitude": 3.139, "longitude": 101.6869, "accuracy_m": 25}}
PATH = "/api/conversations/{id}/calls/call_7f3a/output"


def _asking(tmp_path, reply: str = "a café 200 m from you"):
    """An app whose model asks for the location, then answers."""
    tools = client_tools()
    model = SteppedClient(calls_tool(LOCATION, "{}", id="call_7f3a"), completed(reply))
    service, runs = build(tmp_path, model, *tools.definitions())
    app = web_app(tmp_path, service, runs, skills=no_skills(), client_tools=tools)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://h.test")
    return client, service, runs


async def _pending(client: httpx.AsyncClient, runs: RunStore) -> str:
    """Start the turn and let it end pending."""
    conversation_id = (
        await client.post("/api/conversations", json={"prompt": "coffee near me?"})
    ).json()["id"]
    await settle(runs, conversation_id)
    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    assert detail["running"] is False  # pending is idle: the composer is free
    assert [e["reason"] for e in detail["events"] if e["type"] == "turn/end"] == ["pending"]
    return conversation_id


async def _events(client: httpx.AsyncClient, conversation_id: str) -> list[dict]:
    return events_from(
        (await client.get(f"/api/conversations/{conversation_id}/events?after=0")).text
    )


async def test_the_browser_answers_the_call_and_the_turn_resumes(tmp_path) -> None:
    client, _, runs = _asking(tmp_path)
    conversation_id = await _pending(client, runs)

    answered = await client.post(PATH.format(id=conversation_id), json=SHARED)
    assert answered.status_code == 204
    assert runs.active(conversation_id) is not None  # the answer opened a turn
    await settle(runs, conversation_id)

    events = await _events(client, conversation_id)
    result = next(e for e in events if e["type"] == "tool/result")
    assert result["message"]["tool_call_id"] == "call_7f3a"
    assert result["message"]["content"][0]["text"] == (
        '{"latitude":3.139,"longitude":101.6869,"accuracy_m":25.0}'
    )
    assert result["error"] is None
    assert [e["reason"] for e in events if e["type"] == "turn/end"] == ["pending", "completed"]
    assert (
        next(e for e in events if e["type"] == "assistant/message" and e["message"]["content"])[
            "message"
        ]["content"]
        == "a café 200 m from you"
    )


async def test_declining_reaches_the_model_as_a_typed_failure(tmp_path) -> None:
    client, _, runs = _asking(tmp_path)
    conversation_id = await _pending(client, runs)

    answered = await client.post(PATH.format(id=conversation_id), json={"kind": "declined"})
    assert answered.status_code == 204
    await settle(runs, conversation_id)

    result = next(e for e in await _events(client, conversation_id) if e["type"] == "tool/result")
    assert result["error"] == "DECLINED"
    assert result["message"]["content"][0]["text"].startswith("error: the user chose not to")


async def test_typing_instead_skips_the_ask(tmp_path) -> None:
    """The person moved on. The new turn first answers the dangling call as
    skipped — a provider refuses a history with a call and no result — then
    carries their message."""
    client, _, runs = _asking(tmp_path, reply="9pm in Tokyo")
    conversation_id = await _pending(client, runs)

    sent = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "time in Tokyo?"}
    )
    assert sent.status_code == 202 and sent.json()["queued"] is False
    await settle(runs, conversation_id)

    events = await _events(client, conversation_id)
    types = [e["type"] for e in events]
    skipped = next(e for e in events if e["type"] == "tool/result")
    assert skipped["error"] == SKIPPED
    assert types[types.index("tool/result") + 1 :][:2] == ["turn/start", "user/message"]
    late = await client.post(PATH.format(id=conversation_id), json=SHARED)
    assert late.status_code == 404


async def test_a_call_that_is_not_pending_cannot_be_answered(tmp_path) -> None:
    """Unknown id, unknown conversation, an answered call: 404, every time."""
    client, _, runs = _asking(tmp_path)
    conversation_id = await _pending(client, runs)

    wrong_call = await client.post(
        f"/api/conversations/{conversation_id}/calls/call_nope/output", json=SHARED
    )
    wrong_conversation = await client.post(PATH.format(id="zz"), json=SHARED)
    assert (wrong_call.status_code, wrong_conversation.status_code) == (404, 404)

    await client.post(PATH.format(id=conversation_id), json=SHARED)
    await settle(runs, conversation_id)
    assert (await client.post(PATH.format(id=conversation_id), json=SHARED)).status_code == 404


async def test_an_answer_while_a_turn_runs_is_refused(tmp_path) -> None:
    """Two tabs: the first answer opened the turn; the second finds it running."""
    client, _, runs = _asking(tmp_path)
    conversation_id = await _pending(client, runs)

    first = await client.post(PATH.format(id=conversation_id), json=SHARED)
    second = await client.post(PATH.format(id=conversation_id), json={"kind": "declined"})
    await settle(runs, conversation_id)

    assert (first.status_code, second.status_code) == (204, 409)


async def test_a_malformed_answer_is_rejected_at_the_boundary(tmp_path) -> None:
    client, _, runs = _asking(tmp_path)
    conversation_id = await _pending(client, runs)
    path = PATH.format(id=conversation_id)

    bodies = [
        {"kind": "shared", "data": {**SHARED["data"], "latitude": 95.0}},
        {"kind": "shared", "data": {**SHARED["data"], "altitude": 3.0}},
        {"kind": "shared", "data": {"percent": 80}},
        {"kind": "unavailable", "reason": ""},
        {"kind": "lost"},
    ]
    assert [(await client.post(path, json=body)).status_code for body in bodies] == [422] * 5
    assert runs.active(conversation_id) is None  # nothing was opened


async def test_a_restart_between_the_ask_and_the_answer_changes_nothing(tmp_path) -> None:
    """The pending call lives in the log, not in memory: a new process over
    the same directory takes the answer and resumes."""
    client, _, runs = _asking(tmp_path)
    conversation_id = await _pending(client, runs)

    # "Restart": a fresh service and run store over the same directory, and
    # a fresh app around them. Nothing from the first process survives but
    # the files.
    tools = client_tools()
    reborn = durable_service(tmp_path / "sessions", prefix="d")
    model = SteppedClient(completed("a café 200 m from you"))
    runs2 = run_store(reborn, model, *tools.definitions())
    app2 = web_app(tmp_path, reborn, runs2, skills=no_skills(), client_tools=tools)
    client2 = httpx.AsyncClient(transport=httpx.ASGITransport(app=app2), base_url="http://h.test")

    answered = await client2.post(PATH.format(id=conversation_id), json=SHARED)
    assert answered.status_code == 204
    await settle(runs2, conversation_id)

    events = await _events(client2, conversation_id)
    assert [e["reason"] for e in events if e["type"] == "turn/end"] == ["pending", "completed"]
    result = next(e for e in events if e["type"] == "tool/result")
    assert result["error"] is None
