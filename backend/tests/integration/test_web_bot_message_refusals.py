"""What `message_bot` refuses: the sender itself, a name no bot has, and a group chat."""

from __future__ import annotations

import json

from harness.bots import ASSISTANT_ID
from harness.tools.native.bots import MESSAGE_BOT
from tests.integration.web_helpers import ASSISTANT_START, messaging_app, of_type, once_said, send
from tests.unit.fakes import calls_tool, completed

RESEARCHER = {"name": "Researcher", "instructions": "Find sources and cite every claim."}


def sending_to(name: str) -> list:
    """Assistant's step that sends a message to the bot named `name`."""
    return calls_tool(MESSAGE_BOT, json.dumps({"bot": name, "message": "hello"}))


def result_text(result: dict) -> str:
    return result["message"]["content"][0]["text"]


async def test_a_bot_cannot_message_itself(tmp_path) -> None:
    world = messaging_app(tmp_path, {ASSISTANT_START: [sending_to("Assistant"), completed("ok")]})
    async with world.client as client:
        await send(client, ASSISTANT_ID, "message yourself")
        log = await once_said(client, ASSISTANT_ID, "ok")

    (result,) = of_type(log, "tool/result")
    assert result["error"] == "INVALID_ARGUMENTS"
    assert "you cannot send a message to yourself" in result_text(result)
    assert [e["bot_id"] for e in of_type(log, "turn/start")] == [ASSISTANT_ID]


async def test_a_name_no_bot_has_is_refused(tmp_path) -> None:
    world = messaging_app(tmp_path, {ASSISTANT_START: [sending_to("Nobody"), completed("ok")]})
    async with world.client as client:
        await send(client, ASSISTANT_ID, "message Nobody")
        log = await once_said(client, ASSISTANT_ID, "ok")

    (result,) = of_type(log, "tool/result")
    assert result["error"] == "INVALID_ARGUMENTS"


async def test_a_bot_speaking_in_a_group_cannot_send_a_message(tmp_path) -> None:
    world = messaging_app(
        tmp_path,
        {
            ASSISTANT_START: [sending_to("Researcher"), completed("ok")],
            RESEARCHER["instructions"]: [completed("hi")],
        },
    )
    async with world.client as client:
        researcher = (await client.post("/api/bots", json=RESEARCHER)).json()["id"]
        group = (
            await client.post(
                "/api/groups", json={"name": "Pair", "member_ids": [ASSISTANT_ID, researcher]}
            )
        ).json()["id"]
        await send(client, group, "go")
        group_log = await once_said(client, group, "hi")
        researcher_log = (await client.get(f"/api/conversations/{researcher}")).json()["events"]

    (result,) = of_type(group_log, "tool/result")
    assert result["error"] == "REFUSED"
    assert "only in your own chat, not in a group chat" in result_text(result)
    assert of_type(researcher_log, "bot/message") == []
