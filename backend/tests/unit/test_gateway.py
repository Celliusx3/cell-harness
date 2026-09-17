"""The channel service: queueing, draining, and the delivery cursor.

The rules here are the ones a phone forces and a browser does not — you cannot
grey out someone's keyboard, so a message during a turn must be held rather than
refused, and a restart must not re-text a reply that already arrived.
"""

from __future__ import annotations

import asyncio
import contextlib

from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    gated_tool,
    hanging_tool,
)
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import no_skills

# ── the happy path ────────────────────────────────────────────────────────────


async def test_a_message_becomes_a_turn_and_a_reply(tmp_path) -> None:
    bot, gateway, runs, _, _ = build(
        tmp_path, ScriptedClient(completed("hello there")), skills=no_skills()
    )

    await gateway.receive(msg("hi", 1))
    await settle(runs, gateway)

    assert bot.sent == [(CHAT, "hello there")]


async def test_first_contact_creates_a_conversation(tmp_path) -> None:
    bot, gateway, runs, chats, sessions = build(
        tmp_path, ScriptedClient(completed("hi")), skills=no_skills()
    )

    await gateway.receive(msg("hello", 1))
    await settle(runs, gateway)

    state = await chats.load("telegram", CHAT)
    assert state is not None
    assert [h.id for h in await sessions.list()] == [state.conversation_id]


async def test_a_second_message_continues_the_same_conversation(tmp_path) -> None:
    bot, gateway, runs, chats, sessions = build(
        tmp_path, ScriptedClient(completed("ok")), skills=no_skills()
    )

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
        skills=no_skills(),
    )

    await gateway.receive(msg("what is it?", 1))
    await settle(runs, gateway)

    assert bot.sent == [(CHAT, "it is 42")]


# ── busy: queue, never refuse ─────────────────────────────────────────────────


async def test_a_message_during_a_turn_is_queued(tmp_path) -> None:
    bot, gateway, runs, chats, _ = build(
        tmp_path,
        SteppedClient(calls_tool("hang", '{"value": "x"}')),
        hanging_tool(),
        skills=no_skills(),
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
    bot, gateway, runs, chats, sessions = build(
        tmp_path, ScriptedClient(completed("answered")), skills=no_skills()
    )
    await gateway.receive(msg("opening", 1))
    await settle(runs, gateway)
    state = await chats.load("telegram", CHAT)
    await chats.save(state.model_copy(update={"pending": ("one", "two", "three")}))

    await gateway._following._drain("telegram", CHAT)
    await settle(runs, gateway)

    stored = await sessions.read(state.conversation_id)
    prompts = [e.message.content for e in stored.events() if e.type == "user/message"]
    assert prompts == ["opening", "one\ntwo\nthree"]
    assert (await chats.load("telegram", CHAT)).pending == ()


# ── waiting for the drain ─────────────────────────────────────────────────────
#
# What a stream needs after the run it watched settles: "is another turn about
# to start on this conversation?" — answered once the follower has drained.


async def test_drained_returns_at_once_for_an_idle_chat(tmp_path) -> None:
    _, gateway, _, _, _ = build(tmp_path, ScriptedClient(completed("hi")), skills=no_skills())

    await asyncio.wait_for(gateway.drained("telegram", CHAT), timeout=1)


async def _queued_behind_a_gated_turn(tmp_path, first: asyncio.Event, second: asyncio.Event):
    """A turn parked in `gate`, with a message queued behind it whose own turn
    parks in `gate2` — so both "started" states can be observed, not raced."""
    bot, gateway, runs, chats, sessions = build(
        tmp_path,
        SteppedClient(
            calls_tool("gate", '{"value": "x"}'),
            completed("first done"),
            calls_tool("gate2", '{"value": "y"}', id="c2"),
            completed("second done"),
        ),
        gated_tool(first),
        gated_tool(second, name="gate2"),
        skills=no_skills(),
    )
    await gateway.receive(msg("slow one", 1))
    conversation = (await chats.load("telegram", CHAT)).conversation_id
    for _ in range(200):
        if runs.active(conversation) is not None:
            break
        await asyncio.sleep(0.01)
    await gateway.receive(msg("and another", 2))
    assert (await chats.load("telegram", CHAT)).pending == ("and another",)
    return bot, gateway, runs, chats, sessions, conversation


async def test_drained_waits_out_the_gap_between_turns(tmp_path, monkeypatch) -> None:
    """Asked after the watched turn settled — the only time a stream asks — it
    returns once the queued turn exists, and at once if one is already in flight.

    The drain is parked inside the session load so the gap is a state the test
    holds open, not one it hopes to catch.
    """
    first, second = asyncio.Event(), asyncio.Event()
    _, gateway, runs, chats, sessions, conversation = await _queued_behind_a_gated_turn(
        tmp_path, first, second
    )
    watched = runs.active(conversation)
    loading = asyncio.Event()
    real_resume = sessions.resume

    async def gated_resume(session_id: str):
        await loading.wait()
        return await real_resume(session_id)

    monkeypatch.setattr(sessions, "resume", gated_resume)
    first.set()
    async with watched.condition:
        await watched.condition.wait_for(lambda: watched.settled)

    waiting = asyncio.create_task(gateway.drained("telegram", CHAT))
    await asyncio.sleep(0.05)
    assert not waiting.done(), "returned with the drain still deciding"
    loading.set()
    await asyncio.wait_for(waiting, timeout=5)

    drained = runs.active(conversation)
    assert drained is not None and drained is not watched
    assert (await chats.load("telegram", CHAT)).pending == ()
    # With that turn in flight, asking again does not wait for *it* — or a
    # stream that asked a beat late would get the whole turn as one lump.
    await asyncio.wait_for(gateway.drained("telegram", CHAT), timeout=1)
    assert not drained.settled
    second.set()
    await settle(runs, gateway)


async def test_cancelling_a_drained_waiter_leaves_the_follower_alone(tmp_path) -> None:
    """A watcher owns nothing: a browser hanging up mid-wait must not lose the
    queued message by cancelling the task that was about to drain it."""
    first, second = asyncio.Event(), asyncio.Event()
    bot, gateway, runs, _, sessions, conversation = await _queued_behind_a_gated_turn(
        tmp_path, first, second
    )
    waiting = asyncio.create_task(gateway.drained("telegram", CHAT))
    await asyncio.sleep(0.01)
    waiting.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await waiting

    first.set()
    second.set()
    await settle(runs, gateway)

    stored = await sessions.read(conversation)
    prompts = [e.message.content for e in stored.events() if e.type == "user/message"]
    assert prompts == ["slow one", "and another"]
    assert bot.sent == [(CHAT, "first done"), (CHAT, "second done")]


# ── delivery cursor ───────────────────────────────────────────────────────────


async def test_delivery_advances_the_cursor(tmp_path) -> None:
    bot, gateway, runs, chats, sessions = build(
        tmp_path, ScriptedClient(completed("hi")), skills=no_skills()
    )

    await gateway.receive(msg("hello", 1))
    await settle(runs, gateway)

    state = await chats.load("telegram", CHAT)
    stored = await sessions.read(state.conversation_id)
    assert 0 < state.delivered_through <= len(stored.events())


async def test_a_restart_does_not_resend(tmp_path) -> None:
    """The cursor is what stops someone getting yesterday's reply twice."""
    bot, gateway, runs, chats, sessions = build(
        tmp_path, ScriptedClient(completed("hi")), skills=no_skills()
    )
    await gateway.receive(msg("hello", 1))
    await settle(runs, gateway)
    delivered = len(bot.sent)

    # A fresh service over the same directories — nothing shared in memory.
    reopened_bot, reopened, reopened_runs, _, _ = build(
        tmp_path, ScriptedClient(completed("second")), skills=no_skills()
    )
    await reopened.receive(msg("again", 2))
    await settle(reopened_runs, reopened)

    assert delivered == 1
    # Only the *new* reply, never a repeat of the first.
    assert reopened_bot.sent == [(CHAT, "second")]
