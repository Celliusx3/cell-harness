"""A saved server survives a restart, waits for its Capability key, and is never half-saved."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.mcp_server_world import ServerWorld, draft, exa

EXA_KEY = "EXA_API_KEY"
CAPABILITY_KEY = {
    "name": "exa",
    "details": {"kind": "capability", "server": "exa", "variable": EXA_KEY},
    "value": "exa-secret-key-1234",
    "bot_ids": [],
}


@pytest.fixture
async def world(tmp_path: Path):
    built = ServerWorld(tmp_path)
    await built.mcp.start()
    await built.settled()
    yield built
    await built.mcp.aclose()


async def test_the_servers_survive_a_new_harness_reading_the_same_file(tmp_path: Path) -> None:
    first = ServerWorld(tmp_path)
    await first.mcp.start()
    await first.send("POST", "/api/mcp/servers", exa())
    await first.mcp.aclose()

    second = ServerWorld(tmp_path)
    await second.mcp.start()
    await second.settled()

    assert second.status("exa") == "connected"
    assert second.mcp.server("exa").args == ("-y", "exa-mcp-server")
    assert "exa__search" in second.tool_names()
    await second.mcp.aclose()


async def test_a_server_that_needs_a_key_waits_until_it_is_saved_on_credentials(world) -> None:
    added = await world.send("POST", "/api/mcp/servers", exa(needs=[EXA_KEY]))

    assert added.json()["status"] == "waiting"
    assert added.json()["error"] == f"needs {EXA_KEY}"

    saved = await world.send("POST", "/api/credentials", CAPABILITY_KEY)
    await world.settled()

    assert saved.status_code == 201
    assert world.status("exa") == "connected"
    assert world.factory.started[-1].env[EXA_KEY] == "exa-secret-key-1234"


async def test_a_key_for_a_variable_the_saved_server_does_not_need_is_refused(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa(needs=[EXA_KEY]))
    wrong = {**CAPABILITY_KEY["details"], "variable": "OTHER_KEY"}

    response = await world.send("POST", "/api/credentials", {**CAPABILITY_KEY, "details": wrong})

    assert response.status_code == 422
    assert world.secrets.saved_credentials() == ()


async def test_a_removed_server_leaves_its_key_in_the_keyring(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa(needs=[EXA_KEY]))
    await world.send("POST", "/api/credentials", CAPABILITY_KEY)

    await world.send("DELETE", "/api/mcp/servers/exa")

    assert [c.name for c in world.secrets.saved_credentials()] == ["exa"]
    assert (await world.send("DELETE", "/api/credentials/exa")).status_code == 204


async def test_an_add_that_cannot_be_written_changes_nothing(world) -> None:
    world.repository.broken = True
    opened = world.factory.opens

    response = await world.send("POST", "/api/mcp/servers", exa())

    assert response.status_code == 500
    assert "could not be saved" in response.json()["detail"]
    assert "exa" not in {s.id for s in world.mcp.statuses()}
    assert world.factory.opens == opened
    assert world.saved.servers() == ()


async def test_a_change_or_removal_that_cannot_be_written_changes_nothing(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa())
    await world.settled()
    world.repository.broken = True
    opened = world.factory.opens

    changed = await world.send("PUT", "/api/mcp/servers/exa", draft(exa(command="uvx")))
    removed = await world.send("DELETE", "/api/mcp/servers/exa")

    assert (changed.status_code, removed.status_code) == (500, 500)
    assert world.mcp.server("exa").command == "npx"
    assert world.status("exa") == "connected"
    assert world.factory.opens == opened
    assert [s.command for s in world.saved.servers()] == ["npx"]
