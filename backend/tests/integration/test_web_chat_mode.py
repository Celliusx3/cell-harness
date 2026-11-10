"""A chat's mode over HTTP: Ask shows the card, Auto runs the call, and the latest switch wins."""

from __future__ import annotations

import httpx

from harness.bots import ASSISTANT_ID
from harness.tools import ApprovalService, Ok, Tool, ToolOutcome
from harness.tools.client import ClientToolService
from harness.web.runtime import CLIENT_TOOLS
from tests.integration.web_helpers import send, settle
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.webapp import web_app

WRITE = "memory__write_note"
MODE = f"/api/conversations/{ASSISTANT_ID}/mode"


def _writer(ran: list[str]) -> Tool[EchoArgs]:
    async def execute(args: EchoArgs, _context) -> ToolOutcome:
        ran.append(args.value)
        return Ok(content=f"saved {args.value}")

    return Tool.from_model(
        name=WRITE, description="Save a note.", args_model=EchoArgs, execute=execute
    )


def _app(tmp_path, *notes: str, ran: list[str]):
    """An app whose model saves each of `notes` in its own turn."""
    approvals = ApprovalService(
        frozenset({WRITE}), frozenset, tmp_path / "approvals.json", default_mode="ask"
    )
    tools = ClientToolService(CLIENT_TOOLS, approvals)
    steps = [
        step
        for at, note in enumerate(notes)
        for step in (calls_tool(WRITE, f'{{"value": "{note}"}}', id=f"call_{at}"), completed("ok"))
    ]
    service = durable_service(tmp_path / "sessions")
    runs = run_service(
        service, SteppedClient(*steps), _writer(ran), *tools.tools(), approvals=approvals
    )
    app = web_app(
        tmp_path, service, runs, skills=no_skills(), client_tools=tools, approvals=approvals
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://h.test")
    return client, runs


async def _turn_end_reasons(client: httpx.AsyncClient, runs, prompt: str) -> list[str]:
    await send(client, ASSISTANT_ID, prompt)
    await settle(runs, ASSISTANT_ID)
    detail = (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()
    return [e["reason"] for e in detail["events"] if e["type"] == "turn/end"]


async def test_a_new_chat_asks_before_a_protected_call(tmp_path) -> None:
    ran: list[str] = []
    client, runs = _app(tmp_path, "Kopi", ran=ran)

    assert await _turn_end_reasons(client, runs, "remember Kopi") == ["pending"]
    assert ran == []


async def test_auto_runs_the_call_with_no_card(tmp_path) -> None:
    ran: list[str] = []
    client, runs = _app(tmp_path, "Kopi", ran=ran)

    switched = await client.put(MODE, json={"mode": "auto"})
    assert switched.status_code == 204, switched.text

    assert await _turn_end_reasons(client, runs, "remember Kopi") == ["completed"]
    assert ran == ["Kopi"]
    detail = (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()
    assert {"type": "approval/mode", "mode": "auto"} in detail["events"]


async def test_the_latest_switch_wins(tmp_path) -> None:
    ran: list[str] = []
    client, runs = _app(tmp_path, "Kopi", "Teh", ran=ran)

    await client.put(MODE, json={"mode": "auto"})
    assert await _turn_end_reasons(client, runs, "remember Kopi") == ["completed"]
    await client.put(MODE, json={"mode": "ask"})

    assert await _turn_end_reasons(client, runs, "remember Teh") == ["completed", "pending"]
    assert ran == ["Kopi"]


async def test_a_mode_that_is_not_ask_or_auto_is_refused(tmp_path) -> None:
    client, _ = _app(tmp_path, ran=[])

    refused = await client.put(MODE, json={"mode": "yolo"})

    assert refused.status_code == 422


async def test_mode_typed_in_the_browser_switches_the_chat_and_starts_no_turn(tmp_path) -> None:
    ran: list[str] = []
    client, runs = _app(tmp_path, "Kopi", ran=ran)

    await send(client, ASSISTANT_ID, "/mode auto")
    await settle(runs, ASSISTANT_ID)

    detail = (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()
    assert {"type": "approval/mode", "mode": "auto"} in detail["events"]
    assert not [e for e in detail["events"] if e["type"] == "turn/start"]


async def test_mode_alone_in_the_browser_names_the_mode_on(tmp_path) -> None:
    client, _ = _app(tmp_path, ran=[])

    named = await client.post(
        f"/api/conversations/{ASSISTANT_ID}/messages", json={"prompt": "/mode"}
    )

    assert named.status_code == 422
    assert named.json()["detail"] == "Use /mode ask or /mode auto. Mode: Ask."


async def test_the_chat_says_which_mode_is_on(tmp_path) -> None:
    client, _ = _app(tmp_path, ran=[])
    await send(client, ASSISTANT_ID, "/mode auto")

    detail = (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()
    assert detail["mode"] == "auto"
    await client.put(MODE, json={"mode": "ask"})
    assert (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()["mode"] == "ask"


async def test_a_switch_to_the_mode_already_on_writes_nothing(tmp_path) -> None:
    client, _ = _app(tmp_path, ran=[])
    await client.put(MODE, json={"mode": "auto"})

    again = await client.put(MODE, json={"mode": "auto"})
    await client.put(MODE, json={"mode": "ask"})
    await client.put(MODE, json={"mode": "ask"})

    assert again.status_code == 204
    detail = (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()
    switches = [e["mode"] for e in detail["events"] if e["type"] == "approval/mode"]
    assert switches == ["auto", "ask"]


async def test_a_new_chat_switched_to_the_default_writes_nothing(tmp_path) -> None:
    client, _ = _app(tmp_path, ran=[])

    switched = await client.put(MODE, json={"mode": "ask"})
    detail = await client.get(f"/api/conversations/{ASSISTANT_ID}")

    assert switched.status_code == 204
    assert detail.status_code == 404, detail.text
