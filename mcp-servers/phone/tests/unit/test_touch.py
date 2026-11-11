"""Taps, swipes, text and keys, each one `input` command inside Android."""

from __future__ import annotations

import pytest

from phone.models.command import CommandResult
from phone.services.touch import KEYCODES, Key, Touch, TouchError
from tests.fakes import NAME, FakeEngine


def touch_over(engine: FakeEngine) -> Touch:
    return Touch(engine=engine, name=NAME)


async def test_a_tap_is_input_tap_at_the_point() -> None:
    engine = FakeEngine(state="running")

    await touch_over(engine).tap(0, 1279)

    assert engine.commands == ["input tap 0 1279"]


async def test_a_swipe_is_input_swipe_over_three_hundred_milliseconds() -> None:
    engine = FakeEngine(state="running")

    await touch_over(engine).swipe(10, 20, 30, 40)

    assert engine.commands == ["input swipe 10 20 30 40 300"]


@pytest.mark.parametrize(
    ("text", "command"),
    [
        ("hello", "input text 'hello'"),
        ("a b", "input text 'a%sb'"),
        ("it's", "input text 'it'\\''s'"),
        ('$(reboot) "x" `y`', "input text '$(reboot)%s\"x\"%s`y`'"),
    ],
)
async def test_text_is_typed_with_spaces_as_percent_s_and_quoted_for_sh(
    text: str, command: str
) -> None:
    engine = FakeEngine(state="running")

    await touch_over(engine).type_text(text)

    assert engine.commands == [command]


@pytest.mark.parametrize("text", ["café", "拼多多", "line\nbreak", "tab\there", "\x7f"])
async def test_text_that_is_not_printable_ascii_is_refused(text: str) -> None:
    engine = FakeEngine(state="running")

    with pytest.raises(TouchError, match="can only type ASCII"):
        await touch_over(engine).type_text(text)

    assert engine.commands == []


@pytest.mark.parametrize(
    ("key", "code"),
    [
        ("back", "KEYCODE_BACK"),
        ("home", "KEYCODE_HOME"),
        ("enter", "KEYCODE_ENTER"),
        ("delete", "KEYCODE_DEL"),
        ("recent_apps", "KEYCODE_APP_SWITCH"),
    ],
)
async def test_a_key_is_its_android_keyevent(key: Key, code: str) -> None:
    engine = FakeEngine(state="running")

    await touch_over(engine).press_key(key)

    assert engine.commands == [f"input keyevent {code}"]
    assert KEYCODES[key] == code


async def test_an_input_android_refuses_fails_in_its_words() -> None:
    engine = FakeEngine(
        state="running",
        answers={"input keyevent KEYCODE_HOME": CommandResult(1, "", "input: no such device\n")},
    )

    with pytest.raises(TouchError, match="Pressing home failed: input: no such device"):
        await touch_over(engine).press_key("home")
