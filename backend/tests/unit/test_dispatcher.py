"""Running the tool a call names."""

from __future__ import annotations

from pathlib import Path

from harness.llm import ToolCall
from harness.tools import (
    UNKNOWN_TOOL,
    Approvals,
    Failure,
    Ok,
    Pending,
    ToolService,
)
from tests.unit.fakes import echo_tool
from tests.unit.helpers import ORIGIN, no_approvals, no_progress


def tool_service(*tools) -> ToolService:
    return ToolService(tools, approvals=no_approvals())


def call(name: str, arguments: str = '{"value": "hi"}') -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


async def test_a_known_tool_runs() -> None:
    outcome = await tool_service(echo_tool()).dispatch(
        call("echo"), progress=no_progress, origin=ORIGIN, approved=False
    )

    assert outcome == Ok(content="hi")


async def test_an_unknown_tool_is_a_failure_that_names_the_alternatives() -> None:
    outcome = await tool_service(echo_tool()).dispatch(
        call("nope"), progress=no_progress, origin=ORIGIN, approved=False
    )

    assert isinstance(outcome, Failure)
    assert outcome.code == UNKNOWN_TOOL
    assert "echo" in outcome.message


async def test_an_empty_registry_says_none_rather_than_nothing() -> None:
    outcome = await tool_service().dispatch(
        call("nope"), progress=no_progress, origin=ORIGIN, approved=False
    )

    assert isinstance(outcome, Failure)
    assert "none" in outcome.message


async def test_a_call_that_must_ask_waits_before_its_name_is_looked_up() -> None:
    approvals = Approvals(frozenset({"ghost"}), frozenset, Path("/nonexistent/approvals.json"))

    outcome = await ToolService((), approvals=approvals).dispatch(
        call("ghost"), progress=no_progress, origin=ORIGIN, approved=False
    )

    assert outcome == Pending()
