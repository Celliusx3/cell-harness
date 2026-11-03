"""Which loopback origin a random relay id reaches, until the relay ends."""

from __future__ import annotations

import secrets
from collections.abc import Callable

from harness.relay.models import OpenRelay, Upstream

RELAY_TTL_SECONDS = 60 * 60
RELAY_ID_BYTES = 24


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
