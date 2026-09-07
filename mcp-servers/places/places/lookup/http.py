"""Transport, and the one thing about it that is not obvious.

Split from the client so that *how we talk to Google* is separable from *what we
ask for*: `mapping` turns payloads into our models and changes when our models
change, while this changes when Google's error surface does. They are unrelated
reasons.
"""

from __future__ import annotations

import asyncio

import httpx


class PlacesError(RuntimeError):
    """The API refused. Message is Google's, untruncated."""


class PlacesAuthError(PlacesError):
    """The key is missing, invalid, or the API is not enabled on the project.

    Separated because the fix is completely different from a transient failure:
    the model should report it, never retry it.
    """


# Google does **not** use 401/403 for a bad key: a plainly invalid key comes back
# as **400 `API_KEY_INVALID`**, and an unenabled API as 403 `SERVICE_DISABLED`.
# Keying only on status therefore missed the single most common auth failure and
# reported it through the generic branch, without the hint that actually helps.
# Found by calling the live API with a deliberately invalid key.
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
    """Send, and on a 429 wait once before giving up.

    One retry, not a backoff loop: this runs inside a 60-second MCP deadline the
    server cannot extend, so a second retry spends the budget that would let the
    call finish at all.
    """
    for attempt in (0, 1):
        try:
            response = await request()
        except httpx.HTTPError as err:
            raise PlacesError(f"{type(err).__name__}: {err}") from err

        if response.status_code == 429 and attempt == 0:
            await asyncio.sleep(1.0)
            continue
        if response.status_code == 429:
            # Explicit, and before the generic >= 400 branch: without it a
            # persistent quota error reports as "Places API returned 429", which
            # reads as a bug rather than as a quota the caller has hit.
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
    # Unreachable: the loop either returns or raises on both attempts.
    raise PlacesError("Places API did not answer")  # pragma: no cover
