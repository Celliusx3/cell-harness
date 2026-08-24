"""Repair: answering tool calls a dead process never got back to."""

from __future__ import annotations

from harness.llm.messages import AssistantMessage, ToolCall, ToolMessage, UserMessage
from harness.session.derive import derive_messages
from harness.session.models import (
    AssistantMessageEvent,
    SessionEvent,
    StepStart,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repair import REPAIRED, TOOL_OUTCOME_UNKNOWN, repair
from tests.unit.helpers import unanswered_calls


def call(id: str = "c1") -> ToolCall:
    return ToolCall(id=id, name="get_current_time", arguments="{}")


def asked_for(*calls: ToolCall) -> list[SessionEvent]:
    """A turn where the model requested `calls`, then the process died."""
    return [
        TurnStart(turn=0),
        UserMessageEvent(turn=0, message=UserMessage(content="what time is it?")),
        StepStart(turn=0, step=0),
        AssistantMessageEvent(
            turn=0, step=0, message=AssistantMessage(content="", tool_calls=calls)
        ),
    ]


# ── when it applies ───────────────────────────────────────────────────────────


def test_nothing_outstanding_needs_no_repair() -> None:
    events = [
        TurnStart(turn=0),
        UserMessageEvent(turn=0, message=UserMessage(content="hi")),
        AssistantMessageEvent(turn=0, step=0, message=AssistantMessage(content="hello")),
        TurnEnd(turn=0, reason="completed"),
    ]

    assert repair(events) == []


def test_an_empty_log_needs_no_repair() -> None:
    assert repair([]) == []


def test_an_unclosed_turn_alone_needs_no_repair() -> None:
    """`derive_messages` ignores turn and step boundaries, so an unclosed turn
    changes nothing the model sees. Closing it would be writing an event nothing
    reads."""
    events = [
        TurnStart(turn=0),
        UserMessageEvent(turn=0, message=UserMessage(content="hi")),
        StepStart(turn=0, step=0),
    ]

    assert repair(events) == []


# ── what it writes ────────────────────────────────────────────────────────────


def test_an_unanswered_call_gets_a_result() -> None:
    additions = repair(asked_for(call()))

    assert len(additions) == 1
    assert additions[0].message.tool_call_id == "c1"
    assert additions[0].message.content == TOOL_OUTCOME_UNKNOWN


def test_the_result_does_not_claim_the_tool_never_ran() -> None:
    """It was dispatched before the process died and may have finished, so the
    honest answer is that the outcome is unknown."""
    content = repair(asked_for(call()))[0].message.content

    assert "unknown" in content
    assert "verify" in content


def test_a_repaired_result_is_marked_as_a_crash_not_a_tool_failure() -> None:
    """Telemetry must be able to tell a dead process from a bad argument."""
    assert repair(asked_for(call()))[0].error == REPAIRED


def test_results_follow_the_order_the_model_asked_in() -> None:
    additions = repair(asked_for(call("c1"), call("c2")))

    assert [a.message.tool_call_id for a in additions] == ["c1", "c2"]


def test_an_already_answered_call_is_left_alone() -> None:
    events = [
        *asked_for(call("c1"), call("c2")),
        ToolResultEvent(turn=0, step=0, message=ToolMessage(tool_call_id="c1", content="12:00")),
    ]

    assert [a.message.tool_call_id for a in repair(events)] == ["c2"]


def test_the_result_lands_in_the_step_that_asked() -> None:
    """A provider pairs on the id, but a UI groups by step."""
    additions = repair(asked_for(call()))

    assert (additions[0].turn, additions[0].step) == (0, 0)


# ── the point of all of it ────────────────────────────────────────────────────


def test_a_repaired_log_is_one_a_provider_accepts() -> None:
    """The reason repair exists: an unanswered call makes the next request 400."""
    events = asked_for(call("c1"), call("c2"))

    assert unanswered_calls(derive_messages(events)) == ["c1", "c2"]
    assert unanswered_calls(derive_messages([*events, *repair(events)])) == []


def test_repair_is_idempotent() -> None:
    """Resuming twice must not stack results."""
    events = asked_for(call())
    once = [*events, *repair(events)]

    assert repair(once) == []
