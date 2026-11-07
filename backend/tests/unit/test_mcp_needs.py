"""A server that needs a key waits until its env holds it; a change picks up a key given."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from harness.config.sections import McpServer
from harness.mcp import McpService, RequiredServerError
from tests.unit.mcp_fakes import FakeFactory

MAPS = "GOOGLE_MAPS_API_KEY"


def places(*, env: dict[str, str] | None = None, required: bool = False) -> dict[str, McpServer]:
    return {
        "places": McpServer(command="does-not-run", env=env or {}, needs=(MAPS,), required=required)
    }


async def settled(store: McpService) -> None:
    for _ in range(200):
        if all(s.status != "connecting" for s in store.statuses()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("never left `connecting`")


async def test_a_server_missing_a_needed_key_waits_naming_it_and_offers_nothing() -> None:
    factory = FakeFactory()
    store = McpService(places(), saved={}, client_factory=factory)

    await store.start()

    [status] = store.statuses()
    assert (status.status, status.error) == ("waiting", f"needs {MAPS}")
    assert store.tools() == []
    assert factory.opens == 0
    await store.aclose()


async def test_a_blank_value_in_the_config_env_is_still_missing() -> None:
    factory = FakeFactory()
    store = McpService(places(env={MAPS: "  "}), saved={}, client_factory=factory)

    await store.start()

    assert store.statuses()[0].status == "waiting"
    await store.aclose()


async def test_a_needed_key_in_the_config_env_starts_the_server() -> None:
    factory = FakeFactory()
    store = McpService(places(env={MAPS: "from-config"}), saved={}, client_factory=factory)

    await store.start()
    await settled(store)

    assert store.statuses()[0].status == "connected"
    assert [t.name for t in store.tools()] == ["places__echo"]
    await store.aclose()


async def test_a_change_that_gives_the_key_connects_the_server_with_it_in_its_env() -> None:
    factory = FakeFactory()
    store = McpService({}, saved=places(), client_factory=factory)
    await store.start()

    await store.change("places", places(env={MAPS: "given-later"})["places"])
    await settled(store)

    assert store.statuses()[0].status == "connected"
    assert factory.started[-1].env[MAPS] == "given-later"
    await store.aclose()


async def test_a_change_that_drops_the_key_leaves_the_server_waiting() -> None:
    factory = FakeFactory()
    store = McpService({}, saved=places(env={MAPS: "first"}), client_factory=factory)
    await store.start()
    await settled(store)

    await store.change("places", places()["places"])

    assert store.statuses()[0].status == "waiting"
    assert store.tools() == []
    await store.aclose()


async def test_a_restart_of_a_server_that_is_not_configured_raises_key_error() -> None:
    store = McpService(places(), saved={}, client_factory=FakeFactory())
    await store.start()

    with pytest.raises(KeyError):
        await store.restart("nowhere")
    await store.aclose()


async def test_a_required_server_that_waits_for_a_key_refuses_startup_naming_it() -> None:
    store = McpService(places(required=True), saved={}, client_factory=FakeFactory())

    with pytest.raises(RequiredServerError, match=f"places is required and needs {MAPS}"):
        await store.start()


@pytest.mark.parametrize("blank", ["", "  "])
def test_a_blank_needed_name_is_refused(blank: str) -> None:
    with pytest.raises(ValidationError, match="needs must name env variables"):
        McpServer(command="x", needs=(blank,))
