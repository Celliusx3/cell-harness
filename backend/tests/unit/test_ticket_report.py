"""`ticket_report` refuses a question it cannot carry, and the last accepted report is kept."""

from __future__ import annotations

import json

from harness.llm import ToolCall, ToolMessage
from harness.session.domain.models import SessionEvent, ToolCallEvent, ToolResultEvent, TurnStart
from harness.tickets.service.worker import last_accepted_report
from harness.tools import INVALID_ARGUMENTS, Failure, Ok
from harness.tools.native.tickets import TICKET_REPORT, ticket_report_tool
from tests.unit.helpers import context_for


async def report(**fields: str) -> Ok | Failure:
    outcome = await ticket_report_tool().invoke(json.dumps(fields), context=context_for())
    assert isinstance(outcome, (Ok, Failure))
    return outcome


async def test_a_question_goes_only_with_blocked_or_waiting() -> None:
    refused = await report(state="ready", summary="Done.", question="Which one?")

    assert isinstance(refused, Failure) and refused.code == INVALID_ARGUMENTS
    assert await report(state="waiting", summary="Hold.", question="Which one?") == Ok(
        "Reported. End your turn now.", ends_turn=True
    )
    assert await report(state="progress", summary="Step.") == Ok("Recorded.")


def reported(turn: int, call_id: str, error: str | None = None, **fields: str) -> list:
    call = ToolCall(id=call_id, name=TICKET_REPORT, arguments=json.dumps(fields))
    return [
        ToolCallEvent(turn=turn, step=0, call=call),
        ToolResultEvent(
            turn=turn, step=0, message=ToolMessage(tool_call_id=call_id, content=""), error=error
        ),
    ]


def test_the_last_report_of_the_last_turn_is_kept_skipping_progress_and_refusals() -> None:
    events: list[SessionEvent] = [
        TurnStart(turn=0),
        *reported(0, "a", state="dropped", summary="Old turn."),
        TurnStart(turn=1),
        *reported(1, "b", state="blocked", summary="First."),
        *reported(1, "c", state="ready", summary="Second."),
        *reported(1, "d", state="progress", summary="A step."),
        *reported(1, "e", INVALID_ARGUMENTS, state="failed", summary="Refused."),
    ]

    kept = last_accepted_report(events)

    assert kept is not None and (kept.state, kept.summary) == ("ready", "Second.")
    assert last_accepted_report([TurnStart(turn=2)]) is None


async def test_a_final_report_ends_the_worker_s_turn_and_progress_does_not() -> None:
    tool = ticket_report_tool()

    async def outcome(state: str) -> Ok:
        arguments = json.dumps({"state": state, "summary": "x"})
        result = await tool.invoke(arguments, context=context_for())
        assert isinstance(result, Ok)
        return result

    assert (await outcome("blocked")).ends_turn
    assert (await outcome("ready")).ends_turn
    assert not (await outcome("progress")).ends_turn
