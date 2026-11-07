"""A capability key saved on the Credentials page restarts its server, and ties no bot."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from harness.bots import BotService
from harness.config.sections import McpServer
from harness.mcp import McpService
from harness.secrets import DiskSecretRepository, SecretService
from harness.secrets.models.details import CapabilityDetails
from harness.web.routes.credentials import build_router
from tests.unit.helpers import durable_service
from tests.unit.mcp_fakes import FakeFactory
from tests.webapp import no_platforms

KEY = "0123456789abcdef0123456789abcdef"
PAGE = "http://127.0.0.1:4887"
MAPS = "GOOGLE_MAPS_API_KEY"
COINGECKO = "COINGECKO_API_KEY"
PLACES_KEY = {"kind": "capability", "server": "places", "variable": MAPS}
MARKETS_KEY = {"kind": "capability", "server": "markets", "variable": COINGECKO}


class World:
    """The keyring, the bots, and capabilities that need keys, behind the credentials routes."""

    def __init__(self, tmp_path: Path) -> None:
        self.secrets = SecretService(
            DiskSecretRepository(tmp_path / "secrets.json"), encryption_key=KEY
        )
        self.bots = BotService(
            tmp_path / "bots.json",
            durable_service(tmp_path / "sessions"),
            assistant_instructions="Be kind.",
        )
        self.factory = FakeFactory()
        configured = {
            "places": McpServer(command="does-not-run", needs=(MAPS,)),
            "markets": McpServer(command="does-not-run", needs=(COINGECKO,)),
            "fs": McpServer(command="does-not-run"),
        }
        self.mcp = McpService(configured, saved={}, keys=self.secrets, client_factory=self.factory)
        app = FastAPI()
        app.include_router(
            build_router(self.secrets, self.bots, no_platforms(self.secrets), self.mcp)
        )
        self.app = app

    async def send(self, method: str, url: str, body: dict | None = None) -> httpx.Response:
        transport = httpx.ASGITransport(app=self.app, client=("127.0.0.1", 50000))
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:4886") as http:
            return await http.request(method, url, json=body, headers={"origin": PAGE})

    def status(self, server_id: str) -> str:
        return next(s.status for s in self.mcp.statuses() if s.id == server_id)

    async def settled(self) -> None:
        for _ in range(200):
            if all(s.status != "connecting" for s in self.mcp.statuses()):
                return
            await asyncio.sleep(0.01)
        raise AssertionError("never left `connecting`")


@pytest.fixture
async def world(tmp_path: Path):
    built = World(tmp_path)
    await built.mcp.start()
    yield built
    await built.mcp.aclose()


def _key(name: str, details: dict, value: str = "AIza-maps-key-1234") -> dict:
    return {"name": name, "details": details, "value": value, "bot_ids": []}


async def test_saving_a_capability_key_starts_its_server_with_the_key(world) -> None:
    assert world.status("places") == "waiting"

    response = await world.send("POST", "/api/credentials", _key("maps", PLACES_KEY))
    await world.settled()

    assert response.status_code == 201
    assert world.status("places") == "connected"
    assert world.factory.started[-1].env[MAPS] == "AIza-maps-key-1234"
    assert world.status("markets") == "waiting"


async def test_a_capability_key_ties_no_bot(world) -> None:
    await world.send("POST", "/api/credentials", _key("maps", PLACES_KEY))

    assert all(bot.secret_names == () for bot in await world.bots.active_bots())


async def test_changing_a_capability_key_restarts_its_server_with_the_new_key(world) -> None:
    await world.send("POST", "/api/credentials", _key("maps", PLACES_KEY))
    change = {"details": PLACES_KEY, "value": "AIza-newer-key-9876", "bot_ids": []}

    response = await world.send("PATCH", "/api/credentials/maps", change)
    await world.settled()

    assert response.status_code == 200
    assert world.factory.started[-1].env[MAPS] == "AIza-newer-key-9876"
    assert world.status("places") == "connected"


async def test_moving_a_key_to_another_capability_restarts_both(world) -> None:
    await world.send("POST", "/api/credentials", _key("maps", PLACES_KEY))
    await world.settled()
    change = {"details": MARKETS_KEY, "value": "CG-key-5678", "bot_ids": []}

    response = await world.send("PATCH", "/api/credentials/maps", change)
    await world.settled()

    assert response.status_code == 200
    assert (world.status("places"), world.status("markets")) == ("waiting", "connected")


async def test_deleting_a_capability_key_leaves_its_server_waiting_again(world) -> None:
    await world.send("POST", "/api/credentials", _key("maps", PLACES_KEY))
    await world.settled()

    response = await world.send("DELETE", "/api/credentials/maps")

    assert response.status_code == 204
    assert world.status("places") == "waiting"


@pytest.mark.parametrize(
    "details",
    [
        {"kind": "capability", "server": "nowhere", "variable": MAPS},
        {"kind": "capability", "server": "places", "variable": "OTHER_KEY"},
        {"kind": "capability", "server": "fs", "variable": MAPS},
    ],
)
async def test_a_key_for_a_server_or_variable_not_configured_is_refused_unsaved(
    world, details
) -> None:
    opened = world.factory.opens

    response = await world.send("POST", "/api/credentials", _key("maps", details))

    assert response.status_code == 422
    assert world.secrets.saved_credentials() == ()
    assert world.factory.opens == opened


async def test_a_change_onto_a_variable_not_needed_is_refused_unchanged(world) -> None:
    await world.send("POST", "/api/credentials", _key("maps", PLACES_KEY))
    wrong = {"kind": "capability", "server": "places", "variable": "OTHER_KEY"}

    response = await world.send(
        "PATCH", "/api/credentials/maps", {"details": wrong, "value": None, "bot_ids": []}
    )

    assert response.status_code == 422
    assert world.secrets.saved_credentials()[0].details.variable == MAPS


async def test_a_capability_key_serves_no_bots(world) -> None:
    assistant = (await world.bots.active_bots())[0]

    response = await world.send(
        "POST", "/api/credentials", {**_key("maps", PLACES_KEY), "bot_ids": [assistant.id]}
    )

    assert response.status_code == 422
    assert world.secrets.saved_credentials() == ()


async def test_the_route_answers_before_a_slow_server_finishes_connecting(world) -> None:
    world.factory.connect_delay = 30.0

    async with asyncio.timeout(5):
        response = await world.send("POST", "/api/credentials", _key("maps", PLACES_KEY))

    assert response.status_code == 201
    assert world.status("places") == "connecting"


async def test_a_key_for_a_capability_no_longer_configured_is_still_removed(world) -> None:
    gone = CapabilityDetails(server="gone", variable=MAPS)
    world.secrets.add_credential("old", gone, SecretStr("AIza-old-key-0000"))

    response = await world.send("DELETE", "/api/credentials/old")

    assert response.status_code == 204
    assert world.secrets.saved_credentials() == ()
