"""How many images a request may carry, and how many of the oldest to hide past that."""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.adapters.openai._request import JsonObject

MAX_IMAGES = 600
MAX_IMAGE_BYTES = 20 * 1024 * 1024
HIDE_IMAGES = 20
HIDE_BYTES = 10 * 1024 * 1024

_DATA_URL_SEPARATOR = ","


def images_to_hide(lengths: Sequence[int]) -> int:
    """How many of the oldest images to hide so the rest fit, in blocks; 0 when all fit."""
    by_count = _rounded_up(len(lengths) - MAX_IMAGES, HIDE_IMAGES)
    bytes_to_remove = _rounded_up(sum(lengths) - MAX_IMAGE_BYTES, HIDE_BYTES)
    by_bytes, removed = 0, 0
    for length in lengths:
        if removed >= bytes_to_remove:
            break
        removed, by_bytes = removed + length, by_bytes + 1
    return max(by_count, by_bytes)


def image_lengths(body: JsonObject) -> list[int]:
    """The base64 length of each image `body` sends, in request order."""
    return [
        len(str(part["image_url"]["url"]).split(_DATA_URL_SEPARATOR, 1)[1])
        for part in _content_parts(body)
        if part.get("type") == "image_url"
    ]


def _content_parts(body: JsonObject) -> list[JsonObject]:
    """Every part of every message whose content is a list of parts."""
    messages = body["messages"]
    assert isinstance(messages, list)
    return [
        part
        for message in messages
        if isinstance(message, dict) and isinstance(message.get("content"), list)
        for part in message["content"]
        if isinstance(part, dict)
    ]


def _rounded_up(excess: int, block: int) -> int:
    """`excess` rounded up to a whole number of `block`s; 0 when there is none."""
    if excess <= 0:
        return 0
    return -(-excess // block) * block
