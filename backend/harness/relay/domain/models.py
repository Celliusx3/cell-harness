"""A relay's shapes: the loopback origin it reaches, when it ends, and the entry asking for one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict


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


class Target(NamedTuple):
    upstream: Upstream
    path: str
    query: str
