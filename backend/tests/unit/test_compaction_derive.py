"""Phase 11: compaction appends, never rewrites — and `derive_messages` honours it."""

from __future__ import annotations

from harness.llm.messages import (
    ApplicationMessage,
    AssistantMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from harness.llm.stream import Usage
from harness.session.compaction import (
    PRUNED,
    CompactionEnd,
    CompactionPrune,
    CompactionStart,
    boundary,
    open_start,
    pruned_ids,
)
from harness.session.derive import derive_messages
from harness.session.models import (
    AssistantMessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repair import REPAIRED, repair
from tests.unit.helpers import new_session


def a_call(id: str, name: str = "execute_typescript") -> ToolCall:
    return ToolCall(id=id, name=name, arguments="{}")


def turn_with_tool(session, turn: int, call_id: str, text: str, name: str = "execute_typescript"):
    session.append(TurnStart(turn=turn))
    session.append(UserMessageEvent(turn=turn, message=UserMessage(content=f"q{turn}")))
    session.append(
        AssistantMessageEvent(
            turn=turn,
            step=0,
            message=AssistantMessage(content="", tool_calls=(a_call(call_id, name),)),
            usage=Usage(input_tokens=1000 * (turn + 1), output_tokens=10),
        )
    )
    session.append(ToolCallEvent(turn=turn, step=0, call=a_call(call_id, name)))
    session.append(
        ToolResultEvent(turn=turn, step=0, message=ToolMessage(tool_call_id=call_id, content=text))
    )
    session.append(
        AssistantMessageEvent(turn=turn, step=1, message=AssistantMessage(content=f"a{turn}"))
    )
    session.append(TurnEnd(turn=turn, reason="completed"))


def test_every_compaction_event_round_trips() -> None:
    events = [
        CompactionStart(turn=3, trigger="auto", tokens=13400),
        CompactionStart(turn=None, trigger="manual"),
        CompactionEnd(turn=3, message=ApplicationMessage(content="summary")),
        CompactionEnd(turn=None, error="boom"),
        CompactionPrune(turn=2, call_ids=("c1", "c2")),
    ]
    for event in events:
        assert type(event).model_validate_json(event.model_dump_json()) == event


def test_the_boundary_replaces_everything_before_it() -> None:
    session = new_session()
    turn_with_tool(session, 0, "c0", "big result")
    session.append(CompactionStart(turn=None, trigger="manual", tokens=1010))
    session.append(CompactionEnd(turn=None, message=ApplicationMessage(content="SUMMARY")))
    session.append(TurnStart(turn=1))
    session.append(UserMessageEvent(turn=1, message=UserMessage(content="next")))

    assert derive_messages(session.events()) == [
        UserMessage(content="SUMMARY"),
        UserMessage(content="next"),
    ]
    assert [e.type for e in session.events()][:2] == ["turn/start", "user/message"]


def test_a_failed_end_and_a_bare_start_are_not_boundaries() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(CompactionStart(turn=0, trigger="auto"))
    session.append(CompactionEnd(turn=0, error="summarizer timed out"))
    session.append(CompactionStart(turn=0, trigger="auto"))

    assert derive_messages(session.events()) == [UserMessage(content="hi")]
    assert boundary(session.events()) is None


def test_the_last_boundary_wins() -> None:
    session = new_session()
    session.append(CompactionEnd(turn=None, message=ApplicationMessage(content="first")))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="between")))
    session.append(CompactionEnd(turn=None, message=ApplicationMessage(content="second")))
    assert derive_messages(session.events()) == [UserMessage(content="second")]


def test_a_pruned_result_is_a_placeholder_to_the_model_and_itself_in_the_log() -> None:
    session = new_session()
    turn_with_tool(session, 0, "c0", "four thousand tokens of transcript")
    turn_with_tool(session, 1, "c1", "kept")
    session.append(CompactionPrune(turn=1, call_ids=("c0",)))

    messages = derive_messages(session.events())
    tools = [m for m in messages if isinstance(m, ToolMessage)]
    assert tools == [
        ToolMessage(tool_call_id="c0", content=PRUNED),
        ToolMessage(tool_call_id="c1", content="kept"),
    ]
    logged = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert logged[0].message.content[0].text == "four thousand tokens of transcript"
    assert pruned_ids(session.events()) == frozenset({"c0"})


def test_context_size_is_the_context_after_the_last_reply() -> None:
    session = new_session()
    assert session.context_size() is None
    turn_with_tool(session, 0, "c0", "r")
    turn_with_tool(session, 1, "c1", "r")
    assert session.context_size() == 2000 + 10


def test_repair_closes_a_start_the_crash_left_open() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="hi")))
    session.append(CompactionStart(turn=0, trigger="auto", tokens=5))
    assert open_start(session.events()) is not None

    additions = repair(session.events())
    assert additions == [CompactionEnd(turn=0, error=REPAIRED)]
    for event in additions:
        session.append(event)
    assert repair(session.events()) == []
    assert open_start(session.events()) is None


def test_a_closed_start_needs_no_repair() -> None:
    events = [
        CompactionStart(turn=None, trigger="manual"),
        CompactionEnd(turn=None, message=ApplicationMessage(content="s")),
    ]
    assert repair(events) == []


def test_a_compaction_end_carries_exactly_one_outcome() -> None:
    import pytest
    from pydantic import ValidationError

    assert CompactionEnd(turn=0, message=ApplicationMessage(content="s")).succeeded
    assert not CompactionEnd(turn=0, error="boom").succeeded
    with pytest.raises(ValidationError):
        CompactionEnd(turn=0)
    with pytest.raises(ValidationError):
        CompactionEnd(turn=0, message=ApplicationMessage(content="s"), error="boom")
