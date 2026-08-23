"""The tool definition, registry, and pipeline — phase 2's acceptance criteria."""

from __future__ import annotations

import pytest

from harness.llm.messages import ToolCall
from harness.tools.definition import (
    EXECUTION_ERROR,
    INVALID_ARGUMENTS,
    UNKNOWN_TOOL,
    Failure,
    Ok,
    render_outcome,
)
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import DuplicateToolError, ToolRegistry
from tests.unit.fakes import echo_tool, raising_tool
from tests.unit.helpers import no_progress


def pipeline(*tools, providers=()) -> ToolPipeline:
    return ToolPipeline(ToolRegistry(tools, providers=providers))


def call(name: str, arguments: str = '{"value": "hi"}') -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


# ── the schema allowlist ──────────────────────────────────────────────────────


def test_spec_is_an_allowlist_and_cannot_leak_internals() -> None:
    """Acceptance: `execute` and `parse` never appear in what the model sees.

    Asserted on the serialized spec rather than the field list, because a leak
    would show up as an extra key on the wire.
    """
    wire = echo_tool().spec().model_dump()

    assert set(wire) == {"name", "description", "input_schema"}
    assert "execute" not in str(wire)
    assert "parse" not in str(wire)


def test_from_model_derives_schema_and_parser_from_one_source() -> None:
    """What the model is told and what the executor accepts cannot drift."""
    tool = echo_tool()

    schema = tool.spec().input_schema
    assert schema["properties"]["value"]["description"] == "Text to echo back."
    assert schema["required"] == ["value"]


# ── tolerant failures ─────────────────────────────────────────────────────────


async def test_unknown_tool_is_a_failure_that_names_the_alternatives() -> None:
    """Acceptance: an unknown tool returns a Failure, not an exception.

    Naming what *is* available is what turns a dead end into a correction the
    model can act on next step.
    """
    outcome = await pipeline(echo_tool()).execute(call("nope"), progress=no_progress)

    assert isinstance(outcome, Failure)
    assert outcome.code == UNKNOWN_TOOL
    assert "echo" in outcome.message


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
    """Acceptance: invalid args return a Failure the model can recover from."""
    outcome = await pipeline(echo_tool()).execute(call("echo", arguments), progress=no_progress)

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert reason in outcome.message


async def test_a_tool_that_raises_does_not_kill_the_turn() -> None:
    outcome = await pipeline(raising_tool()).execute(call("boom"), progress=no_progress)

    assert isinstance(outcome, Failure)
    assert outcome.code == EXECUTION_ERROR
    assert "kaboom" in outcome.message


async def test_empty_arguments_mean_no_arguments() -> None:
    """A no-arg tool is often called with `""` rather than `"{}"`."""
    outcome = await pipeline(echo_tool()).execute(call("echo", ""), progress=no_progress)

    # `value` is required, so this is still a failure — but a *validation* one,
    # which is what proves `""` was read as `{}` rather than as malformed JSON.
    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert "not valid JSON" not in outcome.message


def test_failures_wear_one_wire_shape() -> None:
    """The model learns this prefix; a second spelling would read as a different
    kind of thing."""
    assert render_outcome(Failure("X", "went wrong")) == "error: went wrong"
    assert render_outcome(Ok(content="fine")) == "fine"


# ── live resolution ───────────────────────────────────────────────────────────


async def test_a_tool_from_a_provider_is_callable_the_turn_it_appears() -> None:
    """Acceptance: a tool added between turns is callable on the next.

    This is the seam MCP plugs into in phase 5 — the registry re-asks its
    providers on every read, so connecting a server does not require rebuilding
    the agent.
    """
    connected: list = []
    tools = pipeline(providers=[lambda: list(connected)])

    assert tools.specs() == []
    outcome = await tools.execute(call("echo"), progress=no_progress)
    assert isinstance(outcome, Failure)

    connected.append(echo_tool())

    assert [s.name for s in tools.specs()] == ["echo"]
    assert await tools.execute(call("echo"), progress=no_progress) == Ok(content="hi")


def test_a_broken_provider_does_not_take_down_the_tool_set() -> None:
    """One failing source must not cost the model every other tool."""

    def broken():
        raise RuntimeError("server went away")

    registry = ToolRegistry([echo_tool()], providers=[broken])

    assert [s.name for s in registry.specs()] == ["echo"]


def test_duplicate_static_registration_fails_loudly() -> None:
    """Silently shadowing would make which tool runs depend on registration
    order — a bug that only shows as the model getting the wrong answer."""
    registry = ToolRegistry([echo_tool()])

    with pytest.raises(DuplicateToolError):
        registry.register(echo_tool())


def test_a_disposer_removes_exactly_its_registration() -> None:
    registry = ToolRegistry()
    dispose = registry.register(echo_tool())

    assert len(registry.all()) == 1
    dispose()
    assert registry.all() == []
    dispose()  # idempotent


def test_static_tools_win_a_name_collision_with_a_provider() -> None:
    """Deterministic rather than an error: a remote source's names are not ours
    to control, and a collision must not break the turn."""
    registry = ToolRegistry([echo_tool()], providers=[lambda: [raising_tool("echo")]])

    assert len(registry.all()) == 1
    assert registry.get("echo") is not None
