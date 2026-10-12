"""Bots message each other: the message wakes the other bot, and its answer wakes the sender."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from harness.bots import ASSISTANT_ID
from harness.llm.messages import UserMessage
from harness.tools.native.bots import MESSAGE_BOT
from tests.integration.web_helpers import (
    ASSISTANT_START,
    Messaging,
    messaging_app,
    of_type,
    once_said,
    send,
)
from tests.unit.fakes import calls_tool, completed, gated_tool, pending_tool

RESEARCHER = {"name": "Researcher", "instructions": "Find sources and cite every claim."}
ASKED = json.dumps({"bot": "Researcher", "message": "Is B still true?"})


def ask(call_id: str) -> list:
    """Assistant's step that sends Researcher a message under `call_id`."""
    return calls_tool(MESSAGE_BOT, ASKED, id=call_id)


async def make_researcher(world: Messaging) -> str:
    """Researcher's id, once it is made."""
    return (await world.client.post("/api/bots", json=RESEARCHER)).json()["id"]


async def test_a_bot_asks_another_and_its_answer_wakes_the_sender(tmp_path) -> None:
    world = messaging_app(
        tmp_path,
        {
            ASSISTANT_START: [
                ask("c1"),
                completed("I asked Researcher."),
                completed("Researcher says B is current."),
            ],
            RESEARCHER["instructions"]: [completed("Yes, B is current.")],
        },
    )
    async with world.client as client:
        researcher = await make_researcher(world)
        await send(client, ASSISTANT_ID, "ask Researcher if B is still true")
        assistant_log = await once_said(client, ASSISTANT_ID, "Researcher says B is current.")
        researcher_log = await once_said(client, researcher, "Yes, B is current.")

    assert [e["message"] for e in of_type(researcher_log, "bot/message")] == [
        {
            "from_bot_id": ASSISTANT_ID,
            "from_name": "Assistant",
            "text": "Is B still true?",
            "hop": 1,
            "intent": "request",
        }
    ]
    assert [e["message"] for e in of_type(assistant_log, "bot/message")] == [
        {
            "from_bot_id": researcher,
            "from_name": "Researcher",
            "text": "Yes, B is current.",
            "hop": 2,
            "intent": "result",
        }
    ]
    assert of_type(assistant_log, "tool/result")[0]["error"] is None
    assert [e["bot_id"] for e in of_type(assistant_log, "turn/start")] == [ASSISTANT_ID] * 2
    researcher_heard = world.model.seen_by[RESEARCHER["instructions"]][0]
    assert any(
        isinstance(m, UserMessage) and "Assistant" in m.content and "Is B still true?" in m.content
        for m in researcher_heard
    )
    assistant_woken = world.model.seen_by[ASSISTANT_START][2]
    assert any(
        isinstance(m, UserMessage) and "Yes, B is current." in m.content for m in assistant_woken
    )


async def test_a_chain_of_messages_is_refused_at_the_seventh_hop(tmp_path) -> None:
    world = messaging_app(
        tmp_path,
        {
            ASSISTANT_START: [
                ask("c1"),
                completed("asked"),
                ask("c2"),
                completed("asked"),
                ask("c3"),
                completed("asked"),
                ask("c4"),
                completed("stopped"),
            ],
            RESEARCHER["instructions"]: [completed("answer")],
        },
    )
    async with world.client as client:
        researcher = await make_researcher(world)
        await send(client, ASSISTANT_ID, "keep asking")
        assistant_log = await once_said(client, ASSISTANT_ID, "stopped")
        researcher_log = await once_said(client, researcher, "answer")

    assert [e["message"]["hop"] for e in of_type(researcher_log, "bot/message")] == [1, 3, 5]
    assert [e["message"]["hop"] for e in of_type(assistant_log, "bot/message")] == [2, 4, 6]
    results = of_type(assistant_log, "tool/result")
    assert [r["error"] for r in results] == [None, None, None, "REFUSED"]
    assert "reached 6 hops" in results[-1]["message"]["content"][0]["text"]


async def test_a_busy_bot_reads_the_message_once_its_turn_ends(tmp_path) -> None:
    release = asyncio.Event()
    world = messaging_app(
        tmp_path,
        {
            ASSISTANT_START: [ask("c1"), completed("asked"), completed("relayed")],
            RESEARCHER["instructions"]: [
                calls_tool("gate", json.dumps({"value": "x"}), id="g1"),
                completed("done for the person"),
                completed("answer for Assistant"),
            ],
        },
        gated_tool(release),
    )
    async with world.client as client:
        researcher = await make_researcher(world)
        await send(client, researcher, "look something up")
        await send(client, ASSISTANT_ID, "ask Researcher")
        await once_said(client, ASSISTANT_ID, "asked")
        while_busy = (await client.get(f"/api/conversations/{researcher}")).json()
        release.set()
        assistant_log = await once_said(client, ASSISTANT_ID, "relayed")
        researcher_log = await once_said(client, researcher, "answer for Assistant")

    assert while_busy["running"] is True
    assert of_type(while_busy["events"], "bot/message") == []
    kinds = [e["type"] for e in researcher_log]
    assert kinds.index("bot/message") > kinds.index("turn/end")
    answered = of_type(assistant_log, "bot/message")
    assert [e["message"]["text"] for e in answered] == ["answer for Assistant"]


async def test_a_bot_waiting_on_the_person_answers_that_it_is_waiting(tmp_path) -> None:
    world = messaging_app(
        tmp_path,
        {
            ASSISTANT_START: [ask("c1"), completed("asked"), completed("relayed")],
            RESEARCHER["instructions"]: [calls_tool("ask", json.dumps({"value": "x"}), id="p1")],
        },
        pending_tool(),
    )
    async with world.client as client:
        await make_researcher(world)
        await send(client, ASSISTANT_ID, "ask Researcher")
        assistant_log = await once_said(client, ASSISTANT_ID, "relayed")

    assert [e["message"]["text"] for e in of_type(assistant_log, "bot/message")] == [
        "Researcher is waiting for the user to answer it in its own chat."
    ]


@pytest.mark.parametrize("remove", ["archive", "delete"])
async def test_a_message_for_a_bot_removed_while_it_waited_is_dropped(
    tmp_path, caplog: pytest.LogCaptureFixture, remove: str
) -> None:
    release = asyncio.Event()
    world = messaging_app(
        tmp_path,
        {
            ASSISTANT_START: [ask("c1"), completed("asked"), completed("relayed")],
            RESEARCHER["instructions"]: [calls_tool("gate", json.dumps({"value": "x"}), id="g1")],
        },
        gated_tool(release),
    )
    async with world.client as client:
        researcher = await make_researcher(world)
        await send(client, researcher, "look something up")
        await send(client, ASSISTANT_ID, "ask Researcher")
        await once_said(client, ASSISTANT_ID, "asked")
        with caplog.at_level(logging.WARNING, logger="harness.runs"):
            if remove == "archive":
                removed = await client.post(f"/api/bots/{researcher}/archive")
            else:
                removed = await client.delete(f"/api/bots/{researcher}")
            await asyncio.wait_for(asyncio.gather(*world.messages._waiting), timeout=5)
        assistant_log = (await client.get(f"/api/conversations/{ASSISTANT_ID}")).json()["events"]

    assert removed.status_code == 204
    assert "bot message dropped" in caplog.text
    assert of_type(assistant_log, "bot/message") == []
    assert world.runs.active(researcher) is None


async def test_closing_cancels_a_message_still_waiting_for_its_bot(tmp_path) -> None:
    release = asyncio.Event()
    world = messaging_app(
        tmp_path,
        {
            ASSISTANT_START: [ask("c1"), completed("asked")],
            RESEARCHER["instructions"]: [
                calls_tool("gate", json.dumps({"value": "x"}), id="g1"),
                completed("done for the person"),
            ],
        },
        gated_tool(release),
    )
    async with world.client as client:
        researcher = await make_researcher(world)
        await send(client, researcher, "look something up")
        await send(client, ASSISTANT_ID, "ask Researcher")
        await once_said(client, ASSISTANT_ID, "asked")
        await world.messages.aclose()
        release.set()
        researcher_log = await once_said(client, researcher, "done for the person")
        await asyncio.sleep(0.05)
        after = (await client.get(f"/api/conversations/{researcher}")).json()

    assert of_type(researcher_log, "bot/message") == []
    assert after["running"] is False
    assert of_type(after["events"], "bot/message") == []
