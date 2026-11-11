"""The person watches the phone, takes control, and the bots wait until it is handed back."""

from __future__ import annotations

from mcp import Client
from mcp.types import CallToolResult, TextContent

from tests.fakes import GATEWAY_HOST_PORT, FakeEngine, phone_server

RELAY = "io.cell-harness/relay"


def relay_url(result: CallToolResult) -> str:
    assert result.meta is not None
    return result.meta[RELAY]["url"]


def texts(result: CallToolResult) -> str:
    return " ".join(part.text for part in result.content if isinstance(part, TextContent))


async def test_viewing_gives_a_view_only_link_to_the_phones_screen_on_loopback() -> None:
    engine = FakeEngine(state="running")

    async with Client(phone_server(engine)) as client:
        result = await client.call_tool("screen_session", {"mode": "view"})

    assert not result.is_error
    assert result.structured_content == {"mode": "view", "held_until": None}
    url = relay_url(result)
    assert url.startswith(f"http://127.0.0.1:{GATEWAY_HOST_PORT}/embed.html?")
    assert "view_only=1" in url
    assert any(command.startswith("phone-screen view ") for command in engine.screen_commands)


async def test_a_bot_waits_while_the_person_has_the_phone_and_acts_once_released() -> None:
    engine = FakeEngine(state="running")

    async with Client(phone_server(engine)) as client:
        taken = await client.call_tool("screen_session", {"mode": "control"})
        refused = await client.call_tool("tap", {"x": 10, "y": 10})
        released = await client.call_tool("release_control", {})
        tapped = await client.call_tool("tap", {"x": 10, "y": 10})

    assert taken.structured_content is not None
    assert taken.structured_content["mode"] == "control"
    assert taken.structured_content["held_until"] is not None
    assert "view_only=0" in relay_url(taken)
    assert refused.is_error
    assert "a person has the phone" in texts(refused).lower()
    assert released.structured_content == {"mode": "view", "held_until": None}
    assert not tapped.is_error
    assert engine.commands.count("input tap 10 10") == 1
    assert "phone-screen release" in engine.screen_commands


async def test_the_screen_tools_are_hidden_from_the_model() -> None:
    async with Client(phone_server(FakeEngine(state="running"))) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    for name in ("screen_session", "release_control", "keep_awake"):
        assert tools[name].meta == {"ui": {"visibility": ["app"]}}


async def test_watching_while_the_person_holds_the_phone_gives_back_their_hold() -> None:
    engine = FakeEngine(state="running")

    async with Client(phone_server(engine)) as client:
        taken = await client.call_tool("screen_session", {"mode": "control"})
        watched = await client.call_tool("screen_session", {"mode": "view"})

    assert watched.structured_content == taken.structured_content
    assert "view_only=0" in relay_url(watched)
