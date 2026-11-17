"""Relays: which loopback origin a random id reaches, and the entry asking for one."""

from harness.relay.domain.errors import RelayNotFound, RelayUpstreamDown
from harness.relay.domain.models import RELAY_PREFIX, Upstream
from harness.relay.service.relay_service import RELAY_TTL_SECONDS, RelayService

__all__ = [
    "RELAY_PREFIX",
    "RELAY_TTL_SECONDS",
    "RelayNotFound",
    "RelayService",
    "RelayUpstreamDown",
    "Upstream",
]
