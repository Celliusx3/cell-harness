"""Relays: which loopback origin a random id reaches, and the entry asking for one."""

from harness.relay.entry import RELAY_PREFIX, with_relay_url
from harness.relay.models import Upstream
from harness.relay.service import RELAY_TTL_SECONDS, RelayService

__all__ = [
    "RELAY_PREFIX",
    "RELAY_TTL_SECONDS",
    "RelayService",
    "Upstream",
    "with_relay_url",
]
