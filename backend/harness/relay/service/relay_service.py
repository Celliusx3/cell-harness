"""Which loopback origin a random relay id reaches, until the relay ends, and what it serves."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable

import httpx
from mcp.types import CallToolResult
from pydantic import ValidationError

from harness.relay.domain.errors import RelayNotFound, RelayUpstreamDown
from harness.relay.domain.models import (
    RELAY_META,
    RELAY_PREFIX,
    OpenRelay,
    RelayedPage,
    RelayEntry,
    Upstream,
    loopback_target,
    with_query,
)

logger = logging.getLogger("harness.relay")

RELAY_TTL_SECONDS = 60 * 60
RELAY_ID_BYTES = 24
FETCH_TIMEOUT_SECONDS = 15.0


class RelayService:
    """Open relays, in memory; each one ends RELAY_TTL_SECONDS after it was made."""

    def __init__(self, now: Callable[[], float]) -> None:
        self._now = now
        self._relays: dict[str, OpenRelay] = {}

    def open(self, upstream: Upstream) -> str:
        now = self._now()
        live = {key: relay for key, relay in self._relays.items() if relay.expires_at > now}
        relay_id = secrets.token_urlsafe(RELAY_ID_BYTES)
        self._relays = {**live, relay_id: OpenRelay(upstream, now + RELAY_TTL_SECONDS)}
        return relay_id

    def upstream(self, relay_id: str) -> Upstream | None:
        relay = self._relays.get(relay_id)
        if relay is None or relay.expires_at <= self._now():
            return None
        return relay.upstream

    def with_relay_url(self, result: CallToolResult) -> CallToolResult:
        """The result with its relay entry pointed at a new relay; dropped when not loopback."""
        meta = result.meta
        if meta is None or RELAY_META not in meta:
            return result
        others = {key: value for key, value in meta.items() if key != RELAY_META}
        try:
            target = loopback_target(RelayEntry.model_validate(meta[RELAY_META]).url)
        except (ValidationError, ValueError) as err:
            logger.warning("dropped a relay entry from a tool result: %s", err)
            return result.model_copy(update={"meta": others or None})
        relay_id = self.open(target.upstream)
        url = with_query(f"{RELAY_PREFIX}/{relay_id}{target.path}", target.query)
        return result.model_copy(update={"meta": {**others, RELAY_META: {"url": url}}})

    async def fetch_page(self, relay_id: str, path: str, query: str) -> RelayedPage:
        """What the relay's origin answers for `path`; `RelayNotFound` or `RelayUpstreamDown`."""
        upstream = self.upstream(relay_id)
        if upstream is None:
            raise RelayNotFound()
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=FETCH_TIMEOUT_SECONDS) as http:
                response = await http.get(upstream.http_url(path, query))
        except httpx.HTTPError as err:
            logger.warning("relay %s: %s did not answer: %r", relay_id[:6], path, err)
            raise RelayUpstreamDown(f"the relayed page did not answer: {err!r}") from err
        return RelayedPage(
            status_code=response.status_code,
            content=response.content,
            content_type=response.headers.get("content-type"),
        )
