"""A server that needs a key waits for it, and a restart picks up a key saved later."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr, ValidationError

from harness.config.sections import McpServer
from harness.mcp import McpService, RequiredServerError
from tests.unit.mcp_fakes import FakeFactory, SavedKeys, no_keys

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
    store = McpService(places(), keys=no_keys(), client_factory=factory)

    await store.start()

    [status] = store.statuses()
    assert (status.status, status.error) == ("waiting", f"needs {MAPS}")
    assert store.tools() == []
    assert factory.opens == 0
    await store.aclose()


async def test_a_blank_value_in_the_config_env_is_still_missing() -> None:
    factory = FakeFactory()
    store = McpService(places(env={MAPS: "  "}), keys=no_keys(), client_factory=factory)

    await store.start()

    assert store.statuses()[0].status == "waiting"
    await store.aclose()


async def test_a_needed_key_in_the_config_env_starts_the_server() -> None:
    factory = FakeFactory()
    store = McpService(places(env={MAPS: "from-config"}), keys=no_keys(), client_factory=factory)

    await store.start()
    await settled(store)

    assert store.statuses()[0].status == "connected"
    assert [t.name for t in store.tools()] == ["places__echo"]
    await store.aclose()


async def test_a_needed_key_in_the_keyring_starts_the_server_and_reaches_its_env() -> None:
    factory = FakeFactory()
    keys = SavedKeys({"places": {MAPS: SecretStr("from-keyring")}})
    store = McpService(places(env={"PLACES_MAX_RESULTS": "3"}), keys=keys, client_factory=factory)

    await store.start()
    await settled(store)

    assert store.statuses()[0].status == "connected"
    assert factory.started[-1].env == {"PLACES_MAX_RESULTS": "3", MAPS: "from-keyring"}
    await store.aclose()


async def test_the_keyring_value_wins_over_the_config_env() -> None:
    factory = FakeFactory()
    keys = SavedKeys({"places": {MAPS: SecretStr("from-keyring")}})
    store = McpService(places(env={MAPS: "from-config"}), keys=keys, client_factory=factory)

    await store.start()
    await settled(store)

    assert factory.started[-1].env[MAPS] == "from-keyring"
    await store.aclose()


async def test_a_restart_after_the_key_is_saved_connects_the_server() -> None:
    factory = FakeFactory()
    keys = no_keys()
    store = McpService(places(), keys=keys, client_factory=factory)
    await store.start()

    keys.by_server["places"] = {MAPS: SecretStr("saved-later")}
    await store.restart("places")
    await settled(store)

    assert store.statuses()[0].status == "connected"
    assert [t.name for t in store.tools()] == ["places__echo"]
    await store.aclose()


async def test_a_restart_closes_the_running_connection_and_opens_a_new_one() -> None:
    factory = FakeFactory()
    keys = SavedKeys({"places": {MAPS: SecretStr("first")}})
    store = McpService(places(), keys=keys, client_factory=factory)
    await store.start()
    await settled(store)

    keys.by_server["places"] = {MAPS: SecretStr("second")}
    await store.restart("places")
    await settled(store)

    assert factory.opens == 2
    assert factory.client.exited_in is not None
    assert factory.started[-1].env[MAPS] == "second"
    await store.aclose()


async def test_a_restart_after_the_key_is_removed_leaves_the_server_waiting() -> None:
    factory = FakeFactory()
    keys = SavedKeys({"places": {MAPS: SecretStr("first")}})
    store = McpService(places(), keys=keys, client_factory=factory)
    await store.start()
    await settled(store)

    keys.by_server.clear()
    await store.restart("places")

    assert store.statuses()[0].status == "waiting"
    assert store.tools() == []
    await store.aclose()


async def test_a_restart_of_a_server_that_is_not_configured_raises_key_error() -> None:
    store = McpService(places(), keys=no_keys(), client_factory=FakeFactory())
    await store.start()

    with pytest.raises(KeyError):
        await store.restart("nowhere")
    await store.aclose()


async def test_a_required_server_that_waits_for_a_key_refuses_startup_naming_it() -> None:
    store = McpService(places(required=True), keys=no_keys(), client_factory=FakeFactory())

    with pytest.raises(RequiredServerError, match=f"places is required and needs {MAPS}"):
        await store.start()


@pytest.mark.parametrize("blank", ["", "  "])
def test_a_blank_needed_name_is_refused(blank: str) -> None:
    with pytest.raises(ValidationError, match="needs must name env variables"):
        McpServer(command="x", needs=(blank,))
