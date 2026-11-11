"""The input tools: tap, press, swipe, type and press a key, each answered with the screen after."""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.types import ImageContent
from pydantic import Field

from phone.services.touch import Key
from phone.tools import Phone, phone_for_one_call, screen_after_action

TAP_DESCRIPTION = (
    "Tap the phone's screen at x, y, in the pixels of the latest screenshot, where 0, 0 is the "
    "top left. Returns a screenshot after the tap. Take a new screenshot before each tap, "
    "because a button can move as the screen changes."
)
SWIPE_DESCRIPTION = (
    "Drag a finger across the phone's screen from one point to another, in screenshot pixels, "
    "to scroll or swipe. To scroll down a list, swipe from low on the screen to high. Returns a "
    "screenshot."
)
TYPE_TEXT_DESCRIPTION = (
    "Type text into the field that has focus; tap the field first. Only ASCII letters, digits, "
    "spaces and punctuation can be typed. Returns a screenshot."
)
DOUBLE_TAP_DESCRIPTION = (
    "Tap twice quickly at x, y, in the pixels of the latest screenshot, to zoom or to select a "
    "word. Returns a screenshot."
)
MENU_SECONDS = 1.0
LONG_PRESS_DESCRIPTION = (
    "Press and hold the phone's screen at x, y for one second, in the pixels of the latest "
    "screenshot, to open a menu such as Paste or a context menu. Returns a screenshot."
)
PRESS_KEY_DESCRIPTION = (
    "Press one of the phone's keys: back, home, enter, delete, recent_apps, paste, tab, search, "
    "volume_up or volume_down. paste puts in the text that was last copied on the phone. Returns "
    "a screenshot."
)

Pixel = Annotated[int, Field(ge=0)]
Text = Annotated[str, Field(min_length=1)]


def register(server: MCPServer, phone: Phone) -> None:
    @server.tool(name="tap", description=TAP_DESCRIPTION)
    async def tap(x: Pixel, y: Pixel) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.touch.tap(x, y)
            return await screen_after_action(phone)

    @server.tool(name="double_tap", description=DOUBLE_TAP_DESCRIPTION)
    async def double_tap(x: Pixel, y: Pixel) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.touch.double_tap(x, y)
            return await screen_after_action(phone)

    @server.tool(name="long_press", description=LONG_PRESS_DESCRIPTION)
    async def long_press(x: Pixel, y: Pixel) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.touch.long_press(x, y)
            await phone.clock.sleep(MENU_SECONDS)
            return await screen_after_action(phone)

    @server.tool(name="swipe", description=SWIPE_DESCRIPTION)
    async def swipe(from_x: Pixel, from_y: Pixel, to_x: Pixel, to_y: Pixel) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.touch.swipe(from_x, from_y, to_x, to_y)
            return await screen_after_action(phone)

    @server.tool(name="type_text", description=TYPE_TEXT_DESCRIPTION)
    async def type_text(text: Text) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.touch.type_text(text)
            return await screen_after_action(phone)

    @server.tool(name="press_key", description=PRESS_KEY_DESCRIPTION)
    async def press_key(key: Key) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.touch.press_key(key)
            return await screen_after_action(phone)
