"""A listed tool over HTTP: the card's four answers, and the Approvals page's list."""

from __future__ import annotations

import httpx

from harness.runs.store import RunStore
from harness.tools.approval import DENIED, ApprovalGate
from harness.tools.client import ClientToolService
from harness.tools.definition import Ok, ToolDefinition, ToolOutcome
from harness.web.agent import CLIENT_TOOLS
from tests.integration.web_helpers import events_from, settle
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed
from tests.unit.helpers import durable_service, no_skills, run_store
from tests.webapp import web_app

WRITE = "memory__write_note"
PATH = "/api/conversations/{id}/calls/call_7f3a/output"


def _writer(ran: list[str]) -> ToolDefinition[EchoArgs]:
    async def execute(args: EchoArgs, _context) -> ToolOutcome:
        ran.append(args.value)
        return Ok(content=f"saved {args.value}")

    return ToolDefinition.from_model(
        name=WRITE, description="Save a note.", args_model=EchoArgs, execute=execute
    )


def _asking(tmp_path, *steps, ran: list[str]):
    """An app whose model saves a note, then answers."""
    gate = ApprovalGate(frozenset({WRITE}), tmp_path / "approvals.json")
    tools = ClientToolService(CLIENT_TOOLS, gate)
    model = SteppedClient(
        calls_tool(WRITE, '{"value": "Kopi"}', id="call_7f3a"), completed("saved"), *steps
    )
    service = durable_service(tmp_path / "sessions")
    runs = run_store(service, model, _writer(ran), *tools.definitions(), gate=gate)
    app = web_app(tmp_path, service, runs, skills=no_skills(), client_tools=tools, gate=gate)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://h.test")
    return client, runs


async def _pending(client: httpx.AsyncClient, runs: RunStore) -> str:
    conversation_id = (
        await client.post("/api/conversations", json={"prompt": "remember I like Kopi"})
    ).json()["id"]
    await settle(runs, conversation_id)
    detail = (await client.get(f"/api/conversations/{conversation_id}")).json()
    assert detail["running"] is False
    assert [e["reason"] for e in detail["events"] if e["type"] == "turn/end"] == ["pending"]
    return conversation_id


async def _events(client: httpx.AsyncClient, conversation_id: str) -> list[dict]:
    return events_from(
        (await client.get(f"/api/conversations/{conversation_id}/events?after=0")).text
    )


async def test_allow_once_runs_the_call_and_the_turn_resumes(tmp_path) -> None:
    ran: list[str] = []
    client, runs = _asking(tmp_path, ran=ran)
    conversation_id = await _pending(client, runs)
    assert ran == []

    answered = await client.post(
        PATH.format(id=conversation_id), json={"kind": "approved", "scope": "once"}
    )
    assert answered.status_code == 204
    await settle(runs, conversation_id)

    assert ran == ["Kopi"]
    events = await _events(client, conversation_id)
    result = next(e for e in events if e["type"] == "tool/result")
    assert result["error"] is None
    assert result["message"]["content"][0]["text"] == "saved Kopi"
    assert [e["reason"] for e in events if e["type"] == "turn/end"] == ["pending", "completed"]


async def test_deny_reaches_the_model_as_a_typed_failure(tmp_path) -> None:
    ran: list[str] = []
    client, runs = _asking(tmp_path, ran=ran)
    conversation_id = await _pending(client, runs)

    answered = await client.post(PATH.format(id=conversation_id), json={"kind": "denied"})
    assert answered.status_code == 204
    await settle(runs, conversation_id)

    assert ran == []
    result = next(e for e in await _events(client, conversation_id) if e["type"] == "tool/result")
    assert result["error"] == DENIED
    assert result["message"]["content"][0]["text"].startswith("error: the user pressed Deny")


async def test_always_allow_is_listed_and_revoking_brings_the_card_back(tmp_path) -> None:
    ran: list[str] = []
    client, runs = _asking(
        tmp_path, calls_tool(WRITE, '{"value": "Teh"}', id="call_2"), completed("again"), ran=ran
    )
    conversation_id = await _pending(client, runs)
    assert (await client.get("/api/approvals")).json() == {"tools": []}

    answered = await client.post(
        PATH.format(id=conversation_id), json={"kind": "approved", "scope": "always"}
    )
    assert answered.status_code == 204
    await settle(runs, conversation_id)
    assert (await client.get("/api/approvals")).json() == {"tools": [WRITE]}
    assert (tmp_path / "approvals.json").exists()

    sent = await client.post(
        f"/api/conversations/{conversation_id}/messages", json={"prompt": "and Teh"}
    )
    assert sent.status_code == 202
    await settle(runs, conversation_id)
    assert ran == ["Kopi", "Teh"]
    events = await _events(client, conversation_id)
    assert [e["reason"] for e in events if e["type"] == "turn/end"] == [
        "pending",
        "completed",
        "completed",
    ]

    revoked = await client.delete(f"/api/approvals/{WRITE}")
    assert revoked.status_code == 204
    assert (await client.get("/api/approvals")).json() == {"tools": []}
    assert (await client.delete(f"/api/approvals/{WRITE}")).status_code == 404


async def test_a_client_body_for_a_listed_tool_does_not_fit(tmp_path) -> None:
    client, runs = _asking(tmp_path, ran=[])
    conversation_id = await _pending(client, runs)

    wrong = await client.post(PATH.format(id=conversation_id), json={"kind": "shared", "data": {}})
    assert wrong.status_code == 422
    unknown = await client.post(PATH.format(id=conversation_id), json={"kind": "approved"})
    assert unknown.status_code == 422
