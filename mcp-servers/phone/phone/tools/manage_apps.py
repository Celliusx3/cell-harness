"""The tools that manage the phone's apps: list them, name the open one, close, remove or clear."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ImageContent

from phone.tools import Phone, phone_for_one_call, screen_after_action

LIST_APPS_DESCRIPTION = "List the apps installed on the phone from APK files, by package name."
FOREGROUND_APP_DESCRIPTION = "Name the app on the phone's screen now, by its package name."
TERMINATE_APP_DESCRIPTION = (
    "Close an app on the phone by its package name, as force-stop does, when it is stuck. Its "
    "data stays. Returns a screenshot."
)
UNINSTALL_APP_DESCRIPTION = (
    "Remove an app and its data from the phone by its package name. Ask the user first. Returns a "
    "screenshot."
)
CLEAR_APP_DATA_DESCRIPTION = (
    "Clear an app's data by its package name, which signs it out and resets it as if just "
    "installed. Ask the user first. Returns a screenshot."
)
NO_APPS = "No apps are installed on the phone from APK files."


def apps_text(packages: tuple[str, ...]) -> str:
    """The packages one per line, or that there are none."""
    return "\n".join(packages) if packages else NO_APPS


def register(server: MCPServer, phone: Phone) -> None:
    @server.tool(name="list_apps", description=LIST_APPS_DESCRIPTION)
    async def list_apps() -> str:
        async with phone_for_one_call(phone):
            return apps_text(await phone.apps.listed())

    @server.tool(name="foreground_app", description=FOREGROUND_APP_DESCRIPTION)
    async def foreground_app() -> str:
        async with phone_for_one_call(phone):
            return await phone.apps.foreground()

    @server.tool(name="terminate_app", description=TERMINATE_APP_DESCRIPTION)
    async def terminate_app(package: str) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.apps.terminate(package)
            return await screen_after_action(phone)

    @server.tool(name="uninstall_app", description=UNINSTALL_APP_DESCRIPTION)
    async def uninstall_app(package: str) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.apps.uninstall(package)
            return await screen_after_action(phone)

    @server.tool(name="clear_app_data", description=CLEAR_APP_DATA_DESCRIPTION)
    async def clear_app_data(package: str) -> ImageContent:
        async with phone_for_one_call(phone):
            await phone.apps.clear_data(package)
            return await screen_after_action(phone)
