"""A turn no chat app started still reaches every chat app linked to its conversation."""

from __future__ import annotations

from harness.bots import ASSISTANT_ID
from harness.runs.service.bot_messages import BotMessages
from harness.session.models import BotMessage
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.gateway_helpers import CHAT, build, settle
from tests.unit.helpers import no_bots, no_skills

ANSWERED = BotMessage(from_bot_id="r", from_name="Researcher", text="Yes.", hop=1, intent="result")


async def test_a_turn_a_bot_s_answer_opens_is_heard_on_the_linked_chat(tmp_path) -> None:
    bot, gateway, runs, _, sessions = await build(
        tmp_path, ScriptedClient(completed("Researcher says yes.")), skills=no_skills()
    )
    session = await sessions.create(ASSISTANT_ID)

    await gateway.follow(runs.hear(session, ANSWERED))
    await settle(runs, gateway)

    assert bot.sent == [(CHAT, "Researcher says yes.")]


async def test_a_bot_message_s_turn_is_followed_by_the_chats_linked_to_it(tmp_path) -> None:
    bot, gateway, runs, _, sessions = await build(
        tmp_path, ScriptedClient(completed("Researcher says yes.")), skills=no_skills()
    )
    bots = no_bots(sessions)
    await bots.active_bots()
    messages = BotMessages(bots, runs, follow=gateway.follow)

    await messages.deliver(ASSISTANT_ID, ANSWERED)
    await settle(runs, gateway)

    assert bot.sent == [(CHAT, "Researcher says yes.")]
