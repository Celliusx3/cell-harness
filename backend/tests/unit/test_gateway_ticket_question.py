"""A chat app without an answer box is sent a ticket's question itself, before the bot's reply."""

from __future__ import annotations

from harness.bots import ASSISTANT_ID
from harness.session.models import TicketReport
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.gateway_helpers import CHAT, build, settle
from tests.unit.helpers import no_skills

ASKING = TicketReport(
    ticket_id="t1",
    title="Flights to Tokyo",
    state="blocked",
    text="Two airlines need a choice.",
    question="Direct flights only, or are 1-stop flights OK?",
)
READY = TicketReport(
    ticket_id="t1", title="Flights to Tokyo", state="ready", text="Three found.", question=None
)


async def test_a_reports_question_reaches_the_chat_before_the_bots_reply(tmp_path) -> None:
    bot, gateway, runs, _, sessions = await build(
        tmp_path,
        ScriptedClient(completed("The flights ticket waits for your answer.")),
        skills=no_skills(),
    )
    session = await sessions.create(ASSISTANT_ID)

    await gateway.follow(runs.hear(session, ASKING))
    await settle(runs, gateway)

    assert bot.sent == [
        (CHAT, "Flights to Tokyo asks: Direct flights only, or are 1-stop flights OK?"),
        (CHAT, "The flights ticket waits for your answer."),
    ]


async def test_a_report_without_a_question_sends_only_the_bots_reply(tmp_path) -> None:
    bot, gateway, runs, _, sessions = await build(
        tmp_path, ScriptedClient(completed("Here are the flights.")), skills=no_skills()
    )
    session = await sessions.create(ASSISTANT_ID)

    await gateway.follow(runs.hear(session, READY))
    await settle(runs, gateway)

    assert bot.sent == [(CHAT, "Here are the flights.")]
