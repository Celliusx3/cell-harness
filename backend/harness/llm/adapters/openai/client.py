"""Every call the adapter makes to OpenAI: the chat stream and the model listing."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable, Sequence

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from harness.config.sections import LLMSettings
from harness.llm.adapters.openai._errors import failure_code
from harness.llm.adapters.openai._request import openai_messages, request_body
from harness.llm.adapters.openai._streaming import chunk_of
from harness.llm.adapters.openai._tool_calls import ToolCallAssembler
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
listing_logger = logging.getLogger("harness.llm")

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
                    chunk = chunk_of(payload)
                    if chunk.failed:
                        yield Failed(
                            reason=f"provider sent an error: {data}", code=failure_code(data)
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


class _ListedModel(BaseModel):
    """One entry of the listing, narrowed to what we read."""

    model_config = ConfigDict(extra="ignore")

    id: str
    context_length: int | None = Field(default=None, gt=0)


class _Listing(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: list[_ListedModel] = []


def context_window_tokens(settings: LLMSettings) -> int | None:
    """`context_length` of `settings.model` from the endpoint's listing, or `None`."""
    url = f"{settings.base_url.rstrip('/')}/models"
    try:
        with httpx.Client(timeout=settings.timeout_seconds) as http:
            response = http.get(url, headers={"Authorization": f"Bearer {settings.api_key}"})
            response.raise_for_status()
            listing = _Listing.model_validate_json(response.content)
    except (httpx.HTTPError, ValidationError) as err:
        listing_logger.warning("could not read %s: %s", url, err)
        return None
    for entry in listing.data:
        if entry.id == settings.model:
            return entry.context_length
    return None
