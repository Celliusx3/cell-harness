"""Select, then call: a schema the model has read is a tool it may call."""

from __future__ import annotations

import json
from contextlib import aclosing

from harness.llm import Text, ToolCall, ToolMessage, ToolReference, text_of
from harness.llm.adapters.openai._request import openai_messages
from harness.runtime.service import Runtime
from harness.session.models import ToolResultEvent
from harness.tools import Ok, Tool, ToolService, Toolset
from harness.tools.native.code_mode import (
    EXECUTE_TYPESCRIPT,
    GET_FUNCTION_DETAILS,
    LIST_FUNCTIONS,
    code_mode_tools,
)
from harness.tools.toolset import MAX_TOOLS_SELECTED
from tests.unit.code_fakes import FakeRunner
from tests.unit.fakes import SteppedClient, calls_tool, completed, echo_tool
from tests.unit.helpers import ORIGIN, new_session, no_approvals, no_progress

DEFAULTS = (LIST_FUNCTIONS, GET_FUNCTION_DETAILS, EXECUTE_TYPESCRIPT)


def selected(*names: str, call_id: str = "d") -> ToolResultEvent:
    """A result that made `names` callable — what the details tool logs."""
    blocks = (Text(text="…"), *(ToolReference(tool_name=name) for name in names))
    return ToolResultEvent(
        turn=1, step=1, message=ToolMessage(tool_call_id=call_id, content=blocks)
    )


def toolset(*tools: Tool) -> Toolset:
    """Code mode's three plus `tools`, offering the three — as the product does."""
    tool_service = ToolService(tools, approvals=no_approvals())
    for made in code_mode_tools(
        tool_service=tool_service, runner=FakeRunner(), withheld=frozenset()
    ):
        tool_service.register(made)
    return Toolset(tool_service, DEFAULTS)


def named(built: Toolset, tools_selected: tuple[str, ...]) -> list[str]:
    return [spec.name for spec in built.specs(tools_selected)]


async def test_details_states_what_it_made_callable() -> None:
    built = toolset(echo_tool("a"), echo_tool("b"))

    outcome = await built.execute(
        ToolCall(
            id="c1", name=GET_FUNCTION_DETAILS, arguments=json.dumps({"names": ["a", "ghost"]})
        ),
        progress=no_progress,
        origin=ORIGIN,
        session=new_session(),
    )

    assert isinstance(outcome, Ok)
    references = [b for b in outcome.content if isinstance(b, ToolReference)]
    assert references == [ToolReference(tool_name="a")]
    assert "tool list" not in outcome.text


def test_an_ordinary_result_references_nothing() -> None:
    assert Ok("hi").content == (Text(text="hi"),)


def test_the_adapter_spells_a_reference_out_for_a_wire_without_blocks() -> None:
    message = ToolMessage(
        tool_call_id="c1", content=(Text(text="declare …"), ToolReference(tool_name="a"))
    )

    wire = openai_messages([message], {})[0]

    assert wire["role"] == "tool" and wire["tool_call_id"] == "c1"
    assert wire["content"].startswith("declare …")
    assert "Now in your tool list, callable directly: a" in wire["content"]


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
    built = toolset(*(echo_tool(f"t{n}") for n in range(10)))
    history = tuple(f"t{n}" for n in range(10))

    offered = named(built, history)

    assert offered == [*DEFAULTS, *sorted(f"t{n}" for n in range(2, 10))]
    assert len(offered) - len(DEFAULTS) == MAX_TOOLS_SELECTED


def test_re_selecting_an_evicted_tool_brings_it_back() -> None:
    built = toolset(*(echo_tool(f"t{n}") for n in range(10)))
    history = tuple(f"t{n}" for n in range(1, 10)) + ("t0",)

    offered = named(built, history)

    assert "t0" in offered and "t3" in offered
    assert "t1" not in offered and "t2" not in offered


def test_a_selected_tool_joins_the_offer_after_the_defaults_sorted() -> None:
    built = toolset(echo_tool("b"), echo_tool("a"))

    assert named(built, ("b", "a")) == [*DEFAULTS, "a", "b"]


def test_a_selected_tool_whose_server_has_gone_stays_out() -> None:
    built = toolset(echo_tool("a"))

    assert named(built, ("gone",)) == list(DEFAULTS)


def test_a_default_tool_the_model_selects_is_offered_once() -> None:
    built = toolset(echo_tool("a"))

    assert named(built, (EXECUTE_TYPESCRIPT, "a")) == [*DEFAULTS, "a"]


async def test_a_selected_tool_may_be_called_and_an_unselected_one_is_told_to_select() -> None:
    built = toolset(echo_tool("a"))
    call = ToolCall(id="c1", name="a", arguments='{"value": "hi"}')

    read_it = new_session()
    read_it.append(selected("a"))

    refused = await built.execute(call, progress=no_progress, origin=ORIGIN, session=new_session())
    allowed = await built.execute(call, progress=no_progress, origin=ORIGIN, session=read_it)

    assert "get_function_details" in str(refused)
    assert isinstance(allowed, Ok) and allowed.text == "hi"


async def test_reading_a_schema_in_one_step_offers_the_tool_in_the_next() -> None:
    client = SteppedClient(
        calls_tool(GET_FUNCTION_DETAILS, json.dumps({"names": ["a"]})),
        calls_tool("a", '{"value": "direct"}'),
        completed("done"),
    )
    runtime = Runtime(model="m", client=client, images=None, tools=toolset(echo_tool("a")))
    session = new_session()

    async with aclosing(runtime.run("go", session=session, bot_id="b")) as events:
        async for _ in events:
            pass

    offered = [[s.name for s in specs] for specs in client.seen_tools_per_call]
    assert offered[0] == list(DEFAULTS)
    assert offered[1] == [*DEFAULTS, "a"]
    assert offered[2] == [*DEFAULTS, "a"]
    results = [e for e in session.events() if e.type == "tool/result"]
    assert ToolReference(tool_name="a") in results[0].message.content
    assert results[1].error is None and text_of(results[1].message.content) == "direct"


async def test_a_direct_call_before_selecting_is_refused_and_logged() -> None:
    client = SteppedClient(calls_tool("a", '{"value": "direct"}'), completed("ok"))
    runtime = Runtime(model="m", client=client, images=None, tools=toolset(echo_tool("a")))
    session = new_session()

    async with aclosing(runtime.run("go", session=session, bot_id="b")) as events:
        async for _ in events:
            pass

    (result,) = [e for e in session.events() if e.type == "tool/result"]
    assert result.error is not None
    assert not any(isinstance(b, ToolReference) for b in result.message.content)
    assert "get_function_details" in text_of(result.message.content)
