"""A server's tools the person marked offered from the start reach a worker on its first step."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.llm import ToolCall
from harness.mcp import DiskSavedServerRepository, McpService, SavedServer, SavedServerService
from harness.tools import CallOrigin, Ok, ToolService, Toolset
from tests.unit.fakes import echo_tool
from tests.unit.helpers import new_session, no_approvals
from tests.unit.mcp_fakes import FakeFactory, servers, tool
from tests.unit.test_not_offered_refusal import _ignore

ORIGIN = CallOrigin(bot_id="b", conversation_id="s", mode="auto", workspace=None)


async def test_the_service_names_a_server_s_offered_tools_as_the_model_calls_them() -> None:
    factory = FakeFactory()
    factory.client.tools = [tool("shell"), tool("screenshot")]
    store = await connected_with_offered(factory, ("shell", "gone"))

    assert store.offered_from_start() == frozenset({"stub__shell"})
    await store.aclose()
    assert store.offered_from_start() == frozenset()


async def connected_with_offered(factory: FakeFactory, offered: tuple[str, ...]) -> McpService:
    store = McpService(servers(offered=offered), client_factory=factory)
    await store.start()
    for _ in range(200):
        if all(s.status != "connecting" for s in store.statuses()):
            return store
        await asyncio.sleep(0.01)
    raise AssertionError("never left `connecting`")


def toolset_offering(*names: str, from_start: frozenset[str]) -> Toolset:
    tools = [echo_tool(name) for name in names]
    return Toolset(
        ToolService(tools, approvals=no_approvals()),
        default_tools=("get_function_details",),
        sight_tools=frozenset(),
        can_reach_servers=True,
        offered_from_start=lambda: from_start,
    )


async def test_a_tool_offered_from_the_start_is_in_the_first_step_s_list_and_runs() -> None:
    toolset = toolset_offering(
        "computer__shell",
        "computer__screenshot",
        from_start=frozenset({"computer__shell", "missing__tool"}),
    )

    names = [spec.name for spec in toolset.specs((), sees_images=False)]
    outcome = await toolset.execute(
        ToolCall(id="c1", name="computer__shell", arguments=json.dumps({"value": "ls"})),
        progress=_ignore,
        origin=ORIGIN,
        session=new_session(),
        sees_images=False,
    )

    assert names == ["computer__shell"]
    assert isinstance(outcome, Ok)


def test_a_saved_file_from_before_offered_loads_with_none(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    server = {"id": "exa", "command": "npx", "args": [], "env": {}, "needs": []}
    path.write_text(json.dumps({"servers": [server]}))

    [saved] = SavedServerService(DiskSavedServerRepository(path)).servers()

    assert saved.offered == ()
    assert saved.mcp_server().offered == ()


def test_offered_tools_are_saved_and_run_with_the_server(tmp_path: Path) -> None:
    service = SavedServerService(DiskSavedServerRepository(tmp_path / "mcp.json"))
    service.add(
        SavedServer(id="computer", command="uv", args=(), env={}, needs=(), offered=("shell",))
    )

    [saved] = SavedServerService(DiskSavedServerRepository(tmp_path / "mcp.json")).servers()

    assert saved.offered == ("shell",)
    assert saved.mcp_server().offered == ("shell",)


@pytest.mark.parametrize("blank", ["", "  "])
def test_a_blank_offered_tool_name_is_refused(blank: str) -> None:
    with pytest.raises(ValidationError, match="offered"):
        SavedServer(id="computer", command="uv", args=(), env={}, needs=(), offered=(blank,))
