"""A schedule change is told in the user role, never between a tool call and its result."""

from __future__ import annotations

import json

from harness.llm import AssistantMessage, ToolCall, ToolMessage, UserMessage
from harness.prompts import SCHEDULE_CHANGE
from harness.session.domain.derive import derive_messages
from harness.session.domain.models import (
    AssistantMessageEvent,
    ScheduleChange,
    ScheduleChangeEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)

CHANGE = ScheduleChangeEvent(
    turn=0, change=ScheduleChange(schedule_id="s1", title="Café «run»", change="deleted")
)
ASKED = AssistantMessageEvent(
    turn=0,
    step=0,
    message=AssistantMessage(content="", tool_calls=(ToolCall(id="c1", name="ask", arguments=""),)),
)
ANSWERED = ToolResultEvent(turn=1, step=0, message=ToolMessage(tool_call_id="c1", content="yes"))


def test_the_change_is_worded_with_its_id_and_title_as_json() -> None:
    (told,) = derive_messages([CHANGE])

    assert told == UserMessage(
        content=SCHEDULE_CHANGE.format(
            change="deleted",
            schedule_id_json=json.dumps("s1"),
            schedule_title_json=json.dumps("Café «run»", ensure_ascii=False),
        )
    )


def test_a_change_logged_while_a_call_waits_across_turns_follows_its_result() -> None:
    log = [
        TurnStart(turn=0),
        UserMessageEvent(turn=0, message=UserMessage(content="Ask me.")),
        ASKED,
        TurnEnd(turn=0, reason="pending"),
        CHANGE,
        TurnStart(turn=1),
        ANSWERED,
    ]

    kinds = [type(m) for m in derive_messages(log)]

    assert kinds == [UserMessage, AssistantMessage, ToolMessage, UserMessage]


def test_a_change_with_nothing_owed_stays_where_it_was_logged() -> None:
    later = UserMessageEvent(turn=1, message=UserMessage(content="Hi"))

    told, said = derive_messages([CHANGE, later])

    assert (told.content.startswith("[SCHEDULE CHANGE]"), said.content) == (True, "Hi")


def test_a_change_held_behind_a_call_is_told_right_after_its_result() -> None:
    later = UserMessageEvent(turn=1, message=UserMessage(content="Hi"))

    told = derive_messages([ASKED, CHANGE, ANSWERED, later])

    assert [m.content for m in told[2:]] == [derive_messages([CHANGE])[0].content, "Hi"]
