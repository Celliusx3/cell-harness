"""`ask_user` over HTTP: the browser taps an answer, or the person types instead."""

from __future__ import annotations

import json

import httpx

from harness.runs.service import RunService
from harness.runtime.service import SKIPPED
from harness.tools.native.question import QUESTION
from tests.integration.web_helpers import assistant_chat, build, events_from, settle
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import client_tools, no_skills
from tests.webapp import web_app

ASKED = json.dumps({"question": "Which shop?", "options": ["Lazada", "Shopee"]})
PATH = "/api/conversations/{id}/calls/call_9b1c/output"


def _asking(tmp_path, reply: str = "searching Shopee"):
    tools = client_tools()
    model = SteppedClient(calls_tool(QUESTION, ASKED, id="call_9b1c"), completed(reply))
    service, runs = build(tmp_path, model, *tools.definitions())
    app = web_app(tmp_path, service, runs, skills=no_skills(), client_tools=tools)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://h.test")
    return client, runs


async def _pending(client: httpx.AsyncClient, runs: RunService) -> str:
    conversation_id = await assistant_chat(client, "find me a Pokémon ETB")
    await settle(runs, conversation_id)
    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    assert [e["reason"] for e in detail["events"] if e["type"] == "turn/end"] == ["pending"]
    return conversation_id


async def _result(client: httpx.AsyncClient, conversation_id: str) -> dict:
    events = events_from(
        (await client.get(f"/api/conversations/{conversation_id}/events?after=0")).text
    )
    return next(e for e in events if e["type"] == "tool/result")


def _choice(label: str) -> dict:
    return {"kind": "shared", "data": {"choice": label}}


async def test_a_tap_answers_the_question_and_the_turn_resumes(tmp_path) -> None:
    client, runs = _asking(tmp_path)
    conversation_id = await _pending(client, runs)

    tapped = await client.post(PATH.format(id=conversation_id), json=_choice("Shopee"))
    assert tapped.status_code == 204
    await settle(runs, conversation_id)

    result = await _result(client, conversation_id)
    assert result["message"]["content"][0]["text"] == '{"choice":"Shopee"}'
    assert result["error"] is None


async def test_an_answer_that_was_not_offered_is_still_the_answer(tmp_path) -> None:
    client, runs = _asking(tmp_path)
    conversation_id = await _pending(client, runs)

    answered = await client.post(PATH.format(id=conversation_id), json=_choice("Amazon"))
    assert answered.status_code == 204
    await settle(runs, conversation_id)

    result = await _result(client, conversation_id)
    assert result["message"]["content"][0]["text"] == '{"choice":"Amazon"}'


async def test_an_empty_answer_is_refused_at_the_boundary(tmp_path) -> None:
    client, runs = _asking(tmp_path)
    conversation_id = await _pending(client, runs)

    refused = await client.post(PATH.format(id=conversation_id), json=_choice(""))
    assert refused.status_code == 422
    assert runs.active(conversation_id) is None


async def test_typing_instead_skips_the_question(tmp_path) -> None:
    client, runs = _asking(tmp_path, reply="searching Amazon")
    conversation_id = await _pending(client, runs)

    sent = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "neither, try Amazon"}
    )
    assert sent.status_code == 202
    await settle(runs, conversation_id)

    assert (await _result(client, conversation_id))["error"] == SKIPPED
