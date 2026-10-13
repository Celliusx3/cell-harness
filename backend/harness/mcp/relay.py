"""Relays: which loopback origin a random id reaches, and the entry asking for one."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple
from urllib.parse import urlsplit

from mcp.types import CallToolResult
from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger("harness.relay")

RELAY_META = "io.cell-harness/relay"
RELAY_PREFIX = "/api/relay"
RELAY_TTL_SECONDS = 60 * 60
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
RELAY_ID_BYTES = 24


def with_query(url: str, query: str) -> str:
    return f"{url}?{query}" if query else url


@dataclass(frozen=True)
class Upstream:
    """A loopback origin a relay reaches."""

    host: str
    port: int

    def http_url(self, path: str, query: str) -> str:
        return with_query(f"http://{self.host}:{self.port}/{path}", query)

    def ws_url(self, path: str, query: str) -> str:
        return with_query(f"ws://{self.host}:{self.port}/{path}", query)


@dataclass(frozen=True)
class OpenRelay:
    upstream: Upstream
    expires_at: float


class Relays:
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


class RelayEntry(BaseModel):
    """What a tool result's `_meta` carries under RELAY_META."""

    model_config = ConfigDict(frozen=True)

    url: str


class Target(NamedTuple):
    upstream: Upstream
    path: str
    query: str


def loopback_target(url: str) -> Target:
    """The origin, path and query of a plain-http loopback url; anything else is a ValueError."""
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in LOOPBACK_HOSTS:
        raise ValueError(f"{parts.scheme}://{parts.hostname} is not http on 127.0.0.1 or localhost")
    upstream = Upstream(host=parts.hostname, port=parts.port or 80)
    return Target(upstream=upstream, path=parts.path or "/", query=parts.query)


def with_relay_url(result: CallToolResult, relays: Relays) -> CallToolResult:
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
    relay_id = relays.open(target.upstream)
    url = with_query(f"{RELAY_PREFIX}/{relay_id}{target.path}", target.query)
    return result.model_copy(update={"meta": {**others, RELAY_META: {"url": url}}})
