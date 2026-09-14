"""Select, then call: a schema the model has read is a tool it may call.

The Anthropic shape: the tool that selects (`get_function_details`) answers
with `tool_reference` blocks in its result; the log carries them;
`Session.tools_selected()` folds them out of history; the pipeline offers those
tools and its gate accepts them; the adapter tells the model in words. So a
model that never writes a program still reaches every capability by reading
first, and no layer has to know which tool does the selecting.
"""

from __future__ import annotations

import json
from contextlib import aclosing

from harness.agent.loop import LoopAgent
from harness.llm.adapters.openai_wire import wire_message
from harness.llm.messages import Text, ToolCall, ToolMessage, ToolReference
from harness.session.models import ToolResultEvent
from harness.tools.definition import Ok, ToolDefinition
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.code import DETAILS, EXECUTE, LIST, code_mode_tools
from harness.tools.pipeline import MAX_TOOLS_SELECTED, ToolPipeline
from harness.tools.registry import ToolRegistry
from tests.unit.code_fakes import FakeRunner
from tests.unit.fakes import SteppedClient, calls_tool, completed, echo_tool
from tests.unit.helpers import new_session, no_progress

DEFAULTS = (LIST, DETAILS, EXECUTE)


def selected(*names: str, call_id: str = "d") -> ToolResultEvent:
    """A result that made `names` callable — what the details tool logs."""
    blocks = (Text(text="…"), *(ToolReference(tool_name=name) for name in names))
    return ToolResultEvent(
        turn=1, step=1, message=ToolMessage(tool_call_id=call_id, content=blocks)
    )


def pipeline(*tools: ToolDefinition) -> ToolPipeline:
    """Code mode's three plus `tools`, offering the three — as the product does."""
    registry = ToolRegistry(tools)
    dispatcher = ToolDispatcher(registry)
    for made in code_mode_tools(registry=registry, dispatcher=dispatcher, runtime=FakeRunner()):
        registry.register(made)
    return ToolPipeline(registry, dispatcher, DEFAULTS)


def named(built: ToolPipeline, tools_selected: tuple[str, ...]) -> list[str]:
    return [spec.name for spec in built.specs(tools_selected)]


# ── the tool states what it selected ──────────────────────────────────────────


async def test_details_states_what_it_made_callable() -> None:
    built = pipeline(echo_tool("a"), echo_tool("b"))

    outcome = await built.execute(
        ToolCall(id="c1", name=DETAILS, arguments=json.dumps({"names": ["a", "ghost"]})),
        progress=no_progress,
    )

    assert isinstance(outcome, Ok)
    references = [b for b in outcome.content if isinstance(b, ToolReference)]
    assert references == [ToolReference(tool_name="a")]  # not `ghost`: only what was found
    assert "tool list" not in outcome.text  # the tool states the fact; the adapter tells the model


def test_an_ordinary_result_references_nothing() -> None:
    assert Ok("hi").content == (Text(text="hi"),)


def test_the_adapter_spells_a_reference_out_for_a_wire_without_blocks() -> None:
    """Anthropic's API expands `tool_reference` into the tool list itself; this
    endpoint cannot, so the sentence is how the model learns its list changed."""
    message = ToolMessage(
        tool_call_id="c1", content=(Text(text="declare …"), ToolReference(tool_name="a"))
    )

    wire = wire_message(message)

    assert wire["role"] == "tool" and wire["tool_call_id"] == "c1"
    assert wire["content"].startswith("declare …")
    assert "Now in your tool list, callable directly: a" in wire["content"]


# ── the session folds it ──────────────────────────────────────────────────────


def test_the_session_folds_selections_from_every_result() -> None:
    session = new_session()
    session.append(selected("a", "b"))
    session.append(selected("c", call_id="d2"))

    assert session.tools_selected() == ("a", "b", "c")


def test_a_session_that_selected_nothing_has_nothing() -> None:
    assert new_session().tools_selected() == ()


def test_a_re_selection_moves_a_name_to_the_end() -> None:
    session = new_session()
    session.append(selected("a", "b"))
    session.append(selected("a", call_id="d2"))

    assert session.tools_selected() == ("b", "a")


def test_the_request_carries_only_the_most_recent_selections() -> None:
    """Bounded in the pipeline, or a long conversation ends up carrying the
    catalog. The log keeps the whole history; the request does not."""
    built = pipeline(*(echo_tool(f"t{n}") for n in range(10)))
    history = tuple(f"t{n}" for n in range(10))

    offered = named(built, history)

    assert offered == [*DEFAULTS, *sorted(f"t{n}" for n in range(2, 10))]
    assert len(offered) - len(DEFAULTS) == MAX_TOOLS_SELECTED


def test_re_selecting_an_evicted_tool_brings_it_back() -> None:
    """The session's fold moved `t0` to the end; the pipeline's window then keeps
    it and drops the oldest instead."""
    built = pipeline(*(echo_tool(f"t{n}") for n in range(10)))
    history = tuple(f"t{n}" for n in range(1, 10)) + ("t0",)  # t0 selected again, last

    offered = named(built, history)

    assert "t0" in offered and "t3" in offered
    assert "t1" not in offered and "t2" not in offered  # the two oldest fall off


# ── the offer and the gate ────────────────────────────────────────────────────


def test_a_selected_tool_joins_the_offer_after_the_defaults_sorted() -> None:
    built = pipeline(echo_tool("b"), echo_tool("a"))

    assert named(built, ("b", "a")) == [*DEFAULTS, "a", "b"]


def test_a_selected_tool_whose_server_has_gone_stays_out() -> None:
    built = pipeline(echo_tool("a"))

    assert named(built, ("gone",)) == list(DEFAULTS)


async def test_a_selected_tool_may_be_called_and_an_unselected_one_is_told_to_select() -> None:
    built = pipeline(echo_tool("a"))
    call = ToolCall(id="c1", name="a", arguments='{"value": "hi"}')

    refused = await built.execute(call, progress=no_progress)
    allowed = await built.execute(call, progress=no_progress, tools_selected=("a",))

    assert "get_function_details" in str(refused)
    assert isinstance(allowed, Ok) and allowed.text == "hi"


# ── through the loop ──────────────────────────────────────────────────────────


async def test_reading_a_schema_in_one_step_offers_the_tool_in_the_next() -> None:
    """The whole feature, end to end: the model reads `a`'s schema, the log line
    says so, and the very next request carries `a` — whose direct call runs."""
    client = SteppedClient(
        calls_tool(DETAILS, json.dumps({"names": ["a"]})),
        calls_tool("a", '{"value": "direct"}'),
        completed("done"),
    )
    agent = LoopAgent(name="t", model="m", client=client, tools=pipeline(echo_tool("a")))
    session = new_session()

    async with aclosing(agent.run("go", session=session)) as events:
        async for _ in events:
            pass

    offered = [[s.name for s in specs] for specs in client.seen_tools_per_call]
    assert offered[0] == list(DEFAULTS)
    assert offered[1] == [*DEFAULTS, "a"]
    assert offered[2] == [*DEFAULTS, "a"]
    results = [e for e in session.events() if e.type == "tool/result"]
    assert ToolReference(tool_name="a") in results[0].message.content  # the log line states it
    assert results[1].error is None and results[1].message.text == "direct"


async def test_a_direct_call_before_selecting_is_refused_and_logged() -> None:
    client = SteppedClient(calls_tool("a", '{"value": "direct"}'), completed("ok"))
    agent = LoopAgent(name="t", model="m", client=client, tools=pipeline(echo_tool("a")))
    session = new_session()

    async with aclosing(agent.run("go", session=session)) as events:
        async for _ in events:
            pass

    (result,) = [e for e in session.events() if e.type == "tool/result"]
    assert result.error is not None
    assert not any(isinstance(b, ToolReference) for b in result.message.content)
    assert "get_function_details" in result.message.text
