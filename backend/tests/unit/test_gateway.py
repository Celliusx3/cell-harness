"""The channel service: queueing, draining, and the delivery cursor.

The rules here are the ones a phone forces and a browser does not — you cannot
grey out someone's keyboard, so a message during a turn must be held rather than
refused, and a restart must not re-text a reply that already arrived.
"""

from __future__ import annotations

import asyncio

from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    hanging_tool,
)
from tests.unit.gateway_helpers import CHAT, build, msg, settle

# ── the happy path ────────────────────────────────────────────────────────────


async def test_a_message_becomes_a_turn_and_a_reply(tmp_path) -> None:
    bot, gateway, runs, _, _ = build(tmp_path, ScriptedClient(completed("hello there")))

    await gateway.receive(msg("hi", 1))
    await settle(runs, gateway)

    assert bot.sent == [(CHAT, "hello there")]


async def test_first_contact_creates_a_conversation(tmp_path) -> None:
    bot, gateway, runs, chats, sessions = build(tmp_path, ScriptedClient(completed("hi")))

    await gateway.receive(msg("hello", 1))
    await settle(runs, gateway)

    state = await chats.load("telegram", CHAT)
    assert state is not None
    assert [h.id for h in await sessions.list()] == [state.conversation_id]


async def test_a_second_message_continues_the_same_conversation(tmp_path) -> None:
    bot, gateway, runs, chats, sessions = build(tmp_path, ScriptedClient(completed("ok")))

    await gateway.receive(msg("first", 1))
    await settle(runs, gateway)
    first = (await chats.load("telegram", CHAT)).conversation_id
    await gateway.receive(msg("second", 2))
    await settle(runs, gateway)

    assert (await chats.load("telegram", CHAT)).conversation_id == first
    stored = await sessions.read(first)
    prompts = [e.message.content for e in stored.events() if e.type == "user/message"]
    assert prompts == ["first", "second"]


async def test_a_tool_step_sends_no_empty_message(tmp_path) -> None:
    """A tool-calling step records an assistant message with no content."""
    bot, gateway, runs, _, _ = build(
        tmp_path,
        SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("it is 42")),
        echo_tool(),
    )

    await gateway.receive(msg("what is it?", 1))
    await settle(runs, gateway)

    assert bot.sent == [(CHAT, "it is 42")]


# ── busy: queue, never refuse ─────────────────────────────────────────────────


async def test_a_message_during_a_turn_is_queued(tmp_path) -> None:
    bot, gateway, runs, chats, _ = build(
        tmp_path, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool()
    )
    await gateway.receive(msg("slow one", 1))
    conversation = (await chats.load("telegram", CHAT)).conversation_id
    for _ in range(200):
        if runs.active(conversation) is not None:
            break
        await asyncio.sleep(0.01)

    await gateway.receive(msg("and another", 2))

    state = await chats.load("telegram", CHAT)
    assert state.pending == ("and another",)
    await gateway.stop("telegram", CHAT)
    await gateway.aclose()


async def test_the_queue_drains_as_one_turn(tmp_path) -> None:
    """Three lines typed in a burst were one thought."""
    bot, gateway, runs, chats, sessions = build(tmp_path, ScriptedClient(completed("answered")))
    await gateway.receive(msg("opening", 1))
    await settle(runs, gateway)
    state = await chats.load("telegram", CHAT)
    await chats.save(state.model_copy(update={"pending": ("one", "two", "three")}))

    await gateway._drain("telegram", CHAT)
    await settle(runs, gateway)

    stored = await sessions.read(state.conversation_id)
    prompts = [e.message.content for e in stored.events() if e.type == "user/message"]
    assert prompts == ["opening", "one\ntwo\nthree"]
    assert (await chats.load("telegram", CHAT)).pending == ()


# ── delivery cursor ───────────────────────────────────────────────────────────


async def test_delivery_advances_the_cursor(tmp_path) -> None:
    bot, gateway, runs, chats, sessions = build(tmp_path, ScriptedClient(completed("hi")))

    await gateway.receive(msg("hello", 1))
    await settle(runs, gateway)

    state = await chats.load("telegram", CHAT)
    stored = await sessions.read(state.conversation_id)
    assert 0 < state.delivered_through <= len(stored.events())


async def test_a_restart_does_not_resend(tmp_path) -> None:
    """The cursor is what stops someone getting yesterday's reply twice."""
    bot, gateway, runs, chats, sessions = build(tmp_path, ScriptedClient(completed("hi")))
    await gateway.receive(msg("hello", 1))
    await settle(runs, gateway)
    delivered = len(bot.sent)

    # A fresh service over the same directories — nothing shared in memory.
    reopened_bot, reopened, reopened_runs, _, _ = build(
        tmp_path, ScriptedClient(completed("second"))
    )
    await reopened.receive(msg("again", 2))
    await settle(reopened_runs, reopened)

    assert delivered == 1
    # Only the *new* reply, never a repeat of the first.
    assert reopened_bot.sent == [(CHAT, "second")]
