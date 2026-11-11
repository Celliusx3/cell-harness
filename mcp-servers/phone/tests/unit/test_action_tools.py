"""The app and input tools through a real MCP client: their words, their schemas, their failures."""

from __future__ import annotations

from pathlib import Path

from mcp import Client
from mcp.types import CallToolResult, TextContent

from phone.models.command import CommandResult
from phone.services.apps import LIST_PACKAGES
from phone.tools.apps import (
    INSTALL_APP_DESCRIPTION,
    OPEN_APP_DESCRIPTION,
    OPEN_URL_DESCRIPTION,
    REINSTALLED,
)
from phone.tools.elements import LIST_ELEMENTS_DESCRIPTION
from phone.tools.manage_apps import (
    CLEAR_APP_DATA_DESCRIPTION,
    FOREGROUND_APP_DESCRIPTION,
    LIST_APPS_DESCRIPTION,
    NO_APPS,
    TERMINATE_APP_DESCRIPTION,
    UNINSTALL_APP_DESCRIPTION,
)
from phone.tools.touch import (
    DOUBLE_TAP_DESCRIPTION,
    LONG_PRESS_DESCRIPTION,
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
        "Press one of the phone's keys: back, home, enter, delete, recent_apps, paste, tab, "
        "search, volume_up or volume_down. paste puts in the text that was last copied on the "
        "phone. Returns a screenshot."
    ),
    "long_press": (
        "Press and hold the phone's screen at x, y for one second, in the pixels of the latest "
        "screenshot, to open a menu such as Paste or a context menu. Returns a screenshot."
    ),
    "double_tap": (
        "Tap twice quickly at x, y, in the pixels of the latest screenshot, to zoom or to select "
        "a word. Returns a screenshot."
    ),
    "open_url": (
        "Open a web link on the phone. The app that handles the link opens it, such as Pinduoduo "
        "for its own links, and otherwise the browser does. Only http and https links. Returns a "
        "screenshot."
    ),
    "list_apps": "List the apps installed on the phone from APK files, by package name.",
    "foreground_app": "Name the app on the phone's screen now, by its package name.",
    "terminate_app": (
        "Close an app on the phone by its package name, as force-stop does, when it is stuck. Its "
        "data stays. Returns a screenshot."
    ),
    "uninstall_app": (
        "Remove an app and its data from the phone by its package name. Ask the user first. "
        "Returns a screenshot."
    ),
    "clear_app_data": (
        "Clear an app's data by its package name, which signs it out and resets it as if just "
        "installed. Ask the user first. Returns a screenshot."
    ),
    "list_elements": (
        "List what is on the phone's screen as text: each element with words or a description, "
        "its resource id, whether it can be tapped, and its centre in the pixels of a screenshot. "
        "Read this to find words, prices, links or a target to tap; take a screenshot when you "
        "need to see the picture."
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
        "long_press": LONG_PRESS_DESCRIPTION,
        "double_tap": DOUBLE_TAP_DESCRIPTION,
        "open_url": OPEN_URL_DESCRIPTION,
        "list_apps": LIST_APPS_DESCRIPTION,
        "foreground_app": FOREGROUND_APP_DESCRIPTION,
        "terminate_app": TERMINATE_APP_DESCRIPTION,
        "uninstall_app": UNINSTALL_APP_DESCRIPTION,
        "clear_app_data": CLEAR_APP_DATA_DESCRIPTION,
        "list_elements": LIST_ELEMENTS_DESCRIPTION,
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


async def test_a_phone_with_no_apps_from_apk_files_says_so(tmp_path: Path) -> None:
    result = await call(FakeEngine(state="running"), "list_apps", {}, tmp_path)

    assert not result.is_error
    assert text_of(result) == NO_APPS


async def test_an_element_dump_android_refuses_is_a_tool_error(tmp_path: Path) -> None:
    engine = FakeEngine(state="running")

    result = await call(engine, "list_elements", {}, tmp_path)

    assert result.is_error
    assert "not XML" in text_of(result)
