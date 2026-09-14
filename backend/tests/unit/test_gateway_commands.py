"""`/new` and `/stop` through the gateway, and what a chat is left with."""

from __future__ import annotations

import asyncio

from harness.channels.commands import Command, apply
from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    hanging_tool,
)
from tests.unit.gateway_helpers import CHAT, build, msg, settle

# ── commands ──────────────────────────────────────────────────────────────────


async def test_new_points_the_chat_at_a_fresh_conversation(tmp_path) -> None:
    bot, gateway, runs, chats, _ = build(tmp_path, ScriptedClient(completed("hi")))
    await gateway.receive(msg("hello", 1))
    await settle(runs, gateway)
    before = (await chats.load("telegram", CHAT)).conversation_id

    reply = await apply(gateway, "telegram", CHAT, Command.NEW)

    state = await chats.load("telegram", CHAT)
    # Cleared, not replaced — the next message creates one, so `/new` three times
    # in a row leaves no empty sessions behind.
    assert state.conversation_id == ""
    assert state.delivered_through == 0
    assert "New conversation" in reply
    assert before != ""


async def test_stop_cancels_and_clears_the_queue(tmp_path) -> None:
    """ "Stop" means stop — answering the queue afterwards is the opposite."""
    bot, gateway, runs, chats, _ = build(
        tmp_path, SteppedClient(calls_tool("hang", '{"value": "x"}')), hanging_tool()
    )
    await gateway.receive(msg("slow", 1))
    conversation = (await chats.load("telegram", CHAT)).conversation_id
    for _ in range(200):
        if runs.active(conversation) is not None:
            break
        await asyncio.sleep(0.01)
    await gateway.receive(msg("queued", 2))

    reply = await apply(gateway, "telegram", CHAT, Command.STOP)

    assert reply == "Stopped."
    assert (await chats.load("telegram", CHAT)).pending == ()
    await gateway.aclose()


async def test_stop_on_an_idle_chat_says_so(tmp_path) -> None:
    bot, gateway, runs, _, _ = build(tmp_path, ScriptedClient(completed("hi")))

    assert await apply(gateway, "telegram", CHAT, Command.STOP) == "Nothing is running."


async def test_an_unknown_command_is_answered_not_sent_to_the_model(tmp_path) -> None:
    """`/summarise` meant a command; passing it through would produce a confident
    answer to a question nobody asked."""
    bot, gateway, runs, _, sessions = build(tmp_path, ScriptedClient(completed("hi")))

    reply = await apply(gateway, "telegram", CHAT, Command.UNKNOWN)

    assert "Commands:" in reply
    assert bot.sent == []


async def test_stopping_before_the_first_checkpoint_does_not_break_the_chat(tmp_path) -> None:
    """A message, then `/stop` before the loop's first checkpoint.

    The run is cancelled having appended nothing, so lazy materialization leaves
    no file — while the chat already points at the id. Before this was handled
    the chat was **permanently** broken: every later message resumed a
    conversation that would never exist.
    """
    bot, gateway, runs, chats, _ = build(tmp_path, ScriptedClient(completed("hi")))
    await gateway.receive(msg("hello", 1))
    await gateway.stop("telegram", CHAT)

    await gateway.receive(msg("are you there?", 2))
    await settle(runs, gateway)

    assert bot.sent == [(CHAT, "hi")]


async def test_a_drained_turn_delivers_its_reply(tmp_path) -> None:
    """The drain spawns the next delivery from *inside* the current one.

    An earlier `_spawn_delivery` cancelled "the previous delivery for this chat"
    — which on this path is the calling task, so it cancelled itself. It
    survived only because nothing awaited between that line and the function
    returning; one added `await` in the unwind and the drained follow-up would
    have died half-delivered. This asserts the reply actually arrives.
    """
    bot, gateway, runs, chats, _ = build(tmp_path, ScriptedClient(completed("answered")))
    await gateway.receive(msg("opening"))
    await settle(runs, gateway)
    state = await chats.load("telegram", CHAT)
    await chats.save(state.model_copy(update={"pending": ("follow up",)}))

    await gateway._drain("telegram", CHAT)
    await settle(runs, gateway)

    # Two replies: the opening turn's, and the drained one's.
