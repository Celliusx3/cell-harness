"""App-only tools: the preview's screenshot, and the Computer page's sessions, shell and files."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, ImageContent, TextContent

from computer.desktop import Screenshot
from computer.live_screen import Link, NotHeld
from computer.models import (
    FileBytes,
    FilePath,
    FileText,
    FolderPath,
    Listing,
    ScreenMode,
    ScreenSession,
    UploadContent,
    Uploaded,
)
from computer.tools import Computer, computer_for_one_call
from computer.tools.descriptions import (
    FILE_DOWNLOAD_DESCRIPTION,
    FILE_LIST_DESCRIPTION,
    FILE_READ_DESCRIPTION,
    FILE_UPLOAD_DESCRIPTION,
    KEEP_AWAKE_DESCRIPTION,
    RELEASE_CONTROL_DESCRIPTION,
    SCREEN_SESSION_DESCRIPTION,
    SCREENSHOT_DESCRIPTION,
    TERMINAL_SESSION_DESCRIPTION,
)

APP_ONLY = {"ui": {"visibility": ["app"]}}
RELAY = "io.cell-harness/relay"
TERMINAL_NEEDS_CONTROL = "Take control first: the shell opens only while you hold the computer."
UPLOAD_NEEDS_CONTROL = "Take control first: files can be added only while you hold the computer."


@asynccontextmanager
async def control_for_one_call(computer: Computer, refusal_message: str) -> AsyncIterator[None]:
    """The computer for a call only the person holding control may make; refused otherwise."""
    if not computer.live_screen.is_held():
        raise ToolError(refusal_message)
    try:
        async with computer_for_one_call(computer.machine):
            yield
    except NotHeld as err:
        raise ToolError(refusal_message) from err


def image_of(shot: Screenshot) -> ImageContent:
    return ImageContent(type="image", data=shot.image, mime_type=shot.mime_type)


def relayed_result(link: Link) -> CallToolResult:
    """The session for the page, and its loopback link in `_meta` for the harness to relay."""
    return CallToolResult(
        content=[TextContent(type="text", text=link.session.model_dump_json())],
        structured_content=link.session.model_dump(mode="json"),
        _meta={RELAY: {"url": link.url}},
    )


def register(server: MCPServer, computer: Computer) -> None:
    """The app-only tools: hidden from the model, called by the preview and the Computer page."""

    @server.tool(name="screenshot", description=SCREENSHOT_DESCRIPTION, meta=APP_ONLY)
    async def screenshot() -> ImageContent:
        async with computer_for_one_call(computer.machine):
            return image_of(await computer.desktop.screenshot())

    @server.tool(name="screen_session", description=SCREEN_SESSION_DESCRIPTION, meta=APP_ONLY)
    async def screen_session(mode: ScreenMode) -> Annotated[CallToolResult, ScreenSession]:
        async with computer_for_one_call(computer.machine):
            if mode == "view":
                return relayed_result(await computer.live_screen.view())
            return relayed_result(await computer.live_screen.take_control())

    @server.tool(name="release_control", description=RELEASE_CONTROL_DESCRIPTION, meta=APP_ONLY)
    async def release_control() -> ScreenSession:
        if not computer.live_screen.is_held():
            return ScreenSession(mode="view", held_until=None)
        async with computer_for_one_call(computer.machine):
            return await computer.live_screen.release()

    @server.tool(name="terminal_session", description=TERMINAL_SESSION_DESCRIPTION, meta=APP_ONLY)
    async def terminal_session() -> CallToolResult:
        async with control_for_one_call(computer, TERMINAL_NEEDS_CONTROL):
            url = await computer.live_screen.open_terminal()
        return CallToolResult(content=[], _meta={RELAY: {"url": url}})

    @server.tool(name="file_list", description=FILE_LIST_DESCRIPTION, meta=APP_ONLY)
    async def file_list(path: FolderPath) -> Listing:
        async with computer_for_one_call(computer.machine):
            return await computer.files.listing(path)

    @server.tool(name="file_read", description=FILE_READ_DESCRIPTION, meta=APP_ONLY)
    async def file_read(path: FilePath) -> FileText:
        async with computer_for_one_call(computer.machine):
            return await computer.files.text(path)

    @server.tool(name="file_download", description=FILE_DOWNLOAD_DESCRIPTION, meta=APP_ONLY)
    async def file_download(path: FilePath) -> FileBytes:
        async with computer_for_one_call(computer.machine):
            return await computer.files.download(path)

    @server.tool(name="file_upload", description=FILE_UPLOAD_DESCRIPTION, meta=APP_ONLY)
    async def file_upload(path: FilePath, content_base64: UploadContent) -> Uploaded:
        async with control_for_one_call(computer, UPLOAD_NEEDS_CONTROL):
            return await computer.files.upload(path, content_base64)

    @server.tool(name="keep_awake", description=KEEP_AWAKE_DESCRIPTION, meta=APP_ONLY)
    async def keep_awake() -> CallToolResult:
        async with computer_for_one_call(computer.machine):
            pass
        return CallToolResult(content=[])
