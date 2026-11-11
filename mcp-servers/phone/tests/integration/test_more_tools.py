"""Long-press, double-tap, more keys, links, managing apps, and reading the screen as elements."""

from __future__ import annotations

from mcp import Client
from mcp.types import CallToolResult, ImageContent, TextContent

from phone.models.command import CommandResult
from phone.tools.touch import MENU_SECONDS
from tests.fakes import FakeEngine, Ticking, phone_server

PACKAGE = "com.xunmeng.pinduoduo"
VNC = "net.christianbeier.droidvnc_ng"
UI_DUMP = (
    "uiautomator dump /data/local/tmp/cell-harness-ui.xml >/dev/null"
    " && cat /data/local/tmp/cell-harness-ui.xml"
)
DUMP = (
    "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?><hierarchy rotation=\"0\">"
    '<node text="" content-desc="" resource-id="" clickable="false" bounds="[0,0][720,1280]">'
    '<node text="Lenovo M910x Tiny" content-desc="" resource-id="com.x:id/title" '
    'clickable="true" bounds="[10,600][350,640]" />'
    '<node text="" content-desc="Share" resource-id="" clickable="true" '
    'bounds="[600,40][680,120]" />'
    '<node text="" content-desc="" resource-id="com.x:id/spacer" clickable="false" '
    'bounds="[0,0][1,1]" />'
    "</node></hierarchy>"
)
FOREGROUND = (
    "  topResumedActivity=ActivityRecord{1a2b3c u0 com.xunmeng.pinduoduo/"
    ".ui.activity.MainFrameActivity t12}\n"
)


def texts(result: CallToolResult) -> str:
    return " ".join(part.text for part in result.content if isinstance(part, TextContent))


async def test_long_press_double_tap_keys_and_links_run_androids_commands() -> None:
    engine = FakeEngine(state="running")
    calls = [
        ("long_press", {"x": 300, "y": 232}),
        ("double_tap", {"x": 100, "y": 200}),
        ("press_key", {"key": "paste"}),
        ("press_key", {"key": "tab"}),
        ("press_key", {"key": "search"}),
        ("press_key", {"key": "volume_up"}),
        ("press_key", {"key": "volume_down"}),
        ("open_url", {"url": "https://mobile.yangkeduo.com/goods1.html?ps=XgAmhy1ENM"}),
    ]

    async with Client(phone_server(engine)) as client:
        results = [await client.call_tool(name, args) for name, args in calls]

    assert all(not r.is_error and isinstance(r.content[-1], ImageContent) for r in results)
    assert engine.commands == [
        "input swipe 300 232 300 232 1000",
        "input tap 100 200",
        "input tap 100 200",
        "input keyevent KEYCODE_PASTE",
        "input keyevent KEYCODE_TAB",
        "input keyevent KEYCODE_SEARCH",
        "input keyevent KEYCODE_VOLUME_UP",
        "input keyevent KEYCODE_VOLUME_DOWN",
        "am start -W -a android.intent.action.VIEW -d "
        "'https://mobile.yangkeduo.com/goods1.html?ps=XgAmhy1ENM'",
    ]


async def test_a_link_that_is_not_a_web_address_is_refused() -> None:
    engine = FakeEngine(state="running")

    async with Client(phone_server(engine)) as client:
        result = await client.call_tool("open_url", {"url": "file:///data/data/x"})

    assert result.is_error
    assert "only http and https" in texts(result)
    assert engine.commands == []


async def test_a_bot_lists_sees_closes_removes_and_clears_apps() -> None:
    engine = FakeEngine(
        state="running",
        packages=frozenset({PACKAGE, VNC}),
        answers={
            "dumpsys activity activities": CommandResult(0, FOREGROUND, ""),
            f"pm uninstall {PACKAGE}": CommandResult(0, "Success\n", ""),
            f"pm clear {PACKAGE}": CommandResult(0, "Success\n", ""),
        },
    )

    async with Client(phone_server(engine)) as client:
        listed = await client.call_tool("list_apps", {})
        foreground = await client.call_tool("foreground_app", {})
        closed = await client.call_tool("terminate_app", {"package": PACKAGE})
        cleared = await client.call_tool("clear_app_data", {"package": PACKAGE})
        removed = await client.call_tool("uninstall_app", {"package": PACKAGE})

    assert PACKAGE in texts(listed)
    assert VNC not in texts(listed)
    assert PACKAGE in texts(foreground)
    assert not any(r.is_error for r in (closed, cleared, removed))
    assert f"am force-stop {PACKAGE}" in engine.commands
    assert f"pm clear {PACKAGE}" in engine.commands
    assert f"pm uninstall {PACKAGE}" in engine.commands


async def test_the_persons_screen_app_cannot_be_removed_or_cleared() -> None:
    engine = FakeEngine(state="running", packages=frozenset({VNC}))

    async with Client(phone_server(engine)) as client:
        removed = await client.call_tool("uninstall_app", {"package": VNC})
        cleared = await client.call_tool("clear_app_data", {"package": VNC})

    assert removed.is_error and cleared.is_error
    assert "the person's view of the phone" in texts(removed)
    assert not any(VNC in command for command in engine.commands if "list" not in command)


async def test_the_screen_is_read_as_elements_with_their_centres() -> None:
    engine = FakeEngine(state="running", answers={UI_DUMP: CommandResult(0, DUMP, "")})

    async with Client(phone_server(engine)) as client:
        result = await client.call_tool("list_elements", {})

    text = texts(result)
    assert not result.is_error
    assert 'text "Lenovo M910x Tiny"' in text
    assert "center (180, 620)" in text
    assert 'description "Share"' in text
    assert "center (640, 80)" in text
    assert "spacer" not in text


async def test_a_long_press_waits_for_androids_menu_before_its_screenshot() -> None:
    engine, ticking = FakeEngine(state="running", boot_polls_needed=1), Ticking()

    async with Client(phone_server(engine, clock=ticking.clock)) as client:
        before = ticking.now
        await client.call_tool("long_press", {"x": 300, "y": 232})

    assert ticking.now - before >= MENU_SECONDS
