"""HTTP transport to the Places API."""

from __future__ import annotations

import asyncio

import httpx


class PlacesError(RuntimeError):
    """The API refused. Message is Google's, untruncated."""


class PlacesAuthError(PlacesError):
    """The key is missing, invalid, or the API is not enabled on the project."""


# Google answers a bad key with 400 `API_KEY_INVALID`, and an unenabled API with 403.
_KEY_MARKERS = (
    "API_KEY_INVALID",
    "API key not valid",
    "SERVICE_DISABLED",
    "PERMISSION_DENIED",
    "API_KEY_SERVICE_BLOCKED",
    "requests to this API",
)


def is_key_problem(response: httpx.Response) -> bool:
    if response.status_code in (401, 403):
        return True
    if response.status_code != 400:
        return False
    return any(marker in response.text for marker in _KEY_MARKERS)


async def send(request) -> httpx.Response:
    """Send, and on a 429 wait once before giving up."""
    response = await _attempt(request)
    if response.status_code == 429:
        await asyncio.sleep(1.0)
        response = await _attempt(request)
    if response.status_code == 429:
        raise PlacesError(
            "Places API rate-limited the request twice — the project's quota or "
            f"per-minute limit is exhausted: {response.text}"
        )
    if is_key_problem(response):
        raise PlacesAuthError(
            "Google rejected the API key. Check that the key is valid, that Places API "
            "(New) is enabled on its project, and that any key restrictions allow this "
            f"caller: {response.text}"
        )
    if response.status_code >= 400:
        raise PlacesError(f"Places API returned {response.status_code}: {response.text}")
    return response


async def _attempt(request) -> httpx.Response:
    try:
        return await request()
    except httpx.HTTPError as err:
        raise PlacesError(f"{type(err).__name__}: {err}") from err
