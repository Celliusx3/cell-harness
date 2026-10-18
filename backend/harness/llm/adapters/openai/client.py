"""Every call the adapter makes to OpenAI: the chat stream and the list of models."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable, Sequence

import httpx
from pydantic import ValidationError

from harness.config.sections import LLMSettings
from harness.llm.adapters.openai._errors import failure_code
from harness.llm.adapters.openai._request import openai_messages, request_body
from harness.llm.adapters.openai._streaming import chunks_of
from harness.llm.adapters.openai._tool_calls import ToolCallAssembler
from harness.llm.adapters.openai.models.model_list import ModelList
from harness.llm.client import LLMClient
from harness.llm.models.blocks import Image
from harness.llm.models.messages import Message, images_of
from harness.llm.models.stream import (
    Completed,
    Failed,
    StreamEvent,
    TextChunk,
    ToolCallChunk,
    Usage,
)
from harness.llm.models.tools import ToolSpec

logger = logging.getLogger("harness.llm.openai")

ImageReader = Callable[[Image], bytes | None]


def _image_bytes(messages: Sequence[Message], read: ImageReader) -> dict[str, bytes]:
    """The bytes of each image the request shows that `read` could read, by hash."""
    return {
        image.sha256: data
        for message in messages
        for image in images_of(message)
        if (data := read(image)) is not None
    }


def _endpoint(settings: LLMSettings, path: str) -> str:
    """The address of `path` under the configured base URL."""
    return f"{settings.base_url.rstrip('/')}/{path}"


def _auth_headers(settings: LLMSettings) -> dict[str, str]:
    """The header that carries the configured key."""
    return {"Authorization": f"Bearer {settings.api_key}"}


class OpenAIClient(LLMClient):
    """Streams completions from an OpenAI-compatible endpoint."""

    def __init__(self, settings: LLMSettings, *, read_image: ImageReader) -> None:
        self._settings = settings
        self._read_image = read_image

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None
    ) -> AsyncIterator[StreamEvent]:
        settings = self._settings
        body = request_body(
            model,
            openai_messages(messages, _image_bytes(messages, self._read_image)),
            tools,
            settings.temperature,
        )

        accumulated = ""
        usage: Usage | None = None
        calls = ToolCallAssembler()
        try:
            async with (
                httpx.AsyncClient(timeout=settings.timeout_seconds) as http,
                http.stream(
                    "POST",
                    _endpoint(settings, "chat/completions"),
                    headers=_auth_headers(settings),
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

                async for chunk in chunks_of(response.aiter_lines()):
                    if chunk.error is not None:
                        yield Failed(
                            reason=f"provider sent an error: {chunk.error}",
                            code=failure_code(chunk.error),
                        )
                        return
                    usage = chunk.usage or usage
                    calls.add(chunk.tool_deltas)
                    if chunk.text:
                        accumulated += chunk.text
                        yield TextChunk(text=chunk.text)
        except httpx.HTTPError as err:
            yield Failed(reason=f"{type(err).__name__}: {err}")
            return

        assembled = calls.tool_calls()
        for call in assembled:
            yield ToolCallChunk(call=call)
        yield Completed(full_text=accumulated, tool_calls=tuple(assembled), usage=usage)


def context_window_tokens(settings: LLMSettings) -> int | None:
    """`context_length` of `settings.model` from the endpoint's list of models, or `None`."""
    url = _endpoint(settings, "models")
    try:
        with httpx.Client(timeout=settings.timeout_seconds) as http:
            response = http.get(url, headers=_auth_headers(settings))
            response.raise_for_status()
            model_list = ModelList.model_validate_json(response.content)
    except (httpx.HTTPError, ValidationError) as err:
        logger.warning("could not read %s: %s", url, err)
        return None
    for info in model_list.data:
        if info.id == settings.model:
            return info.context_length
    return None
