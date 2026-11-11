"""The screenshot tool through a real MCP client, in-process, and how its failures read."""

from __future__ import annotations

from mcp import Client
from mcp.types import CallToolResult, TextContent

from phone.models.command import CommandResult
from phone.server import PHONE_INSTRUCTIONS
from phone.tools.screenshot import SCREENSHOT_DESCRIPTION
from tests.fakes import FakeEngine, phone_server

DESCRIPTION = (
    "Take a screenshot of the phone: one Android phone shared by every bot, with no Google Play. "
    "Returns its screen as a PNG. The first call starts the phone and waits for Android, which "
    "takes a few seconds. Take a new screenshot before acting on the screen, because it changes "
    "as you act."
)
INSTRUCTIONS = (
    "You have a phone: one Android phone, shared by every bot, with apps installed from APK files "
    "and no Google Play. Read its screen as text with phone__list_elements, or see it with "
    "phone__screenshot. Install an APK from this chat's files with phone__install_app, open apps "
    "with phone__open_app or links with phone__open_url, and act with phone__tap, "
    "phone__double_tap, phone__long_press, phone__swipe, phone__type_text and phone__press_key. "
    "phone__list_apps, phone__foreground_app, phone__terminate_app, phone__uninstall_app and "
    "phone__clear_app_data manage apps. Each action returns a new screenshot."
)
TOOLS = [
    "screenshot",
    "list_elements",
    "install_app",
    "open_app",
    "open_url",
    "list_apps",
    "foreground_app",
    "terminate_app",
    "uninstall_app",
    "clear_app_data",
    "tap",
    "double_tap",
    "long_press",
    "swipe",
    "type_text",
    "press_key",
    "screen_session",
    "release_control",
    "keep_awake",
]


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


async def screenshot_of(engine: FakeEngine) -> CallToolResult:
    async with Client(phone_server(engine)) as client:
        return await client.call_tool("screenshot", {})


async def test_the_screenshot_is_listed_first_with_no_arguments() -> None:
    async with Client(phone_server(FakeEngine(state="running"))) as client:
        listed = await client.list_tools()

    assert [tool.name for tool in listed.tools] == TOOLS
    tool = listed.tools[0]
    assert tool.description == SCREENSHOT_DESCRIPTION
    assert tool.input_schema.get("properties", {}) == {}


def test_the_description_and_instructions_are_word_for_word() -> None:
    assert SCREENSHOT_DESCRIPTION == DESCRIPTION
    assert PHONE_INSTRUCTIONS == INSTRUCTIONS


async def test_a_phone_that_does_not_boot_is_not_available() -> None:
    result = await screenshot_of(FakeEngine(state="missing", boot_polls_needed=10_000))

    assert result.is_error
    assert text_of(result) == (
        "Error executing tool screenshot: The phone is not available: "
        "Android did not finish booting within 180 seconds"
    )


async def test_a_screen_that_cannot_be_read_says_why() -> None:
    result = await screenshot_of(FakeEngine(state="running", screen=CommandResult(0, "x", "")))

    assert result.is_error
    assert text_of(result) == (
        "Error executing tool screenshot: The phone's screenshot is not a PNG."
    )
