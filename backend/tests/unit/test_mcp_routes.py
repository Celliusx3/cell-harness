"""`/api/mcp/{server}/…`: an app's HTML, and the calls an app makes back."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from mcp.types import CallToolResult, ImageContent, TextContent

from harness.web.routes.mcp import build_csp
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import no_skills
from tests.unit.mcp_fakes import FakeClient, FakeFactory, html_resource, servers, text_result, tool
from tests.webapp import web_app, web_mcp

APP = "ui://stub/app.html"


@pytest.fixture
async def api(tmp_path):
    client = FakeClient(
        tools=[
            tool("get-info", meta={"ui": {"resourceUri": APP}}),
            tool("poll-stats", meta={"ui": {"visibility": ["app"]}}),
            tool("model-only", meta={"ui": {"visibility": ["model"]}}),
            tool("other-app", meta={"ui": {"resourceUri": "ui://stub/other.html"}}),
            tool("boom"),
        ],
        behaviour={
            "get-info": CallToolResult(
                content=[TextContent(type="text", text="info")], structuredContent={"cpu": 4}
            ),
            "poll-stats": CallToolResult(
                content=[
                    TextContent(type="text", text="stats"),
                    ImageContent(type="image", data="QUJD", mimeType="image/png"),
                ],
                structuredContent={"load": 0.5},
                _meta={"ts": 1},
            ),
            "boom": text_result("it broke", is_error=True),
        },
        resources={
            APP: html_resource(APP, "<html><body>app</body></html>"),
            "ui://stub/cdn.html": html_resource(
                "ui://stub/cdn.html",
                "<p>",
                meta={"ui": {"csp": {"resourceDomains": ["https://cdn.example/x.js"]}}},
            ),
            "ui://stub/plain.html": html_resource("ui://stub/plain.html", "<p>", mime="text/html"),
        },
    )
    store = web_mcp(servers("stub"), client_factory=FakeFactory(client))
    await store.start()
    for _ in range(200):
        if store.statuses()[0].status != "connecting":
            break
        await asyncio.sleep(0.01)
    service, runs = build(tmp_path, ScriptedClient(completed("hi")))
    app = web_app(tmp_path, service, runs, mcp=store, skills=no_skills())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as http:
        yield http, store, client
    await store.aclose()


async def test_an_apps_html_is_read_with_the_default_policy(api) -> None:
    http, _, client = api

    response = await http.get("/api/mcp/stub/resources", params={"uri": APP})

    assert response.status_code == 200
    body = response.json()
    assert body["html"] == "<html><body>app</body></html>"
    assert body["csp"] == build_csp(None)
    assert "connect-src 'none'" in body["csp"]
    assert client.reads == [APP]


async def test_declared_domains_widen_the_policy(api) -> None:
    http, _, _ = api

    response = await http.get("/api/mcp/stub/resources", params={"uri": "ui://stub/cdn.html"})

    assert "script-src 'unsafe-inline' https://cdn.example" in response.json()["csp"]


async def test_only_a_ui_resource_can_be_read(api) -> None:
    http, _, client = api

    response = await http.get("/api/mcp/stub/resources", params={"uri": "file:///etc/passwd"})

    assert response.status_code == 400
    assert client.reads == []


async def test_a_resource_that_is_not_an_app_is_refused(api) -> None:
    http, _, _ = api

    response = await http.get("/api/mcp/stub/resources", params={"uri": "ui://stub/plain.html"})

    assert response.status_code == 400
    assert "text/html;profile=mcp-app" in response.json()["detail"]


async def test_an_unknown_server_is_not_found(api) -> None:
    http, _, _ = api
    assert (await http.get("/api/mcp/nope/resources", params={"uri": APP})).status_code == 404
    assert (await http.post("/api/mcp/nope/tools/x", json=call())).status_code == 404


async def test_a_server_that_is_down_is_unavailable(api) -> None:
    http, store, _ = api
    await store.aclose()

    response = await http.get("/api/mcp/stub/resources", params={"uri": APP})

    assert response.status_code == 503


def call(arguments: dict | None = None, *, app: str = APP) -> dict:
    return {"arguments": arguments or {}, "resource_uri": app}


async def test_an_apps_call_is_proxied_and_answered_verbatim(api) -> None:
    http, _, client = api

    response = await http.post("/api/mcp/stub/tools/poll-stats", json=call({"n": 1}))

    assert response.status_code == 200
    assert response.json() == {
        "content": [
            {"type": "text", "text": "stats"},
            {"type": "image", "data": "QUJD", "mimeType": "image/png"},
        ],
        "structuredContent": {"load": 0.5},
        "isError": False,
        "_meta": {"ts": 1},
        "resultType": "complete",
    }
    assert client.calls == [("poll-stats", {"n": 1})]


async def test_a_tool_that_fails_is_a_result_the_app_can_show(api) -> None:
    http, _, _ = api

    response = await http.post("/api/mcp/stub/tools/boom", json=call())

    assert response.status_code == 200
    body = response.json()
    assert body["isError"] is True
    assert body["content"] == [{"type": "text", "text": "it broke"}]


async def test_an_app_cannot_reach_beyond_its_server(api) -> None:
    http, _, client = api

    response = await http.post("/api/mcp/stub/tools/clock", json=call())

    assert response.status_code == 404
    assert response.json() == {"detail": "stub has no tool 'clock'"}
    assert (
        await http.post("/api/mcp/stub/tools/execute_typescript", json=call())
    ).status_code == 404
    assert client.calls == []


async def test_a_model_only_tool_is_refused_to_apps(api) -> None:
    http, _, client = api

    response = await http.post("/api/mcp/stub/tools/model-only", json=call())

    assert response.status_code == 403
    assert client.calls == []


async def test_a_tool_bound_to_another_app_is_refused(api) -> None:
    http, _, client = api

    response = await http.post("/api/mcp/stub/tools/other-app", json=call())

    assert response.status_code == 403
    assert "ui://stub/other.html" in response.json()["detail"]
    assert (await http.post("/api/mcp/stub/tools/get-info", json=call())).status_code == 200
    assert client.calls == [("get-info", {})]


async def test_calling_a_server_that_is_down_is_unavailable(api) -> None:
    http, store, _ = api
    await store.aclose()

    assert (await http.post("/api/mcp/stub/tools/get-info", json=call())).status_code == 503


def test_the_default_policy_allows_inline_and_no_network() -> None:
    csp = build_csp(None)
    assert csp.startswith("default-src 'none'; object-src 'none'; base-uri 'none'")
    assert "script-src 'unsafe-inline'" in csp
    assert "connect-src 'none'" in csp


def test_only_https_origins_survive_into_the_policy() -> None:
    csp = build_csp(
        {
            "ui": {
                "csp": {
                    "connectDomains": [
                        "https://api.example/v1",
                        "wss://live.example",
                        "http://plain.example",
                        "https://*",
                        "'unsafe-eval'; script-src *",
                        42,
                    ],
                    "frameDomains": ["https://frames.example"],
                }
            }
        }
    )
    assert "connect-src https://api.example wss://live.example" in csp
    assert "frame-src https://frames.example" in csp
    assert "plain.example" not in csp
    assert "unsafe-eval" not in csp
