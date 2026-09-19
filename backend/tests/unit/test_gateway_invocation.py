"""`/name` at the gateway."""

from __future__ import annotations

import asyncio

import pytest

from harness.skills import UnknownSkill
from tests.unit.fakes import ScriptedClient, SteppedClient, calls_tool, completed, gated_tool
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import skills_at
from tests.unit.test_skill_tool import write_skill


async def test_a_slash_name_expands_before_the_turn_starts(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    bot, gateway, runs, chats, sessions = build(
        tmp_path, ScriptedClient(completed("Village Park")), skills=skills_at(root)
    )

    await gateway.receive(msg("/find-place https://x", 1))
    await settle(runs, gateway)

    state = await chats.load("telegram", CHAT)
    stored = await sessions.read(state.conversation_id)
    (content,) = [e.message.content for e in stored.events() if e.type == "user/message"]
    assert content.startswith('/find-place https://x\n\n<skill name="find-place">')
    assert bot.sent == [(CHAT, "Village Park")]


async def test_an_unknown_slash_name_is_refused_before_anything_is_queued(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    bot, gateway, runs, chats, sessions = build(
        tmp_path, ScriptedClient(completed("never")), skills=skills_at(root)
    )

    with pytest.raises(UnknownSkill) as caught:
        await gateway.receive(msg("/summarise this", 1))

    assert caught.value.name == "summarise"
    assert await chats.load("telegram", CHAT) is None
    assert await sessions.list() == []


async def test_a_queued_slash_name_is_expanded_when_it_drains(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    gate = asyncio.Event()
    bot, gateway, runs, chats, sessions = build(
        tmp_path,
        SteppedClient(
            calls_tool("gate", '{"value": "x"}'), completed("first"), completed("second")
        ),
        gated_tool(gate),
        skills=skills_at(root),
    )

    await gateway.receive(msg("hold on", 1))
    conversation = (await chats.load("telegram", CHAT)).conversation_id
    for _ in range(200):
        if runs.active(conversation) is not None:
            break
        await asyncio.sleep(0.01)
    assert await gateway.receive(msg("/find-place https://x", 2)) is None
    assert (await chats.load("telegram", CHAT)).pending == ("/find-place https://x",)
    gate.set()
    await settle(runs, gateway)

    stored = await sessions.read((await chats.load("telegram", CHAT)).conversation_id)
    prompts = [e.message.content for e in stored.events() if e.type == "user/message"]
    assert prompts[0] == "hold on"
    assert prompts[1].startswith('/find-place https://x\n\n<skill name="find-place">')


async def test_start_turn_expands_too(tmp_path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "find-place")
    _, gateway, runs, _, sessions = build(
        tmp_path, ScriptedClient(completed("ok")), skills=skills_at(root)
    )
    session = await sessions.create()

    run = await gateway.start_turn(session, "/find-place go", channel="telegram")
    await settle(runs, gateway)

    (content,) = [e.message.content for e in run.session.events() if e.type == "user/message"]
    assert content.startswith("/find-place go\n\n<skill name=")
