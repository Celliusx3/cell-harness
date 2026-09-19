"""Builders. Hermetic: the Places API is faked at the `httpx` transport."""

from __future__ import annotations

import httpx
import pytest

from places.config import Config
from places.lookup import PlacesClient


def make_config(**overrides: object) -> Config:
    values: dict[str, object] = {
        "api_key": "test-key",
        "base_url": "https://places.test/v1",
        "max_results": 3,
        "timeout_seconds": 5.0,
    }
    values.update(overrides)
    return Config(**values)


def client_with(handler) -> PlacesClient:
    return PlacesClient(
        api_key="test-key",
        base_url="https://places.test/v1",
        timeout_seconds=5.0,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def place(
    place_id: str = "ChIJabc",
    name: str = "Natalina Italian Kitchen",
    address: str = "Avenue K, Jalan Ampang, Kuala Lumpur",
    kind: str = "Italian restaurant",
) -> dict:
    """A place shaped exactly as Places API (New) returns it."""
    return {
        "id": place_id,
        "displayName": {"text": name, "languageCode": "en"},
        "formattedAddress": address,
        "location": {"latitude": 3.1595, "longitude": 101.7123},
        "primaryTypeDisplayName": {"text": kind, "languageCode": "en"},
        "googleMapsUri": f"https://maps.google.com/?cid={place_id}",
    }


def search_reply(*places: dict) -> httpx.Response:
    return httpx.Response(200, json={"places": list(places)} if places else {})


def capturing(response: httpx.Response):
    """Returns `(handler, seen)` so a test can assert on the request itself."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return response

    return handler, seen


def server_with(handler, **config_overrides: object):
    """Both halves wired into a real `MCPServer`."""
    from places.server import build

    return build(config=make_config(**config_overrides), client=client_with(handler))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
