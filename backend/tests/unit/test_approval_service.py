"""The approvals, their grants file, and the service that turns a tap into an answer."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.llm import AssistantMessage, ToolCall
from harness.session.models import AssistantMessageEvent, ToolCallEvent, TurnEnd, TurnStart
from harness.session.repair import REPAIRED, repair
from harness.tools import Approval, Approvals
from harness.tools.client import (
    AcceptedAnswer,
    ClientTool,
    ClientTools,
    ClientToolService,
    RefusalReason,
)
from harness.tools.models.decision import Denial
from harness.tools.native.location.models import NoArgs
from tests.unit.helpers import new_session

WRITE = "memory__write_note"


def _approvals(tmp_path: Path, *tools: str) -> Approvals:
    return Approvals(frozenset(tools), frozenset, tmp_path / "approvals.json")


def _call(call_id: str) -> ToolCallEvent:
    return ToolCallEvent(
        turn=0, step=0, call=ToolCall(id=call_id, name=WRITE, arguments='{"value": "Kopi"}')
    )


def _asked(call_id: str):
    call = ToolCall(id=call_id, name=WRITE, arguments='{"value": "Kopi"}')
    return AssistantMessageEvent(
        turn=0, step=0, message=AssistantMessage(content="", tool_calls=(call,)), usage=None
    )


def test_always_allow_is_written_to_the_grants_file_and_the_tool_stops_asking(tmp_path) -> None:
    approvals = _approvals(tmp_path, WRITE)
    assert approvals.should_ask(WRITE) is True
    assert approvals.should_ask("clock") is False

    approvals.grant(WRITE)

    assert approvals.should_ask(WRITE) is False
    assert _approvals(tmp_path, WRITE).granted_tools() == frozenset({WRITE})
    approvals.revoke(WRITE)
    assert _approvals(tmp_path, WRITE).should_ask(WRITE) is True
    with pytest.raises(ValueError):
        approvals.grant("clock")


def test_the_service_grants_always_before_the_turn_resumes(tmp_path) -> None:
    approvals = _approvals(tmp_path, WRITE)
    service = ClientToolService(ClientTools(()), approvals)
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(_call("c1"))

    accepted = service.accept_by_call_id(session, "c1", {"kind": "approved", "scope": "always"})

    assert accepted == AcceptedAnswer("c1", Approval(scope="always"))
    assert approvals.granted_tools() == frozenset({WRITE})


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
    service = ClientToolService(ClientTools(()), _approvals(tmp_path, WRITE))
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(_call("c1"))

    assert service.accept_by_call_id(
        session, "c1", {"kind": "approved", "scope": "once"}
    ) == AcceptedAnswer("c1", Approval(scope="once"))
    assert (
        service.accept_by_call_id(session, "c1", {"kind": "shared", "data": {}})
        is RefusalReason.DOES_NOT_FIT
    )
    assert service.accept_by_call_id(session, "c9", {"kind": "denied"}) is RefusalReason.NOT_PENDING
    assert isinstance(Denial(), Denial)
    assert service.awaited_tools == frozenset({WRITE})


def test_a_name_that_is_both_client_and_listed_is_refused_at_construction(tmp_path) -> None:
    class Nothing(NoArgs):
        pass

    both = ClientTool(name=WRITE, description="d", args_model=NoArgs, data_model=Nothing)
    with pytest.raises(ValueError):
        ClientToolService(ClientTools((both,)), _approvals(tmp_path, WRITE))


def test_a_server_tool_that_may_write_asks_until_it_is_allowed_always(tmp_path) -> None:
    approvals = Approvals(
        frozenset(), lambda: frozenset({"mail__send_email"}), tmp_path / "approvals.json"
    )

    assert approvals.should_ask("mail__send_email")
    approvals.grant("mail__send_email")
    assert not approvals.should_ask("mail__send_email")


def test_the_servers_tools_are_read_again_on_every_check(tmp_path) -> None:
    connected: set[str] = set()
    approvals = Approvals(frozenset(), lambda: frozenset(connected), tmp_path / "approvals.json")

    assert not approvals.should_ask("mail__send_email")
    connected.add("mail__send_email")
    assert approvals.should_ask("mail__send_email")
