"""The screen preview on a browser_navigate card: the ui:// resource, and which tools it binds."""

from __future__ import annotations

from mcp import Client
from mcp.server.apps import APP_MIME_TYPE
from mcp.types import TextResourceContents, Tool

from tests.conftest import FakeDocker, server_with

PREVIEW_URI = "ui://computer/screen"
UNBOUND = ("browser_read_page", "browser_act")


async def offered_tools() -> dict[str, Tool]:
    async with Client(server_with(FakeDocker(status="missing"))) as client:
        return {tool.name: tool for tool in (await client.list_tools()).tools}


async def preview_resource() -> TextResourceContents:
    async with Client(server_with(FakeDocker(status="missing"))) as client:
        (content,) = (await client.read_resource(PREVIEW_URI)).contents
    assert isinstance(content, TextResourceContents)
    return content


async def test_screenshot_is_app_only_and_bound_to_no_preview() -> None:
    screenshot = (await offered_tools())["screenshot"]

    assert screenshot.meta is not None
    assert screenshot.meta["ui"] == {"visibility": ["app"]}


async def test_keep_awake_is_app_only_and_bound_to_no_preview() -> None:
    keep_awake = (await offered_tools())["keep_awake"]

    assert keep_awake.meta is not None
    assert keep_awake.meta["ui"] == {"visibility": ["app"]}


async def test_the_screen_session_tools_are_app_only_and_bound_to_no_preview() -> None:
    tools = await offered_tools()

    for name in ("screen_session", "release_control"):
        meta = tools[name].meta
        assert meta is not None
        assert meta["ui"] == {"visibility": ["app"]}


async def test_browser_navigate_opens_the_preview() -> None:
    navigate = (await offered_tools())["browser_navigate"]

    assert navigate.meta is not None
    assert navigate.meta["ui"]["resourceUri"] == PREVIEW_URI


async def test_the_preview_cannot_open_pages_past_the_approval_card() -> None:
    navigate = (await offered_tools())["browser_navigate"]

    assert navigate.meta is not None
    assert navigate.meta["ui"]["visibility"] == ["model"]


async def test_reading_and_acting_carry_no_ui() -> None:
    tools = await offered_tools()

    assert all("ui" not in (tools[name].meta or {}) for name in UNBOUND)


async def test_the_preview_is_served_as_an_mcp_app_that_reaches_no_network() -> None:
    content = await preview_resource()

    assert content.mime_type == APP_MIME_TYPE
    assert content.meta is not None
    assert "connectDomains" not in content.meta["ui"]["csp"]


async def test_the_preview_asks_for_a_screenshot_only_after_each_answer() -> None:
    html = (await preview_resource()).text

    assert '"tools/call"' in html
    assert 'name: "screenshot"' in html
    assert "setInterval" not in html
    assert "<script src" not in html


async def test_the_preview_only_watches_and_sends_no_input() -> None:
    html = (await preview_resource()).text

    assert 'name: "control"' not in html
    assert 'addEventListener("keydown"' not in html
    assert 'addEventListener("click"' not in html


async def test_the_preview_fits_itself_to_the_display_mode_the_host_names() -> None:
    html = (await preview_resource()).text

    assert "hostContext" in html
    assert "displayMode" in html
