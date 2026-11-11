"""The app tools: install an APK from the chat's files, open an app by its package, or a link."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ImageContent, TextContent

from phone.tools import Phone, phone_for_one_call, screen_after_action

INSTALL_APP_DESCRIPTION = (
    "Install an Android app on the phone from an APK file in this chat's files. `path` is the "
    "file's full path, as the chat names it. Returns the installed app's package name and a "
    "screenshot."
)
OPEN_APP_DESCRIPTION = (
    "Open an installed app by its package name, such as com.example.notes. Returns a screenshot."
)
OPEN_URL_DESCRIPTION = (
    "Open a web link on the phone. The app that handles the link opens it, such as Pinduoduo for "
    "its own links, and otherwise the browser does. Only http and https links. Returns a "
    "screenshot."
)
REINSTALLED = "Reinstalled an app that was already on the phone; its package name is unchanged."


def installed(packages: tuple[str, ...]) -> str:
    """What the install did, in a sentence naming the packages it added."""
    return f"Installed {', '.join(packages)}." if packages else REINSTALLED


def register(server: MCPServer, phone: Phone) -> None:
    @server.tool(name="install_app", description=INSTALL_APP_DESCRIPTION)
    async def install_app(path: str) -> list[TextContent | ImageContent]:
        async with phone_for_one_call(phone):
            packages = await phone.apps.install(path)
            screen = await screen_after_action(phone)
        return [TextContent(type="text", text=installed(packages)), screen]

    @server.tool(name="open_app", description=OPEN_APP_DESCRIPTION)
    async def open_app(package: str) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.apps.open(package)
            return await screen_after_action(phone)

    @server.tool(name="open_url", description=OPEN_URL_DESCRIPTION)
    async def open_url(url: str) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.apps.open_url(url)
            return await screen_after_action(phone)
