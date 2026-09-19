"""Reading frames: sentinel stripping, section parsing, and the failure paths."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from instagram.read import vision
from instagram.read.http import ProviderError, ProviderRateLimited
from tests.conftest import chat_reply, http_with, scripted


def frame(tmp_path: Path) -> Path:
    path = tmp_path / "frame01.jpg"
    path.write_bytes(b"jpegbytes")
    return path


async def test_vision_sentinels_are_stripped_from_the_answer(tmp_path: Path) -> None:
    http = http_with(
        scripted(
            {
                "/chat/completions": chat_reply(
                    "<|begin_of_box|>ON-SCREEN TEXT:\nWARUNG MAK CIK\n\n"
                    "SCENE:\nA roadside stall.<|end_of_box|>"
                )
            }
        )
    )

    described = await vision.describe(http, [frame(tmp_path)], model="m")

    assert described.overlay_text == ("WARUNG MAK CIK",)
    assert described.scene == "A roadside stall."
    assert "begin_of_box" not in described.scene


def test_the_two_sections_are_split_and_overlay_lines_deduplicated() -> None:
    parsed = vision.parse_description(
        "ON-SCREEN TEXT:\n- BEST NASI LEMAK\n- BEST NASI LEMAK\n- @warung.mak.cik\n\n"
        "SCENE:\nA banana-leaf plate on a roadside table."
    )

    assert parsed.overlay_text == ("BEST NASI LEMAK", "@warung.mak.cik")
    assert parsed.scene == "A banana-leaf plate on a roadside table."


def test_an_unlabelled_answer_becomes_the_scene_rather_than_an_error() -> None:
    parsed = vision.parse_description("A hill fort on a steep ridge in the Western Ghats.")

    assert parsed.overlay_text == ()
    assert parsed.scene == "A hill fort on a steep ridge in the Western Ghats."


def test_NONE_is_not_mistaken_for_a_line_of_overlay_text() -> None:
    parsed = vision.parse_description("ON-SCREEN TEXT:\nNONE\n\nSCENE:\nA quiet street.")

    assert parsed.overlay_text == ()


async def test_a_429_is_retried_once_then_surfaces_as_rate_limited(tmp_path: Path) -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(429, headers={"Retry-After": "0"}, text="slow down")

    http = http_with(handler)

    with pytest.raises(ProviderRateLimited):
        await vision.describe(http, [frame(tmp_path)], model="m")

    assert len(attempts) == 2


async def test_a_429_that_clears_on_the_retry_succeeds(tmp_path: Path) -> None:
    responses = [
        httpx.Response(429, headers={"Retry-After": "0"}, text="slow down"),
        chat_reply("ON-SCREEN TEXT:\nNONE\n\nSCENE:\nA street."),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    http = http_with(handler)

    assert (await vision.describe(http, [frame(tmp_path)], model="m")).scene == "A street."


async def test_an_empty_message_is_an_error_not_nothing_visible(tmp_path: Path) -> None:
    http = http_with(
        scripted({"/chat/completions": httpx.Response(200, json={"choices": [{"message": {}}]})})
    )

    with pytest.raises(ProviderError, match="empty message"):
        await vision.describe(http, [frame(tmp_path)], model="m")


async def test_no_frames_means_no_request_at_all(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not have called the provider")

    described = await vision.describe(http_with(handler), [], model="m")

    assert described == type(described)(overlay_text=(), scene="")
