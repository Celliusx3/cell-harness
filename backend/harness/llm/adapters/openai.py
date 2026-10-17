"""OpenAI-compatible Chat Completions adapter."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from harness.config.sections import LLMSettings
from harness.llm.adapters.errors import classify
from harness.llm.adapters.openai_calls import ToolCallAccumulator
from harness.llm.adapters.openai_wire import wire_message, wire_tool
from harness.llm.client import LLMClient
from harness.llm.messages import Message, ToolSpec
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
    delta = choices[0].get("delta")
    return delta if isinstance(delta, dict) else {}


def _text(delta: dict) -> str:
    """The text this frame adds, or `""`."""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


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
                        code=classify(detail),
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
                    if payload.get("error"):
                        yield Failed(reason=f"provider sent an error: {data}", code=classify(data))
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

        assembled = calls.drain()
        for call in assembled:
            yield ToolCallChunk(call=call)
        yield Completed(full_text=accumulated, tool_calls=tuple(assembled), usage=usage)
