"""The channel service: queueing, draining, and the delivery cursor.

The rules here are the ones a phone forces and a browser does not — you cannot
grey out someone's keyboard, so a message during a turn must be held rather than
refused, and a restart must not re-text a reply that already arrived.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from harness.agent.loop import LoopAgent
from harness.channels.commands import Command, apply
from harness.channels.gateway import ChannelGateway, app_url
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.transport import InboundMessage
from harness.runs.store import RunStore
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.definition import Ok, ToolDefinition, ToolOutcome, ToolUi
from harness.tools.progress import ToolProgressReporter
from tests.unit.fakes import (
    EchoArgs,
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    hanging_tool,
)
from tests.unit.helpers import pipeline_for
from tests.unit.telegram_fakes import telegram_channel

CHAT = "4242"


def build(tmp_path: Path, model, *tools, public_url: str = "http://t"):
    ids = iter(f"c{n}" for n in range(100))
    sessions = SessionService(
        JsonlSessionRepository(tmp_path / "sessions"),
        now=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        new_id=lambda: next(ids),
    )
    agent = LoopAgent(
        name="t",
        model="m",
        client=model,
        tools=pipeline_for(*tools) if tools else None,
        checkpoint=sessions.flush,
    )
    runs = RunStore(sessions, agent)
    chats = JsonlChatRepository(tmp_path / "chats")
    gateway = ChannelGateway(chats, runs, sessions, public_url=public_url)
    channel, bot = telegram_channel(gateway)
    gateway.register(channel)
    return bot, gateway, runs, chats, sessions


def msg(text: str, _seq: int = 0) -> InboundMessage:
    """One inbound message. `_seq` is ignored — kept so the call sites still read
    as a sequence of arrivals now that messages carry no id."""
    return InboundMessage(channel="telegram", chat_id=CHAT, text=text)


async def settle(runs: RunStore, gateway: ChannelGateway, chat_id: int = CHAT) -> None:
    """Let the turn, its delivery, and any drained follow-on finish."""
    for _ in range(200):
        task = gateway._following.get(("telegram", chat_id))
        busy = task is not None and not task.done()
        if not busy and not any(runs._runs.values()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("channel never went idle")


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


def app_tool() -> ToolDefinition[EchoArgs]:
    """A tool whose result is bound to an MCP App."""

    async def execute(args: EchoArgs, progress: ToolProgressReporter) -> ToolOutcome:
        return Ok(args.value, ui=ToolUi(server="srv", resource_uri="ui://srv/app.html"))

    return ToolDefinition.from_model(
        name="srv__show", description="Show.", args_model=EchoArgs, execute=execute
    )


async def test_a_result_with_an_app_is_delivered_as_a_link_before_the_reply(tmp_path) -> None:
    """A chat cannot render the app, so it gets the page that does — named for
    the tool, and before the prose that follows the tool."""
    bot, gateway, runs, _, _ = build(
        tmp_path,
        SteppedClient(calls_tool("srv__show", '{"value": "42"}'), completed("there it is")),
        app_tool(),
    )

    await gateway.receive(msg("show me", 1))
    await settle(runs, gateway)

    ((chat_id, text, markup),) = bot.linked
    assert (chat_id, text) == (CHAT, "srv__show")
    assert markup.inline_keyboard[0][0].url == app_url("http://t", "c0", "c1")
    assert bot.sent == [(CHAT, "there it is")]


async def test_a_link_the_platform_refuses_does_not_cost_the_reply(tmp_path) -> None:
    """Telegram rejects a `localhost` button. The reply after it must still
    arrive, and the cursor must move past the event — or the next turn replays
    it into the same refusal, forever."""
    bot, gateway, runs, chats, _ = build(
        tmp_path,
        SteppedClient(calls_tool("srv__show", '{"value": "42"}'), completed("there it is")),
        app_tool(),
    )
    bot.refuse_links = RuntimeError("Bad Request: inline keyboard button URL is invalid")

    await gateway.receive(msg("show me", 1))
    await settle(runs, gateway)

    assert bot.linked == []
    assert bot.sent == [(CHAT, "there it is")]
    state = await chats.load("telegram", CHAT)
    assert state is not None and state.delivered_through > 0


async def test_no_public_url_means_no_link(tmp_path) -> None:
    bot, gateway, runs, _, _ = build(
        tmp_path,
        SteppedClient(calls_tool("srv__show", '{"value": "42"}'), completed("there it is")),
        app_tool(),
        public_url="",
    )

    await gateway.receive(msg("show me", 1))
    await settle(runs, gateway)

    assert bot.linked == []
    assert bot.sent == [(CHAT, "there it is")]


async def test_a_result_without_an_app_sends_no_link(tmp_path) -> None:
    bot, gateway, runs, _, _ = build(
        tmp_path,
        SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("it is 42")),
        echo_tool(),
    )

    await gateway.receive(msg("what is it?", 1))
    await settle(runs, gateway)

    assert bot.linked == []


def test_the_app_page_url_escapes_its_ids() -> None:
    assert app_url("http://t", "c/1", "call:2") == "http://t/apps/c%2F1/call%3A2"


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
    assert bot.sent == [(CHAT, "answered"), (CHAT, "answered")]
