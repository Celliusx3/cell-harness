"""The OpenAI adapter: SSE parsing, and the one-terminal contract.

Driven through `httpx.MockTransport` rather than a stubbed client object, so the
bytes-to-events path is the one under test — that is where the tolerance rules
live, and none of them are exercised by a fake that hands over dicts.
"""

from __future__ import annotations

import json

import httpx
import pytest

from harness.config.settings import LLMSettings
from harness.llm.adapters import openai as adapter_module
from harness.llm.adapters.openai import OpenAIClient
from harness.llm.messages import UserMessage
from harness.llm.stream import Completed, Failed, TextChunk


def settings() -> LLMSettings:
    return LLMSettings(_env_file=None, api_key="k", model="m", base_url="https://x/v1")


def sse(*frames: str) -> bytes:
    return "".join(f"data: {f}\n\n" for f in frames).encode()


def delta(text: str) -> str:
    return json.dumps({"choices": [{"delta": {"content": text}}]})


def client_over(handler) -> OpenAIClient:
    """An `OpenAIClient` whose httpx calls hit `handler`.

    Patches the module's `httpx.AsyncClient` rather than injecting a transport,
    because the adapter deliberately owns its client's lifetime (one per call,
    closed on exit) and threading a transport through would change that.
    """
    real = httpx.AsyncClient

    def factory(**kwargs):
        return real(transport=httpx.MockTransport(handler), **kwargs)

    return factory, OpenAIClient(settings())


async def collect(monkeypatch, handler, messages=None, tools=None) -> list:
    factory, client = client_over(handler)
    monkeypatch.setattr(adapter_module.httpx, "AsyncClient", factory)
    stream = client.stream_completion(messages or [UserMessage(content="hi")], "m", tools=tools)
    return [event async for event in stream]


async def test_streams_chunks_then_one_completed(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(delta("he"), delta("llo"), "[DONE]"))

    events = await collect(monkeypatch, handler)

    assert events == [
        TextChunk(text="he"),
        TextChunk(text="llo"),
        Completed(full_text="hello"),
    ]


async def test_usage_is_read_from_the_final_frame(monkeypatch) -> None:
    usage = json.dumps({"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2}})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(delta("ok"), usage, "[DONE]"))

    events = await collect(monkeypatch, handler)

    assert events[-1].usage.input_tokens == 7
    assert events[-1].usage.output_tokens == 2


@pytest.mark.parametrize(
    "frame",
    [
        json.dumps({"choices": [], "usage": None}),
        json.dumps({"choices": [], "usage": {"prompt_tokens": "seven"}}),
        json.dumps({"choices": [], "usage": {"prompt_tokens": 7}}),  # half-reported
        json.dumps({"choices": []}),
    ],
)
async def test_absent_or_malformed_usage_stays_none(monkeypatch, frame: str) -> None:
    """Not zero: "not reported" and "cost nothing" are different facts."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(delta("ok"), frame, "[DONE]"))

    events = await collect(monkeypatch, handler)

    assert events[-1].usage is None


@pytest.mark.parametrize(
    "frame",
    [
        json.dumps({"choices": []}),  # usage-only frame
        json.dumps({"choices": [{"delta": {}}]}),  # role header
        json.dumps({"choices": [{"delta": {"content": None}}]}),  # finish reason
        json.dumps({"choices": [{"delta": "not-an-object"}]}),  # malformed
        json.dumps({"choices": "not-a-list"}),  # malformed
        json.dumps({}),  # no choices key at all
    ],
)
async def test_empty_frames_are_normal_traffic_not_errors(monkeypatch, frame: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(frame, delta("ok"), "[DONE]"))

    events = await collect(monkeypatch, handler)

    assert events == [TextChunk(text="ok"), Completed(full_text="ok")]


async def test_one_unparseable_frame_does_not_kill_the_turn(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(delta("a"), "{not json", delta("b"), "[DONE]"))

    events = await collect(monkeypatch, handler)

    assert events == [TextChunk(text="a"), TextChunk(text="b"), Completed(full_text="ab")]


async def test_http_error_becomes_failed_with_the_body(monkeypatch) -> None:
    """The reason is user-facing, so it carries the provider's detail in full."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, content=b'{"error":"rate limited, retry in 20s"}')

    events = await collect(monkeypatch, handler)

    assert len(events) == 1
    assert isinstance(events[0], Failed)
    assert "429" in events[0].reason
    assert "retry in 20s" in events[0].reason


async def test_transport_failure_becomes_failed_not_an_exception(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    events = await collect(monkeypatch, handler)

    assert events == [Failed(reason="ConnectError: no route to host")]


async def test_request_pins_temperature_and_asks_for_usage(monkeypatch) -> None:
    """Both are deliberate: an unpinned temperature inherits whatever the
    provider currently defaults to, and without `stream_options` a streamed
    response reports no usage at all."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, content=sse("[DONE]"))

    await collect(monkeypatch, handler)

    assert captured["temperature"] == 1.0
    assert captured["stream_options"] == {"include_usage": True}
    assert captured["stream"] is True
