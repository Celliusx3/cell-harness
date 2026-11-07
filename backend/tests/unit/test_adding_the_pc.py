"""The bots' PC is added on the MCP servers screen with the command `config.json` used to run it."""

from __future__ import annotations

from pathlib import Path

from tests.unit.mcp_fakes import FakeFactory
from tests.unit.mcp_server_world import ServerWorld

NO_VIRTUALIZATION = "this Mac cannot run the PC: turn on virtualization"
PC = {
    "id": "computer",
    "command": "uv",
    "args": ["run", "--quiet", "--project", "../mcp-servers/computer", "computer"],
    "env": {
        "COMPUTER_ENGINE": "microsandbox",
        "COMPUTER_IDLE_MINUTES": "10",
        "COMPUTER_FILES_DIR": "~/.harness/files",
        "COMPUTER_SKILLS_DIRS": "../.agents/skills",
    },
    "needs": [],
    "keys": {},
}


async def test_the_pc_added_on_the_screen_runs_with_its_command_and_is_listed(tmp_path) -> None:
    world = ServerWorld(tmp_path)

    added = await world.send("POST", "/api/mcp/servers", PC)
    await world.settled()

    assert added.status_code == 201, added.text
    started = world.factory.started[-1]
    assert (started.command, started.args) == ("uv", tuple(PC["args"]))
    assert started.env["COMPUTER_FILES_DIR"] == str(Path.home() / ".harness" / "files")
    assert world.status("computer") == "connected"
    assert (await world.send("GET", "/api/mcp")).json() == {"servers": ["computer"]}
    await world.mcp.aclose()


async def test_a_pc_that_cannot_start_shows_why_and_the_app_goes_on(tmp_path) -> None:
    world = ServerWorld(tmp_path, FakeFactory(connect_error=RuntimeError(NO_VIRTUALIZATION)))

    added = await world.send("POST", "/api/mcp/servers", PC)
    await world.settled()
    listed = await world.send("GET", "/api/mcp/servers")

    assert added.status_code == 201, added.text
    [entry] = listed.json()["servers"]
    assert (entry["id"], entry["status"]) == ("computer", "failed")
    assert NO_VIRTUALIZATION in entry["error"]
    assert [server.id for server in world.saved.servers()] == ["computer"]
    await world.mcp.aclose()
