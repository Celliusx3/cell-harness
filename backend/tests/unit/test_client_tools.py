"""The client-tool spine, proven without a real client tool."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from harness.llm.messages import Text, ToolCall, ToolMessage
from harness.session.models import ToolCallEvent, ToolResultEvent, TurnStart
from harness.tools.client import (
    DECLINED,
    UNAVAILABLE,
    Accepted,
    ClientTool,
    ClientTools,
    ClientToolService,
    Declined,
    PendingCall,
    Refused,
    Shared,
    Unavailable,
    pending_call,
)
from harness.tools.definition import Failure, Ok, Pending
from tests.unit.helpers import context_for, new_session


class NoArgs(BaseModel):
    pass


class Battery(BaseModel):
    """Strict, as a datum should be: the declaration decides what is refused."""

    model_config = ConfigDict(extra="forbid")

    percent: int


BATTERY = ClientTool(
    name="get_battery", description="The device's charge.", args_model=NoArgs, data_model=Battery
)
CHARGED = Shared[Battery](data=Battery(percent=80))
NAMES = frozenset({"get_battery"})


def test_a_body_is_held_to_the_declared_shape() -> None:
    tools = ClientTools((BATTERY,))
    assert tools.names == NAMES
    assert tools.parse("get_battery", {"kind": "shared", "data": {"percent": 80}}) == CHARGED
    assert tools.parse("get_battery", {"kind": "declined"}) == Declined()
    assert tools.parse("get_battery", {"kind": "unavailable", "reason": "NO_BATTERY"}) == (
        Unavailable(reason="NO_BATTERY")
    )
    for bad in (
        {"kind": "shared", "data": {"latitude": 3.0}},
        {"kind": "shared", "data": {"percent": 80, "volts": 4}},
        {"kind": "unavailable", "reason": ""},
        {"kind": "lost"},
        "80",
    ):
        with pytest.raises(ValidationError):
            tools.parse("get_battery", bad)


def test_two_declarations_cannot_share_a_name() -> None:
    with pytest.raises(ValueError):
        ClientTools((BATTERY, BATTERY))


def test_what_the_model_reads_for_each_answer() -> None:
    tools = ClientTools((BATTERY,))
    assert tools.outcome(CHARGED) == Ok(content='{"percent":80}')
    declined = tools.outcome(Declined())
    assert isinstance(declined, Failure) and declined.code == DECLINED
    assert "ask them in words" in declined.message
    unavailable = tools.outcome(Unavailable(reason="NO_BATTERY"))
    assert isinstance(unavailable, Failure) and unavailable.code == UNAVAILABLE
    assert "NO_BATTERY" in unavailable.message


async def test_the_tool_itself_only_says_pending() -> None:
    (tool,) = ClientTools((BATTERY,)).definitions()
    spec = tool.spec()
    assert (spec.name, spec.description) == ("get_battery", "The device's charge.")
    assert spec.input_schema.get("properties", {}) == {}
    assert await tool.invoke("{}", context=context_for("c1")) == Pending()


def _call(call_id: str, name: str = "get_battery") -> ToolCallEvent:
    return ToolCallEvent(turn=0, step=0, call=ToolCall(id=call_id, name=name, arguments="{}"))


def _result(call_id: str) -> ToolResultEvent:
    message = ToolMessage(tool_call_id=call_id, content=(Text(text="x"),))
    return ToolResultEvent(turn=0, step=0, message=message, error=None)


def test_the_pending_call_is_the_unanswered_client_call_of_the_current_turn() -> None:
    session = new_session()
    assert pending_call(session, NAMES) is None

    session.append(TurnStart(turn=0))
    session.append(_call("other", name="echo"))
    assert pending_call(session, NAMES) is None

    session.append(_call("c1"))
    assert pending_call(session, NAMES) == PendingCall("get_battery", "c1", "{}")

    session.append(_result("c1"))
    assert pending_call(session, NAMES) is None


def test_a_call_from_an_earlier_turn_is_never_pending() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(_call("c1"))
    session.append(TurnStart(turn=1))
    assert pending_call(session, NAMES) is None


def _session_with_pending(call_id: str = "c1"):
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(_call(call_id))
    return session


def test_the_service_accepts_by_call_id_or_by_tool_name() -> None:
    service = ClientToolService(ClientTools((BATTERY,)))
    body = {"kind": "shared", "data": {"percent": 80}}

    assert service.accept_call(_session_with_pending(), "c1", body) == Accepted(
        "c1", Ok(content='{"percent":80}')
    )
    accepted = service.accept_tool(_session_with_pending("c2"), "get_battery", {"kind": "declined"})
    assert isinstance(accepted, Accepted) and accepted.call_id == "c2"
    assert isinstance(accepted.outcome, Failure) and accepted.outcome.code == DECLINED


def test_each_refusal_is_its_own_answer() -> None:
    service = ClientToolService(ClientTools((BATTERY,)))
    body = {"kind": "shared", "data": {"percent": 80}}

    assert service.accept_call(new_session(), "c1", body) is Refused.NOT_PENDING
    session = _session_with_pending()
    assert service.accept_call(session, "c9", body) is Refused.NOT_PENDING
    assert service.accept_tool(session, "get_location", body) is Refused.NOT_PENDING
    assert service.accept_call(session, "c1", {"kind": "lost"}) is Refused.DOES_NOT_FIT


def test_the_service_exposes_what_composition_needs() -> None:
    service = ClientToolService(ClientTools((BATTERY,)))
    assert service.names == NAMES
    assert [tool.name for tool in service.definitions()] == ["get_battery"]
    assert service.pending(_session_with_pending()) == PendingCall("get_battery", "c1", "{}")
