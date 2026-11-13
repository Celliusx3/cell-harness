"""Relays: which loopback origin a random id reaches, and the entry asking for one."""

from harness.relay.domain.models import Upstream
from harness.relay.service.entry import RELAY_PREFIX, with_relay_url
from harness.relay.service.relay_service import RELAY_TTL_SECONDS, RelayService

__all__ = [
    "RELAY_PREFIX",
    "RELAY_TTL_SECONDS",
    "RelayService",
    "Upstream",
    "with_relay_url",
]
