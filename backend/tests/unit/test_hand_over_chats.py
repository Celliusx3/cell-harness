"""`hand_over` in a chat app: no buttons of its own, so the person is sent the answer page."""

from __future__ import annotations

import json

import discord

from harness.bots import ASSISTANT_ID
from harness.channels.discord.channel import ASK_BY_LINK as DISCORD_ASK
from harness.channels.discord.channel import OPEN_LABEL
from harness.channels.gateway import ChannelGateway
from harness.channels.repositories.jsonl import JsonlChatRepository
from harness.channels.telegram.asking import ASK_BY_LINK
from harness.session.models import TurnEnd
from harness.tools.native.hand_over import HAND_OVER
from tests.unit import discord_fakes
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import client_tools, durable_service, no_skills, run_service

ASKED = json.dumps({"step": "Type the two-factor code from your phone on GitHub."})
PAGE = f"http://t/answer/{ASSISTANT_ID}/call_h1"


def _hands_over_then_carries_on() -> SteppedClient:
    return SteppedClient(calls_tool(HAND_OVER, ASKED, id="call_h1"), completed("carrying on"))


async def test_telegram_is_sent_the_answer_page_and_the_turn_waits(tmp_path) -> None:
    tools = client_tools()
    bot, gateway, runs, chats, sessions = build(
        tmp_path,
        _hands_over_then_carries_on(),
        *tools.definitions(),
        skills=no_skills(),
        client_tools=tools,
    )

    await gateway.receive(msg("push my branch"))
    await settle(runs, gateway)

    ((chat_id, text, markup),) = bot.linked
    assert (chat_id, text) == (CHAT, ASK_BY_LINK)
    assert markup.inline_keyboard[0][0].url == PAGE
    state = await chats.load("telegram", CHAT)
    assert state is not None
    events = (await sessions.read(state.conversation_id)).events()
    assert events[-1] == TurnEnd(turn=0, reason="pending")


async def test_discord_is_sent_the_open_button_to_the_answer_page(tmp_path) -> None:
    sessions = durable_service(tmp_path / "sessions")
    runs = run_service(sessions, _hands_over_then_carries_on(), *client_tools().definitions())
    gateway = ChannelGateway(
        JsonlChatRepository(tmp_path / "chats"), runs, sessions, no_skills(), public_url="http://t"
    )
    channel, client = discord_fakes.discord_channel(gateway)
    gateway.register(channel)
    chat = client.chat("42")

    await channel.on_message(discord_fakes.message("42", "push my branch"))
    await discord_fakes.settle(gateway, runs)

    ((text, view),) = chat.linked
    (button,) = view.children
    assert text == DISCORD_ASK
    assert isinstance(button, discord.ui.Button)
    assert (button.label, button.url) == (OPEN_LABEL, PAGE)
