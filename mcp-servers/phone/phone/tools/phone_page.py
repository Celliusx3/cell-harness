"""App-only tools: the Computer page's live screen of the phone, its hold, and its keep-awake."""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent

from phone.models.screen import ScreenMode, ScreenSession
from phone.services.live_screen import Link
from phone.tools import Phone, machine_for_one_call

APP_ONLY = {"ui": {"visibility": ["app"]}}
RELAY = "io.cell-harness/relay"

SCREEN_SESSION_DESCRIPTION = (
    "App-only: the person's Computer page calls this to watch the phone's screen live, or to "
    "take control of it; do not call it. To see the phone, call screenshot. args: "
    '{ mode: "view" | "control" }. Returns { mode, held_until }, and a link to the live '
    "screen for the Computer page."
)
RELEASE_CONTROL_DESCRIPTION = (
    "App-only: the person's Computer page calls this to hand the phone back; do not call it. "
    "args: {}. Returns { mode, held_until }."
)
KEEP_AWAKE_DESCRIPTION = (
    "App-only: the person's Computer page calls this every minute while it is open, so the "
    "phone does not stop for being idle; do not call it. args: {}. Returns {}."
)


def relayed_result(link: Link) -> CallToolResult:
    """The session for the page, and its loopback link in `_meta` for the harness to relay."""
    return CallToolResult(
        content=[TextContent(type="text", text=link.session.model_dump_json())],
        structured_content=link.session.model_dump(mode="json"),
        _meta={RELAY: {"url": link.url}},
    )


def register(server: MCPServer, phone: Phone) -> None:
    """The app-only tools: hidden from the model, called by the Computer page."""

    @server.tool(name="screen_session", description=SCREEN_SESSION_DESCRIPTION, meta=APP_ONLY)
    async def screen_session(mode: ScreenMode) -> Annotated[CallToolResult, ScreenSession]:
        async with machine_for_one_call(phone.machine):
            if mode == "view":
                return relayed_result(await phone.live_screen.view())
            return relayed_result(await phone.live_screen.take_control())

    @server.tool(name="release_control", description=RELEASE_CONTROL_DESCRIPTION, meta=APP_ONLY)
    async def release_control() -> ScreenSession:
        if not phone.live_screen.is_held:
            return ScreenSession(mode="view", held_until=None)
        async with machine_for_one_call(phone.machine):
            return await phone.live_screen.release()

    @server.tool(name="keep_awake", description=KEEP_AWAKE_DESCRIPTION, meta=APP_ONLY)
    async def keep_awake() -> CallToolResult:
        async with machine_for_one_call(phone.machine):
            pass
        return CallToolResult(content=[])
