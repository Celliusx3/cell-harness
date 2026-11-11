"""The phone's screen: one PNG from screencap inside Android, refused in plain words otherwise."""

from __future__ import annotations

import base64

import pytest

from phone.models.command import CommandResult
from phone.services.screen import Screen, ScreenError
from tests.fakes import NAME, PNG, FakeEngine


def screen_showing(result: CommandResult) -> Screen:
    return Screen(engine=FakeEngine(state="running", screen=result), name=NAME)


async def test_the_screenshot_is_the_commands_png_as_base64() -> None:
    shot = await screen_showing(CommandResult(0, base64.b64encode(PNG).decode(), "")).screenshot()

    assert (base64.b64decode(shot.image), shot.mime_type) == (PNG, "image/png")


async def test_a_screencap_that_fails_says_so_in_its_own_words() -> None:
    screen = screen_showing(CommandResult(1, "", "android: Android is not running\n"))

    with pytest.raises(ScreenError, match="screenshot failed: android: Android is not running"):
        await screen.screenshot()


async def test_a_failure_without_words_gives_its_exit_code() -> None:
    with pytest.raises(ScreenError, match="failed: exit 2"):
        await screen_showing(CommandResult(2, "", "")).screenshot()


@pytest.mark.parametrize("stdout", ["not base64!", base64.b64encode(b"GIF89a").decode()])
async def test_anything_but_a_png_is_refused(stdout: str) -> None:
    with pytest.raises(ScreenError, match="The phone's screenshot is not a PNG."):
        await screen_showing(CommandResult(0, stdout, "")).screenshot()
