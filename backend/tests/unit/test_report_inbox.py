"""A goal run's report inbox: what it hands back to delivery, and an approval it only logs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from harness.runs.service.goal_wait import TeamTurnEnd, team_turn
from harness.runs.service.report_inbox import ReportInbox, ReportInboxes
from harness.runtime.events import AgentCompleted, TurnEvent
from harness.session.domain.models import GoalStepEvent, TicketReport, TicketReportEvent
from tests.unit.fakes import SteppedClient
from tests.unit.helpers import new_session, runtime_over


def _report(ticket_id: str) -> TicketReport:
    return TicketReport(ticket_id=ticket_id, title="T", state="ready", text="done", question=None)


async def test_a_report_nobody_waits_for_is_not_taken() -> None:
    inboxes = ReportInboxes()
    with inboxes.opened("c"):
        assert await inboxes.hand_over("c", _report("t1")) is False
    assert await inboxes.hand_over("c", _report("t1")) is False


async def test_a_report_handed_over_and_then_released_goes_back_to_delivery() -> None:
    inbox = ReportInbox()
    inbox.expect("t1", "w")
    handing = asyncio.create_task(inbox.hand_over(_report("t1")))
    await asyncio.sleep(0)
    inbox.release("w")

    assert await handing is False
    assert await inbox.next_for("w") is None


async def test_a_closed_inbox_gives_every_report_back() -> None:
    inboxes = ReportInboxes()
    with inboxes.opened("c") as inbox:
        inboxes.expect("c", "t1", "w")
        handing = asyncio.create_task(inbox.hand_over(_report("t1")))
        await asyncio.sleep(0)

    assert await handing is False


async def test_a_withdrawn_ticket_is_waited_for_no_more() -> None:
    inboxes = ReportInboxes()
    with inboxes.opened("c") as inbox:
        inboxes.expect("c", "t1", "w")
        waiting = asyncio.create_task(inbox.next_for("w"))
        await asyncio.sleep(0)
        inboxes.withdraw("t1")

        assert await waiting is None


async def test_an_approval_is_logged_not_heard_and_ends_the_team_turn_asking() -> None:
    session = new_session()
    inbox = ReportInbox()
    inbox.expect("t1", "w")
    asked = _report("t1").model_copy(update={"question": "Allow fetch?", "ask": "approval"})
    handing = asyncio.create_task(inbox.hand_over(asked))
    ended = TeamTurnEnd()
    step = GoalStepEvent(turn=0, bot_id="w", role="member", step=2, task="x", note=None)

    async def first() -> AsyncIterator[TurnEvent]:
        yield AgentCompleted(text="Started.")

    runtime = runtime_over(SteppedClient())
    events = [e async for e in team_turn(runtime, session, inbox, step, first(), ended)]

    assert events == [AgentCompleted(text="Started.")]
    assert ended.question == "Allow fetch?"
    assert TicketReportEvent(turn=0, report=asked) in session.events()
    assert await handing is True
