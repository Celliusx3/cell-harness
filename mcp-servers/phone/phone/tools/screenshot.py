"""The screenshot tool: the phone's whole screen as one PNG."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ImageContent

from phone.tools import Phone, phone_for_one_call, screen_now

SCREENSHOT_DESCRIPTION = (
    "Take a screenshot of the phone: one Android phone shared by every bot, with no Google "
    "Play. Returns its screen as a PNG. The first call starts the phone and waits for Android, "
    "which takes a few seconds. Take a new screenshot before acting on the screen, because it "
    "changes as you act."
)


def register(server: MCPServer, phone: Phone) -> None:
    @server.tool(name="screenshot", description=SCREENSHOT_DESCRIPTION)
    async def screenshot() -> ImageContent:
        async with phone_for_one_call(phone.machine):
            return await screen_now(phone)
