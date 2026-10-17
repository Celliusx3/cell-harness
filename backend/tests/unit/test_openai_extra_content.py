"""A call's `extra_content`, such as Gemini's thought signature: kept, and sent back with it."""

from __future__ import annotations

import json

import httpx
from pydantic import JsonValue

from harness.llm.messages import AssistantMessage, ExtraContent, ToolCall, ToolMessage
from tests.unit.test_openai_adapter import collect, sse

SIGNED: ExtraContent = {"google": {"thought_signature": "sig"}}


def call_carrying(extra: JsonValue) -> str:
    """One frame carrying a whole call and its `extra_content`, the way Gemini 3 sends it."""
    piece = {
        "id": "g1",
        "type": "function",
        "function": {"name": "t", "arguments": "{}"},
        "extra_content": extra,
    }
    return json.dumps({"choices": [{"delta": {"tool_calls": [piece]}}]})


def answering(frame: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(frame, "[DONE]"))

    return handler


async def test_a_call_keeps_the_extra_content_it_arrived_with(monkeypatch) -> None:
    events = await collect(monkeypatch, answering(call_carrying(SIGNED)))

    assert events[-1].tool_calls == (
        ToolCall(id="g1", name="t", arguments="{}", extra_content=SIGNED),
    )


async def test_extra_content_that_is_not_an_object_is_not_kept(monkeypatch) -> None:
    events = await collect(monkeypatch, answering(call_carrying("sig")))

    assert events[-1].tool_calls == (ToolCall(id="g1", name="t", arguments="{}"),)


async def test_a_call_with_extra_content_is_sent_back_with_it(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, content=sse("[DONE]"))

    signed = ToolCall(id="g1", name="t", arguments="{}", extra_content=SIGNED)
    history = [
        AssistantMessage(content="", tool_calls=(signed,)),
        ToolMessage(tool_call_id="g1", content="ok"),
    ]
    await collect(monkeypatch, handler, messages=history)

    assert captured["messages"][0]["tool_calls"][0] == {
        "id": "g1",
        "type": "function",
        "function": {"name": "t", "arguments": "{}"},
        "extra_content": {"google": {"thought_signature": "sig"}},
    }
