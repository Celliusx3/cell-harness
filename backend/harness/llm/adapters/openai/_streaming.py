"""The streamed Chat Completions lines, each read once into a typed chunk."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Mapping

from pydantic import JsonValue, TypeAdapter, ValidationError

from harness.llm.adapters.openai.models.chunk import Chunk
from harness.llm.adapters.openai.models.tool_delta import ToolDelta
from harness.llm.models.stream import Usage
from harness.llm.models.tools import ExtraContent

logger = logging.getLogger("harness.llm.openai")

_DONE = "[DONE]"

_EXTRA_CONTENT = TypeAdapter(ExtraContent)


async def chunks_of(lines: AsyncIterator[str]) -> AsyncIterator[Chunk]:
    """The chunk of each `data: ` line before `[DONE]`, skipping one that is not a JSON object."""
    async for line in lines:
        if not line.startswith("data: "):
            continue
        data = line.removeprefix("data: ").strip()
        if data == _DONE:
            return
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("skipping unparseable SSE frame: %r", data)
            continue
        if not isinstance(payload, dict):
            logger.warning("skipping SSE frame that is not an object: %r", data)
            continue
        yield chunk_of(payload, data)


def chunk_of(parsed: dict[str, JsonValue], line: str) -> Chunk:
    """The chunk one line says, from `parsed`, its JSON, each field of the wrong type left out."""
    if parsed.get("error"):
        return Chunk(text="", tool_deltas=(), usage=None, error=line)
    delta = _delta(parsed)
    content = delta.get("content")
    return Chunk(
        text=content if isinstance(content, str) else "",
        tool_deltas=_tool_deltas(delta),
        usage=_usage(parsed),
        error=None,
    )


def _usage(payload: Mapping[str, JsonValue]) -> Usage | None:
    """Token accounting from a line that carries it, or `None`."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None
    return Usage(input_tokens=prompt, output_tokens=completion)


def _delta(payload: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
    """The `delta` object of the line's first choice, or `{}`."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    choice = choices[0]
    delta = choice.get("delta") if isinstance(choice, dict) else None
    return delta if isinstance(delta, dict) else {}


def _tool_deltas(delta: Mapping[str, JsonValue]) -> tuple[ToolDelta, ...]:
    """Each tool call fragment in `delta` that is an object."""
    items = delta.get("tool_calls")
    if not isinstance(items, list):
        return ()
    return tuple(_tool_delta(item) for item in items if isinstance(item, dict))


def _tool_delta(raw: Mapping[str, JsonValue]) -> ToolDelta:
    """One fragment, each field kept only when it has the type the wire promises."""
    function = raw.get("function")
    fields = function if isinstance(function, dict) else {}
    index, call_id = raw.get("index"), raw.get("id")
    name, arguments = fields.get("name"), fields.get("arguments")
    return ToolDelta(
        index=index if isinstance(index, int) else None,
        id=call_id if isinstance(call_id, str) else None,
        name=name if isinstance(name, str) else None,
        arguments=arguments if isinstance(arguments, str) else None,
        extra_content=_extra_content(raw),
    )


def _extra_content(raw: Mapping[str, JsonValue]) -> ExtraContent | None:
    """The fragment's `extra_content`, such as Gemini's thought signature, when it is an object."""
    value = raw.get("extra_content")
    if value is None:
        return None
    try:
        return _EXTRA_CONTENT.validate_python(value)
    except ValidationError:
        logger.warning("dropped a tool call's extra_content that is not an object: %r", value)
        return None
