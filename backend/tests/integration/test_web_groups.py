"""Groups over HTTP: every member takes a turn, and an @mention brings a teammate back."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from harness.bots import BotService
from harness.llm.messages import SystemMessage, UserMessage
from harness.runs.service import RunService
from harness.tools.native.question import QUESTION
from tests.integration.web_helpers import settle
from tests.unit.fakes import SteppedClient, calls_tool, completed, hanging_tool
from tests.unit.helpers import client_tools, durable_service, no_skills, runtime_over
from tests.webapp import web_app

RESEARCHER = {"name": "Researcher", "instructions": "Find sources and cite every claim."}
WRITER = {"name": "Writer", "instructions": "Write short posts."}
ASKED = json.dumps({"question": "Which tone?", "options": ["Calm", "Loud"]})


async def _group(tmp_path, *scripts, extra=()):
    model = SteppedClient(*scripts)
    tools = client_tools()
    service = durable_service(tmp_path / "sessions")
    store = BotService(tmp_path / "bots.json", service, assistant_instructions="ASSISTANT")
    runtime = runtime_over(
        model, *tools.definitions(), *extra, guidance="GUIDE", checkpoint=service.flush
    )
    runs = RunService(service, runtime, store)
    app = web_app(tmp_path, service, runs, skills=no_skills(), bots=store, client_tools=tools)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as setup:
        researcher = (await setup.post("/api/bots", json=RESEARCHER)).json()["id"]
        writer = (await setup.post("/api/bots", json=WRITER)).json()["id"]
        created = await setup.post(
            "/api/groups", json={"name": "Launch", "member_ids": [researcher, writer]}
        )
    assert created.status_code == 201, created.text
    client = httpx.AsyncClient(transport=transport, base_url="http://t")
    return client, model, runs, created.json()["id"], researcher, writer


async def _send(client: httpx.AsyncClient, runs: RunService, chat: str, prompt: str) -> list[dict]:
    sent = await client.post(f"/api/conversations/{chat}/messages", json={"prompt": prompt})
    assert sent.status_code == 202, sent.text
    await settle(runs, chat)
    return (await client.get(f"/api/conversations/{chat}")).json()["events"]


async def test_every_member_takes_a_turn_and_a_mention_brings_one_back(tmp_path) -> None:
    client, model, runs, chat, researcher, writer = await _group(
        tmp_path,
        completed("Three trends: A, B, C."),
        completed("B fits. @Researcher is B still true?"),
        completed("Yes, B is current."),
    )
    async with client:
        events = await _send(client, runs, chat, "what should we post today?")

    speakers = [e["bot_id"] for e in events if e["type"] == "turn/start"]
    assert speakers == [researcher, writer, researcher]
    writer_saw = model.seen_per_call[1]
    assert isinstance(writer_saw[0], SystemMessage)
    assert writer_saw[0].content.startswith(WRITER["instructions"])
    assert UserMessage(content="what should we post today?") in writer_saw
    assert (
        UserMessage(content='<speaker name="Researcher" />\nThree trends: A, B, C.') in writer_saw
    )


async def test_bots_that_keep_mentioning_each_other_stop_after_six(tmp_path) -> None:
    client, model, runs, chat, _, _ = await _group(
        tmp_path, completed("Over to you @Researcher @Writer.")
    )
    async with client:
        await _send(client, runs, chat, "go")

    assert model.calls == 2 + 6


async def test_a_member_with_nothing_to_add_is_not_shown_to_the_others(tmp_path) -> None:
    client, model, runs, chat, _, _ = await _group(
        tmp_path, completed("NO_RESPONSE"), completed("Here is a draft.")
    )
    async with client:
        await _send(client, runs, chat, "draft something")

    history = model.seen_per_call[1][1:]
    assert not any("NO_RESPONSE" in str(m.content) for m in history)


@pytest.mark.parametrize("members", [[], ["nope"]])
async def test_a_group_needs_two_bots_that_exist(tmp_path, members) -> None:
    client, _, _, _, researcher, _ = await _group(tmp_path, completed("hi"))
    async with client:
        response = await client.post(
            "/api/groups", json={"name": "Solo", "member_ids": [researcher, *members][:2]}
        )

    assert response.status_code == 422


async def test_a_group_whose_bots_are_all_archived_keeps_its_chat_but_takes_no_message(
    tmp_path,
) -> None:
    client, _, _, chat, researcher, writer = await _group(tmp_path, completed("hi"))
    async with client:
        for bot_id in (researcher, writer):
            assert (await client.post(f"/api/bots/{bot_id}/archive")).status_code == 204
        sent = await client.post(f"/api/conversations/{chat}/messages", json={"prompt": "hi?"})
        read = await client.get(f"/api/conversations/{chat}")
        listed = (await client.get("/api/groups")).json()

    assert sent.status_code == 409
    assert read.status_code == 200
    assert [group["id"] for group in listed] == [chat]


async def test_a_group_s_member_list_is_written_again_once_a_member_leaves(tmp_path) -> None:
    client, _, runs, chat, _, writer = await _group(tmp_path, completed("Sources."))
    async with client:
        assert (await client.post(f"/api/bots/{writer}/archive")).status_code == 204
        events = await _send(client, runs, chat, "go")

    kinds = [e["type"] for e in events]
    rosters = [e["members"] for e in events if e["type"] == "group/members"]
    assert rosters == [["Researcher", "Writer"], ["Researcher"]]
    assert kinds.index("turn/start") > len(kinds) - 1 - kinds[::-1].index("group/members")


async def test_answering_a_bot_that_was_archived_since_it_asked_is_refused(tmp_path) -> None:
    client, _, runs, chat, researcher, _ = await _group(
        tmp_path, calls_tool(QUESTION, ASKED, id="call_q"), completed("Calm it is.")
    )
    async with client:
        await _send(client, runs, chat, "pick a tone")
        assert (await client.post(f"/api/bots/{researcher}/archive")).status_code == 204
        answered = await client.post(
            f"/api/conversations/{chat}/calls/call_q/output",
            json={"kind": "shared", "data": {"choice": "Calm"}},
        )

    assert answered.status_code == 409


@pytest.mark.parametrize(("method", "suffix"), [("POST", "/archive"), ("DELETE", "")])
async def test_removing_a_bot_stops_the_discussion_it_is_speaking_in(
    tmp_path, method, suffix
) -> None:
    client, _, runs, chat, researcher, _ = await _group(
        tmp_path, calls_tool("hang", '{"value": "x"}'), extra=(hanging_tool(),)
    )
    async with client:
        sent = await client.post(f"/api/conversations/{chat}/messages", json={"prompt": "go"})
        assert sent.status_code == 202
        for _ in range(200):
            running = runs.active(chat)
            if running is not None and running.session.speaker_id() == researcher:
                break
            await asyncio.sleep(0.01)
        removed = await client.request(method, f"/api/bots/{researcher}{suffix}")

    assert removed.status_code == 204
    assert runs.active(chat) is None
