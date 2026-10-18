"""The adapter's rules for odd streamed lines."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import JsonValue

from harness.llm import Completed, TextChunk, Usage
from tests.unit.test_openai_adapter import collect, delta, sse


def piece_frame(piece: dict[str, JsonValue]) -> str:
    return json.dumps({"choices": [{"delta": {"tool_calls": [piece]}}]})


def answering(*frames: str):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(*frames, "[DONE]"))

    return handler


async def test_an_index_sent_as_text_is_treated_as_no_index(monkeypatch) -> None:
    first = piece_frame({"index": 0, "id": "a", "function": {"name": "t", "arguments": "{"}})
    second = piece_frame({"index": "0", "id": "b", "function": {"name": "u", "arguments": "}"}})

    events = await collect(monkeypatch, answering(first, second))

    assert [(c.id, c.name, c.arguments) for c in events[-1].tool_calls] == [
        ("a", "t", "{"),
        ("b", "u", "}"),
    ]


async def test_an_id_sent_as_a_number_is_ignored(monkeypatch) -> None:
    frame = piece_frame({"index": 0, "id": 5, "function": {"name": "t", "arguments": "{}"}})

    events = await collect(monkeypatch, answering(frame))

    assert events[-1].tool_calls[0].id == "call_0"


async def test_a_token_count_sent_as_text_gives_no_usage(monkeypatch) -> None:
    frame = json.dumps({"choices": [], "usage": {"prompt_tokens": "7", "completion_tokens": "2"}})

    events = await collect(monkeypatch, answering(delta("ok"), frame))

    assert events[-1].usage is None


async def test_usage_from_an_earlier_line_is_kept(monkeypatch) -> None:
    counted = json.dumps({"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2}})

    events = await collect(monkeypatch, answering(counted, delta("ok")))

    assert events[-1].usage == Usage(input_tokens=7, output_tokens=2)


async def test_empty_text_gives_no_chunk(monkeypatch) -> None:
    empty = json.dumps({"choices": [{"delta": {"content": ""}}]})

    events = await collect(monkeypatch, answering(empty, delta("ok")))

    assert events == [TextChunk(text="ok"), Completed(full_text="ok")]


@pytest.mark.parametrize("error", [None, "", {}])
async def test_an_empty_error_is_not_an_error(monkeypatch, error: JsonValue) -> None:
    frame = json.dumps({"error": error, "choices": [{"delta": {"content": "ok"}}]})

    events = await collect(monkeypatch, answering(frame))

    assert events == [TextChunk(text="ok"), Completed(full_text="ok")]


async def test_lines_after_the_end_marker_are_ignored(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(delta("a"), "[DONE]", delta("b")))

    events = await collect(monkeypatch, handler)

    assert events == [TextChunk(text="a"), Completed(full_text="a")]


async def test_a_later_extra_content_replaces_the_earlier_one(monkeypatch) -> None:
    first = piece_frame(
        {"index": 0, "id": "g1", "function": {"name": "t"}, "extra_content": {"sig": "one"}}
    )
    second = piece_frame(
        {"index": 0, "function": {"arguments": "{}"}, "extra_content": {"sig": "two"}}
    )

    events = await collect(monkeypatch, answering(first, second))

    assert events[-1].tool_calls[0].extra_content == {"sig": "two"}


async def test_a_later_extra_content_that_is_not_an_object_keeps_the_earlier_one(
    monkeypatch,
) -> None:
    first = piece_frame(
        {"index": 0, "id": "g1", "function": {"name": "t"}, "extra_content": {"sig": "one"}}
    )
    second = piece_frame({"index": 0, "function": {"arguments": "{}"}, "extra_content": "two"})

    events = await collect(monkeypatch, answering(first, second))

    assert events[-1].tool_calls[0].extra_content == {"sig": "one"}


@pytest.mark.parametrize("frame", ["5", "null", '"text"', "[1]", '{"choices": [5]}'])
async def test_a_line_that_is_not_an_object_is_skipped(monkeypatch, frame: str) -> None:
    events = await collect(monkeypatch, answering(frame, delta("ok")))

    assert events == [TextChunk(text="ok"), Completed(full_text="ok")]
