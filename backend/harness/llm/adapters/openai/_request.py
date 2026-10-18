"""Our messages and tools as OpenAI's request."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from typing import assert_never

from pydantic import JsonValue

from harness.llm.models.blocks import Block, Image, Text, ToolReference, text_of
from harness.llm.models.messages import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from harness.llm.models.tools import ExtraContent, ToolSpec
from harness.prompts import IMAGE_NOT_SHOWN, IMAGES_FOLLOW, REFERENCES_NOTE, TOOL_IMAGES

JsonObject = dict[str, JsonValue]
WireContent = str | list[JsonObject]


def openai_messages(
    messages: Sequence[Message], image_bytes: Mapping[str, bytes]
) -> list[JsonObject]:
    """Every message in the provider's shape, tool images in a user message after the results."""
    wired: list[JsonObject] = []
    held: list[Image] = []
    for message in messages:
        if held and not isinstance(message, ToolMessage):
            wired.append(_tool_images_message(held, image_bytes))
            held = []
        wired.append(_openai_message(message, image_bytes))
        if isinstance(message, ToolMessage):
            held.extend(_readable_images(message.content, image_bytes))
    if held:
        wired.append(_tool_images_message(held, image_bytes))
    return wired


def _tool_images_message(shown: Sequence[Image], image_bytes: Mapping[str, bytes]) -> JsonObject:
    return {"role": "user", "content": _content_with_images(TOOL_IMAGES, shown, image_bytes)}


def _readable_images(blocks: tuple[Block, ...], image_bytes: Mapping[str, bytes]) -> list[Image]:
    """The images among `blocks` whose bytes could be read."""
    return [b for b in blocks if isinstance(b, Image) and b.sha256 in image_bytes]


def _openai_message(message: Message, image_bytes: Mapping[str, bytes]) -> JsonObject:
    """One message in the provider's shape."""
    if isinstance(message, AssistantMessage) and message.tool_calls:
        return {
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": _sendable_arguments(call.arguments),
                    },
                    **_extra_content_field(call.extra_content),
                }
                for call in message.tool_calls
            ],
        }
    if isinstance(message, AssistantMessage):
        # Some providers treat `tool_calls: []` differently from the key being absent.
        return {"role": "assistant", "content": message.content}
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": _tool_content(message.content, image_bytes),
        }
    if isinstance(message, UserMessage):
        return {"role": "user", "content": _user_content(message, image_bytes)}
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    assert_never(message)


def _extra_content_field(extra: ExtraContent | None) -> dict[str, ExtraContent]:
    """The field that hands a call's extra content back to its provider, or none without any."""
    if extra is None:
        return {}
    return {"extra_content": extra}


def _sendable_arguments(arguments: str) -> str:
    """The model's raw arguments, unless the provider cannot carry them."""
    try:
        json.loads(arguments)
    except json.JSONDecodeError:
        return "{}"
    return arguments


def _tool_content(blocks: tuple[Block, ...], image_bytes: Mapping[str, bytes]) -> str:
    """A result's words as one string, and how many of its images follow the step's results."""
    readable = tuple(
        Text(text=IMAGE_NOT_SHOWN) if isinstance(b, Image) and b.sha256 not in image_bytes else b
        for b in blocks
    )
    parts = [text_of(readable)] if any(isinstance(b, Text) for b in readable) else []
    referenced = sorted(b.tool_name for b in readable if isinstance(b, ToolReference))
    if referenced:
        parts.append(REFERENCES_NOTE.format(names=", ".join(referenced)))
    shown = _readable_images(blocks, image_bytes)
    if shown:
        parts.append(IMAGES_FOLLOW.format(count=len(shown)))
    return "\n\n".join(parts)


def _user_content(message: UserMessage, image_bytes: Mapping[str, bytes]) -> WireContent:
    """The person's text, a note for each image that could not be read, then the rest."""
    shown = [image for image in message.images if image.sha256 in image_bytes]
    notes = [IMAGE_NOT_SHOWN] * (len(message.images) - len(shown))
    return _content_with_images("\n".join([message.content, *notes]), shown, image_bytes)


def _content_with_images(
    text: str, shown: Sequence[Image], image_bytes: Mapping[str, bytes]
) -> WireContent:
    """`text` alone when no image is shown; else a text part, then each image as a data URL."""
    if not shown:
        return text
    return [
        {"type": "text", "text": text},
        *(
            {"type": "image_url", "image_url": {"url": _data_url(image, image_bytes[image.sha256])}}
            for image in shown
        ),
    ]


def _data_url(image: Image, data: bytes) -> str:
    return f"data:{image.media_type};base64,{base64.b64encode(data).decode('ascii')}"


def openai_tool(spec: ToolSpec) -> JsonObject:
    """One tool declaration in the provider's shape."""
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.input_schema,
        },
    }


def request_body(
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
        body["tools"] = [openai_tool(t) for t in tools]
    return body
