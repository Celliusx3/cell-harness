"""`/api/mcp/servers`: the servers listed, and added, changed, removed and restarted live."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.mcp_server_world import PAGE, ServerWorld, draft, exa


@pytest.fixture
async def world(tmp_path: Path):
    built = ServerWorld(tmp_path)
    await built.mcp.start()
    await built.settled()
    yield built
    await built.mcp.aclose()


async def test_a_fresh_harness_lists_no_server(world) -> None:
    response = await world.send("GET", "/api/mcp/servers")

    assert response.status_code == 200
    assert response.json() == {"servers": []}


async def test_the_list_holds_every_saved_server(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa())
    await world.settled()

    response = await world.send("GET", "/api/mcp/servers")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PAGE
    assert response.json() == {
        "servers": [
            {
                "id": "exa",
                "command": "npx",
                "args": ["-y", "exa-mcp-server"],
                "env": {"EXA_LIMIT": "5"},
                "keys": [],
                "status": "connected",
                "error": "",
            },
        ]
    }


async def test_an_added_server_starts_and_its_tools_are_offered(world) -> None:
    response = await world.send("POST", "/api/mcp/servers", exa())
    await world.settled()

    assert response.status_code == 201
    assert response.json()["id"] == "exa"
    assert world.status("exa") == "connected"
    assert "exa__search" in world.tool_names()
    assert world.factory.started[-1].env == {"EXA_LIMIT": "5"}


async def test_a_change_restarts_the_server_with_its_new_command(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa())
    await world.settled()

    response = await world.send("PUT", "/api/mcp/servers/exa", draft(exa(command="uvx")))
    await world.settled()

    assert response.status_code == 200
    assert response.json()["command"] == "uvx"
    assert world.factory.started[-1].command == "uvx"
    assert world.saved.servers()[0].command == "uvx"
    assert world.status("exa") == "connected"


async def test_a_removed_server_stops_and_its_tools_go(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa())
    await world.settled()

    response = await world.send("DELETE", "/api/mcp/servers/exa")

    assert response.status_code == 204
    assert "exa" not in {s.id for s in world.mcp.statuses()}
    assert not any(name.startswith("exa__") for name in world.tool_names())
    assert world.saved.servers() == ()


async def test_a_restart_opens_the_server_again(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa())
    await world.settled()
    opened = world.factory.opens

    response = await world.send("POST", "/api/mcp/servers/exa/restart")
    await world.settled()

    assert response.status_code == 200
    assert world.factory.opens == opened + 1
    assert world.status("exa") == "connected"


async def test_an_unknown_server_is_not_found(world) -> None:
    for method, url, body in [
        ("PUT", "/api/mcp/servers/nowhere", draft(exa())),
        ("DELETE", "/api/mcp/servers/nowhere", None),
        ("POST", "/api/mcp/servers/nowhere/restart", None),
    ]:
        response = await world.send(method, url, body)
        assert response.status_code == 404, (method, url)


async def test_an_id_another_server_has_is_refused(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa())
    opened = world.factory.opens

    response = await world.send("POST", "/api/mcp/servers", exa(command="uvx"))

    assert response.status_code == 409
    assert response.headers["access-control-allow-origin"] == PAGE
    assert world.factory.opens == opened
    assert [s.command for s in world.saved.servers()] == ["npx"]


@pytest.mark.parametrize(
    ("client", "origin"),
    [
        (("192.168.1.20", 50000), PAGE),
        (("127.0.0.1", 50000), "https://evil.example"),
    ],
)
async def test_a_change_from_another_device_or_page_is_refused(world, client, origin) -> None:
    await world.send("POST", "/api/mcp/servers", exa())
    opened = world.factory.opens

    answers = [
        await world.send("POST", "/api/mcp/servers", exa(id="maps"), client=client, origin=origin),
        await world.send(
            "PUT", "/api/mcp/servers/exa", draft(exa(command="x")), client=client, origin=origin
        ),
        await world.send("DELETE", "/api/mcp/servers/exa", client=client, origin=origin),
        await world.send("POST", "/api/mcp/servers/exa/restart", client=client, origin=origin),
    ]

    assert [answer.status_code for answer in answers] == [403, 403, 403, 403]
    assert world.factory.opens == opened
    assert [s.id for s in world.saved.servers()] == ["exa"]


async def test_a_body_that_cannot_run_is_refused_unsaved(world) -> None:
    response = await world.send("POST", "/api/mcp/servers", exa(command="  "))

    assert response.status_code == 422
    assert world.saved.servers() == ()


async def test_the_preflight_grants_a_page_on_this_mac_a_change(world) -> None:
    granted = await world.send("OPTIONS", "/api/mcp/servers/exa")
    withheld = await world.send("OPTIONS", "/api/mcp/servers/exa", origin="https://evil.example")

    assert "PUT" in granted.headers["access-control-allow-methods"]
    assert "access-control-allow-origin" not in withheld.headers


async def test_the_sidebar_list_names_every_server_and_nothing_else(world) -> None:
    await world.send("POST", "/api/mcp/servers", exa(needs=["EXA_API_KEY"]))

    body = (await world.send("GET", "/api/mcp")).json()

    assert body == {"servers": ["exa"]}
