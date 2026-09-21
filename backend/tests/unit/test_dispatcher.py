"""Running the tool a call names."""

from __future__ import annotations

from harness.llm.messages import ToolCall
from harness.tools.definition import UNKNOWN_TOOL, Failure, Ok
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.registry import ToolRegistry
from tests.unit.fakes import echo_tool
from tests.unit.helpers import no_gate, no_progress


def dispatcher(*tools) -> ToolDispatcher:
    return ToolDispatcher(ToolRegistry(tools), no_gate())


def call(name: str, arguments: str = '{"value": "hi"}') -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


async def test_a_known_tool_runs() -> None:
    outcome = await dispatcher(echo_tool()).dispatch(
        call("echo"), progress=no_progress, approved=False
    )

    assert outcome == Ok(content="hi")


async def test_an_unknown_tool_is_a_failure_that_names_the_alternatives() -> None:
    outcome = await dispatcher(echo_tool()).dispatch(
        call("nope"), progress=no_progress, approved=False
    )

    assert isinstance(outcome, Failure)
    assert outcome.code == UNKNOWN_TOOL
    assert "echo" in outcome.message


async def test_an_empty_registry_says_none_rather_than_nothing() -> None:
    outcome = await dispatcher().dispatch(call("nope"), progress=no_progress, approved=False)

    assert isinstance(outcome, Failure)
    assert "none" in outcome.message
