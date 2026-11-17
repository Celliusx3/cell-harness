"""Why a relayed page cannot be shown."""

from __future__ import annotations


class RelayNotFound(LookupError):
    """No open relay has this id: it never existed, or it ended."""

    def __init__(self) -> None:
        super().__init__("no such relay")


class RelayUpstreamDown(RuntimeError):
    """The loopback origin a relay reaches did not answer the page fetch."""
