"""The phone's touchscreen and keys, worked by Android's `input` command."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from phone.clock import Clock
from phone.engine import Engine
from phone.models.command import COMMAND_TIMEOUT_SECONDS, stdout_of
from phone.models.phone import android, sh_quoted

SWIPE_MILLISECONDS = 300
LONG_PRESS_MILLISECONDS = 1000
DOUBLE_TAP_GAP_SECONDS = 0.1
FIRST_TYPABLE = " "
LAST_TYPABLE = "~"

Key = Literal[
    "back",
    "home",
    "enter",
    "delete",
    "recent_apps",
    "paste",
    "tab",
    "search",
    "volume_up",
    "volume_down",
]
KEYCODES: Mapping[Key, str] = {
    "back": "KEYCODE_BACK",
    "home": "KEYCODE_HOME",
    "enter": "KEYCODE_ENTER",
    "delete": "KEYCODE_DEL",
    "recent_apps": "KEYCODE_APP_SWITCH",
    "paste": "KEYCODE_PASTE",
    "tab": "KEYCODE_TAB",
    "search": "KEYCODE_SEARCH",
    "volume_up": "KEYCODE_VOLUME_UP",
    "volume_down": "KEYCODE_VOLUME_DOWN",
}


class TouchError(RuntimeError):
    """The phone did not take the touch, text or key. The message says why, in plain words."""


def typable(text: str) -> str:
    """`text` as `input text` takes it, quoted for sh, or a refusal unless it is plain ASCII."""
    if not all(FIRST_TYPABLE <= char <= LAST_TYPABLE for char in text):
        raise TouchError(
            f"The phone can only type ASCII letters, digits, spaces and punctuation: {text!r}"
        )
    return sh_quoted(text.replace(" ", "%s"))


class Touch:
    """Fingers and keys on the phone, one `input` command each."""

    def __init__(self, *, engine: Engine, name: str, clock: Clock) -> None:
        self._engine = engine
        self._name = name
        self._clock = clock

    async def tap(self, x: int, y: int) -> None:
        await self._input(f"tap {x} {y}", "Tapping the screen")

    async def double_tap(self, x: int, y: int) -> None:
        await self.tap(x, y)
        await self._clock.sleep(DOUBLE_TAP_GAP_SECONDS)
        await self.tap(x, y)

    async def long_press(self, x: int, y: int) -> None:
        command = f"swipe {x} {y} {x} {y} {LONG_PRESS_MILLISECONDS}"
        await self._input(command, "Pressing and holding the screen")

    async def swipe(self, from_x: int, from_y: int, to_x: int, to_y: int) -> None:
        command = f"swipe {from_x} {from_y} {to_x} {to_y} {SWIPE_MILLISECONDS}"
        await self._input(command, "Swiping the screen")

    async def type_text(self, text: str) -> None:
        await self._input(f"text {typable(text)}", "Typing")

    async def press_key(self, key: Key) -> None:
        await self._input(f"keyevent {KEYCODES[key]}", f"Pressing {key}")

    async def _input(self, arguments: str, action: str) -> None:
        completed = await self._engine.run(
            self._name,
            android(f"input {arguments}"),
            stdin=None,
            timeout_seconds=COMMAND_TIMEOUT_SECONDS,
        )
        stdout_of(completed, action, error=TouchError)
