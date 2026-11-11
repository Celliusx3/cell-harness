"""The OpenAI adapter refuses, unsent, a request past its image limit, with how many to hide."""

from __future__ import annotations

import httpx

from harness.llm import IMAGES_OVER_LIMIT, Failed, Image, UserMessage
from harness.llm.adapters.openai._image_limit import (
    HIDE_BYTES,
    MAX_IMAGE_BYTES,
    MAX_IMAGES,
    images_to_hide,
)
from tests.unit.test_openai_adapter import collect

MIB = 1024 * 1024


def test_25_small_images_fit() -> None:
    assert images_to_hide([1_000] * 25) == 0


def test_one_image_past_the_count_hides_a_block_of_20() -> None:
    assert images_to_hide([10] * (MAX_IMAGES + 1)) == 20


def test_just_over_the_bytes_hides_at_least_10_mib_of_the_oldest() -> None:
    lengths = [MIB] * 20 + [1]

    count = images_to_hide(lengths)

    assert sum(lengths) > MAX_IMAGE_BYTES
    assert sum(lengths[:count]) >= HIDE_BYTES
    assert sum(lengths[: count - 1]) < HIDE_BYTES


def test_the_larger_of_the_two_counts_is_asked_for() -> None:
    lengths = [MIB] * 40 + [1] * (MAX_IMAGES - 40 + 1)

    assert images_to_hide(lengths) == 30


async def test_past_the_limit_the_request_is_refused_before_it_is_sent(monkeypatch) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(500)

    pages = tuple(Image(media_type="image/png", sha256=f"{n:064x}", size=1) for n in range(601))
    message = UserMessage(content="look", images=pages)

    events = await collect(monkeypatch, handler, [message], read_image=lambda image: b"x")

    assert sent == []
    [failed] = events
    assert isinstance(failed, Failed)
    assert failed.code == IMAGES_OVER_LIMIT
    assert failed.images_to_hide == 20
