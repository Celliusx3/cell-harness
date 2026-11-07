"""A saved server survives a restart, keeps its keys in its own file, and is never half-saved."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.mcp_server_world import ServerWorld, draft, exa

EXA_KEY = "EXA_API_KEY"
SECRET = "exa-secret-key-1234"


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


async def test_a_server_that_needs_a_key_waits_until_an_edit_gives_it(world) -> None:
    added = await world.send("POST", "/api/mcp/servers", exa(needs=[EXA_KEY]))

    assert added.json()["status"] == "waiting"
    assert added.json()["error"] == f"needs {EXA_KEY}"

    body = draft(exa(needs=[EXA_KEY], keys={EXA_KEY: SECRET}))
    changed = await world.send("PUT", "/api/mcp/servers/exa", body)
    await world.settled()

    assert changed.status_code == 200
    assert changed.json()["keys"] == [{"name": EXA_KEY, "is_set": True}]
    assert world.status("exa") == "connected"
    assert world.factory.started[-1].env[EXA_KEY] == SECRET


@pytest.mark.parametrize(
    ("keys", "refusal"),
    [
        ({"OTHER_KEY": SECRET}, "OTHER_KEY is not a key this server needs"),
        ({EXA_KEY: "  "}, f"{EXA_KEY} is blank; leave a key out to keep the one saved"),
    ],
)
async def test_a_key_not_needed_or_blank_is_refused_unsaved_and_unechoed(
    world, keys: dict[str, str], refusal: str
) -> None:
    response = await world.send("POST", "/api/mcp/servers", exa(needs=[EXA_KEY], keys=keys))

    assert response.status_code == 422
    assert refusal in response.text
    assert SECRET not in response.text
    assert world.saved.servers() == ()


async def test_a_key_no_longer_needed_is_dropped_from_the_file(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa(needs=[EXA_KEY], keys={EXA_KEY: SECRET}))

    await world.send("PUT", "/api/mcp/servers/exa", draft(exa()))

    assert SECRET not in world.path.read_text()
    assert EXA_KEY not in world.saved.servers()[0].env


async def test_a_removed_server_takes_its_key_with_it(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa(needs=[EXA_KEY], keys={EXA_KEY: SECRET}))

    await world.send("DELETE", "/api/mcp/servers/exa")

    assert SECRET not in world.path.read_text()


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
