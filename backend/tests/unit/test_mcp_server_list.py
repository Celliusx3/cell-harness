"""`GET /api/mcp`: the capabilities this harness is set up with."""

from __future__ import annotations

import httpx

from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import no_skills
from tests.unit.mcp_fakes import servers
from tests.webapp import web_app, web_mcp


async def _listed(tmp_path, mcp) -> list[str]:
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    app = web_app(tmp_path, service, runs, mcp=mcp, skills=no_skills())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as http:
        response = await http.get("/api/mcp")
    assert response.status_code == 200
    return response.json()["servers"]


async def test_every_configured_server_is_listed_by_its_namespace(tmp_path) -> None:
    assert await _listed(tmp_path, web_mcp(servers("computer", "places"))) == [
        "computer",
        "places",
    ]


async def test_a_harness_with_no_capability_lists_none(tmp_path) -> None:
    assert await _listed(tmp_path, web_mcp()) == []


async def test_each_capability_that_needs_a_key_is_listed_with_its_keys_and_status(
    tmp_path,
) -> None:
    configured = {
        **servers("fs"),
        **servers("places", needs=("GOOGLE_MAPS_API_KEY",)),
    }
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    mcp = web_mcp(configured)
    await mcp.start()
    app = web_app(tmp_path, service, runs, mcp=mcp, skills=no_skills())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as http:
        body = (await http.get("/api/mcp")).json()
    await mcp.aclose()

    assert body["servers"] == ["fs", "places"]
    assert body["keyed"] == [
        {
            "id": "places",
            "needs": ["GOOGLE_MAPS_API_KEY"],
            "status": "waiting",
            "error": "needs GOOGLE_MAPS_API_KEY",
        }
    ]
