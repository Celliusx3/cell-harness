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

from harness.config.settings import LLMSettings
from harness.llm.client import LLMClient
from harness.llm.messages import Message
from harness.llm.stream import Completed, Failed, StreamEvent, TextChunk, Usage

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


def _text(payload: dict) -> str:
    """The text this chunk adds, or `""`.

    Tolerant by construction. A chunk with no choices, an empty delta, or a
    `null` content is normal — it is how a provider signals a role header, a
    finish reason, or a usage-only final frame — so none of those is an error
    worth failing a turn over.
    """
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    delta = choices[0].get("delta")
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content")
    return content if isinstance(content, str) else ""


class OpenAIClient(LLMClient):
    """Streams completions from an OpenAI-compatible endpoint."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings

    async def stream_completion(
        self, messages: list[Message], model: str
    ) -> AsyncIterator[StreamEvent]:
        settings = self._settings
        body = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "temperature": settings.temperature,
            "stream": True,
            # Without this, a streamed response reports no usage at all.
            "stream_options": {"include_usage": True},
        }

        accumulated = ""
        usage: Usage | None = None
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
                    text = _text(payload)
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

        yield Completed(full_text=accumulated, usage=usage)
