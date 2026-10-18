"""OpenAI-compatible Chat Completions adapter."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable, Sequence

import httpx

from harness.config.sections import LLMSettings
from harness.llm.adapters.errors import failure_code
from harness.llm.adapters.openai_calls import ToolCallAccumulator
from harness.llm.adapters.openai_wire import wire_messages, wire_tool
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


def _usage(payload: dict) -> Usage | None:
    """Token accounting from a chunk that carries it, or `None`."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None
    return Usage(input_tokens=prompt, output_tokens=completion)


def _delta(payload: dict) -> dict:
    """The `delta` object of this frame, or `{}`."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    choice = choices[0]
    delta = choice.get("delta") if isinstance(choice, dict) else None
    return delta if isinstance(delta, dict) else {}


def _text(delta: dict) -> str:
    """The text this frame adds, or `""`."""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


class OpenAIClient(LLMClient):
    """Streams completions from an OpenAI-compatible endpoint."""

    def __init__(self, settings: LLMSettings, *, read_image: ImageReader) -> None:
        self._settings = settings
        self._read_image = read_image

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None
    ) -> AsyncIterator[StreamEvent]:
        settings = self._settings
        image_bytes = _image_bytes(messages, self._read_image)
        body: dict = {
            "model": model,
            "messages": wire_messages(messages, image_bytes),
            "temperature": settings.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            # Some providers reject `"tools": []`, so the key is omitted when empty.
            body["tools"] = [wire_tool(t) for t in tools]

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
                    if payload.get("error"):
                        yield Failed(
                            reason=f"provider sent an error: {data}", code=failure_code(data)
                        )
                        return
                    usage = _usage(payload) or usage
                    delta = _delta(payload)
                    calls.add(delta)
                    text = _text(delta)
                    if text:
                        accumulated += text
                        yield TextChunk(text=text)
        except httpx.HTTPError as err:
            yield Failed(reason=f"{type(err).__name__}: {err}")
            return

        assembled = calls.tool_calls()
        for call in assembled:
            yield ToolCallChunk(call=call)
        yield Completed(full_text=accumulated, tool_calls=tuple(assembled), usage=usage)
