"""A server marked `required` is connected before the app serves, or the app does not start."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.mcp import McpService, RequiredServerError
from harness.mcp import service as service_module
from tests.integration.web_helpers import build
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import no_skills
from tests.unit.mcp_fakes import FakeFactory, servers
from tests.webapp import web_app


async def test_a_required_server_that_fails_stops_startup_naming_it_and_its_error() -> None:
    factory = FakeFactory(connect_error=RuntimeError("turn on virtualization"))
    store = McpService(servers("computer", required=True), client_factory=factory, saved={})

    with pytest.raises(RequiredServerError, match="computer.*turn on virtualization"):
        await store.start()

    assert store.tools() == []


async def test_a_required_server_that_connects_lets_startup_continue() -> None:
    factory = FakeFactory(connect_delay=0.05)
    store = McpService(servers("computer", required=True), client_factory=factory, saved={})

    await store.start()

    assert store.statuses()[0].status == "connected"
    assert [t.name for t in store.tools()] == ["computer__echo"]
    await store.aclose()


async def test_a_server_that_is_not_required_still_fails_quietly() -> None:
    factory = FakeFactory(connect_error=RuntimeError("no such command"))
    store = McpService(servers("sysmon"), client_factory=factory, saved={})

    await store.start()
    await store.aclose()


async def test_a_required_server_that_never_answers_stops_startup_after_the_wait(
    monkeypatch,
) -> None:
    monkeypatch.setattr(service_module, "REQUIRED_CONNECT_TIMEOUT_SECONDS", 0.05)
    factory = FakeFactory(connect_delay=5.0)
    store = McpService(servers("computer", required=True), client_factory=factory, saved={})

    with pytest.raises(RequiredServerError, match="computer.*within 0.05s"):
        await store.start()


async def test_the_app_does_not_serve_without_a_required_server(tmp_path) -> None:
    service, runs = build(tmp_path, ScriptedClient([]))
    factory = FakeFactory(connect_error=RuntimeError("Docker is not running"))
    mcp = McpService(servers("computer", required=True), client_factory=factory, saved={})
    app = web_app(tmp_path, service, runs, mcp=mcp, skills=no_skills())

    with pytest.raises(RequiredServerError, match="computer.*Docker is not running"):
        async with app.router.lifespan_context(app):
            raise AssertionError("the app served without its required server")


def test_the_computer_is_required_and_nothing_else_is() -> None:
    committed = json.loads((Path(__file__).parents[2] / "config.json").read_text())

    required = {
        name for name, server in committed["mcp"]["servers"].items() if server.get("required")
    }

    assert required == {"computer"}
