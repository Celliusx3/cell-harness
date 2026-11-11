"""The one tool through a real MCP client, in-process, and how its failures read."""

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
    "and no Google Play. See its screen with phone__screenshot."
)


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


async def screenshot_of(engine: FakeEngine) -> CallToolResult:
    async with Client(phone_server(engine)) as client:
        return await client.call_tool("screenshot", {})


async def test_the_only_tool_is_the_screenshot_with_no_arguments() -> None:
    async with Client(phone_server(FakeEngine(state="running"))) as client:
        listed = await client.list_tools()

    [tool] = listed.tools
    assert (tool.name, tool.description) == ("screenshot", SCREENSHOT_DESCRIPTION)
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
