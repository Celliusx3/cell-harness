"""A relay's shapes: the loopback origin it reaches, when it ends, and the entry asking for one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict

RELAY_META = "io.cell-harness/relay"
RELAY_PREFIX = "/api/relay"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})


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


class RelayEntry(BaseModel):
    """What a tool result's `_meta` carries under RELAY_META."""

    model_config = ConfigDict(frozen=True)

    url: str


class LoopbackTarget(NamedTuple):
    upstream: Upstream
    path: str
    query: str


@dataclass(frozen=True)
class RelayedPage:
    """What the upstream answered a page fetch with: its status, its bytes and their type."""

    status_code: int
    content: bytes
    content_type: str | None


def loopback_target(url: str) -> LoopbackTarget:
    """The origin, path and query of a plain-http loopback url; anything else is a ValueError."""
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in LOOPBACK_HOSTS:
        raise ValueError(f"{parts.scheme}://{parts.hostname} is not http on 127.0.0.1 or localhost")
    upstream = Upstream(host=parts.hostname, port=parts.port or 80)
    return LoopbackTarget(upstream=upstream, path=parts.path or "/", query=parts.query)
