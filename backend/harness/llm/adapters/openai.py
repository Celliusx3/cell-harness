"""OpenAI-compatible Chat Completions adapter."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable, Sequence

import httpx

from harness.config.sections import LLMSettings
from harness.llm.adapters.errors import failure_code
from harness.llm.adapters.openai_calls import ToolCallAccumulator
from harness.llm.adapters.openai_frames import frame_of
from harness.llm.adapters.openai_wire import JsonObject, wire_messages, wire_tool
from harness.llm.client import LLMClient
from harness.llm.messages import Image, Message, ToolSpec, images_of
from harness.llm.stream import (
    Completed,
    Failed,
    StreamEvent,
    TextChunk,
    ToolCallChunk,
    Usage,
)

logger = logging.getLogger("harness.llm.openai")

_DONE = "[DONE]"

ImageReader = Callable[[Image], bytes | None]


def _image_bytes(messages: Sequence[Message], read: ImageReader) -> dict[str, bytes]:
    """The bytes of each image the request shows that `read` could read, by hash."""
    return {
        image.sha256: data
        for message in messages
        for image in images_of(message)
        if (data := read(image)) is not None
    }


def _request_body(
    model: str, messages: list[JsonObject], tools: list[ToolSpec] | None, temperature: float
) -> JsonObject:
    """The streamed completion request, asking for usage, with tools only when there are some."""
    body: JsonObject = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        # Some providers reject `"tools": []`, so the key is omitted when empty.
        body["tools"] = [wire_tool(t) for t in tools]
    return body


class OpenAIClient(LLMClient):
    """Streams completions from an OpenAI-compatible endpoint."""

    def __init__(self, settings: LLMSettings, *, read_image: ImageReader) -> None:
        self._settings = settings
        self._read_image = read_image

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None
    ) -> AsyncIterator[StreamEvent]:
        settings = self._settings
        body = _request_body(
            model,
            wire_messages(messages, _image_bytes(messages, self._read_image)),
            tools,
            settings.temperature,
        )

        accumulated = ""
        usage: Usage | None = None
        calls = ToolCallAccumulator()
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
                    detail = (await response.aread()).decode(errors="replace")
                    yield Failed(
                        reason=f"provider returned {response.status_code}: {detail}",
                        code=failure_code(detail),
                    )
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
                        logger.warning("skipping unparseable SSE frame: %r", data)
                        continue
                    if not isinstance(payload, dict):
                        logger.warning("skipping SSE frame that is not an object: %r", data)
                        continue
                    frame = frame_of(payload)
                    if frame.failed:
                        yield Failed(
                            reason=f"provider sent an error: {data}", code=failure_code(data)
                        )
                        return
                    usage = frame.usage or usage
                    calls.add(frame.pieces)
                    if frame.text:
                        accumulated += frame.text
                        yield TextChunk(text=frame.text)
        except httpx.HTTPError as err:
            yield Failed(reason=f"{type(err).__name__}: {err}")
            return

        assembled = calls.tool_calls()
        for call in assembled:
            yield ToolCallChunk(call=call)
        yield Completed(full_text=accumulated, tool_calls=tuple(assembled), usage=usage)
