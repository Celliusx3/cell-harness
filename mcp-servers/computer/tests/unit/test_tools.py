"""The tools through a real MCP client, in-process."""

from __future__ import annotations

import json

import pytest
from mcp import Client
from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent

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
from tests.conftest import (
    ACTED,
    CDP_DOWN,
    IDLE_SECONDS,
    NAME,
    NAVIGATED,
    SNAPSHOT,
    STALE_REF_REPLY,
    Dial,
    FakeDocker,
    server_with,
)

CLICK = {"kind": "click", "ref": "e1"}
BROWSER_TOOLS = ("browser_act", "browser_navigate", "browser_read_page")
APP_ONLY_TOOLS = {
    "file_download": FILE_DOWNLOAD_DESCRIPTION,
    "file_list": FILE_LIST_DESCRIPTION,
    "file_read": FILE_READ_DESCRIPTION,
    "file_upload": FILE_UPLOAD_DESCRIPTION,
    "keep_awake": KEEP_AWAKE_DESCRIPTION,
    "release_control": RELEASE_CONTROL_DESCRIPTION,
    "screen_session": SCREEN_SESSION_DESCRIPTION,
    "screenshot": SCREENSHOT_DESCRIPTION,
    "terminal_session": TERMINAL_SESSION_DESCRIPTION,
}


def text_of(result: CallToolResult) -> str:
    return "".join(block.text for block in result.content if isinstance(block, TextContent))


async def call(server: MCPServer, tool: str, args: dict[str, object]) -> CallToolResult:
    async with Client(server) as client:
        return await client.call_tool(tool, args)


async def test_exactly_twelve_tools_are_offered_and_the_browser_ones_have_output_schemas() -> None:
    async with Client(server_with(FakeDocker(status="missing"))) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert sorted(tools) == sorted([*BROWSER_TOOLS, *APP_ONLY_TOOLS])
    assert all(tools[name].output_schema is not None for name in BROWSER_TOOLS)
    assert {name: tools[name].description for name in APP_ONLY_TOOLS} == APP_ONLY_TOOLS
    assert all(tools[name].meta == {"ui": {"visibility": ["app"]}} for name in APP_ONLY_TOOLS)


async def test_a_screen_session_publishes_mode_and_held_until_as_its_output() -> None:
    async with Client(server_with(FakeDocker(status="missing"))) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    for name in ("screen_session", "release_control"):
        schema = tools[name].output_schema
        assert schema is not None
        assert set(schema["properties"]) == {"mode", "held_until"}
    assert tools["screen_session"].input_schema["properties"]["mode"]["enum"] == [
        "view",
        "control",
    ]


async def test_the_act_schema_allows_1_to_24_actions() -> None:
    async with Client(server_with(FakeDocker(status="missing"))) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    actions = tools["browser_act"].input_schema["properties"]["actions"]
    assert (actions["minItems"], actions["maxItems"]) == (1, 24)


async def test_navigating_starts_the_computer_and_returns_url_and_title() -> None:
    docker = FakeDocker(status="missing", page_replies=[NAVIGATED])

    result = await call(server_with(docker), "browser_navigate", {"url": "https://example.com"})

    assert not result.is_error, text_of(result)
    assert result.structured_content == {"url": "https://example.com/", "title": "Example Domain"}
    assert docker.verbs() == ["inspect", "inspect", "run", "exec", "exec"]


async def test_reading_returns_url_title_and_content() -> None:
    result = await call(
        server_with(FakeDocker(status="running", page_replies=[SNAPSHOT])), "browser_read_page", {}
    )

    assert result.structured_content is not None
    assert set(result.structured_content) == {"url", "title", "content"}
    assert "Learn more" in result.structured_content["content"]


async def test_acting_returns_the_page_and_how_many_actions_completed() -> None:
    docker = FakeDocker(status="running", page_replies=[ACTED])
    fill = {"kind": "fill", "ref": "e2", "text": "Ada"}

    result = await call(server_with(docker), "browser_act", {"actions": [CLICK, fill]})

    assert result.structured_content is not None
    assert set(result.structured_content) == {"url", "title", "content", "actions_completed"}
    assert result.structured_content["actions_completed"] == 2


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("browser_act", {"actions": [CLICK] * 25}),
        ("browser_act", {"actions": []}),
        ("browser_act", {"actions": [CLICK | {"text": "x"}]}),
        ("browser_act", {"actions": [{"kind": "fill", "ref": "e1"}]}),
        ("browser_navigate", {"url": "example.com"}),
        ("browser_navigate", {"url": "file:///home/rakazo/.bashrc"}),
    ],
)
async def test_arguments_that_do_not_fit_are_refused_before_any_docker_call(
    tool: str, args: dict[str, object]
) -> None:
    docker = FakeDocker(status="running")
    async with Client(server_with(docker)) as client:
        at_startup = list(docker.calls)
        result = await client.call_tool(tool, args)

    assert result.is_error
    assert docker.calls == at_startup


async def test_a_stale_ref_reaches_the_model_as_an_error_naming_what_completed() -> None:
    docker = FakeDocker(status="running", page_replies=[STALE_REF_REPLY])

    result = await call(server_with(docker), "browser_act", {"actions": [CLICK, CLICK]})

    assert result.is_error
    assert "0 of 2 actions completed" in text_of(result)
    assert text_of(result).endswith("Call browser_read_page before going on.")


@pytest.mark.parametrize(
    ("tool", "args", "replies"),
    [
        ("browser_navigate", {"url": "https://example.com"}, [CDP_DOWN, NAVIGATED]),
        ("browser_read_page", {}, [SNAPSHOT]),
        ("browser_read_page", {}, [STALE_REF_REPLY]),
        ("browser_act", {"actions": [CLICK]}, [ACTED]),
        ("browser_act", {"actions": [CLICK]}, [STALE_REF_REPLY]),
    ],
)
async def test_the_model_never_sees_the_scripts_fallback(
    tool: str, args: dict[str, object], replies: list[str]
) -> None:
    result = await call(server_with(FakeDocker(status="running", page_replies=replies)), tool, args)

    seen = text_of(result) + json.dumps(result.structured_content)
    assert "fallback" not in seen
    assert "computer_act" not in seen
    assert "elements" not in seen


async def test_a_docker_failure_reaches_the_model_as_an_error_it_can_report() -> None:
    docker = FakeDocker(status="missing")
    docker.refused_verbs.add("run")

    result = await call(server_with(docker), "browser_navigate", {"url": "https://example.com"})

    assert result.is_error
    assert "The computer is not available: docker run failed" in text_of(result)


async def test_a_server_start_adopts_a_running_computer_and_arms_its_idle_stop() -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    async with Client(server_with(docker, dial)):
        assert docker.verbs() == ["inspect", "exec"]
        await dial.turn(IDLE_SECONDS)

        assert docker.calls[-1] == ["stop", NAME]


async def test_a_server_shutting_down_leaves_the_computer_running() -> None:
    docker, dial = FakeDocker(status="running", page_replies=[SNAPSHOT]), Dial()
    async with Client(server_with(docker, dial)) as client:
        await client.call_tool("browser_read_page", {})
    await dial.turn(IDLE_SECONDS)

    assert "stop" not in docker.verbs()
    assert docker.status == "running"


async def test_keep_awake_starts_a_stopped_computer_and_answers_with_an_empty_result() -> None:
    docker = FakeDocker(status="exited")

    result = await call(server_with(docker), "keep_awake", {})

    assert not result.is_error, text_of(result)
    assert ["start", NAME] in docker.calls
    assert (result.content, result.structured_content) == ([], None)


async def test_a_keep_awake_call_postpones_the_idle_stop() -> None:
    docker, dial = FakeDocker(status="running"), Dial()
    async with Client(server_with(docker, dial)) as client:
        await client.call_tool("keep_awake", {})
        await dial.turn(IDLE_SECONDS - 60)
        await client.call_tool("keep_awake", {})
        await dial.turn(IDLE_SECONDS - 60)
        assert ["stop", NAME] not in docker.calls

        await dial.turn(60)

        assert docker.calls[-1] == ["stop", NAME]
