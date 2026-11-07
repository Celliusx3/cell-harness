"""A key an MCP server needs is typed on the MCP servers screen and saved with that server."""

from __future__ import annotations

import asyncio
import stat
import sys
from pathlib import Path

import httpx
import pytest

from harness.mcp import McpService
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import no_skills
from tests.webapp import web_app, web_mcp

STUB = Path(__file__).resolve().parent.parent / "mcp_stub.py"
PAGE = "http://127.0.0.1:4887"
THIS_MAC = ("127.0.0.1", 50000)
FAKE_KEY = "FAKE_KEY"
FIRST = "fake-secret-first-1234"
SECOND = "fake-secret-second-5678"
TIMEOUT = 30.0


def stub(server_id: str, keys: dict[str, str]) -> dict:
    """An add-server body for the stub, needing `FAKE_KEY`, with the keys typed in."""
    return {"id": server_id, **change(keys)}


def change(keys: dict[str, str]) -> dict:
    """A change-server body for the stub: its command, one plain setting, and the keys typed."""
    return {
        "command": sys.executable,
        "args": ["-u", str(STUB)],
        "env": {"STUB_LABEL": "plain"},
        "needs": [FAKE_KEY],
        "keys": keys,
    }


@pytest.fixture
async def harness(tmp_path: Path):
    """The app over a real stdio MCP service and a servers file under `tmp_path`."""
    mcp = web_mcp()
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    app = web_app(tmp_path, service, runs, mcp=mcp, skills=no_skills())
    transport = httpx.ASGITransport(app=app, client=THIS_MAC)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1:4886", headers={"origin": PAGE}
    ) as http:
        yield http, mcp
    await mcp.aclose()


async def connected(mcp: McpService, server_id: str) -> None:
    for _ in range(int(TIMEOUT * 10)):
        state = next(s for s in mcp.statuses() if s.id == server_id)
        if state.status != "connecting":
            break
        await asyncio.sleep(0.1)
    assert state.status == "connected", state.error


async def key_in_env(mcp: McpService, server_id: str) -> str:
    result = await mcp.call(server_id, "env_value", {"name": FAKE_KEY})
    return result.content[0].text


async def test_a_key_typed_with_its_server_reaches_its_env_and_is_never_listed(
    harness, tmp_path: Path
) -> None:
    http, mcp = harness
    servers_file = tmp_path / "mcp.json"

    added = await http.post("/api/mcp/servers", json=stub("stub", {FAKE_KEY: FIRST}))
    assert added.status_code == 201, added.text
    await connected(mcp, "stub")

    assert await key_in_env(mcp, "stub") == FIRST
    assert stat.S_IMODE(servers_file.stat().st_mode) == 0o600
    assert FIRST in servers_file.read_text()

    listed = await http.get("/api/mcp/servers")
    assert FIRST not in listed.text
    [entry] = listed.json()["servers"]
    assert entry["env"] == {"STUB_LABEL": "plain"}
    assert entry["keys"] == [{"name": FAKE_KEY, "is_set": True}]

    credentials = await http.get("/api/credentials")
    assert credentials.json()["credentials"] == []
    assert "capability" not in credentials.text


async def test_a_key_left_blank_on_an_edit_is_kept_and_a_new_one_restarts_the_server(
    harness, tmp_path: Path
) -> None:
    http, mcp = harness
    await http.post("/api/mcp/servers", json=stub("stub", {FAKE_KEY: FIRST}))
    await connected(mcp, "stub")

    kept = await http.put("/api/mcp/servers/stub", json=change({}))
    assert kept.status_code == 200, kept.text
    await connected(mcp, "stub")
    assert await key_in_env(mcp, "stub") == FIRST
    assert FIRST in (tmp_path / "mcp.json").read_text()

    replaced = await http.put("/api/mcp/servers/stub", json=change({FAKE_KEY: SECOND}))
    assert replaced.status_code == 200, replaced.text
    await connected(mcp, "stub")
    assert await key_in_env(mcp, "stub") == SECOND


async def test_a_server_saved_without_its_key_waits_naming_it(harness) -> None:
    http, _ = harness

    added = await http.post("/api/mcp/servers", json=stub("bare", {}))

    assert added.status_code == 201, added.text
    assert (added.json()["status"], added.json()["error"]) == ("waiting", f"needs {FAKE_KEY}")
    assert added.json()["keys"] == [{"name": FAKE_KEY, "is_set": False}]
