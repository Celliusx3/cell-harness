"""A tool result's relay entry: pointed at a new relay when loopback, dropped otherwise."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from mcp.types import CallToolResult
from pydantic import ValidationError

from harness.relay.models import RelayEntry, Target, Upstream, with_query
from harness.relay.service import RelayService

logger = logging.getLogger("harness.relay")

RELAY_META = "io.cell-harness/relay"
RELAY_PREFIX = "/api/relay"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})


def loopback_target(url: str) -> Target:
    """The origin, path and query of a plain-http loopback url; anything else is a ValueError."""
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in LOOPBACK_HOSTS:
        raise ValueError(f"{parts.scheme}://{parts.hostname} is not http on 127.0.0.1 or localhost")
    upstream = Upstream(host=parts.hostname, port=parts.port or 80)
    return Target(upstream=upstream, path=parts.path or "/", query=parts.query)


def with_relay_url(result: CallToolResult, relays: RelayService) -> CallToolResult:
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
