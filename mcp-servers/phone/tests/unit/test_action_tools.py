"""The app and input tools through a real MCP client: their words, their schemas, their failures."""

from __future__ import annotations

from pathlib import Path

from mcp import Client
from mcp.types import CallToolResult, TextContent

from phone.models.command import CommandResult
from phone.services.apps import LIST_PACKAGES
from phone.tools.apps import INSTALL_APP_DESCRIPTION, OPEN_APP_DESCRIPTION, REINSTALLED
from phone.tools.touch import (
    PRESS_KEY_DESCRIPTION,
    SWIPE_DESCRIPTION,
    TAP_DESCRIPTION,
    TYPE_TEXT_DESCRIPTION,
)
from tests.fakes import FakeEngine, phone_server

DESCRIPTIONS = {
    "install_app": (
        "Install an Android app on the phone from an APK file in this chat's files. `path` is the "
        "file's full path, as the chat names it. Returns the installed app's package name and a "
        "screenshot."
    ),
    "open_app": (
        "Open an installed app by its package name, such as com.example.notes. Returns a "
        "screenshot."
    ),
    "tap": (
        "Tap the phone's screen at x, y, in the pixels of the latest screenshot, where 0, 0 is the "
        "top left. Returns a screenshot after the tap. Take a new screenshot before each tap, "
        "because a button can move as the screen changes."
    ),
    "swipe": (
        "Drag a finger across the phone's screen from one point to another, in screenshot pixels, "
        "to scroll or swipe. To scroll down a list, swipe from low on the screen to high. Returns "
        "a screenshot."
    ),
    "type_text": (
        "Type text into the field that has focus; tap the field first. Only ASCII letters, "
        "digits, spaces and punctuation can be typed. Returns a screenshot."
    ),
    "press_key": (
        "Press one of the phone's keys: back, home, enter, delete or recent_apps. Returns a "
        "screenshot."
    ),
}


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


async def call(
    engine: FakeEngine, name: str, args: dict[str, object], files: Path
) -> CallToolResult:
    async with Client(phone_server(engine, files_dir=files)) as client:
        return await client.call_tool(name, args)


def test_the_descriptions_are_word_for_word() -> None:
    assert {
        "install_app": INSTALL_APP_DESCRIPTION,
        "open_app": OPEN_APP_DESCRIPTION,
        "tap": TAP_DESCRIPTION,
        "swipe": SWIPE_DESCRIPTION,
        "type_text": TYPE_TEXT_DESCRIPTION,
        "press_key": PRESS_KEY_DESCRIPTION,
    } == DESCRIPTIONS


async def test_the_listed_tools_carry_their_descriptions() -> None:
    async with Client(phone_server(FakeEngine(state="running"))) as client:
        listed = await client.list_tools()

    described = {tool.name: tool.description for tool in listed.tools if tool.name in DESCRIPTIONS}
    assert described == DESCRIPTIONS


async def test_a_negative_coordinate_is_refused_before_the_phone_is_touched(tmp_path: Path) -> None:
    engine = FakeEngine(state="running")

    result = await call(engine, "tap", {"x": -1, "y": 10}, tmp_path)

    assert result.is_error
    assert engine.commands == []


async def test_a_key_the_phone_does_not_have_is_refused(tmp_path: Path) -> None:
    engine = FakeEngine(state="running")

    result = await call(engine, "press_key", {"key": "power"}, tmp_path)

    assert result.is_error
    assert engine.commands == []


async def test_an_apk_that_adds_no_package_says_it_was_reinstalled(tmp_path: Path) -> None:
    apk = tmp_path / "notes.apk"
    apk.write_bytes(b"PK")

    result = await call(FakeEngine(state="running"), "install_app", {"path": str(apk)}, tmp_path)

    assert not result.is_error
    assert text_of(result) == REINSTALLED


async def test_a_failure_android_reports_is_a_tool_error_in_its_words(tmp_path: Path) -> None:
    refused = CommandResult(1, "", "pm: broken\n")
    engine = FakeEngine(state="running", answers={LIST_PACKAGES: refused})
    apk = tmp_path / "notes.apk"
    apk.write_bytes(b"PK")

    result = await call(engine, "install_app", {"path": str(apk)}, tmp_path)

    assert result.is_error
    assert text_of(result) == (
        "Error executing tool install_app: Listing the phone's apps failed: pm: broken"
    )


async def test_an_input_android_refuses_is_a_tool_error(tmp_path: Path) -> None:
    engine = FakeEngine(state="running", answers={"input tap 1 2": CommandResult(1, "", "")})

    result = await call(engine, "tap", {"x": 1, "y": 2}, tmp_path)

    assert result.is_error
    assert text_of(result) == "Error executing tool tap: Tapping the screen failed: exit 1"
