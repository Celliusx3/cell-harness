"""One HTTP client for the provider, and the one retry it allows."""

from __future__ import annotations

import re
from pathlib import Path

import httpx

# Some GLM-family vision models wrap their answer: `<|begin_of_box|>red<|end_of_box|>`.
_SENTINELS = re.compile(r"<\|(?:begin|end)_of_box\|>")


class ProviderError(RuntimeError):
    """The provider refused or failed. Message is the provider's, untruncated."""


class ProviderRateLimited(ProviderError):
    """429 after one honoured retry."""


def strip_sentinels(text: str) -> str:
    return _SENTINELS.sub("", text).strip()


class ProviderHttp:
    """Transport only: it knows a base URL, a key, and how to retry once."""

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
        """Close the client only if this instance created it."""
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
        """Send, and on a 429 wait out `Retry-After` exactly once."""
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
    """The assistant text, or a `ProviderError` naming what came back instead."""
    if "error" in body:
        raise ProviderError(str(body["error"]))
    choices = body.get("choices") or []
    if not choices:
        raise ProviderError("provider returned no choices")
    text = (choices[0].get("message") or {}).get("content")
    if not text:
        raise ProviderError("provider returned an empty message")
    return str(text)
