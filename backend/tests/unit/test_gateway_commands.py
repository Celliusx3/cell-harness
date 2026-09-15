"""`/new` and `/stop` through the gateway, and what a chat is left with."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.channels.commands import Command, apply, skills_reply, unknown_skill
from harness.skills import Skill
from tests.unit.fakes import (
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    hanging_tool,
)
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import no_skills, skills_at
from tests.unit.test_skill_tool import write_skill

# ── commands ──────────────────────────────────────────────────────────────────


async def test_new_points_the_chat_at_a_fresh_conversation(tmp_path) -> None:
    bot, gateway, runs, chats, _ = build(
        tmp_path, ScriptedClient(completed("hi")), skills=no_skills()
    )
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
        tmp_path,
        SteppedClient(calls_tool("hang", '{"value": "x"}')),
        hanging_tool(),
        skills=no_skills(),
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
    bot, gateway, runs, _, _ = build(tmp_path, ScriptedClient(completed("hi")), skills=no_skills())

    assert await apply(gateway, "telegram", CHAT, Command.STOP) == "Nothing is running."


def test_an_unknown_skill_reply_says_what_can_be_typed() -> None:
    """`/summarise` meant something; the reply is the list it could have been."""
    reply = unknown_skill("summarise", named("find-place", "weekly-report"))

    assert reply == (
        "No skill named 'summarise'. Skills: /find-place, /weekly-report. Commands: /new, /stop."
    )
    assert unknown_skill("x", []) == "No skill named 'x'. Skills: none. Commands: /new, /stop."


def named(*names: str) -> list[Skill]:
    return [
        Skill(
            name=name,
            description="d",
            dir=Path("/x") / name,
            root=Path("/x"),
            model_invocable=True,
            user_invocable=True,
        )
        for name in names
    ]


async def test_stopping_before_the_first_checkpoint_does_not_break_the_chat(tmp_path) -> None:
    """A message, then `/stop` before the loop's first checkpoint.

    The run is cancelled having appended nothing, so lazy materialization leaves
    no file — while the chat already points at the id. Before this was handled
    the chat was **permanently** broken: every later message resumed a
    conversation that would never exist.
    """
    bot, gateway, runs, chats, _ = build(
        tmp_path, ScriptedClient(completed("hi")), skills=no_skills()
    )
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
    bot, gateway, runs, chats, _ = build(
        tmp_path, ScriptedClient(completed("answered")), skills=no_skills()
    )
    await gateway.receive(msg("opening"))
    await settle(runs, gateway)
    state = await chats.load("telegram", CHAT)
    await chats.save(state.model_copy(update={"pending": ("follow up",)}))

    await gateway._drain("telegram", CHAT)
    await settle(runs, gateway)

    # Two replies: the opening turn's, and the drained one's.


async def test_skills_lists_what_can_be_typed(tmp_path) -> None:
    """The phone has no `/skills` page; this is its list."""
    root = tmp_path / "skills"
    write_skill(root, "find-place", "Where a reel was filmed.")
    write_skill(root, "internal", "Not for typing.", user_invocable="false")
    bot, gateway, runs, _, _ = build(
        tmp_path, ScriptedClient(completed("hi")), skills=skills_at(root)
    )

    reply = await apply(gateway, "telegram", CHAT, Command.SKILLS)

    assert (
        reply
        == "Skills you can type:\n/find-place — Where a reel was filmed.\n\nCommands: /new, /stop."
    )
    assert bot.sent == []


def test_no_skills_says_so() -> None:
    assert skills_reply([]) == "No skills installed. Commands: /new, /stop."
