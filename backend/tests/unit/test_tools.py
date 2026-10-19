"""The tool definition, registry, and pipeline — phase 2's acceptance criteria."""

from __future__ import annotations

import pytest

from harness.llm import Text, ToolCall, ToolMessage
from harness.tools import (
    EXECUTION_ERROR,
    INVALID_ARGUMENTS,
    REFUSED,
    Failure,
    Ok,
    Tool,
    ToolPipeline,
    ToolService,
)
from harness.tools.service import DuplicateToolError
from tests.unit.fakes import echo_tool, raising_tool
from tests.unit.helpers import ORIGIN, no_gate, no_progress, pipeline_for


def pipeline(*tools, providers=(), offer=()) -> ToolPipeline:
    return pipeline_for(*tools, providers=providers, offer=offer)


def call(name: str, arguments: str = '{"value": "hi"}') -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


def test_spec_is_an_allowlist_and_cannot_leak_internals() -> None:
    wire = echo_tool().spec().model_dump()

    assert set(wire) == {"name", "description", "input_schema"}
    assert "execute" not in str(wire)
    assert "parse" not in str(wire)


def test_from_model_derives_schema_and_parser_from_one_source() -> None:
    tool = echo_tool()

    schema = tool.spec().input_schema
    assert schema["properties"]["value"]["description"] == "Text to echo back."
    assert schema["required"] == ["value"]


@pytest.mark.parametrize(
    ("arguments", "reason"),
    [
        ("{not json", "not valid JSON"),
        ('"a string"', "must be a JSON object"),
        ("[1, 2]", "must be a JSON object"),
        ('{"wrong": 1}', "invalid arguments"),
    ],
)
async def test_bad_arguments_are_a_failure_not_an_exception(arguments, reason) -> None:
    outcome = await pipeline(echo_tool()).execute(
        call("echo", arguments), progress=no_progress, origin=ORIGIN
    )

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert reason in outcome.message


async def test_a_tool_that_raises_does_not_kill_the_turn() -> None:
    outcome = await pipeline(raising_tool()).execute(
        call("boom"), progress=no_progress, origin=ORIGIN
    )

    assert isinstance(outcome, Failure)
    assert outcome.code == EXECUTION_ERROR
    assert "kaboom" in outcome.message


async def test_empty_arguments_mean_no_arguments() -> None:
    outcome = await pipeline(echo_tool()).execute(
        call("echo", ""), progress=no_progress, origin=ORIGIN
    )

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert "not valid JSON" not in outcome.message


def test_data_never_reaches_the_model() -> None:
    blocks = Ok(content="Found 3 jobs.", data={"jobs": [1, 2, 3]}).content
    assert blocks == (Text(text="Found 3 jobs."),)


def test_ok_still_compares_by_value_with_data_defaulted() -> None:
    assert Ok(content="hi") == Ok(content="hi", data=None)
    assert Ok(content="hi") != Ok(content="hi", data={})


def test_failures_wear_one_wire_shape() -> None:
    assert Failure("X", "went wrong").content == (Text(text="error: went wrong"),)
    assert Ok(content="fine").content == (Text(text="fine"),)


def test_a_plain_string_is_one_text_block() -> None:
    assert Ok("hi").content == (Text(text="hi"),)
    assert Ok("hi").text == "hi"
    assert ToolMessage(tool_call_id="c1", content="hi").content == (Text(text="hi"),)


async def test_a_tool_from_a_provider_is_callable_the_turn_it_appears() -> None:
    connected: list = []
    tools = pipeline(providers=[lambda: list(connected)], offer=("echo",))

    assert tools.specs() == []
    outcome = await tools.execute(call("echo"), progress=no_progress, origin=ORIGIN)
    assert isinstance(outcome, Failure)

    connected.append(echo_tool())

    assert [s.name for s in tools.specs()] == ["echo"]
    assert await tools.execute(call("echo"), progress=no_progress, origin=ORIGIN) == Ok(
        content="hi"
    )


def test_a_broken_provider_does_not_take_down_the_tool_set() -> None:

    def broken():
        raise RuntimeError("server went away")

    tool_service = ToolService([echo_tool()], gate=no_gate(), providers=[broken])

    assert [t.name for t in tool_service.all()] == ["echo"]


def test_duplicate_static_registration_fails_loudly() -> None:
    tool_service = ToolService([echo_tool()], gate=no_gate())

    with pytest.raises(DuplicateToolError):
        tool_service.register(echo_tool())


def test_a_disposer_removes_exactly_its_registration() -> None:
    tool_service = ToolService((), gate=no_gate())
    dispose = tool_service.register(echo_tool())

    assert len(tool_service.all()) == 1
    dispose()
    assert tool_service.all() == []
    dispose()


def test_static_tools_win_a_name_collision_with_a_provider() -> None:
    tool_service = ToolService(
        [echo_tool()], gate=no_gate(), providers=[lambda: [raising_tool("echo")]]
    )

    assert len(tool_service.all()) == 1
    assert tool_service.get("echo") is not None


def test_a_provider_disposer_removes_exactly_its_source() -> None:
    tool_service = ToolService((), gate=no_gate())
    dispose = tool_service.add_provider(lambda: [echo_tool()])
    tool_service.add_provider(lambda: [raising_tool("boom")])

    assert sorted(t.name for t in tool_service.all()) == ["boom", "echo"]
    dispose()
    assert [t.name for t in tool_service.all()] == ["boom"]
    dispose()


def offering(*tools: Tool, default: tuple[str, ...]) -> ToolPipeline:
    """A pipeline with a chosen `default_tools` that offers every tool it was given."""
    return ToolPipeline(ToolService(tools, gate=no_gate()), default)


async def test_a_registered_tool_outside_the_offer_is_refused_by_name() -> None:
    pipeline = offering(echo_tool(), echo_tool("hidden"), default=("echo",))

    outcome = await pipeline.execute(
        ToolCall(id="c1", name="hidden", arguments="{}"), progress=no_progress, origin=ORIGIN
    )

    assert isinstance(outcome, Failure) and outcome.code == REFUSED
    assert "list_functions" in outcome.message
    assert "echo" not in outcome.message


async def test_an_offered_tool_executes() -> None:
    pipeline = offering(echo_tool(), echo_tool("hidden"), default=("echo",))

    outcome = await pipeline.execute(
        ToolCall(id="c1", name="echo", arguments='{"value": "hi"}'),
        progress=no_progress,
        origin=ORIGIN,
    )

    assert isinstance(outcome, Ok) and outcome.text == "hi"


async def test_an_empty_default_offers_nothing_and_refuses_everything() -> None:
    pipeline = offering(echo_tool(), default=())

    assert pipeline.specs() == []
    outcome = await pipeline.execute(
        ToolCall(id="c1", name="echo", arguments='{"value": "hi"}'),
        progress=no_progress,
        origin=ORIGIN,
    )
    assert isinstance(outcome, Failure) and outcome.code == REFUSED
