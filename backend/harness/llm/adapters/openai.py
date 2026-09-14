"""OpenAI-compatible Chat Completions adapter.

Hand-rolled over `httpx` rather than the vendor SDK: the wire format we depend on
is four fields of one SSE frame, and an SDK would bring a second streaming
abstraction to translate into ours plus its own error taxonomy to map. The whole
adapter is the ~60 lines below.

"OpenAI-compatible" is the real target — the same endpoint shape is spoken by
DeepSeek, Together, vLLM, Ollama and others, so `base_url` is the only thing that
changes between them.

Every exit path yields exactly one terminal event. That is the contract in
`llm.client`, and it is why the request lives inside one `try` whose `except`
converts *any* transport failure into `Failed` rather than letting it propagate:
a provider being down is ordinary traffic on this channel, not a bug.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from harness.config.sections import LLMSettings
from harness.llm.adapters.openai_wire import wire_message, wire_tool
from harness.llm.client import LLMClient
from harness.llm.messages import Message, ToolCall, ToolSpec
from harness.llm.stream import (
    Completed,
    Failed,
    StreamEvent,
    TextChunk,
    ToolCallChunk,
    Usage,
)

logger = logging.getLogger("harness.llm.openai")

# The frame the SSE stream ends with. It is not JSON, so it must be recognized
# before parsing rather than after failing to parse.
_DONE = "[DONE]"


def _usage(payload: dict) -> Usage | None:
    """Token accounting from a chunk that carries it, or `None`.

    Only the final chunk has it, and only when the caller asked for it — hence
    `stream_options` in the request below. Absent stays absent: reporting zeros
    would claim the call was free.
    """
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None
    return Usage(input_tokens=prompt, output_tokens=completion)


def _delta(payload: dict) -> dict:
    """The `delta` object of this frame, or `{}`.

    Tolerant by construction. A frame with no choices, an empty delta, or a
    `null` content is normal — it is how a provider signals a role header, a
    finish reason, or a usage-only final frame — so none of those is an error
    worth failing a turn over.
    """
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    delta = choices[0].get("delta")
    return delta if isinstance(delta, dict) else {}


def _text(delta: dict) -> str:
    """The text this frame adds, or `""`."""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


class _ToolCallAccumulator:
    """Reassembles tool calls that arrive in fragments.

    A provider streams one call across many frames: the id and name usually
    arrive once, the `arguments` JSON string a few characters at a time. Frames
    carry an `index` rather than the id, because the id itself may not have
    arrived yet — so the index is the only thing that can group them.

    A call is *complete* when its `finish_reason` says so, which is a frame that
    carries no delta at all. Providers do not mark individual calls finished, so
    completion is a property of the whole response: `drain()` at the end. The
    `arguments` string is passed through untouched, never parsed — invalid JSON
    from the model is a tool failure it can recover from, and parsing here would
    turn it into a stream failure it cannot.
    """

    def __init__(self) -> None:
        self._by_index: dict[int, dict[str, str]] = {}

    def add(self, delta: dict) -> None:
        fragments = delta.get("tool_calls")
        if not isinstance(fragments, list):
            return
        for fragment in fragments:
            if not isinstance(fragment, dict):
                continue
            index = fragment.get("index")
            if not isinstance(index, int):
                # Without an index there is nothing to group this onto. Dropping
                # it loses a fragment; guessing would corrupt a sibling call.
                logger.warning("tool call fragment with no index: %r", fragment)
                continue
            call = self._by_index.setdefault(index, {"id": "", "name": "", "arguments": ""})
            if isinstance(fragment.get("id"), str):
                call["id"] = fragment["id"]
            function = fragment.get("function")
            if isinstance(function, dict):
                if isinstance(function.get("name"), str):
                    call["name"] = function["name"]
                if isinstance(function.get("arguments"), str):
                    call["arguments"] += function["arguments"]

    def drain(self) -> list[ToolCall]:
        """Every assembled call, in the index order the provider used.

        A call with no name is dropped: it cannot be dispatched, and inventing a
        name would send the model a result for something it never asked for. One
        with no id gets a synthetic one — the id only has to pair a call with its
        result within this turn, and refusing to run an otherwise valid call
        because the provider omitted an identifier helps nobody.
        """
        calls = []
        for index in sorted(self._by_index):
            call = self._by_index[index]
            if not call["name"]:
                logger.warning("dropping tool call fragment with no name: %r", call)
                continue
            calls.append(
                ToolCall(
                    id=call["id"] or f"call_{index}",
                    name=call["name"],
                    arguments=call["arguments"],
                )
            )
        return calls


class OpenAIClient(LLMClient):
    """Streams completions from an OpenAI-compatible endpoint."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        settings = self._settings
        body: dict = {
            "model": model,
            "messages": [wire_message(m) for m in messages],
            "temperature": settings.temperature,
            "stream": True,
            # Without this, a streamed response reports no usage at all.
            "stream_options": {"include_usage": True},
        }
        if tools:
            # Omitted entirely rather than sent empty: some providers reject
            # `"tools": []`, and an empty list says something different from
            # "this call has no tools available".
            body["tools"] = [wire_tool(t) for t in tools]

        accumulated = ""
        usage: Usage | None = None
        calls = _ToolCallAccumulator()
        try:
            async with (
                httpx.AsyncClient(timeout=settings.timeout_seconds) as http,
                http.stream(
                    "POST",
                    f"{settings.base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.api_key}"},
                    json=body,
                ) as response,
            ):
                if response.status_code >= 400:
                    # The body must be read before it can be reported: `stream`
                    # gives us headers first, and the detail we need is downstream.
                    detail = (await response.aread()).decode(errors="replace")
                    yield Failed(reason=f"provider returned {response.status_code}: {detail}")
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if data == _DONE:
                        break
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        # One unparseable frame is not worth killing a turn that
                        # is otherwise streaming fine; the text it carried is
                        # lost and the rest continues.
                        logger.warning("skipping unparseable SSE frame: %r", data)
                        continue
                    usage = _usage(payload) or usage
                    delta = _delta(payload)
                    calls.add(delta)
                    text = _text(delta)
                    if text:
                        accumulated += text
                        yield TextChunk(text=text)
        except httpx.HTTPError as err:
            # Includes timeouts, DNS failures, and a connection dropped
            # mid-stream. Whatever was accumulated is discarded: the caller gets
            # one terminal, and a partial answer presented as complete is worse
            # than none. The loop preserves the streamed prefix from the chunks
            # it already saw.
            yield Failed(reason=f"{type(err).__name__}: {err}")
            return

        # Calls are announced only once the whole response is in — a fragment is
        # not something a consumer can act on, and the provider never says which
        # individual call is finished.
        assembled = calls.drain()
        for call in assembled:
            yield ToolCallChunk(call=call)
        yield Completed(full_text=accumulated, tool_calls=tuple(assembled), usage=usage)
