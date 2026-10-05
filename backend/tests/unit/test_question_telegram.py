"""`ask_user` on Telegram: one button per option, and a tap that answers and edits the message."""

from __future__ import annotations

import json

from harness.bots import ASSISTANT_ID
from harness.channels.telegram.asking import ASK_BY_LINK
from harness.channels.telegram.channel import STALE_TAP
from harness.session.models import ToolResultEvent, TurnEnd
from harness.tools.native.question import QUESTION
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.gateway_helpers import CHAT, build, msg, settle
from tests.unit.helpers import client_tools, no_skills
from tests.unit.telegram_fakes import choice_update

ASKED = json.dumps({"question": "Which shop?", "options": ["Lazada", "Shopee"]})


def _asking(tmp_path, *, call_id: str = "c1"):
    tools = client_tools()
    model = SteppedClient(calls_tool(QUESTION, ASKED, id=call_id), completed("searching Shopee"))
    return build(tmp_path, model, *tools.definitions(), skills=no_skills(), client_tools=tools)


async def _log(sessions, chats):
    state = await chats.load("telegram", CHAT)
    assert state is not None
    return (await sessions.read(state.conversation_id)).events()


async def test_a_question_is_asked_with_one_button_per_option(tmp_path) -> None:
    bot, gateway, runs, chats, sessions = _asking(tmp_path)

    await gateway.receive(msg("find me a Pokémon ETB"))
    await settle(runs, gateway)

    ((chat_id, text, markup),) = bot.linked
    assert (chat_id, text) == (CHAT, "Which shop?")
    rows = [[(b.text, b.callback_data) for b in row] for row in markup.inline_keyboard]
    assert rows == [[("Lazada", "qa:c1:0")], [("Shopee", "qa:c1:1")]]
    assert (await _log(sessions, chats))[-1] == TurnEnd(turn=0, reason="pending")


async def test_a_tap_answers_with_its_label_and_edits_the_message(tmp_path) -> None:
    bot, gateway, runs, chats, sessions = _asking(tmp_path)
    channel = gateway._channels["telegram"].channel
    await gateway.receive(msg("find me a Pokémon ETB"))
    await settle(runs, gateway)
    ((_, text, markup),) = bot.linked

    tap = choice_update(CHAT, "qa:c1:1", text, markup)
    await channel._on_choice(tap, None)
    await settle(runs, gateway)

    assert tap.callback_query.answered is True
    assert tap.callback_query.edits == [("Which shop?\n\n✅ Shopee", None)]
    result = next(e for e in await _log(sessions, chats) if isinstance(e, ToolResultEvent))
    assert result.message.content[0].text == '{"choice":"Shopee"}'
    assert bot.sent[-1] == (CHAT, "searching Shopee")


async def test_a_stale_tap_is_told_so(tmp_path) -> None:
    bot, gateway, runs, chats, sessions = _asking(tmp_path)
    channel = gateway._channels["telegram"].channel
    await gateway.receive(msg("find me a Pokémon ETB"))
    await settle(runs, gateway)
    ((_, text, markup),) = bot.linked
    await channel._on_choice(choice_update(CHAT, "qa:c1:0", text, markup), None)
    await settle(runs, gateway)

    late = choice_update(CHAT, "qa:c1:1", text, markup)
    await channel._on_choice(late, None)
    await settle(runs, gateway)

    assert late.callback_query.answered is True
    assert late.callback_query.edits == [(f"Which shop?\n\n{STALE_TAP}", None)]


async def test_a_call_id_too_long_for_a_button_is_asked_by_link(tmp_path) -> None:
    long_id = "call_" + "x" * 60
    bot, gateway, runs, chats, sessions = _asking(tmp_path, call_id=long_id)

    await gateway.receive(msg("find me a Pokémon ETB"))
    await settle(runs, gateway)

    ((_, text, markup),) = bot.linked
    assert text == ASK_BY_LINK
    assert markup.inline_keyboard[0][0].url.endswith(f"/answer/{ASSISTANT_ID}/{long_id}")
