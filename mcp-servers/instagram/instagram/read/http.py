"""One HTTP client for the provider, and the one retry it allows.

Split out of what used to be a single `provider.py` so that *transport* is
separable from *what we ask for*: `vision` and `speech` are different questions
that happen to share a base URL and a key, and fusing them made a 265-line
module that changed for two unrelated reasons.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx

# Emitted by some GLM-family vision models around their whole answer —
# `ilmu-vision-v1.3` returns `<|begin_of_box|>red<|end_of_box|>`. Passed through,
# those tokens end up inside a POI name. `glm-5.3-flash` does not do it, but the
# model is configurable and the fallback is exactly the one that does, so
# stripping is unconditional and lives here where every response passes.
_SENTINELS = re.compile(r"<\|(?:begin|end)_of_box\|>")


class ProviderError(RuntimeError):
    """The provider refused or failed. Message is the provider's, untruncated."""


class ProviderRateLimited(ProviderError):
    """429 after one honoured retry."""


def strip_sentinels(text: str) -> str:
    return _SENTINELS.sub("", text).strip()


class ProviderHttp:
    """Transport only: it knows a base URL, a key, and how to retry once.

    The `httpx.AsyncClient` is injectable so tests drive `MockTransport` rather
    than monkeypatching a module global — which tests the patch, not the code.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def aclose(self) -> None:
        """Only close what we opened — an injected client belongs to its owner."""
        if self._owns_client:
            await self._client.aclose()

    async def post_json(self, path: str, payload: dict[str, object]) -> dict:
        response = await self._send(
            lambda: self._client.post(f"{self._base}{path}", headers=self._headers, json=payload)
        )
        return response.json()

    async def post_file(self, path: str, file: Path, form: dict[str, str]) -> dict:
        response = await self._send(
            lambda: self._client.post(
                f"{self._base}{path}",
                headers=self._headers,
                files={"file": (file.name, file.read_bytes())},
                data=form,
            )
        )
        return response.json()

    async def _send(self, send) -> httpx.Response:
        """Send, and on a 429 wait out `Retry-After` exactly once.

        One retry, not a backoff loop: this call is already inside a 60-second
        MCP deadline the server cannot extend, so a second retry would spend the
        budget that lets the *other* reels in the batch finish.
        """
        import asyncio

        for attempt in (0, 1):
            try:
                response = await send()
            except httpx.HTTPError as err:
                raise ProviderError(f"{type(err).__name__}: {err}") from err

            if response.status_code == 429 and attempt == 0:
                await asyncio.sleep(_retry_after(response))
                continue
            if response.status_code == 429:
                raise ProviderRateLimited(f"provider rate-limited: {response.text}")
            if response.status_code >= 400:
                raise ProviderError(f"provider returned {response.status_code}: {response.text}")
            return response
        raise ProviderRateLimited("provider rate-limited")


def _retry_after(response: httpx.Response) -> float:
    raw = response.headers.get("Retry-After", "")
    try:
        return min(float(raw), 10.0)
    except ValueError:
        return 1.0


def message_text(body: dict) -> str:
    """The assistant text, or a `ProviderError` naming what came back instead.

    A reasoning-heavy model can spend its whole budget thinking and return an
    empty `content`. Reported rather than treated as "nothing visible", because
    those two mean opposite things to the model reading the result.
    """
    if "error" in body:
        raise ProviderError(str(body["error"]))
    choices = body.get("choices") or []
    if not choices:
        raise ProviderError("provider returned no choices")
    text = (choices[0].get("message") or {}).get("content")
    if not text:
        raise ProviderError("provider returned an empty message")
    return str(text)
