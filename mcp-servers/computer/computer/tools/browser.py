"""The bot's browser: open, read and act on a page, refused while the person holds the screen."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.apps import Apps
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from computer.models import Acted, Action, Opened, Page
from computer.tools import PREVIEW_URI, Computer, computer_for_one_call
from computer.tools.descriptions import (
    ACT_DESCRIPTION,
    HELD_BY_PERSON,
    NAVIGATE_DESCRIPTION,
    READ_PAGE_DESCRIPTION,
)

MAX_ACTIONS = 24

Url = Annotated[str, Field(pattern=r"^https?://", description="Starts with http:// or https://.")]
Actions = Annotated[list[Action], Field(min_length=1, max_length=MAX_ACTIONS)]


@asynccontextmanager
async def browser_for_one_call(computer: Computer) -> AsyncIterator[None]:
    """The computer for a bot's browser call, refused while the person holds the screen."""
    if computer.live_screen.is_held():
        raise ToolError(HELD_BY_PERSON)
    async with computer_for_one_call(computer.machine):
        yield


def register_navigate(apps: Apps, computer: Computer) -> None:
    """browser_navigate, whose card opens the preview; the preview itself may not call it."""

    @apps.tool(
        resource_uri=PREVIEW_URI,
        visibility=["model"],
        name="browser_navigate",
        description=NAVIGATE_DESCRIPTION,
    )
    async def browser_navigate(url: Url) -> Opened:
        async with browser_for_one_call(computer):
            return await computer.browser.navigate(url)


def register_read_and_act(server: MCPServer, computer: Computer) -> None:
    """browser_read_page and browser_act, which open no preview."""

    @server.tool(name="browser_read_page", description=READ_PAGE_DESCRIPTION)
    async def browser_read_page() -> Page:
        async with browser_for_one_call(computer):
            return await computer.browser.read()

    @server.tool(name="browser_act", description=ACT_DESCRIPTION)
    async def browser_act(actions: Actions) -> Acted:
        async with browser_for_one_call(computer):
            return await computer.browser.act(actions)
