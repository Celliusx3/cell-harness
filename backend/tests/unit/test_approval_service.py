"""The gate, its grants file, and the service that turns a tap into an answer."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.llm.messages import AssistantMessage, ToolCall
from harness.session.models import AssistantMessageEvent, ToolCallEvent, TurnEnd, TurnStart
from harness.session.repair import REPAIRED, repair
from harness.tools.approval import ApprovalGate, Approved, Denied
from harness.tools.client import Accepted, ClientTool, ClientTools, ClientToolService, Refused
from harness.tools.native.location.tool import NoArgs
from tests.unit.helpers import new_session

WRITE = "memory__write_note"


def _gate(tmp_path: Path, *tools: str) -> ApprovalGate:
    return ApprovalGate(frozenset(tools), tmp_path / "approvals.json")


def _call(call_id: str) -> ToolCallEvent:
    return ToolCallEvent(
        turn=0, step=0, call=ToolCall(id=call_id, name=WRITE, arguments='{"value": "Kopi"}')
    )


def _asked(call_id: str):
    call = ToolCall(id=call_id, name=WRITE, arguments='{"value": "Kopi"}')
    return AssistantMessageEvent(
        turn=0, step=0, message=AssistantMessage(content="", tool_calls=(call,)), usage=None
    )


def test_always_allow_is_written_to_the_grants_file_and_the_gate_stops_asking(tmp_path) -> None:
    gate = _gate(tmp_path, WRITE)
    assert gate.asks(WRITE) is True
    assert gate.asks("clock") is False

    gate.grant(WRITE)

    assert gate.asks(WRITE) is False
    assert _gate(tmp_path, WRITE).granted() == frozenset({WRITE})
    gate.revoke(WRITE)
    assert _gate(tmp_path, WRITE).asks(WRITE) is True
    with pytest.raises(ValueError):
        gate.grant("clock")


def test_the_service_grants_always_before_the_turn_resumes(tmp_path) -> None:
    gate = _gate(tmp_path, WRITE)
    service = ClientToolService(ClientTools(()), gate)
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(_call("c1"))

    accepted = service.accept_call(session, "c1", {"kind": "approved", "scope": "always"})

    assert accepted == Accepted("c1", Approved(scope="always"))
    assert gate.granted() == frozenset({WRITE})


def test_repair_answers_a_call_left_by_a_crash_after_approval() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(_asked("c1"))
    session.append(_call("c1"))
    session.append(TurnEnd(turn=0, reason="pending"))
    assert repair(session.events()) == []

    session.append(TurnStart(turn=1))

    additions = repair(session.events())
    assert [type(e).__name__ for e in additions] == ["ToolResultEvent"]
    assert additions[0].message.tool_call_id == "c1" and additions[0].error == REPAIRED


def test_the_service_parses_a_decision_for_a_listed_tool_and_refuses_a_client_body(
    tmp_path,
) -> None:
    service = ClientToolService(ClientTools(()), _gate(tmp_path, WRITE))
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(_call("c1"))

    assert service.accept_call(session, "c1", {"kind": "approved", "scope": "once"}) == Accepted(
        "c1", Approved(scope="once")
    )
    assert (
        service.accept_call(session, "c1", {"kind": "shared", "data": {}}) is Refused.DOES_NOT_FIT
    )
    assert service.accept_call(session, "c9", {"kind": "denied"}) is Refused.NOT_PENDING
    assert isinstance(Denied(), Denied)
    assert service.awaited == frozenset({WRITE})


def test_a_name_that_is_both_client_and_listed_is_refused_at_construction(tmp_path) -> None:
    class Nothing(NoArgs):
        pass

    both = ClientTool(name=WRITE, description="d", args_model=NoArgs, data_model=Nothing)
    with pytest.raises(ValueError):
        ClientToolService(ClientTools((both,)), _gate(tmp_path, WRITE))
