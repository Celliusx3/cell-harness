"""`hand_over` over HTTP: the turn waits, then I'm done or Skip resumes it, or the person types."""

from __future__ import annotations

import json

import httpx
import pytest

from harness.llm import ToolMessage, text_of
from harness.runs.service import RunService
from harness.runtime.service import SKIPPED
from harness.tools.native.hand_over import HAND_OVER
from tests.integration.web_helpers import assistant_chat, build, events_from, settle
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import client_tools, no_skills
from tests.webapp import web_app

ASKED = json.dumps({"step": "Sign in to Shopee with your password."})
PATH = "/api/conversations/{id}/calls/call_h1/output"


def _handing_over(tmp_path, reply: str = "signed in, carrying on"):
    tools = client_tools()
    model = SteppedClient(calls_tool(HAND_OVER, ASKED, id="call_h1"), completed(reply))
    service, runs = build(tmp_path, model, *tools.definitions())
    app = web_app(tmp_path, service, runs, skills=no_skills(), client_tools=tools)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://h.test")
    return client, runs, model


async def _events(client: httpx.AsyncClient, conversation_id: str) -> list[dict]:
    return events_from(
        (await client.get(f"/api/conversations/{conversation_id}/events?after=0")).text
    )


async def _pending(client: httpx.AsyncClient, runs: RunService) -> str:
    conversation_id = await assistant_chat(client, "order my usual from Shopee")
    await settle(runs, conversation_id)
    return conversation_id


def _answer(finished: object) -> dict:
    return {"kind": "shared", "data": {"finished": finished}}


async def test_a_hand_over_ends_the_turn_pending_with_no_result(tmp_path) -> None:
    client, runs, _ = _handing_over(tmp_path)

    conversation_id = await _pending(client, runs)

    events = await _events(client, conversation_id)
    assert [e["reason"] for e in events if e["type"] == "turn/end"] == ["pending"]
    assert [e for e in events if e["type"] == "tool/result"] == []


@pytest.mark.parametrize(
    ("finished", "read"), [(True, '{"finished":true}'), (False, '{"finished":false}')]
)
async def test_done_or_skip_resumes_the_turn_and_the_model_reads_it(
    tmp_path, finished: bool, read: str
) -> None:
    client, runs, model = _handing_over(tmp_path)
    conversation_id = await _pending(client, runs)

    answered = await client.post(PATH.format(id=conversation_id), json=_answer(finished))
    assert answered.status_code == 204
    await settle(runs, conversation_id)

    result = next(e for e in await _events(client, conversation_id) if e["type"] == "tool/result")
    assert result["message"]["content"][0]["text"] == read
    assert result["error"] is None
    tool_messages = [m for m in model.seen_per_call[-1] if isinstance(m, ToolMessage)]
    assert [text_of(m.content) for m in tool_messages] == [read]


@pytest.mark.parametrize(
    "data", [{}, {"finished": True, "note": "used my phone"}, {"finished": "yes"}, {"finished": 1}]
)
async def test_an_answer_that_does_not_fit_is_refused_at_the_boundary(tmp_path, data) -> None:
    client, runs, _ = _handing_over(tmp_path)
    conversation_id = await _pending(client, runs)

    refused = await client.post(
        PATH.format(id=conversation_id), json={"kind": "shared", "data": data}
    )

    assert refused.status_code == 422
    assert runs.active(conversation_id) is None


async def test_typing_instead_skips_the_hand_over(tmp_path) -> None:
    client, runs, _ = _handing_over(tmp_path, reply="sure, what instead?")
    conversation_id = await _pending(client, runs)

    sent = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "forget Shopee"}
    )
    assert sent.status_code == 202
    await settle(runs, conversation_id)

    result = next(e for e in await _events(client, conversation_id) if e["type"] == "tool/result")
    assert result["error"] == SKIPPED
