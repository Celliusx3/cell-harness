"""A bot installs an APK from the chat files, opens it, and taps, swipes, types and presses keys."""

from __future__ import annotations

import base64
from pathlib import Path

from mcp import Client
from mcp.types import CallToolResult, ImageContent, TextContent

from phone.models.command import CommandResult
from tests.fakes import FakeEngine, phone_server

APK = b"PK\x03\x04apk"
PACKAGE = "com.example.notes"
ACTIVITY = f"{PACKAGE}/.MainActivity"
RESOLVE = f"cmd package resolve-activity --brief -c android.intent.category.LAUNCHER {PACKAGE}"
RESOLVED = CommandResult(0, f"priority=0 preferredOrder=0 match=0x108000\n{ACTIVITY}\n", "")


def texts(result: CallToolResult) -> str:
    return " ".join(part.text for part in result.content if isinstance(part, TextContent))


def ends_with_screenshot(result: CallToolResult) -> bool:
    return not result.is_error and isinstance(result.content[-1], ImageContent)


async def test_an_apk_from_the_chat_files_is_installed_and_its_package_named(
    tmp_path: Path,
) -> None:
    apk = tmp_path / "notes.apk"
    apk.write_bytes(APK)
    engine = FakeEngine(state="running", installs=PACKAGE)

    async with Client(phone_server(engine, files_dir=tmp_path)) as client:
        result = await client.call_tool("install_app", {"path": str(apk)})

    assert ends_with_screenshot(result)
    assert PACKAGE in texts(result)
    install = f"base64 -d | pm install -S {len(APK)}"
    assert engine.commands.count(install) == 1
    assert engine.stdins[engine.commands.index(install)] == base64.b64encode(APK).decode()


async def test_a_file_outside_the_chat_files_is_refused(tmp_path: Path) -> None:
    files = tmp_path / "files"
    files.mkdir()
    elsewhere = tmp_path / "elsewhere.apk"
    elsewhere.write_bytes(APK)
    engine = FakeEngine(state="running", installs=PACKAGE)

    async with Client(phone_server(engine, files_dir=files)) as client:
        result = await client.call_tool("install_app", {"path": str(elsewhere)})

    assert result.is_error
    assert "is not one of this chat's files" in texts(result)
    assert not any("pm install" in command for command in engine.commands)


async def test_each_action_runs_its_input_command_and_ends_with_a_screenshot(
    tmp_path: Path,
) -> None:
    engine = FakeEngine(state="running", answers={RESOLVE: RESOLVED})
    calls = [
        ("open_app", {"package": PACKAGE}),
        ("tap", {"x": 300, "y": 232}),
        ("swipe", {"from_x": 360, "from_y": 1000, "to_x": 360, "to_y": 300}),
        ("type_text", {"text": "Hello from Cell's phone"}),
        ("press_key", {"key": "back"}),
    ]

    async with Client(phone_server(engine, files_dir=tmp_path)) as client:
        results = [await client.call_tool(name, args) for name, args in calls]

    assert all(ends_with_screenshot(result) for result in results)
    assert engine.commands == [
        RESOLVE,
        f"am start -W -n {ACTIVITY}",
        "input tap 300 232",
        "input swipe 360 1000 360 300 300",
        "input text 'Hello%sfrom%sCell'\\''s%sphone'",
        "input keyevent KEYCODE_BACK",
    ]


async def test_text_android_cannot_type_is_refused(tmp_path: Path) -> None:
    engine = FakeEngine(state="running")

    async with Client(phone_server(engine, files_dir=tmp_path)) as client:
        result = await client.call_tool("type_text", {"text": "拼多多"})

    assert result.is_error
    assert "can only type ASCII" in texts(result)
    assert engine.commands == []
