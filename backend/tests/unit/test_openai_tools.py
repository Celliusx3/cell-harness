"""The adapter's tool-call handling: fragment reassembly and the wire shape."""

from __future__ import annotations

import json

import httpx
import pytest

from harness.llm.messages import AssistantMessage, ToolCall, ToolMessage, ToolSpec, UserMessage
from harness.llm.stream import Completed, ToolCallChunk
from tests.unit.test_openai_adapter import collect, sse


def fragment(
    index: int, *, id: str | None = None, name: str | None = None, args: str | None = None
) -> str:
    """One `tool_calls` delta frame, with only the parts that arrived."""
    function: dict = {}
    if name is not None:
        function["name"] = name
    if args is not None:
        function["arguments"] = args
    piece: dict = {"index": index}
    if id is not None:
        piece["id"] = id
    if function:
        piece["function"] = function
    return json.dumps({"choices": [{"delta": {"tool_calls": [piece]}}]})


async def test_a_call_split_across_frames_is_reassembled(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse(
                fragment(0, id="call_a", name="get_current_time"),
                fragment(0, args='{"timez'),
                fragment(0, args='one": "UTC"}'),
                "[DONE]",
            ),
        )

    events = await collect(monkeypatch, handler)

    expected = ToolCall(id="call_a", name="get_current_time", arguments='{"timezone": "UTC"}')
    assert events == [ToolCallChunk(call=expected), Completed(full_text="", tool_calls=(expected,))]


async def test_two_calls_are_grouped_by_index_not_arrival_order(monkeypatch) -> None:

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse(
                fragment(0, id="a", name="first"),
                fragment(1, id="b", name="second"),
                fragment(1, args='{"x":'),
                fragment(0, args='{"y":'),
                fragment(1, args=" 2}"),
                fragment(0, args=" 1}"),
                "[DONE]",
            ),
        )

    events = await collect(monkeypatch, handler)

    assert events[-1].tool_calls == (
        ToolCall(id="a", name="first", arguments='{"y": 1}'),
        ToolCall(id="b", name="second", arguments='{"x": 2}'),
    )


async def test_arguments_are_never_parsed_by_the_adapter(monkeypatch) -> None:

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse(fragment(0, id="a", name="t", args="{not json"), "[DONE]"),
        )

    events = await collect(monkeypatch, handler)

    assert events[-1].tool_calls[0].arguments == "{not json"


async def test_a_call_with_no_name_is_dropped(monkeypatch) -> None:

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(fragment(0, id="a", args="{}"), "[DONE]"))

    events = await collect(monkeypatch, handler)

    assert events == [Completed(full_text="")]


async def test_a_call_with_no_id_gets_a_synthetic_one(monkeypatch) -> None:

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(fragment(0, name="t", args="{}"), "[DONE]"))

    events = await collect(monkeypatch, handler)

    assert events[-1].tool_calls[0].id == "call_0"


@pytest.mark.parametrize(
    "frame",
    [
        json.dumps({"choices": [{"delta": {"tool_calls": "not-a-list"}}]}),
        json.dumps({"choices": [{"delta": {"tool_calls": ["not-an-object"]}}]}),
        json.dumps({"choices": [{"delta": {"tool_calls": [{"no": "index"}]}}]}),
    ],
)
async def test_malformed_fragments_do_not_kill_the_stream(monkeypatch, frame: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=sse(frame, fragment(0, id="a", name="t", args="{}"), "[DONE]")
        )

    events = await collect(monkeypatch, handler)

    assert events[-1].tool_calls[0].name == "t"


async def test_text_and_calls_can_arrive_in_the_same_response(monkeypatch) -> None:
    text = json.dumps({"choices": [{"delta": {"content": "Let me check. "}}]})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=sse(text, fragment(0, id="a", name="t", args="{}"), "[DONE]")
        )

    events = await collect(monkeypatch, handler)

    assert events[-1].full_text == "Let me check. "
    assert events[-1].tool_calls[0].name == "t"


async def test_tool_specs_are_sent_in_the_provider_shape(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, content=sse("[DONE]"))

    spec = ToolSpec(name="t", description="d", input_schema={"type": "object"})
    await collect(monkeypatch, handler, tools=[spec])

    assert captured["tools"] == [
        {
            "type": "function",
            "function": {"name": "t", "description": "d", "parameters": {"type": "object"}},
        }
    ]


async def test_no_tools_means_the_field_is_absent(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, content=sse("[DONE]"))

    await collect(monkeypatch, handler, tools=[])

    assert "tools" not in captured


async def test_assistant_tool_calls_are_nested_for_the_wire(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, content=sse("[DONE]"))

    history = [
        UserMessage(content="q"),
        AssistantMessage(
            content="checking",
            tool_calls=(ToolCall(id="c1", name="t", arguments="{}"),),
        ),
        ToolMessage(tool_call_id="c1", content="42"),
    ]
    await collect(monkeypatch, handler, messages=history)

    assert captured["messages"][1] == {
        "role": "assistant",
        "content": "checking",
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "t", "arguments": "{}"}}
        ],
    }
    assert captured["messages"][2] == {"role": "tool", "tool_call_id": "c1", "content": "42"}


async def test_an_assistant_message_without_calls_omits_the_field(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, content=sse("[DONE]"))

    await collect(monkeypatch, handler, messages=[AssistantMessage(content="hi")])

    assert captured["messages"][0] == {"role": "assistant", "content": "hi"}


@pytest.mark.parametrize("arguments", ["", "   ", "{not json"])
async def test_unparseable_arguments_are_replayed_as_an_empty_object(
    monkeypatch, arguments: str
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, content=sse("[DONE]"))

    history = [
        AssistantMessage(
            content="", tool_calls=(ToolCall(id="c1", name="t", arguments=arguments),)
        ),
        ToolMessage(tool_call_id="c1", content="error: invalid arguments"),
    ]
    await collect(monkeypatch, handler, messages=history)

    assert captured["messages"][0]["tool_calls"][0]["function"]["arguments"] == "{}"


async def test_valid_arguments_are_replayed_byte_for_byte(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, content=sse("[DONE]"))

    raw = '{ "b": 1,\n"a": [ ] }'
    history = [
        AssistantMessage(content="", tool_calls=(ToolCall(id="c1", name="t", arguments=raw),)),
        ToolMessage(tool_call_id="c1", content="ok"),
    ]
    await collect(monkeypatch, handler, messages=history)

    assert captured["messages"][0]["tool_calls"][0]["function"]["arguments"] == raw
