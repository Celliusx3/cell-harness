"""A message sent while the bot works reaches it at its next step, in the same turn."""

from __future__ import annotations

import asyncio

from tests.unit.fakes import SteppedClient, calls_tool, completed, gated_tool
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import no_skills


async def test_a_message_during_a_turn_is_read_at_its_next_step(tmp_path) -> None:
    release = asyncio.Event()
    bot, gateway, runs, chats, sessions = await build(
        tmp_path,
        SteppedClient(calls_tool("gate", '{"value": "x"}'), completed("adjusted")),
        gated_tool(release),
        skills=no_skills(),
    )
    await gateway.receive(msg("plan my trip", 1))
    conversation = (await chats.load("telegram", CHAT)).conversation_id
    for _ in range(200):
        if runs.active(conversation) is not None:
            break
        await asyncio.sleep(0.01)

    await gateway.receive(msg("actually, only two days", 2))
    release.set()
    await settle(runs, gateway)

    stored = await sessions.read(conversation)
    said = [(e.turn, e.message.content) for e in stored.events() if e.type == "user/message"]
    assert said == [(0, "plan my trip"), (0, "actually, only two days")]
    assert [e.type for e in stored.events()].count("turn/start") == 1
    assert (await chats.load("telegram", CHAT)).pending == ()
    assert bot.sent == [(CHAT, "adjusted")]
