"""A client tool from a chat: the ask goes out as the platform's own prompt
where it has one, the turn ends pending, and the answer that comes back — or
the message typed instead — opens the turn that settles it."""

from __future__ import annotations

import discord

from harness.agent.loop import SKIPPED
from harness.channels.client import ChatAnswers
from harness.channels.discord.channel import ASK_BY_LINK as DISCORD_ASK
from harness.channels.discord.channel import NO_ANSWER_PAGE as DISCORD_NO_PAGE
from harness.channels.gateway import ChannelGateway
from harness.channels.replies import answer_url
from harness.channels.telegram.asking import ASK, ASK_BY_LINK, NO_ANSWER_PAGE, SHARE_LABEL
from harness.session.models import ToolResultEvent, TurnEnd
from harness.tools.client import PendingCall, Refused
from harness.tools.native.location import LOCATION
from tests.unit.discord_fakes import discord_channel
from tests.unit.fakes import ScriptedClient, SteppedClient, calls_tool, completed
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import client_tools, no_skills
from tests.unit.telegram_fakes import location_update, telegram_channel


def _asks_then_answers(answer: str = "a café 200 m away") -> SteppedClient:
    return SteppedClient(calls_tool(LOCATION, "{}"), completed(answer))


async def _log(sessions, chats, chat_id: str):
    state = await chats.load("telegram", chat_id)
    assert state is not None
    return (await sessions.read(state.conversation_id)).events()


async def test_telegram_is_asked_with_its_own_share_button_and_the_turn_ends(tmp_path) -> None:
    tools = client_tools()
    bot, gateway, runs, chats, sessions = build(
        tmp_path, _asks_then_answers(), *tools.definitions(), skills=no_skills(), client_tools=tools
    )

    await gateway.receive(msg("what's near me"))
    await settle(runs, gateway)

    ((chat_id, text, markup),) = bot.linked
    assert (chat_id, text) == (CHAT, ASK[LOCATION])
    button = markup.keyboard[0][0]
    assert (button.text, button.request_location) == (SHARE_LABEL, True)
    assert markup.one_time_keyboard is True
    events = await _log(sessions, chats, CHAT)
    assert events[-1] == TurnEnd(turn=0, reason="pending")
    assert bot.sent == []  # nothing to say until the person answers
    assert not any(runs._runs.values())  # and nothing is running meanwhile


async def test_a_pin_from_telegram_opens_the_turn_that_answers(tmp_path) -> None:
    tools = client_tools()
    bot, gateway, runs, chats, sessions = build(
        tmp_path, _asks_then_answers(), *tools.definitions(), skills=no_skills(), client_tools=tools
    )
    channel = gateway._channels["telegram"].channel
    await gateway.receive(msg("what's near me"))
    await settle(runs, gateway)

    await channel._on_location(location_update(CHAT, 3.139, 101.6869), None)  # type: ignore[arg-type]
    await settle(runs, gateway)

    events = await _log(sessions, chats, CHAT)
    (result,) = [e for e in events if isinstance(e, ToolResultEvent)]
    assert result.message.content[0].text == (  # type: ignore[union-attr]
        '{"latitude":3.139,"longitude":101.6869,"accuracy_m":0.0}'
    )
    assert [e.reason for e in events if isinstance(e, TurnEnd)] == ["pending", "completed"]
    assert bot.sent == [(CHAT, "a café 200 m away")]


async def test_typing_instead_skips_the_ask_and_answers_the_message(tmp_path) -> None:
    tools = client_tools()
    bot, gateway, runs, chats, sessions = build(
        tmp_path,
        _asks_then_answers("9pm in Tokyo"),
        *tools.definitions(),
        skills=no_skills(),
        client_tools=tools,
    )
    await gateway.receive(msg("what's near me"))
    await settle(runs, gateway)

    await gateway.receive(msg("never mind, time in Tokyo?"))
    await settle(runs, gateway)

    events = await _log(sessions, chats, CHAT)
    (result,) = [e for e in events if isinstance(e, ToolResultEvent)]
    assert result.error == SKIPPED
    types = [e.type for e in events]
    assert types[types.index("tool/result") + 1 :][:2] == ["turn/start", "user/message"]
    assert bot.sent == [(CHAT, "9pm in Tokyo")]


async def test_an_unprompted_pin_is_a_message(tmp_path) -> None:
    """Nothing asked, so the pin is what the person said — sent as text."""
    bot, gateway, runs, chats, sessions = build(
        tmp_path, ScriptedClient(completed("noted")), skills=no_skills()
    )
    channel = gateway._channels["telegram"].channel

    await channel._on_location(location_update(CHAT, 1.5, 2.5), None)  # type: ignore[arg-type]
    await settle(runs, gateway)

    events = await _log(sessions, chats, CHAT)
    user = next(e for e in events if e.type == "user/message")
    assert user.message.content == "(shared location: 1.5, 2.5)"  # type: ignore[union-attr]
    assert bot.sent == [(CHAT, "noted")]


async def test_a_client_tool_telegram_has_no_button_for_is_asked_by_link() -> None:
    """The spine's promise: a new declaration reaches a chat without the
    channel learning its name — as the page, the way Discord always is."""
    channel, bot = telegram_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    request = PendingCall("get_battery", "c1", "{}")

    await channel.ask_client("42", request, answer_url("http://t", "c0", "c1"))
    await channel.ask_client("42", request, answer_url("", "c0", "c1"))

    ((chat_id, text, markup),) = bot.linked
    assert (chat_id, text) == ("42", ASK_BY_LINK)
    assert markup.inline_keyboard[0][0].url == "http://t/answer/c0/c1"
    assert bot.sent == [("42", f"{ASK_BY_LINK} {NO_ANSWER_PAGE}")]


async def test_discord_is_sent_the_page_that_asks_the_browser() -> None:
    channel, client = discord_channel(
        ChannelGateway(None, None, None, no_skills(), public_url="http://t")
    )
    chat = client.chat("42")

    await channel.ask_client(
        "42", PendingCall(LOCATION, "c1", "{}"), answer_url("http://t", "c0", "c1")
    )

    ((text, view),) = chat.linked
    (button,) = view.children
    assert text == DISCORD_ASK
    assert isinstance(button, discord.ui.Button)
    assert button.url == "http://t/answer/c0/c1"


async def test_discord_without_a_public_url_is_told_why() -> None:
    channel, client = discord_channel(ChannelGateway(None, None, None, no_skills(), public_url=""))
    chat = client.chat("42")

    await channel.ask_client("42", PendingCall(LOCATION, "c1", "{}"), answer_url("", "c0", "c1"))

    assert chat.linked == []
    assert chat.sent == [f"{DISCORD_ASK} {DISCORD_NO_PAGE}"]


def test_the_answer_page_is_addressed_like_an_app_page() -> None:
    assert answer_url("http://h", "c 0", "call/1") == "http://h/answer/c%200/call%2F1"
    assert answer_url("", "c0", "c1") == ""


async def test_a_chat_with_nothing_pending_refuses_an_answer(tmp_path) -> None:
    """False for a chat with no conversation, one whose turn is running, one
    whose last turn is not pending, and one answering the wrong tool."""
    tools = client_tools()
    bot, gateway, runs, chats, sessions = build(
        tmp_path, SteppedClient(calls_tool("echo", "{}"), completed("ok")), skills=no_skills()
    )
    channel = gateway._channels["telegram"].channel
    resolver = ChatAnswers(chats, sessions, gateway, tools)
    declined = {"kind": "declined"}

    assert await resolver.answer(channel, CHAT, LOCATION, declined) is False
    await gateway.receive(msg("hi"))
    assert await resolver.answer(channel, CHAT, LOCATION, declined) is False
    await settle(runs, gateway)
    assert await resolver.answer(channel, CHAT, LOCATION, declined) is False


async def test_a_chat_answer_that_does_not_fit_is_refused(tmp_path) -> None:
    tools = client_tools()
    bot, gateway, runs, chats, sessions = build(
        tmp_path, _asks_then_answers(), *tools.definitions(), skills=no_skills(), client_tools=tools
    )
    channel = gateway._channels["telegram"].channel
    resolver = ChatAnswers(chats, sessions, gateway, tools)
    await gateway.receive(msg("what's near me"))
    await settle(runs, gateway)

    assert await resolver.answer(channel, CHAT, LOCATION, {"kind": "shared", "data": {}}) is False
    assert await resolver.answer(channel, CHAT, "get_battery", {"kind": "declined"}) is False
    assert await resolver.answer(channel, CHAT, LOCATION, {"kind": "declined"}) is True
    await settle(runs, gateway)
    events = await _log(sessions, chats, CHAT)
    assert [e.reason for e in events if isinstance(e, TurnEnd)] == ["pending", "completed"]


async def test_an_answer_from_the_page_is_still_delivered_to_the_chat(tmp_path) -> None:
    """Discord's ask is a link; the person answers on the browser page, which
    knows nothing about Discord. The resumed turn must still be followed by
    the chat the conversation belongs to, or the reply lands only in the log
    — which is exactly what happened the first time."""
    tools = client_tools()
    bot, gateway, runs, chats, sessions = build(
        tmp_path, _asks_then_answers(), *tools.definitions(), skills=no_skills(), client_tools=tools
    )
    await gateway.receive(msg("what's near me"))
    await settle(runs, gateway)
    state = await chats.load("telegram", CHAT)
    assert state is not None

    # What the route does: no chat in hand, only the conversation.
    session = await sessions.resume(state.conversation_id)
    accepted = tools.accept_call(session, "c1", {"kind": "declined"})
    assert not isinstance(accepted, Refused)
    await gateway.resume(session, accepted.call_id, accepted.outcome)
    await settle(runs, gateway)

    assert bot.sent == [(CHAT, "a café 200 m away")]
    refreshed = await chats.load("telegram", CHAT)
    assert refreshed is not None and refreshed.delivered_through > state.delivered_through


async def test_the_ask_is_sent_once_even_though_the_answer_opens_a_new_turn(tmp_path) -> None:
    """The follow of the resumed turn subscribes from the chat's cursor. If the
    ask did not advance it, the `tool/call` is replayed and the person is
    asked twice — which is what Discord showed."""
    tools = client_tools()
    bot, gateway, runs, chats, sessions = build(
        tmp_path, _asks_then_answers(), *tools.definitions(), skills=no_skills(), client_tools=tools
    )
    channel = gateway._channels["telegram"].channel
    await gateway.receive(msg("what's near me"))
    await settle(runs, gateway)
    assert len(bot.linked) == 1

    await channel._on_location(location_update(CHAT, 3.139, 101.6869), None)  # type: ignore[arg-type]
    await settle(runs, gateway)

    assert len(bot.linked) == 1  # asked once
    assert bot.sent == [(CHAT, "a café 200 m away")]
